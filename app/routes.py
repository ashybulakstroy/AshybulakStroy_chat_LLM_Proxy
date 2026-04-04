import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.admin_ui import ADMIN_PAGE_HTML
from app.config import settings
from app.p2p_admin_ui import P2P_ADMIN_PAGE_HTML
from app.p2p_service import p2p_service
from app.rate_limits import rate_limit_store
from app.router_service import ProviderRouter, UpstreamProvidersExhausted
from app.schemas import ChatCompletionRequest, EmbeddingRequest

router = APIRouter()
provider_router = ProviderRouter()
LIMITS_FILE = Path(__file__).resolve().parent.parent / "provider_limits.json"
MODEL_VALIDATION_FILE = Path(__file__).resolve().parent.parent / "model_validation_snapshot.json"
ADMIN_CACHE_FILE = Path(__file__).resolve().parent.parent / "admin_dashboard_cache.json"
PREFERRED_TEST_MODELS = {
    "groq": ["llama-3.1-8b-instant", "qwen/qwen3-32b"],
    "openrouter": ["qwen/qwen3.6-plus-preview:free", "openai/gpt-5.4-mini"],
    "cerebras": ["llama3.1-8b", "qwen-3-235b-a22b-instruct-2507"],
    "gemini": ["models/gemini-2.5-flash", "models/gemini-2.0-flash"],
    "sambanova": ["DeepSeek-V3.2", "DeepSeek-V3.1"],
}
GROQ_EXCLUDED_PREFIXES = ("canopylabs/orpheus",)
GEMINI_FREE_TIER_PREFIXES = (
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemma-",
)
TEST_PROMPT = "Ассаламу алейкум! Верни: Ва алейкум ассалам!"
EXPECTED_TEST_REPLIES = {
    "ва алейкум ассалам",
    "ва алейкум асс салам",
    "وعليكم السلام",
}
VALIDATED_LLM_JOB_STATE = {
    "status": "idle",
    "running": False,
    "requests_started": 0,
    "responses_received": 0,
    "total_models": 0,
    "passed": 0,
    "failed": 0,
    "started_by": None,
    "last_started_at": None,
    "last_finished_at": None,
    "error": None,
}
VALIDATED_LLM_JOB_TASK: asyncio.Task | None = None
LIVE_LIMITS_JOB_STATE = {
    "status": "idle",
    "running": False,
    "started_by": None,
    "last_started_at": None,
    "last_finished_at": None,
    "probe_successful": 0,
    "probe_failed": 0,
    "error": None,
}
LIVE_LIMITS_JOB_TASK: asyncio.Task | None = None
RUNTIME_DISPATCHER_CACHE: dict = {}


def _set_runtime_dispatcher_cache(payload: dict | None) -> dict:
    global RUNTIME_DISPATCHER_CACHE
    RUNTIME_DISPATCHER_CACHE = dict(payload or {})
    return RUNTIME_DISPATCHER_CACHE


def _get_runtime_dispatcher_cache() -> dict:
    if not RUNTIME_DISPATCHER_CACHE:
        return _set_runtime_dispatcher_cache(_load_admin_cache())
    return RUNTIME_DISPATCHER_CACHE


def _load_estimated_limits() -> dict:
    if not LIMITS_FILE.exists():
        return {"snapshot_date": None, "providers": {}}
    return json.loads(LIMITS_FILE.read_text(encoding="utf-8"))


def _load_model_validation_results() -> dict:
    if not MODEL_VALIDATION_FILE.exists():
        return {"validated_at": None, "models": {}}
    try:
        return json.loads(MODEL_VALIDATION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"validated_at": None, "models": {}}


def _save_model_validation_results(payload: dict) -> None:
    MODEL_VALIDATION_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_admin_cache() -> dict:
    if not ADMIN_CACHE_FILE.exists():
        return {"validated_llm": {"object": "list", "data": [], "meta": {"cache_created_at": None}}}
    try:
        return json.loads(ADMIN_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"validated_llm": {"object": "list", "data": [], "meta": {"cache_created_at": None}}}


def _save_admin_cache(payload: dict) -> None:
    ADMIN_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


_set_runtime_dispatcher_cache(_load_admin_cache())


async def _last_session_index(limit: int = 100) -> dict[str, dict]:
    sessions = await provider_router.get_completed_sessions(limit)
    index: dict[str, dict] = {}
    for session in sessions:
        provider_name = session.get("provider")
        model_id = session.get("model")
        if not provider_name or not model_id:
            continue
        key = _model_validation_key(provider_name, model_id)
        if key in index:
            continue
        index[key] = {
            "last_session_status": session.get("status"),
            "last_session_status_code": session.get("status_code"),
            "last_session_error": session.get("detail"),
            "last_session_at": session.get("finished_at") or session.get("started_at"),
            "last_session_mode": session.get("mode"),
        }
    return index


def _apply_last_session_index(cache_payload: dict, sessions_index: dict[str, dict]) -> dict:
    for route in cache_payload.get("routes", []):
        key = _model_validation_key(route.get("provider", ""), route.get("model_id", ""))
        session = sessions_index.get(key, {})
        route["last_session_status"] = session.get("last_session_status")
        route["last_session_status_code"] = session.get("last_session_status_code")
        route["last_session_error"] = session.get("last_session_error")
        route["last_session_at"] = session.get("last_session_at")
        route["last_session_mode"] = session.get("last_session_mode")
    return cache_payload


def _get_validated_llm_job_state() -> dict:
    return dict(VALIDATED_LLM_JOB_STATE)


def _reset_validated_llm_job_state(started_by: str | None = None) -> None:
    VALIDATED_LLM_JOB_STATE.update(
        {
            "status": "running",
            "running": True,
            "requests_started": 0,
            "responses_received": 0,
            "total_models": 0,
            "passed": 0,
            "failed": 0,
            "started_by": started_by,
            "last_started_at": datetime.now(timezone.utc).isoformat(),
            "last_finished_at": None,
            "error": None,
        }
    )


def _provider_recommendation(provider_state: dict) -> str:
    if provider_state.get("last_error"):
        return "retry"
    limits = provider_state.get("limits", {})
    requests_minute = limits.get("requests", {}).get("minute", {})
    requests_day = limits.get("requests", {}).get("day", {})
    rpm_remaining = requests_minute.get("remaining")
    rpd_remaining = requests_day.get("remaining")
    source = limits.get("source")

    if rpm_remaining == 0 or rpd_remaining == 0:
        return "wait"
    if source == "fallback_default":
        return "wait"
    return "ready"


def _model_validity(model: dict, validation_payload: dict) -> bool | None:
    if _category_for_model(model) != "llm":
        return None
    key = _model_validation_key(model.get("provider", ""), model.get("id", ""))
    item = validation_payload.get("models", {}).get(key, {})
    if "passed" not in item:
        return None
    return item.get("passed") is True


def _build_dispatcher_cache_payload(
    all_models: list[dict] | None = None,
    block_two_payload: dict | None = None,
    validated_llm_payload: dict | None = None,
) -> dict:
    provider_names = list(settings.get_provider_configs().keys())
    limits_snapshot = rate_limit_store.get_snapshot(provider_names)
    estimated_limits = _load_estimated_limits().get("providers", {})
    validation_payload = _load_model_validation_results()
    cache = _load_admin_cache()

    if block_two_payload is None:
        block_two_payload = cache.get("block_two", {"object": "list", "data": [], "meta": {}})
    if validated_llm_payload is None:
        validated_llm_payload = cache.get("validated_llm", {"object": "list", "data": [], "meta": {}})

    routes = cache.get("routes", [])
    if all_models is not None:
        routes = []
        for model in all_models:
            provider_name = model.get("provider")
            provider_state = limits_snapshot.get(provider_name, {})
            validity = _model_validity(model, validation_payload)
            routes.append(
                {
                    "provider": provider_name,
                    "model_id": model.get("id"),
                    "category": _category_for_model(model),
                    "valid": validity,
                    "last_status_code": provider_state.get("last_status_code"),
                    "last_error": provider_state.get("last_error"),
                    "last_observed_at": provider_state.get("last_observed_at"),
                    "rpm_remaining": provider_state.get("limits", {}).get("requests", {}).get("minute", {}).get("remaining"),
                    "rpd_remaining": provider_state.get("limits", {}).get("requests", {}).get("day", {}).get("remaining"),
                    "tpm_remaining": provider_state.get("limits", {}).get("tokens", {}).get("minute", {}).get("remaining"),
                    "validity_source": "llm_text_test" if _category_for_model(model) == "llm" else "not_required",
                    "recommendation": _provider_recommendation(provider_state),
                }
            )

    providers = []
    for provider_name in provider_names:
        provider_state = limits_snapshot.get(provider_name, {})
        providers.append(
            {
                "provider": provider_name,
                "valid": provider_state.get("last_error") in (None, ""),
                "last_status_code": provider_state.get("last_status_code"),
                "last_error": provider_state.get("last_error"),
                "last_observed_at": provider_state.get("last_observed_at"),
                "limits": provider_state.get("limits", {}),
                "estimated_limits": estimated_limits.get(provider_name, {}),
                "recommendation": _provider_recommendation(provider_state),
            }
        )

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "providers": providers,
        "routes": routes,
        "block_two": block_two_payload,
        "validated_llm": validated_llm_payload,
    }


def _refresh_admin_cache(
    all_models: list[dict] | None = None,
    block_two_payload: dict | None = None,
    validated_llm_payload: dict | None = None,
) -> dict:
    cache_payload = _load_admin_cache()
    dispatcher_payload = _build_dispatcher_cache_payload(
        all_models=all_models,
        block_two_payload=block_two_payload,
        validated_llm_payload=validated_llm_payload,
    )
    cache_payload.update(dispatcher_payload)
    _save_admin_cache(cache_payload)
    return _set_runtime_dispatcher_cache(cache_payload)


def _get_live_limits_job_state() -> dict:
    return dict(LIVE_LIMITS_JOB_STATE)


def _reset_live_limits_job_state(started_by: str | None = None) -> None:
    LIVE_LIMITS_JOB_STATE.update(
        {
            "status": "running",
            "running": True,
            "started_by": started_by,
            "last_started_at": datetime.now(timezone.utc).isoformat(),
            "last_finished_at": None,
            "probe_successful": 0,
            "probe_failed": 0,
            "error": None,
        }
    )


async def _refresh_admin_cache_async(
    all_models: list[dict] | None = None,
    block_two_payload: dict | None = None,
    validated_llm_payload: dict | None = None,
) -> dict:
    cache_payload = _refresh_admin_cache(
        all_models=all_models,
        block_two_payload=block_two_payload,
        validated_llm_payload=validated_llm_payload,
    )
    cache_payload = _apply_last_session_index(cache_payload, await _last_session_index())
    _save_admin_cache(cache_payload)
    return cache_payload


def _normalize_test_reply(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.lower().replace("С‘", "Рµ")
    return "".join(ch for ch in lowered if ch.isalnum() or ch.isspace()).strip()


def _normalize_test_reply(value: str | None) -> str:
    if not value:
        return ""
    lowered = (
        value.lower()
        .replace("С‘", "Рµ")
        .replace("-", " ")
        .replace("СѓР° ", "РІР° ")
    )
    return "".join(ch for ch in lowered if ch.isalnum() or ch.isspace()).strip()


def _is_valid_test_reply(value: str | None) -> bool:
    normalized = _normalize_test_reply(value)
    if not normalized:
        return False
    return any(expected in normalized for expected in EXPECTED_TEST_REPLIES)


def _live_limit_models(models: list[dict]) -> list[dict]:
    return _filter_models_by_validation(_filter_models_with_live_limits(models))


def _block_two_model_keys(models: list[dict]) -> set[str]:
    return {
        _model_validation_key(model.get("provider", ""), model.get("id", ""))
        for model in models
        if isinstance(model, dict) and model.get("provider") and model.get("id")
    }


def _block_two_llm_candidates(all_models: list[dict]) -> list[dict]:
    current_plan_models = _filter_models_for_current_plan(all_models)
    live_limit_models = _filter_models_with_live_limits(current_plan_models)
    return [model for model in live_limit_models if _category_for_model(model) == "llm"]


def _remaining_llm_models(all_models: list[dict]) -> list[dict]:
    block_two_models = _block_two_llm_candidates(all_models)
    excluded_keys = _block_two_model_keys(block_two_models)
    return [
        model
        for model in _filter_models_for_current_plan(all_models)
        if _category_for_model(model) == "llm"
        and _model_validation_key(model.get("provider", ""), model.get("id", "")) not in excluded_keys
    ]


def _remaining_llm_models_from_keys(all_models: list[dict], excluded_keys: set[str]) -> list[dict]:
    current_plan_models = _filter_models_for_current_plan(all_models)
    return [
        model
        for model in current_plan_models
        if _category_for_model(model) == "llm"
        and _model_validation_key(model.get("provider", ""), model.get("id", "")) not in excluded_keys
    ]


def _merge_validation_results(existing_payload: dict, new_results: dict, validated_at: str) -> dict:
    merged = dict(existing_payload or {})
    merged_models = dict((existing_payload or {}).get("models", {}))
    merged_models.update(new_results)
    merged["validated_at"] = validated_at
    merged["models"] = merged_models
    return merged


def _build_validated_llm_cache_payload(
    candidate_models: list[dict],
    validation_payload: dict,
) -> dict:
    validation_models = validation_payload.get("models", {})
    passed_models = []

    for model in candidate_models:
        key = _model_validation_key(model.get("provider", ""), model.get("id", ""))
        validation_item = validation_models.get(key, {})
        if validation_item.get("passed") is True:
            enriched = dict(model)
            enriched["_validation"] = {
                "message_excerpt": validation_item.get("message_excerpt"),
                "error": validation_item.get("error"),
                "validated_at": validation_payload.get("validated_at"),
            }
            passed_models.append(enriched)

    return {
        "object": "list",
        "data": passed_models,
        "meta": {
            "filter": "block_two_first_then_remaining_llm_passed_validation",
            "validated_at": validation_payload.get("validated_at"),
            "total_candidates": len(candidate_models),
            "total_after_filter": len(passed_models),
            "cache_created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _group_models_by_id(candidate_models: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {}
    for model in candidate_models:
        if not isinstance(model, dict):
            continue
        provider_name = str(model.get("provider") or "").strip()
        model_id = str(model.get("id") or "").strip()
        if not provider_name or not model_id:
            continue
        grouped.setdefault(model_id, []).append(model)
    return sorted(grouped.items(), key=lambda item: item[0].lower())


async def _execute_model_test(provider_name: str, model_id: str) -> tuple[bool | None, str | None, str | None]:
    request = ChatCompletionRequest(
        provider=provider_name,
        model=model_id,
        messages=[{"role": "user", "content": TEST_PROMPT}],
        max_tokens=32,
        temperature=0.1,
    )

    try:
        response = await provider_router.race_chat_completion(request)
        choices = response.get("choices", [])
        message_excerpt = None
        if choices and isinstance(choices[0], dict):
            message_excerpt = ((choices[0].get("message") or {}).get("content") or "")[:300]
        return _is_valid_test_reply(message_excerpt), message_excerpt, None
    except Exception as exc:
        return False, None, str(exc)


def _store_model_test_result(
    provider_name: str,
    model_id: str,
    passed_validation: bool | None,
    message_excerpt: str | None,
    error_text: str | None,
) -> dict:
    validation_payload = _load_model_validation_results()
    validation_payload["validated_at"] = datetime.now(timezone.utc).isoformat()
    validation_payload.setdefault("models", {})[_model_validation_key(provider_name, model_id)] = {
        "provider": provider_name,
        "model_id": model_id,
        "passed": passed_validation,
        "message_excerpt": message_excerpt,
        "error": error_text,
        "tested_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_model_validation_results(validation_payload)
    return validation_payload


async def _validate_llm_models(candidate_models: list[dict], merge_existing: bool = False) -> dict:
    validation_payload = _load_model_validation_results() if merge_existing else {"validated_at": None, "models": {}}
    new_results: dict[str, dict] = {}
    passed = 0
    failed = 0

    grouped_models = _group_models_by_id(candidate_models)

    for group_index, (model_id, group_models) in enumerate(grouped_models):
        logger.info("llm_validation_group_started model_id=%s providers=%s", model_id, len(group_models))
        group_tasks = [
            _execute_model_test(str(model.get("provider") or "").strip(), model_id)
            for model in group_models
        ]
        group_results = await asyncio.gather(*group_tasks)

        merge_payload: dict[str, dict] = {}
        for model, result in zip(group_models, group_results):
            provider_name = str(model.get("provider") or "").strip()
            if not provider_name:
                continue
            passed_validation, message_excerpt, error_text = result
            key = _model_validation_key(provider_name, model_id)
            new_results[key] = {
                "provider": provider_name,
                "model_id": model_id,
                "passed": passed_validation,
                "message_excerpt": message_excerpt,
                "error": error_text,
            }
            merge_payload[key] = new_results[key]

            if passed_validation:
                passed += 1
            else:
                failed += 1

        if merge_payload:
            validation_payload = _merge_validation_results(
                validation_payload,
                merge_payload,
                datetime.now(timezone.utc).isoformat(),
            )
            _save_model_validation_results(validation_payload)

        logger.info(
            "llm_validation_group_completed model_id=%s providers=%s passed=%s failed=%s",
            model_id,
            len(group_models),
            sum(1 for item in merge_payload.values() if item.get("passed") is True),
            sum(1 for item in merge_payload.values() if item.get("passed") is not True),
        )

        if group_index < len(grouped_models) - 1:
            await asyncio.sleep(1)

    return {
        "status": "ok",
        "validated": len(candidate_models),
        "passed": passed,
        "failed": failed,
        "validated_at": validation_payload.get("validated_at"),
    }


async def _run_validated_llm_job(started_by: str) -> None:
    global VALIDATED_LLM_JOB_TASK

    _reset_validated_llm_job_state(started_by)
    try:
        models_payload = await provider_router.get_models()
        all_models = models_payload.get("data", [])
        block_two_priority_models = _block_two_llm_candidates(all_models)
        excluded_keys = _block_two_model_keys(block_two_priority_models)
        remaining_models = _remaining_llm_models_from_keys(all_models, excluded_keys)
        validation_candidates = [*block_two_priority_models, *remaining_models]

        seen_candidate_keys: set[str] = set()
        ordered_candidates: list[dict] = []
        for model in validation_candidates:
            key = _model_validation_key(model.get("provider", ""), model.get("id", ""))
            if not key or key in seen_candidate_keys:
                continue
            seen_candidate_keys.add(key)
            ordered_candidates.append(model)

        VALIDATED_LLM_JOB_STATE["total_models"] = len(ordered_candidates)
        passed = 0
        failed = 0

        grouped_candidates = _group_models_by_id(ordered_candidates)

        for group_index, (model_id, group_models) in enumerate(grouped_candidates):
            logger.info("llm_validation_job_group_started model_id=%s providers=%s", model_id, len(group_models))
            VALIDATED_LLM_JOB_STATE["requests_started"] += len(group_models)

            group_tasks = [
                _execute_model_test(str(model.get("provider") or "").strip(), model_id)
                for model in group_models
            ]
            group_results = await asyncio.gather(*group_tasks)

            group_passed = 0
            group_failed = 0
            for model, result in zip(group_models, group_results):
                provider_name = str(model.get("provider") or "").strip()
                if not provider_name:
                    continue
                passed_validation, message_excerpt, error_text = result
                _store_model_test_result(provider_name, model_id, passed_validation, message_excerpt, error_text)
                VALIDATED_LLM_JOB_STATE["responses_received"] += 1

                if passed_validation:
                    passed += 1
                    group_passed += 1
                else:
                    failed += 1
                    group_failed += 1

                VALIDATED_LLM_JOB_STATE["passed"] = passed
                VALIDATED_LLM_JOB_STATE["failed"] = failed

            logger.info(
                "llm_validation_job_group_completed model_id=%s providers=%s passed=%s failed=%s",
                model_id,
                len(group_models),
                group_passed,
                group_failed,
            )

            if group_index < len(grouped_candidates) - 1:
                await asyncio.sleep(1)

        validation_payload = _load_model_validation_results()
        validated_llm_payload = _build_validated_llm_cache_payload(ordered_candidates, validation_payload)
        block_two_payload = await get_available_models_for_admin()
        await _refresh_admin_cache_async(
            all_models=all_models,
            block_two_payload=block_two_payload,
            validated_llm_payload=validated_llm_payload,
        )
        VALIDATED_LLM_JOB_STATE["status"] = "completed"
    except Exception as exc:
        VALIDATED_LLM_JOB_STATE["status"] = "failed"
        VALIDATED_LLM_JOB_STATE["error"] = str(exc)
    finally:
        VALIDATED_LLM_JOB_STATE["running"] = False
        VALIDATED_LLM_JOB_STATE["last_finished_at"] = datetime.now(timezone.utc).isoformat()
        VALIDATED_LLM_JOB_TASK = None


async def _run_live_limits_job(started_by: str) -> None:
    global LIVE_LIMITS_JOB_TASK

    _reset_live_limits_job_state(started_by)
    try:
        probe_summary = await provider_router.probe_provider_limits()
        rate_limit_store.record_probe_summary(
            successful=probe_summary["successful"],
            failed=probe_summary["failed"],
        )
        LIVE_LIMITS_JOB_STATE["probe_successful"] = len(probe_summary["successful"])
        LIVE_LIMITS_JOB_STATE["probe_failed"] = len(probe_summary["failed"])

        await _sample_provider_limits()
        await validate_all_models_for_admin()
        await _refresh_admin_cache_async()

        LIVE_LIMITS_JOB_STATE["status"] = "completed"
    except Exception as exc:
        LIVE_LIMITS_JOB_STATE["status"] = "failed"
        LIVE_LIMITS_JOB_STATE["error"] = str(exc)
    finally:
        LIVE_LIMITS_JOB_STATE["running"] = False
        LIVE_LIMITS_JOB_STATE["last_finished_at"] = datetime.now(timezone.utc).isoformat()
        LIVE_LIMITS_JOB_TASK = None


def _model_validation_key(provider: str, model_id: str) -> str:
    return f"{provider}::{model_id}"


def _category_for_model(model: dict) -> str:
    explicit_category = str(model.get("category", "")).strip().lower()
    if explicit_category in {"llm", "audio", "video", "other"}:
        return explicit_category

    model_id = str(model.get("id", "")).lower()
    name = str(model.get("name", "")).lower()
    description = str(model.get("description", "")).lower()
    haystack = f"{model_id} {name} {description}"

    audio_hints = ["whisper", "transcribe", "transcription", "speech-to-text", "stt", "asr", "audio"]
    video_hints = ["video", "veo", "sora", "movie", "clip", "vision-video", "gen-video"]
    llm_hints = [
        "chat",
        "instruct",
        "llama",
        "gpt",
        "gemini",
        "gemma",
        "glm",
        "qwen",
        "deepseek",
        "claude",
        "mistral",
        "allam",
        "minimax",
        "compound",
        "command",
        "language",
        "reason",
        "completion",
    ]

    if any(hint in haystack for hint in audio_hints):
        return "audio"
    if any(hint in haystack for hint in video_hints):
        return "video"
    if any(hint in haystack for hint in llm_hints):
        return "llm"
    return "other"


def _select_test_model(provider_name: str, models: list[dict]) -> str | None:
    model_ids = [item.get("id") for item in models if isinstance(item, dict) and item.get("id")]
    for preferred in PREFERRED_TEST_MODELS.get(provider_name, []):
        if preferred in model_ids:
            return preferred
    return model_ids[0] if model_ids else None


def _is_model_available_for_current_plan(model: dict) -> bool:
    provider = model.get("provider")
    model_id = str(model.get("id", "")).lower()

    if provider == "openrouter":
        return model_id.endswith(":free")

    if provider == "gemini":
        return any(model_id.startswith(prefix) for prefix in GEMINI_FREE_TIER_PREFIXES)

    if provider == "groq":
        if not model.get("active", True):
            return False
        return not any(model_id.startswith(prefix) for prefix in GROQ_EXCLUDED_PREFIXES)

    if provider in {"cerebras", "sambanova"}:
        return True

    return True


def _filter_models_for_current_plan(models: list[dict]) -> list[dict]:
    return [
        model
        for model in models
        if isinstance(model, dict) and model.get("id") and _is_model_available_for_current_plan(model)
    ]


def _filter_models_with_live_limits(models: list[dict]) -> list[dict]:
    snapshot = rate_limit_store.get_snapshot(list(settings.get_provider_configs().keys()))
    providers_with_live_limits = {
        provider
        for provider, item in snapshot.items()
        if item.get("limits", {}).get("source") == "response_headers"
    }
    if not providers_with_live_limits:
        estimated_limits = _load_estimated_limits().get("providers", {})
        providers_with_live_limits = {
            provider
            for provider, item in estimated_limits.items()
            if isinstance(item, dict) and (isinstance(item.get("estimated_rpm"), int) or isinstance(item.get("estimated_rpd"), int))
        }
    return [
        model
        for model in models
        if isinstance(model, dict) and model.get("provider") in providers_with_live_limits
    ]


def _filter_models_by_validation(models: list[dict]) -> list[dict]:
    validation_payload = _load_model_validation_results()
    validated_models = validation_payload.get("models", {})
    passed_keys = {
        key
        for key, item in validated_models.items()
        if isinstance(item, dict) and item.get("passed") is True
    }
    if not passed_keys:
        return models
    return [
        model
        for model in models
        if _category_for_model(model) != "llm"
        or _model_validation_key(model.get("provider", ""), model.get("id", "")) in passed_keys
    ]


def _remaining_rpm(item: dict) -> int | None:
    return item.get("limits", {}).get("requests", {}).get("minute", {}).get("remaining")


def _remaining_rpd(item: dict) -> int | None:
    return item.get("limits", {}).get("requests", {}).get("day", {}).get("remaining")


def _remaining_tpm(item: dict) -> int | None:
    return item.get("limits", {}).get("tokens", {}).get("minute", {}).get("remaining")


def _is_auto_value(value: str | None) -> bool:
    return str(value or "").strip().lower() == "auto"


def _estimated_provider_limits(provider_name: str) -> tuple[int, int]:
    estimated = _load_estimated_limits().get("providers", {}).get(provider_name, {})
    rpm = estimated.get("estimated_rpm")
    rpd = estimated.get("estimated_rpd")
    return (
        rpm if isinstance(rpm, int) else -1,
        rpd if isinstance(rpd, int) else -1,
    )


def _runtime_chat_models() -> list[dict]:
    cache = _get_runtime_dispatcher_cache()
    validated_llm_models = (cache.get("validated_llm") or {}).get("data") or []
    if validated_llm_models:
        return [model for model in validated_llm_models if isinstance(model, dict)]

    block_two_models = (cache.get("block_two") or {}).get("data") or []
    if block_two_models:
        return [model for model in block_two_models if isinstance(model, dict)]

    routes = cache.get("routes") or []
    return [
        {
            "provider": route.get("provider"),
            "id": route.get("model_id"),
            "category": route.get("category"),
        }
        for route in routes
        if isinstance(route, dict) and route.get("provider") and route.get("model_id")
    ]


def _pick_auto_route(
    chat_models: list[dict],
    requested_provider: str | None = None,
    requested_model: str | None = None,
) -> dict[str, str] | None:
    provider_names = list(settings.get_provider_configs().keys())
    snapshot = rate_limit_store.get_snapshot(provider_names)
    filtered_models = [
        model
        for model in chat_models
        if _category_for_model(model) == "llm"
        and (
            _is_auto_value(requested_provider)
            or not requested_provider
            or model.get("provider") == requested_provider
        )
        and (
            _is_auto_value(requested_model)
            or not requested_model
            or model.get("id") == requested_model
        )
    ]
    if not filtered_models:
        return None

    models_count_by_provider: dict[str, int] = {}
    for model in filtered_models:
        provider_name = model.get("provider")
        if provider_name:
            models_count_by_provider[provider_name] = models_count_by_provider.get(provider_name, 0) + 1

    route_candidates: list[dict] = []
    for index, model in enumerate(filtered_models):
        provider_name = model.get("provider")
        if not provider_name:
            continue
        item = snapshot.get(provider_name, {})
        source = item.get("limits", {}).get("source")
        estimated_rpm, estimated_rpd = _estimated_provider_limits(provider_name)
        has_live_limits = source == "response_headers"
        has_estimated_limits = estimated_rpm >= 0 or estimated_rpd >= 0
        if not has_live_limits and not has_estimated_limits:
            continue

        rpm_remaining = _remaining_rpm(item)
        rpd_remaining = _remaining_rpd(item)
        tpm_remaining = _remaining_tpm(item)
        route_candidates.append(
            {
                "provider": provider_name,
                "model": model.get("id"),
                "source_rank": 0 if has_live_limits else 1,
                "rpm_remaining": rpm_remaining if rpm_remaining is not None else estimated_rpm,
                "rpd_remaining": rpd_remaining if rpd_remaining is not None else estimated_rpd,
                "tpm_remaining": tpm_remaining if tpm_remaining is not None else -1,
                "models_count": models_count_by_provider.get(provider_name, 0),
                "index": index,
            }
        )

    if not route_candidates:
        return None

    route_candidates.sort(
        key=lambda item: (
            item["source_rank"],
            -item["rpm_remaining"],
            -item["tpm_remaining"],
            -item["rpd_remaining"],
            -item["models_count"],
            item["index"],
        )
    )
    return {
        "provider": route_candidates[0]["provider"],
        "model": route_candidates[0]["model"],
    }


async def _sample_provider_limits() -> None:
    for provider_name in provider_router.list_available_providers():
        try:
            models_payload = await provider_router.get_models(provider_name)
        except (ValueError, UpstreamProvidersExhausted):
            continue

        models = models_payload.get("data", [])
        selected_model = _select_test_model(provider_name, models)
        if not selected_model:
            continue

        request = ChatCompletionRequest(
            provider=provider_name,
            model=selected_model,
            messages=[{"role": "user", "content": TEST_PROMPT}],
            max_tokens=32,
            temperature=0.1,
        )
        try:
            await provider_router.race_chat_completion(request)
        except (ValueError, UpstreamProvidersExhausted):
            continue


@router.get("/health/limits", tags=["Health"])
async def get_limits_health() -> dict:
    provider_names = list(settings.get_provider_configs().keys())
    return {
        "status": "ok",
        "providers": provider_names,
        **rate_limit_store.get_health_payload(provider_names),
    }


@router.get("/admin", response_class=HTMLResponse, tags=["Admin"])
async def admin_dashboard() -> HTMLResponse:
    return HTMLResponse(content=ADMIN_PAGE_HTML)


@router.get("/admin/p2p", response_class=HTMLResponse, tags=["Admin"])
async def p2p_admin_dashboard() -> HTMLResponse:
    return HTMLResponse(content=P2P_ADMIN_PAGE_HTML)


@router.get("/admin/p2p/status", tags=["Admin"])
async def get_p2p_status() -> dict:
    return p2p_service.get_status()


@router.get("/admin/p2p/peers", tags=["Admin"])
async def get_p2p_peers() -> dict:
    status = p2p_service.get_status()
    return {
        "status": "ok",
        "count": len(status.get("peers", [])),
        "peers": status.get("peers", []),
    }


@router.post("/admin/p2p/config", tags=["Admin"])
async def update_p2p_runtime_config(
    node_mode: str | None = Query(default=None),
    p2p_enabled: bool | None = Query(default=None),
) -> dict:
    try:
        return p2p_service.update_runtime_config(
            node_mode=node_mode,
            p2p_enabled=p2p_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/admin/p2p/peers/heartbeat", tags=["Admin"])
async def upsert_p2p_peer_heartbeat(
    peer_id: str = Query(...),
    node_name: str = Query(...),
    node_mode: str = Query(default="peer"),
    scope: str = Query(default="private"),
    base_url: str = Query(default=""),
    status: str = Query(default="online"),
    note: str = Query(default=""),
    accept_remote_tasks: bool = Query(default=True),
    share_capacity: bool = Query(default=True),
    direct_provider_access: bool = Query(default=True),
    supports_chat: bool = Query(default=True),
    supports_embeddings: bool = Query(default=True),
    providers: str | None = Query(default=None),
    models: str | None = Query(default=None),
    route_catalog: str | None = Query(default=None),
    health_score: float | None = Query(default=None),
    active_sessions: int = Query(default=0),
    last_error: str = Query(default=""),
    shared_rpm_ratio: float = Query(default=1.0),
    shared_tpm_ratio: float = Query(default=1.0),
) -> dict:
    try:
        peer = p2p_service.register_or_update_peer(
            peer_id=peer_id,
            node_name=node_name,
            node_mode=node_mode,
            scope=scope,
            base_url=base_url,
            status=status,
            note=note,
            accept_remote_tasks=accept_remote_tasks,
            share_capacity=share_capacity,
            direct_provider_access=direct_provider_access,
            supports_chat=supports_chat,
            supports_embeddings=supports_embeddings,
            providers=providers,
            models=models,
            route_catalog=route_catalog,
            health_score=health_score,
            active_sessions=active_sessions,
            last_error=last_error,
            shared_rpm_ratio=shared_rpm_ratio,
            shared_tpm_ratio=shared_tpm_ratio,
        )
        return {"status": "ok", "peer": peer}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/admin/p2p/sessions", tags=["Admin"])
async def update_p2p_session_counters(
    active_incoming_sessions: int | None = Query(default=None),
    active_outgoing_sessions: int | None = Query(default=None),
    queued_tasks: int | None = Query(default=None),
) -> dict:
    return p2p_service.set_session_counters(
        active_incoming_sessions=active_incoming_sessions,
        active_outgoing_sessions=active_outgoing_sessions,
        queued_tasks=queued_tasks,
    )


@router.post("/admin/p2p/nodes/remove", tags=["Admin"])
async def remove_p2p_node(
    mode: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    node_key: str = Query(...),
) -> dict:
    try:
        return p2p_service.remove_known_node(mode=(mode or kind or ""), node_key=node_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/admin/p2p/dispatch/preview", tags=["Admin"])
async def p2p_dispatch_preview(
    requested_provider: str | None = Query(default="auto"),
    requested_model: str | None = Query(default="auto"),
    requested_mode: str | None = Query(default=None),
    task_type: str = Query(default="chat_completion"),
) -> dict:
    try:
        return p2p_service.dispatch_preview(
            requested_provider=requested_provider,
            requested_model=requested_model,
            requested_mode=requested_mode,
            task_type=task_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/internal/p2p/re-register", tags=["Internal"])
async def p2p_reregister_to_master(
    master_url: str | None = Query(default=None),
    reason: str = Query(default="manual_reregister"),
) -> dict:
    try:
        return await p2p_service.send_local_heartbeat(master_url=master_url, reason=reason)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/internal/p2p/network-map", tags=["Internal"])
async def get_internal_p2p_network_map() -> dict:
    return p2p_service.export_network_map()


@router.get("/admin/limits/estimated", tags=["Admin"])
async def get_estimated_limits() -> dict:
    return _load_estimated_limits()


@router.get("/admin/dispatcher/cache", tags=["Admin"])
async def get_dispatcher_cache() -> dict:
    return await _refresh_admin_cache_async()


@router.get("/admin/dispatcher/status", tags=["Admin"])
async def get_dispatcher_status() -> dict:
    try:
        return await provider_router.get_dispatcher_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/admin/dispatcher/mode", tags=["Admin"])
async def set_dispatcher_mode(mode: str = Query(...)) -> dict:
    try:
        proxy_mode = provider_router.set_proxy_mode(mode)
        await _refresh_admin_cache_async()
        return {"proxy_mode": proxy_mode}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/admin/models/available", tags=["Admin"])
async def get_available_models_for_admin() -> dict:
    try:
        models_payload = await provider_router.get_models()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)

    all_models = models_payload.get("data", [])
    filtered_models = _filter_models_for_current_plan(all_models)
    filtered_models = _filter_models_with_live_limits(filtered_models)
    filtered_models = _filter_models_by_validation(filtered_models)
    payload = {
        "object": "list",
        "data": filtered_models,
        "meta": {
            "filter": "current_plan_only_and_live_limits_only",
            "total_before_filter": len(all_models),
            "total_after_filter": len(filtered_models),
        },
    }
    await _refresh_admin_cache_async(all_models=all_models, block_two_payload=payload)
    return payload


@router.get("/admin/models/validated-llm", tags=["Admin"])
async def get_validated_llm_models_for_admin() -> dict:
    cache_payload = _load_admin_cache()
    validated_llm = cache_payload.get("validated_llm")
    if isinstance(validated_llm, dict):
        return validated_llm
    return {"object": "list", "data": [], "meta": {"cache_created_at": None}}


@router.get("/admin/models/validate-remaining-llm/status", tags=["Admin"])
async def get_validate_remaining_llm_status() -> dict:
    return _get_validated_llm_job_state()


@router.post("/admin/models/validate-all", tags=["Admin"])
async def validate_all_models_for_admin() -> dict:
    try:
        models_payload = await provider_router.get_models()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)

    all_models = models_payload.get("data", [])
    candidate_models = _filter_models_for_current_plan(all_models)
    candidate_models = _filter_models_with_live_limits(candidate_models)
    candidate_models = [model for model in candidate_models if _category_for_model(model) == "llm"]

    result = await _validate_llm_models(candidate_models, merge_existing=True)
    block_two_payload = await get_available_models_for_admin()
    await _refresh_admin_cache_async(all_models=all_models, block_two_payload=block_two_payload)
    return result


@router.post("/admin/models/validate-remaining-llm", tags=["Admin"])
async def validate_remaining_llm_models_for_admin(started_by: str = Query(default="manual")) -> dict:
    global VALIDATED_LLM_JOB_TASK

    if VALIDATED_LLM_JOB_TASK and not VALIDATED_LLM_JOB_TASK.done():
        return {"status": "running", "job": _get_validated_llm_job_state()}

    _reset_validated_llm_job_state(started_by)
    VALIDATED_LLM_JOB_TASK = asyncio.create_task(_run_validated_llm_job(started_by))
    return {"status": "started", "job": _get_validated_llm_job_state()}


@router.post("/admin/test", tags=["Admin"])
async def test_provider(
    provider_name: str = Query(...),
    model_id: str | None = Query(default=None),
) -> dict:
    try:
        models_payload = await provider_router.get_models(provider_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)

    models = models_payload.get("data", [])
    available_ids = [item.get("id") for item in models if isinstance(item, dict) and item.get("id")]
    selected_model = model_id if model_id in available_ids else _select_test_model(provider_name, models)
    if not selected_model:
        raise HTTPException(status_code=404, detail=f"No models available for provider '{provider_name}'")

    request = ChatCompletionRequest(
        provider=provider_name,
        model=selected_model,
        messages=[{"role": "user", "content": TEST_PROMPT}],
        max_tokens=32,
        temperature=0.1,
    )

    try:
        response = await provider_router.race_chat_completion(request)
    except ValueError as exc:
        _store_model_test_result(provider_name, selected_model, None, None, str(exc))
        await _refresh_admin_cache_async()
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        _store_model_test_result(provider_name, selected_model, None, None, str(exc))
        await _refresh_admin_cache_async()
        raise HTTPException(status_code=502, detail=exc.errors)

    message = None
    choices = response.get("choices", [])
    if choices and isinstance(choices[0], dict):
        message = (choices[0].get("message") or {}).get("content")

    passed_validation = None
    if any(
        item.get("id") == selected_model and _category_for_model(item) == "llm"
        for item in models
        if isinstance(item, dict)
    ):
        passed_validation = _is_valid_test_reply(message)
    _store_model_test_result(
        provider_name,
        selected_model,
        passed_validation,
        message[:300] if isinstance(message, str) else None,
        None,
    )
    await _refresh_admin_cache_async()

    return {
        "provider": provider_name,
        "model": selected_model,
        "selected_provider": response.get("_proxy", {}).get("selected_provider"),
        "message_excerpt": message[:300] if isinstance(message, str) else None,
    }


@router.get("/health/limits/live/status", tags=["Health"])
async def get_live_limits_refresh_status() -> dict:
    return _get_live_limits_job_state()


@router.post("/health/limits/live", tags=["Health"])
async def refresh_limits_health(started_by: str = Query(default="manual")) -> dict:
    global LIVE_LIMITS_JOB_TASK

    provider_names = list(settings.get_provider_configs().keys())
    if not provider_names:
        raise HTTPException(status_code=400, detail="No providers are configured")

    if LIVE_LIMITS_JOB_TASK and not LIVE_LIMITS_JOB_TASK.done():
        return {"status": "running", "job": _get_live_limits_job_state()}

    _reset_live_limits_job_state(started_by)
    LIVE_LIMITS_JOB_TASK = asyncio.create_task(_run_live_limits_job(started_by))
    return {"status": "started", "job": _get_live_limits_job_state()}


@router.get("/v1/models", tags=["Models"])
async def get_models() -> dict:
    try:
        return await provider_router.get_models()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)


@router.post("/v1/chat/completions", tags=["Chat"])
async def create_chat_completion(request: ChatCompletionRequest) -> dict:
    effective_request = request
    requested_provider_auto = _is_auto_value(request.provider)
    requested_model_auto = _is_auto_value(request.model)

    if requested_provider_auto or requested_model_auto:
        candidate_models = _runtime_chat_models()
        selected_route = _pick_auto_route(
            candidate_models,
            requested_provider=request.provider,
            requested_model=request.model,
        )
        if not selected_route:
            raise HTTPException(status_code=404, detail="No available provider/model route for requested auto selection")

        update_payload = {}
        if requested_provider_auto:
            update_payload["provider"] = selected_route["provider"]
        if requested_model_auto:
            update_payload["model"] = selected_route["model"]
        effective_request = request.model_copy(update=update_payload)

    try:
        response = await provider_router.race_chat_completion(effective_request)
        response.setdefault("_proxy", {})
        response["provider"] = response["_proxy"].get("selected_provider") or effective_request.provider
        response["model"] = response["_proxy"].get("selected_model") or effective_request.model
        if requested_provider_auto or requested_model_auto:
            response["_proxy"]["requested_provider"] = request.provider
            response["_proxy"]["requested_model"] = request.model
            response["_proxy"]["auto_selected_provider"] = effective_request.provider
            response["_proxy"]["auto_selected_model"] = effective_request.model
            response["_proxy"]["selected_policy"] = (
                "recommendations" if effective_request.provider and effective_request.model else "fastest_fallback"
            )
        await _refresh_admin_cache_async()
        return response
    except ValueError as exc:
        await _refresh_admin_cache_async()
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        await _refresh_admin_cache_async()
        raise HTTPException(status_code=502, detail=exc.errors)


@router.post("/v1/embeddings", tags=["Embeddings"])
async def create_embeddings(request: EmbeddingRequest) -> dict:
    try:
        response = await provider_router.race_embeddings(request)
        await _refresh_admin_cache_async()
        return response
    except ValueError as exc:
        await _refresh_admin_cache_async()
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        await _refresh_admin_cache_async()
        raise HTTPException(status_code=502, detail=exc.errors)

