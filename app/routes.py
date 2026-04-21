import asyncio
from collections import deque
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from typing import Any

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse

from app.admin_ui import ADMIN_PAGE_HTML
from app.audio_transcription import (
    build_audio_transcription_request,
    normalize_audio_transcription_response,
)
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
INVALID_RESOURCES_FILE = Path(__file__).resolve().parent.parent / "invalid_resources.json"
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
AUTO_RESOURCE_USAGE_WINDOW_SEC = 60
AUTO_RESOURCE_AFFINITY_TTL_SEC = 60 * 60 * 12
AUTO_RESOURCE_USAGE: dict[str, dict] = {}
CLIENT_RESOURCE_AFFINITY: dict[str, dict] = {}
AUTO_RESOURCE_ROUND_ROBIN_CURSOR = 0
AUTO_LAST_SELECTED_PROVIDER: str | None = None
REQUEST_INCOMPATIBLE_QUARANTINE_MINUTES = 30
MODEL_NOT_FOUND_INVALID_MINUTES = 24 * 60
CREDITS_INVALID_MINUTES = 6 * 60
BAD_REQUEST_INVALID_MINUTES = 24 * 60


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
        return {
            "validated_llm": {"object": "list", "data": [], "meta": {"cache_created_at": None}},
            "invalid_resources": {"object": "list", "data": [], "meta": {"updated_at": None}},
        }
    try:
        return json.loads(ADMIN_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "validated_llm": {"object": "list", "data": [], "meta": {"cache_created_at": None}},
            "invalid_resources": {"object": "list", "data": [], "meta": {"updated_at": None}},
        }


def _save_admin_cache(payload: dict) -> None:
    ADMIN_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _empty_invalid_resources_payload() -> dict:
    return {
        "object": "list",
        "data": [],
        "meta": {
            "updated_at": None,
            "total": 0,
            "temporary_backoff": {},
        },
    }


def _load_invalid_resources() -> dict:
    if not INVALID_RESOURCES_FILE.exists():
        return _empty_invalid_resources_payload()
    try:
        payload = json.loads(INVALID_RESOURCES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_invalid_resources_payload()
    if not isinstance(payload, dict):
        return _empty_invalid_resources_payload()
    payload.setdefault("object", "list")
    payload.setdefault("data", [])
    payload.setdefault("meta", {})
    payload["meta"].setdefault("updated_at", None)
    payload["meta"].setdefault("temporary_backoff", {})
    payload["meta"]["total"] = len(payload.get("data", []))
    return payload


def _save_invalid_resources(payload: dict) -> dict:
    meta = dict(payload.get("meta", {}))
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    meta["total"] = len(payload.get("data", []))
    meta["temporary_backoff"] = dict(meta.get("temporary_backoff", {}))
    normalized = {
        "object": "list",
        "data": list(payload.get("data", [])),
        "meta": meta,
    }
    INVALID_RESOURCES_FILE.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def _resource_id(provider_name: str, model_id: str) -> str:
    return f"{provider_name.strip()}::{model_id.strip()}"


def _resolve_local_route_id(provider_name: str | None, model_id: str | None) -> str:
    if not provider_name or not model_id:
        return ""
    return p2p_service.resolve_local_route_id(str(provider_name), str(model_id))


def _active_invalid_resource_entries() -> list[dict]:
    payload = _load_invalid_resources()
    now = datetime.now(timezone.utc)
    active: list[dict] = []
    changed = False
    for item in payload.get("data", []):
        if not isinstance(item, dict):
            changed = True
            continue
        invalid_until = item.get("invalid_until")
        if invalid_until:
            try:
                until = datetime.fromisoformat(str(invalid_until))
            except ValueError:
                changed = True
                continue
            if until <= now:
                changed = True
                continue
        active.append(item)
    if changed:
        payload["data"] = active
        _save_invalid_resources(payload)
    return active


def _is_blocking_invalid_entry(item: dict[str, Any] | None) -> bool:
    if not isinstance(item, dict):
        return False
    return bool(item.get("blocking", True))


def _invalid_resource_index() -> dict[str, dict]:
    return {
        str(item.get("resource_id") or ""): item
        for item in _active_invalid_resource_entries()
        if item.get("resource_id") and _is_blocking_invalid_entry(item)
    }


def _invalid_route_id_index() -> dict[str, dict]:
    return {
        str(item.get("route_id") or ""): item
        for item in _active_invalid_resource_entries()
        if item.get("route_id") and _is_blocking_invalid_entry(item)
    }


def _is_invalid_resource(provider_name: str | None, model_id: str | None) -> bool:
    if not provider_name or not model_id:
        return False
    route_id = _resolve_local_route_id(provider_name, model_id)
    if route_id and route_id in _invalid_route_id_index():
        return True
    return _resource_id(provider_name, model_id) in _invalid_resource_index()


def _find_invalid_resource(provider_name: str | None, model_id: str | None) -> dict:
    route_id = _resolve_local_route_id(provider_name, model_id)
    if route_id:
        item = _invalid_route_id_index().get(route_id)
        if item:
            return item
    if provider_name and model_id:
        item = _invalid_resource_index().get(_resource_id(provider_name, model_id))
        if item:
            return item
    return {}


def _normalize_response_type(value: str | None) -> str:
    cleaned = str(value or "json").strip().lower()
    if cleaned in {"json", "text", "audio", "video"}:
        return cleaned
    return "json"


def _parse_error_detail(detail: str | None) -> tuple[Any, str]:
    raw_detail = str(detail or "").strip()
    if not raw_detail:
        return None, ""
    try:
        return json.loads(raw_detail), raw_detail
    except json.JSONDecodeError:
        return None, raw_detail


def _flatten_error_text(detail: str | None) -> str:
    parsed, raw_detail = _parse_error_detail(detail)
    texts: list[str] = []

    def _walk(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            cleaned = " ".join(value.split()).strip()
            if cleaned:
                texts.append(cleaned)
            return
        if isinstance(value, dict):
            for key in ("message", "detail", "code", "type", "status", "param", "error"):
                if key in value:
                    _walk(value.get(key))
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    _walk(nested)
            return
        if isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(parsed)
    if texts:
        return " | ".join(texts).lower()
    return " ".join(raw_detail.split()).lower()


def _error_reason_suffix(detail: str | None) -> str:
    flat = _flatten_error_text(detail)
    if "tool_call_id" in flat:
        return "tool_call_id_missing"
    if "developer instruction" in flat:
        return "developer_instruction_not_supported"
    if "roles must alternate" in flat:
        return "roles_must_alternate"
    if "last message role must be 'user'" in flat:
        return "last_role_must_be_user"
    if "max_tokens" in flat:
        return "max_tokens_limit"
    if "not found" in flat:
        return "not_found"
    if "not available" in flat or "gone" in flat or "deprecated" in flat:
        return "gone"
    if "insufficient credits" in flat or "payment required" in flat:
        return "credits"
    return "generic"


def _is_request_incompatible_error(status_code: int | None, detail: str | None) -> bool:
    if status_code not in {400, 404, 410, 422}:
        return False
    flat = _flatten_error_text(detail)
    keywords = (
        "tool_call_id",
        "developer instruction is not enabled",
        "roles must alternate",
        "last message role must be 'user'",
        "max_tokens",
        "wrong_api_format",
        "validation_error",
        "jinja template rendering failed",
    )
    return any(keyword in flat for keyword in keywords)


def _classify_resource_error(errors: list[dict[str, Any]]) -> dict[str, Any]:
    items = [error for error in errors if isinstance(error, dict)]
    first = items[0] if items else {}
    status_code = first.get("status_code")
    detail = str(first.get("detail") or "")
    suffix = _error_reason_suffix(detail)

    if items and all(_is_temporary_resource_error_status(item.get("status_code")) for item in items):
        return {
            "action": "temporary_quarantine",
            "reason": _temporary_error_reason(status_code, detail),
            "status_code": status_code,
            "detail": detail,
            "retry_auto": True,
        }

    if status_code == 402:
        return {
            "action": "invalid_resource",
            "reason": f"provider_credits_exhausted:{suffix}",
            "status_code": status_code,
            "detail": detail,
            "invalid_minutes": CREDITS_INVALID_MINUTES,
            "retry_auto": True,
        }

    if status_code == 400:
        return {
            "action": "invalid_resource",
            "reason": f"bad_request:{suffix}",
            "status_code": status_code,
            "detail": detail,
            "invalid_minutes": BAD_REQUEST_INVALID_MINUTES,
            "retry_auto": True,
        }

    if status_code == 404:
        return {
            "action": "invalid_resource",
            "reason": f"model_not_found:{suffix}",
            "status_code": status_code,
            "detail": detail,
            "invalid_minutes": MODEL_NOT_FOUND_INVALID_MINUTES,
            "retry_auto": True,
        }

    if status_code == 410:
        return {
            "action": "invalid_resource",
            "reason": f"model_gone:{suffix}",
            "status_code": status_code,
            "detail": detail,
            "invalid_minutes": MODEL_NOT_FOUND_INVALID_MINUTES,
            "retry_auto": True,
        }

    if _is_request_incompatible_error(status_code, detail):
        return {
            "action": "request_incompatible",
            "reason": f"request_incompatible:{suffix}",
            "status_code": status_code,
            "detail": detail,
            "invalid_minutes": REQUEST_INCOMPATIBLE_QUARANTINE_MINUTES,
            "retry_auto": True,
        }

    return {
        "action": "observe_only",
        "reason": f"resource_error:{status_code or 'unknown'}",
        "status_code": status_code,
        "detail": detail,
        "retry_auto": False,
    }


def _is_retryable_auto_dispatch_status(status_code: int | None) -> bool:
    if status_code is None:
        return True
    if status_code in {401, 402, 403, 408, 409, 425, 429}:
        return True
    return 500 <= status_code <= 599


def _should_retry_auto_dispatch(errors: list[dict[str, Any]]) -> bool:
    if not errors:
        return False
    classification = _classify_resource_error(errors)
    if classification.get("retry_auto"):
        return True
    retryable_errors = [error for error in errors if isinstance(error, dict)]
    if not retryable_errors:
        return False
    return all(_is_retryable_auto_dispatch_status(error.get("status_code")) for error in retryable_errors)


def _is_temporary_resource_error_status(status_code: int | None) -> bool:
    if status_code is None:
        return True
    if status_code in {408, 409, 425, 429}:
        return True
    return 500 <= status_code <= 599


def _should_temporarily_quarantine_resource(errors: list[dict[str, Any]]) -> bool:
    if not errors:
        return False
    temporary_errors = [error for error in errors if isinstance(error, dict)]
    if not temporary_errors:
        return False
    return all(_is_temporary_resource_error_status(error.get("status_code")) for error in temporary_errors)


def _temporary_backoff_key(provider_name: str, model_id: str, route_id: str | None = None) -> str:
    cleaned_route_id = str(route_id or "").strip()
    if cleaned_route_id:
        return cleaned_route_id
    return _resource_id(provider_name, model_id)


def _temporary_error_reason(status_code: int | None, detail: str | None) -> str:
    suffix = ""
    raw_detail = str(detail or "").strip()
    if raw_detail:
        try:
            parsed = json.loads(raw_detail)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            code = parsed.get("code") or ((parsed.get("error") or {}).get("code") if isinstance(parsed.get("error"), dict) else None)
            error_type = parsed.get("type") or ((parsed.get("error") or {}).get("type") if isinstance(parsed.get("error"), dict) else None)
            message = parsed.get("message") or ((parsed.get("error") or {}).get("message") if isinstance(parsed.get("error"), dict) else None)
            suffix = str(code or error_type or message or "").strip()
        else:
            suffix = raw_detail[:80]
    if suffix:
        return f"temporary_upstream_error:{status_code or 'network'}:{suffix}"
    return f"temporary_upstream_error:{status_code or 'network'}"


def _extract_assistant_content(response: dict[str, Any]) -> Any:
    choices = response.get("choices", [])
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        if isinstance(message, dict):
            return message.get("content")
    return None


def _response_supports_type(response: dict[str, Any], expected_type: str) -> bool:
    expected = _normalize_response_type(expected_type)
    content = _extract_assistant_content(response)
    message = ((response.get("choices") or [{}])[0].get("message") or {}) if isinstance((response.get("choices") or [{}])[0], dict) else {}

    if expected == "json":
        return isinstance(response, dict)

    if expected == "text":
        return isinstance(content, str) and bool(content.strip())

    if expected == "audio":
        if "audio" in response or "audio_url" in response:
            return True
        if isinstance(message, dict) and ("audio" in message or "audio_url" in message):
            return True
        if isinstance(content, dict) and ("audio" in content or content.get("type") == "audio"):
            return True
        if isinstance(content, list):
            return any(isinstance(item, dict) and (item.get("type") == "audio" or "audio_url" in item) for item in content)
        return False

    if expected == "video":
        if "video" in response or "video_url" in response:
            return True
        if isinstance(message, dict) and ("video" in message or "video_url" in message):
            return True
        if isinstance(content, dict) and ("video" in content or content.get("type") == "video"):
            return True
        if isinstance(content, list):
            return any(isinstance(item, dict) and (item.get("type") == "video" or "video_url" in item) for item in content)
        return False

    return False


async def _arrest_invalid_resource(
    provider_name: str,
    model_id: str,
    *,
    reason: str,
    status_code: int | None = None,
    source: str = "system",
    invalid_minutes: int = 60,
    sync_p2p: bool = True,
    blocking: bool = True,
) -> dict:
    payload = _load_invalid_resources()
    resource_id = _resource_id(provider_name, model_id)
    resolved_route_id = _resolve_local_route_id(provider_name, model_id)
    arrested_at = datetime.now(timezone.utc).isoformat()
    invalid_until = (datetime.now(timezone.utc) + timedelta(minutes=max(1, invalid_minutes))).isoformat()
    next_item = {
        "resource_id": resource_id,
        "provider": provider_name,
        "model": model_id,
        "route_id": resolved_route_id,
        "reason": reason,
        "status_code": status_code,
        "source": source,
        "blocking": blocking,
        "arrested_at": arrested_at,
        "invalid_until": invalid_until,
    }
    data = [
        item
        for item in payload.get("data", [])
        if isinstance(item, dict)
        and not (
            not _is_blocking_invalid_entry(item)
            and item.get("resource_id") == resource_id
            and (not resolved_route_id or item.get("route_id") == resolved_route_id)
        )
    ]
    data.append(next_item)
    payload["data"] = sorted(data, key=lambda item: str(item.get("arrested_at") or ""), reverse=True)
    _save_invalid_resources(payload)
    if sync_p2p:
        await _sync_p2p_route_catalog(reason=f"invalid_resource_added:{resolved_route_id or resource_id}")
    return next_item


async def _record_resource_issue(
    provider_name: str,
    model_id: str,
    *,
    reason: str,
    status_code: int | None = None,
    source: str,
    detail: str | None = None,
    route_id: str | None = None,
) -> dict:
    payload = _load_invalid_resources()
    resource_id = _resource_id(provider_name, model_id)
    resolved_route_id = str(route_id or "").strip() or _resolve_local_route_id(provider_name, model_id)
    observed_at = datetime.now(timezone.utc).isoformat()
    next_item = {
        "resource_id": resource_id,
        "provider": provider_name,
        "model": model_id,
        "route_id": resolved_route_id,
        "reason": reason,
        "status_code": status_code,
        "source": source,
        "blocking": False,
        "arrested_at": observed_at,
        "invalid_until": None,
        "detail": " ".join(str(detail or "").split())[:500],
    }
    data = [
        item
        for item in payload.get("data", [])
        if isinstance(item, dict)
        and item.get("resource_id") != resource_id
        and (not resolved_route_id or item.get("route_id") != resolved_route_id)
    ]
    data.append(next_item)
    payload["data"] = sorted(data, key=lambda item: str(item.get("arrested_at") or ""), reverse=True)
    _save_invalid_resources(payload)
    return next_item


async def _arrest_temporary_resource(
    provider_name: str,
    model_id: str,
    *,
    reason: str,
    status_code: int | None = None,
    detail: str | None = None,
    route_id: str | None = None,
) -> dict:
    payload = _load_invalid_resources()
    resolved_route_id = str(route_id or "").strip() or _resolve_local_route_id(provider_name, model_id)
    backoff_key = _temporary_backoff_key(provider_name, model_id, resolved_route_id)
    temporary_backoff = dict((payload.get("meta") or {}).get("temporary_backoff", {}))
    previous_minutes = int(temporary_backoff.get(backoff_key) or 0)
    next_minutes = max(10, previous_minutes * 2 if previous_minutes else 10)
    temporary_backoff[backoff_key] = next_minutes
    payload.setdefault("meta", {})
    payload["meta"]["temporary_backoff"] = temporary_backoff
    item = await _arrest_invalid_resource(
        provider_name,
        model_id,
        reason=reason,
        status_code=status_code,
        source="temporary_quarantine",
        invalid_minutes=next_minutes,
        sync_p2p=False,
        blocking=True,
    )
    payload = _load_invalid_resources()
    payload.setdefault("meta", {})
    payload["meta"]["temporary_backoff"] = temporary_backoff
    _save_invalid_resources(payload)
    provider_router.logger.warning(
        "resource_temporary_quarantine provider=%s model=%s route_id=%s status_code=%s minutes=%s reason=%s detail=%s",
        provider_name,
        model_id,
        resolved_route_id,
        status_code,
        next_minutes,
        reason,
        " ".join(str(detail or "").split())[:300],
    )
    await _sync_p2p_route_catalog(reason=f"temporary_quarantine:{resolved_route_id or _resource_id(provider_name, model_id)}")
    return item


async def _sync_p2p_route_catalog(reason: str) -> dict[str, Any]:
    await _refresh_admin_cache_async()
    try:
        return await p2p_service.sync_local_route_catalog(reason=reason)
    except Exception:
        provider_router.logger.exception("p2p_route_catalog_sync_failed reason=%s", reason)
        return {"status": "error", "reason": reason}


def _invalid_resources_payload() -> dict:
    active = _active_invalid_resource_entries()
    source = _load_invalid_resources()
    return {
        "object": "list",
        "data": active,
        "meta": {
            "updated_at": (source.get("meta") or {}).get("updated_at"),
            "total": len(active),
        },
    }


def _require_runtime_admin_mutations_enabled() -> None:
    if settings.ALLOW_RUNTIME_ADMIN_MUTATIONS:
        return
    raise HTTPException(
        status_code=403,
        detail="Runtime admin mutations are disabled by env. Set ALLOW_RUNTIME_ADMIN_MUTATIONS=true to enable.",
    )


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
    quarantine = provider_state.get("quarantine", {})
    if quarantine.get("active"):
        return "quarantined"
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
    invalid_resources_payload = _invalid_resources_payload()
    invalid_index = {
        item.get("resource_id"): item
        for item in invalid_resources_payload.get("data", [])
        if isinstance(item, dict) and item.get("resource_id")
    }

    routes = cache.get("routes", [])
    if all_models is not None:
        routes = []
        for model in all_models:
            provider_name = model.get("provider")
            model_id = model.get("id")
            invalid_item = invalid_index.get(_resource_id(str(provider_name or ""), str(model_id or "")))
            if invalid_item:
                continue
            provider_state = limits_snapshot.get(provider_name, {})
            quarantine = provider_state.get("quarantine", {})
            if quarantine.get("active"):
                continue
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
                    "quarantine": quarantine,
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
                "quarantine": provider_state.get("quarantine", {}),
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
        "invalid_resources": invalid_resources_payload,
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
        if isinstance(model, dict)
        and model.get("id")
        and _is_model_available_for_current_plan(model)
        and not _is_invalid_resource(str(model.get("provider") or ""), str(model.get("id") or ""))
    ]


def _filter_models_with_live_limits(models: list[dict]) -> list[dict]:
    snapshot = rate_limit_store.get_snapshot(list(settings.get_provider_configs().keys()))
    providers_with_live_limits = {
        provider
        for provider, item in snapshot.items()
        if item.get("limits", {}).get("source") == "response_headers"
        and not item.get("quarantine", {}).get("active")
    }
    if not providers_with_live_limits:
        estimated_limits = _load_estimated_limits().get("providers", {})
        providers_with_live_limits = {
            provider
            for provider, item in estimated_limits.items()
            if isinstance(item, dict)
            and (isinstance(item.get("estimated_rpm"), int) or isinstance(item.get("estimated_rpd"), int))
            and not snapshot.get(provider, {}).get("quarantine", {}).get("active")
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


def _model_supports_chat(model: dict[str, Any]) -> bool:
    explicit = model.get("supports_chat")
    if isinstance(explicit, bool):
        return explicit
    return _category_for_model(model) == "llm"


def _model_supports_tools(model: dict[str, Any]) -> bool:
    explicit = model.get("supports_tools")
    if isinstance(explicit, bool):
        return explicit
    return False


def _known_model_catalog() -> dict[str, dict[str, Any]]:
    cache = _get_runtime_dispatcher_cache()
    combined_models = [
        *(((cache.get("validated_llm") or {}).get("data") or [])),
        *(((cache.get("block_two") or {}).get("data") or [])),
    ]
    catalog: dict[str, dict[str, Any]] = {}
    for model in combined_models:
        if not isinstance(model, dict):
            continue
        provider = str(model.get("provider") or "").strip()
        model_id = str(model.get("id") or model.get("model_id") or "").strip()
        if not provider or not model_id:
            continue
        catalog[_resource_id(provider, model_id)] = model
    return catalog


def _find_known_model(provider_name: str | None, model_id: str | None) -> dict[str, Any]:
    if not provider_name or not model_id:
        return {}
    return dict(_known_model_catalog().get(_resource_id(provider_name, model_id)) or {})


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
    # Block #2 and Block #4 are both real execution resource pools for incoming LLM requests.
    # The practical difference is observability:
    # - Block #2 contains resources with measurable live/estimated limits for admin visibility.
    # - Block #4 contains validated working LLM resources, but their limit telemetry may be absent
    #   or not suitable for the numeric Block #2 presentation.
    # Runtime dispatcher should build a union of both pools instead of using Block #4 as a fallback switch.
    cache = _get_runtime_dispatcher_cache()
    combined_models = [
        *(((cache.get("validated_llm") or {}).get("data") or [])),
        *(((cache.get("block_two") or {}).get("data") or [])),
    ]
    deduped: list[dict] = []
    seen_keys: set[str] = set()
    for model in combined_models:
        if not isinstance(model, dict):
            continue
        provider = str(model.get("provider") or "").strip()
        model_id = str(model.get("id") or "").strip()
        if not provider or not model_id:
            continue
        if _category_for_model(model) != "llm":
            continue
        if not _model_supports_chat(model):
            continue
        if rate_limit_store.is_provider_quarantined(provider):
            continue
        if _is_invalid_resource(provider, model_id):
            continue
        key = f"{provider}::{model_id}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(model)
    if deduped:
        return deduped

    routes = cache.get("routes") or []
    return [
        {
            "provider": route.get("provider"),
            "id": route.get("model_id"),
            "category": route.get("category"),
        }
        for route in routes
        if isinstance(route, dict)
        and route.get("provider")
        and route.get("model_id")
        and route.get("category") == "llm"
        and not rate_limit_store.is_provider_quarantined(str(route.get("provider") or ""))
        and not _is_invalid_resource(str(route.get("provider") or ""), str(route.get("model_id") or ""))
    ]


def _normalize_resource_affinity(value: str | None) -> str:
    cleaned = str(value or "auto").strip().lower()
    return "sticky" if cleaned == "sticky" else "auto"


def _extract_client_id(request: ChatCompletionRequest) -> str | None:
    metadata = request.metadata or {}
    if not isinstance(metadata, dict):
        return None
    for key in ("client_id", "user_id", "session_id", "chat_id", "thread_id", "sender_id"):
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _request_uses_tools(request: ChatCompletionRequest) -> bool:
    for message in request.messages:
        role = str(getattr(message, "role", "") or "").strip().lower()
        if role == "tool":
            return True
        if getattr(message, "tool_call_id", None):
            return True
        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list) and tool_calls:
            return True
    return False


def _validate_chat_payload(request: ChatCompletionRequest, known_model: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not request.messages:
        return {"reason": "messages_empty", "detail": "messages must not be empty"}

    for index, message in enumerate(request.messages):
        role = str(getattr(message, "role", "") or "").strip().lower()
        if role == "tool" and not str(getattr(message, "tool_call_id", "") or "").strip():
            return {
                "reason": "tool_call_id_missing",
                "detail": f"messages[{index}].tool_call_id is required for role='tool'",
            }

    if known_model:
        if _category_for_model(known_model) != "llm" or not _model_supports_chat(known_model):
            return {
                "reason": "model_not_chat_capable",
                "detail": "selected model is not eligible for chat/completions",
            }
        if _request_uses_tools(request) and not _model_supports_tools(known_model):
            return {
                "reason": "supports_tools_false",
                "detail": "selected model does not support tool usage in chat/completions",
            }
        max_tokens = request.max_tokens
        if isinstance(max_tokens, int) and max_tokens > 0:
            max_completion_tokens = known_model.get("max_completion_tokens")
            if isinstance(max_completion_tokens, int) and max_completion_tokens > 0 and max_tokens > max_completion_tokens:
                return {
                    "reason": "max_tokens_limit",
                    "detail": f"max_tokens={max_tokens} exceeds model limit {max_completion_tokens}",
                }

    return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _prune_auto_resource_state() -> None:
    now = _utc_now().timestamp()
    stale_usage_keys: list[str] = []
    for resource_id, usage in AUTO_RESOURCE_USAGE.items():
        recent_calls = deque(
            timestamp
            for timestamp in usage.get("recent_calls", deque())
            if now - float(timestamp) <= AUTO_RESOURCE_USAGE_WINDOW_SEC
        )
        if recent_calls:
            usage["recent_calls"] = recent_calls
        else:
            stale_usage_keys.append(resource_id)

    for resource_id in stale_usage_keys:
        AUTO_RESOURCE_USAGE.pop(resource_id, None)

    stale_affinity_keys = [
        client_id
        for client_id, binding in CLIENT_RESOURCE_AFFINITY.items()
        if now - float(binding.get("bound_at_ts", 0)) > AUTO_RESOURCE_AFFINITY_TTL_SEC
    ]
    for client_id in stale_affinity_keys:
        CLIENT_RESOURCE_AFFINITY.pop(client_id, None)


def _build_resource_id(provider_name: str, model_id: str) -> str:
    return f"{provider_name}::{model_id}"


def _resource_usage(resource_id: str) -> dict:
    return AUTO_RESOURCE_USAGE.setdefault(resource_id, {"recent_calls": deque(), "last_used_ts": 0.0})


def _mark_resource_selected(resource_id: str, provider_name: str) -> None:
    global AUTO_LAST_SELECTED_PROVIDER
    usage = _resource_usage(resource_id)
    now = _utc_now().timestamp()
    usage["last_used_ts"] = now
    recent_calls = usage.get("recent_calls")
    if not isinstance(recent_calls, deque):
        recent_calls = deque(recent_calls or [])
        usage["recent_calls"] = recent_calls
    recent_calls.append(now)
    while recent_calls and now - float(recent_calls[0]) > AUTO_RESOURCE_USAGE_WINDOW_SEC:
        recent_calls.popleft()
    AUTO_LAST_SELECTED_PROVIDER = provider_name


def _resource_recent_request_count(resource_id: str) -> int:
    usage = AUTO_RESOURCE_USAGE.get(resource_id)
    if not usage:
        return 0
    recent_calls = usage.get("recent_calls", deque())
    if not isinstance(recent_calls, deque):
        recent_calls = deque(recent_calls or [])
        usage["recent_calls"] = recent_calls
    now = _utc_now().timestamp()
    while recent_calls and now - float(recent_calls[0]) > AUTO_RESOURCE_USAGE_WINDOW_SEC:
        recent_calls.popleft()
    return len(recent_calls)


def _resource_last_used_ts(resource_id: str) -> float:
    usage = AUTO_RESOURCE_USAGE.get(resource_id) or {}
    return float(usage.get("last_used_ts") or 0.0)


def _select_round_robin_candidate(candidates: list[dict], tie_key: tuple) -> dict:
    global AUTO_RESOURCE_ROUND_ROBIN_CURSOR

    tied = [candidate for candidate in candidates if candidate["sort_key"] == tie_key]
    tied.sort(key=lambda item: item["resource_id"])
    if not tied:
        raise ValueError("Expected at least one tied candidate for round-robin selection")

    selected = tied[AUTO_RESOURCE_ROUND_ROBIN_CURSOR % len(tied)]
    AUTO_RESOURCE_ROUND_ROBIN_CURSOR = (AUTO_RESOURCE_ROUND_ROBIN_CURSOR + 1) % max(len(tied), 1)
    return selected


def _pick_auto_route(
    chat_models: list[dict],
    request: ChatCompletionRequest,
    excluded_resource_ids: set[str] | None = None,
) -> dict[str, str | bool | int | None] | None:
    _prune_auto_resource_state()
    excluded_resource_ids = excluded_resource_ids or set()

    requested_provider = request.provider
    requested_model = request.model
    resource_affinity = _normalize_resource_affinity(getattr(request, "resource_affinity", None))
    client_id = _extract_client_id(request)
    requires_tools = _request_uses_tools(request)

    provider_names = list(settings.get_provider_configs().keys())
    snapshot = rate_limit_store.get_snapshot(provider_names)
    filtered_models = [
        model
        for model in chat_models
        if _category_for_model(model) == "llm"
        and _model_supports_chat(model)
        and (not requires_tools or _model_supports_tools(model))
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
    previous_binding = CLIENT_RESOURCE_AFFINITY.get(client_id) if client_id else None
    previous_provider = previous_binding.get("provider") if isinstance(previous_binding, dict) else None

    for index, model in enumerate(filtered_models):
        provider_name = model.get("provider")
        model_id = model.get("id")
        if not provider_name or not model_id:
            continue
        item = snapshot.get(provider_name, {})
        if item.get("quarantine", {}).get("active"):
            continue
        if _is_invalid_resource(provider_name, model_id):
            continue
        source = item.get("limits", {}).get("source")
        estimated_rpm, estimated_rpd = _estimated_provider_limits(provider_name)
        has_live_limits = source == "response_headers"
        has_estimated_limits = estimated_rpm >= 0 or estimated_rpd >= 0
        if not has_live_limits and not has_estimated_limits:
            continue

        rpm_remaining = _remaining_rpm(item)
        rpd_remaining = _remaining_rpd(item)
        tpm_remaining = _remaining_tpm(item)
        effective_rpm_remaining = rpm_remaining if rpm_remaining is not None else estimated_rpm
        effective_rpd_remaining = rpd_remaining if rpd_remaining is not None else estimated_rpd
        effective_tpm_remaining = tpm_remaining if tpm_remaining is not None else -1
        has_recent_error = bool(item.get("last_error"))
        if has_recent_error:
            continue
        if effective_rpm_remaining == 0 or effective_rpd_remaining == 0 or effective_tpm_remaining == 0:
            continue

        resource_id = _build_resource_id(provider_name, model_id)
        if resource_id in excluded_resource_ids:
            continue
        recent_request_count = _resource_recent_request_count(resource_id)
        last_used_ts = _resource_last_used_ts(resource_id)
        same_provider_penalty = 0
        if previous_provider and previous_provider == provider_name:
            same_provider_penalty += 1
        if AUTO_LAST_SELECTED_PROVIDER and AUTO_LAST_SELECTED_PROVIDER == provider_name:
            same_provider_penalty += 1
        route_candidates.append(
            {
                "provider": provider_name,
                "model": model_id,
                "resource_id": resource_id,
                "source_rank": 0 if has_live_limits else 1,
                "rpm_remaining": effective_rpm_remaining,
                "rpd_remaining": effective_rpd_remaining,
                "tpm_remaining": effective_tpm_remaining,
                "models_count": models_count_by_provider.get(provider_name, 0),
                "recent_request_count": recent_request_count,
                "last_used_ts": last_used_ts,
                "same_provider_penalty": same_provider_penalty,
                "index": index,
            }
        )

    if not route_candidates:
        return None

    candidate_by_resource_id = {candidate["resource_id"]: candidate for candidate in route_candidates}
    sticky_reused = False
    if resource_affinity == "sticky" and client_id and previous_binding:
        sticky_candidate = candidate_by_resource_id.get(previous_binding.get("resource_id"))
        if sticky_candidate is not None:
            sticky_reused = True
            selected = sticky_candidate
            _mark_resource_selected(selected["resource_id"], selected["provider"])
            CLIENT_RESOURCE_AFFINITY[client_id] = {
                "resource_id": selected["resource_id"],
                "provider": selected["provider"],
                "model": selected["model"],
                "bound_at_ts": _utc_now().timestamp(),
            }
            provider_router.logger.info(
                "resource_selected policy=sticky_reuse client_id=%s resource_id=%s provider=%s model=%s eligible=%s",
                client_id,
                selected["resource_id"],
                selected["provider"],
                selected["model"],
                len(route_candidates),
            )
            return {
                "provider": selected["provider"],
                "model": selected["model"],
                "resource_id": selected["resource_id"],
                "client_id": client_id,
                "sticky_reused": sticky_reused,
                "selection_policy": "sticky_reuse",
                "eligible_resources": len(route_candidates),
            }

    for candidate in route_candidates:
        candidate["sort_key"] = (
            candidate["source_rank"],
            candidate["last_used_ts"],
            candidate["recent_request_count"],
            candidate["same_provider_penalty"],
            -candidate["rpm_remaining"],
            -candidate["tpm_remaining"],
            -candidate["rpd_remaining"],
            -candidate["models_count"],
        )

    route_candidates.sort(key=lambda item: item["sort_key"])
    selected = _select_round_robin_candidate(route_candidates, route_candidates[0]["sort_key"])
    _mark_resource_selected(selected["resource_id"], selected["provider"])
    if resource_affinity == "sticky" and client_id:
        CLIENT_RESOURCE_AFFINITY[client_id] = {
            "resource_id": selected["resource_id"],
            "provider": selected["provider"],
            "model": selected["model"],
            "bound_at_ts": _utc_now().timestamp(),
        }
    provider_router.logger.info(
        "resource_selected policy=coldest_eligible_round_robin client_id=%s resource_id=%s provider=%s model=%s eligible=%s affinity=%s",
        client_id,
        selected["resource_id"],
        selected["provider"],
        selected["model"],
        len(route_candidates),
        resource_affinity,
    )
    return {
        "provider": selected["provider"],
        "model": selected["model"],
        "resource_id": selected["resource_id"],
        "client_id": client_id,
        "sticky_reused": sticky_reused,
        "selection_policy": "coldest_eligible_round_robin",
        "eligible_resources": len(route_candidates),
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
    return HTMLResponse(
        content=ADMIN_PAGE_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/admin/p2p", response_class=HTMLResponse, tags=["Admin"])
async def p2p_admin_dashboard() -> HTMLResponse:
    return HTMLResponse(
        content=P2P_ADMIN_PAGE_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


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
    _require_runtime_admin_mutations_enabled()
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
    _require_runtime_admin_mutations_enabled()
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
    _require_runtime_admin_mutations_enabled()
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
    _require_runtime_admin_mutations_enabled()
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
    _require_runtime_admin_mutations_enabled()
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


@router.get("/admin/invalid-resources", tags=["Admin"])
@router.get("/invalid_resource", tags=["Admin"])
async def get_invalid_resources() -> dict:
    return _invalid_resources_payload()


@router.post("/admin/invalid-resources", tags=["Admin"])
@router.post("/invalid_resource", tags=["Admin"])
async def add_invalid_resource(
    provider_name: str = Query(...),
    model_id: str = Query(...),
    route_id: str | None = Query(default=None),
    reason: str = Query(default="manual_invalid_resource"),
    status_code: int | None = Query(default=None),
    invalid_days: int | None = Query(default=None),
    source: str = Query(default="manual"),
    blocking: bool = Query(default=True),
) -> dict:
    _require_runtime_admin_mutations_enabled()
    provider_name = provider_name.strip()
    model_id = model_id.strip()
    if not provider_name or not model_id:
        raise HTTPException(status_code=400, detail="provider_name and model_id are required")

    payload = _load_invalid_resources()
    resource_id = _resource_id(provider_name, model_id)
    resolved_route_id = str(route_id or "").strip() or _resolve_local_route_id(provider_name, model_id)
    arrested_at = datetime.now(timezone.utc).isoformat()
    invalid_until = None
    if invalid_days is not None and invalid_days > 0:
        invalid_until = (datetime.now(timezone.utc) + timedelta(days=invalid_days)).isoformat()

    next_item = {
        "resource_id": resource_id,
        "provider": provider_name,
        "model": model_id,
        "route_id": resolved_route_id,
        "reason": reason,
        "status_code": status_code,
        "source": source,
        "blocking": blocking,
        "arrested_at": arrested_at,
        "invalid_until": invalid_until,
    }

    data = [
        item
        for item in payload.get("data", [])
        if isinstance(item, dict)
        and item.get("resource_id") != resource_id
        and (not resolved_route_id or item.get("route_id") != resolved_route_id)
    ]
    data.append(next_item)
    payload["data"] = sorted(data, key=lambda item: str(item.get("arrested_at") or ""), reverse=True)
    saved = _save_invalid_resources(payload)
    await _sync_p2p_route_catalog(reason=f"invalid_resource_added:{resolved_route_id or resource_id}")
    return {"status": "ok", "item": next_item, "invalid_resources": saved}


@router.delete("/admin/invalid-resources", tags=["Admin"])
@router.delete("/invalid_resource", tags=["Admin"])
async def delete_invalid_resource(
    resource_id: str | None = Query(default=None),
    route_id: str | None = Query(default=None),
    provider_name: str | None = Query(default=None),
    model_id: str | None = Query(default=None),
) -> dict:
    _require_runtime_admin_mutations_enabled()
    resolved_resource_id = (resource_id or "").strip()
    resolved_route_id = (route_id or "").strip()
    if not resolved_resource_id:
        if not provider_name or not model_id:
            if not resolved_route_id:
                raise HTTPException(status_code=400, detail="resource_id, route_id, or provider_name + model_id are required")
        if provider_name and model_id:
            resolved_resource_id = _resource_id(provider_name, model_id)
            resolved_route_id = resolved_route_id or _resolve_local_route_id(provider_name, model_id)

    payload = _load_invalid_resources()
    existing = payload.get("data", [])
    next_data = [
        item
        for item in existing
        if not (
            isinstance(item, dict)
            and (
                item.get("resource_id") == resolved_resource_id
                or (resolved_route_id and item.get("route_id") == resolved_route_id)
            )
        )
    ]
    if len(next_data) == len(existing):
        raise HTTPException(status_code=404, detail="Invalid resource not found")
    payload["data"] = next_data
    saved = _save_invalid_resources(payload)
    await _sync_p2p_route_catalog(reason=f"invalid_resource_removed:{resolved_route_id or resolved_resource_id}")
    return {
        "status": "ok",
        "removed_resource_id": resolved_resource_id,
        "removed_route_id": resolved_route_id or None,
        "invalid_resources": saved,
    }


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
    _require_runtime_admin_mutations_enabled()
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
        payload = await provider_router.get_models()
        payload["data"] = [
            model
            for model in payload.get("data", [])
            if isinstance(model, dict) and not _is_invalid_resource(str(model.get("provider") or ""), str(model.get("id") or ""))
        ]
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        raise HTTPException(status_code=502, detail=exc.errors)


@router.post("/v1/chat/completions", tags=["Chat"])
async def create_chat_completion(request: ChatCompletionRequest) -> dict:
    requested_provider_auto = _is_auto_value(request.provider)
    requested_model_auto = _is_auto_value(request.model)
    expected_response_type = _normalize_response_type(getattr(request, "response_type", None))
    candidate_models = _runtime_chat_models() if (requested_provider_auto or requested_model_auto) else []
    excluded_resource_ids: set[str] = set()
    last_selected_route: dict[str, str | bool | int | None] | None = None
    mismatch_errors: list[dict[str, Any]] = []
    dispatch_retry_errors: list[dict[str, Any]] = []

    while True:
        effective_request = request
        selected_route: dict[str, str | bool | int | None] | None = None

        if requested_provider_auto or requested_model_auto:
            selected_route = _pick_auto_route(candidate_models, request, excluded_resource_ids=excluded_resource_ids)
            last_selected_route = selected_route
            if not selected_route:
                detail: Any = "No available provider/model route for requested auto selection"
                if mismatch_errors:
                    detail = {
                        "error": "response_type_mismatch_exhausted",
                        "expected_response_type": expected_response_type,
                        "attempts": mismatch_errors,
                    }
                elif dispatch_retry_errors:
                    detail = {
                        "error": "auto_route_exhausted",
                        "attempts": dispatch_retry_errors,
                        "last_selected_route": last_selected_route,
                    }
                raise HTTPException(status_code=404 if not (mismatch_errors or dispatch_retry_errors) else 502, detail=detail)

            update_payload = {}
            if requested_provider_auto:
                update_payload["provider"] = str(selected_route["provider"])
            if requested_model_auto:
                update_payload["model"] = str(selected_route["model"])
            effective_request = request.model_copy(update=update_payload)

        known_model = _find_known_model(effective_request.provider, effective_request.model)
        payload_error = _validate_chat_payload(effective_request, known_model)
        if payload_error:
            provider_name = str(effective_request.provider or "")
            model_id = str(effective_request.model or "")
            route_id = _resolve_local_route_id(provider_name, model_id)
            if provider_name and model_id:
                await _arrest_invalid_resource(
                    provider_name,
                    model_id,
                    reason=f"request_incompatible:{payload_error['reason']}",
                    source="request_preflight",
                    invalid_minutes=REQUEST_INCOMPATIBLE_QUARANTINE_MINUTES,
                    status_code=400,
                )
            await _refresh_admin_cache_async()
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "request_incompatible",
                    "reason": payload_error["reason"],
                    "detail": payload_error["detail"],
                    "provider": provider_name,
                    "model": model_id,
                    "route_id": route_id,
                },
            )

        if _is_invalid_resource(effective_request.provider, effective_request.model):
            invalid_item = _find_invalid_resource(effective_request.provider, effective_request.model)
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "invalid_resource",
                    "provider": effective_request.provider,
                    "model": effective_request.model,
                    "route_id": invalid_item.get("route_id"),
                    "reason": invalid_item.get("reason"),
                    "status_code": invalid_item.get("status_code"),
                    "arrested_at": invalid_item.get("arrested_at"),
                    "invalid_until": invalid_item.get("invalid_until"),
                },
            )

        try:
            response = await provider_router.race_chat_completion(effective_request)
        except ValueError as exc:
            await _refresh_admin_cache_async()
            raise HTTPException(status_code=400, detail=str(exc))
        except UpstreamProvidersExhausted as exc:
            retryable_errors = [error for error in exc.errors if isinstance(error, dict)]
            classification = _classify_resource_error(retryable_errors)
            if effective_request.provider and effective_request.model:
                provider_name = str(effective_request.provider)
                model_id = str(effective_request.model)
                route_id = _resolve_local_route_id(provider_name, model_id)
                if classification["action"] == "temporary_quarantine":
                    await _arrest_temporary_resource(
                        provider_name,
                        model_id,
                        reason=str(classification["reason"]),
                        status_code=classification.get("status_code"),
                        detail=str(classification.get("detail") or ""),
                        route_id=route_id,
                    )
                elif classification["action"] in {"invalid_resource", "request_incompatible"}:
                    await _arrest_invalid_resource(
                        provider_name,
                        model_id,
                        reason=str(classification["reason"]),
                        status_code=classification.get("status_code"),
                        source=classification["action"],
                        invalid_minutes=int(classification.get("invalid_minutes") or REQUEST_INCOMPATIBLE_QUARANTINE_MINUTES),
                    )
                else:
                    first_non_temporary_error = retryable_errors[0] if retryable_errors else {}
                    await _record_resource_issue(
                        provider_name,
                        model_id,
                        reason=str(classification["reason"]),
                        status_code=first_non_temporary_error.get("status_code"),
                        source="error_observation",
                        detail=str(first_non_temporary_error.get("detail") or ""),
                        route_id=route_id,
                    )
                    provider_router.logger.warning(
                        "resource_not_quarantined provider=%s model=%s route_id=%s status_code=%s reason=non_temporary_error detail=%s",
                        effective_request.provider,
                        effective_request.model,
                        route_id,
                        first_non_temporary_error.get("status_code"),
                        " ".join(str(first_non_temporary_error.get("detail") or "").split())[:300],
                    )
            if (requested_provider_auto or requested_model_auto) and selected_route and selected_route.get("resource_id"):
                if _should_retry_auto_dispatch(retryable_errors):
                    failed_resource_id = str(selected_route["resource_id"])
                    excluded_resource_ids.add(failed_resource_id)
                    first_error = retryable_errors[0] if retryable_errors else {}
                    provider_router.logger.warning(
                        "resource_problem_detected provider=%s model=%s resource_id=%s status_code=%s detail=%s action=retry_next_resource",
                        selected_route.get("provider"),
                        selected_route.get("model"),
                        failed_resource_id,
                        first_error.get("status_code"),
                        " ".join(str(first_error.get("detail") or "").split())[:300],
                    )
                    provider_router.logger.warning(
                        "auto_route_retry provider=%s model=%s resource_id=%s reason=upstream_error errors=%s",
                        selected_route.get("provider"),
                        selected_route.get("model"),
                        failed_resource_id,
                        retryable_errors,
                    )
                    dispatch_retry_errors.extend(retryable_errors)
                    continue
            await _refresh_admin_cache_async()
            if dispatch_retry_errors:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "auto_route_exhausted",
                        "attempts": dispatch_retry_errors + list(exc.errors),
                        "last_selected_route": last_selected_route,
                    },
                )
            raise HTTPException(status_code=502, detail=exc.errors)

        response.setdefault("_proxy", {})
        response["provider"] = response["_proxy"].get("selected_provider") or effective_request.provider
        response["model"] = response["_proxy"].get("selected_model") or effective_request.model
        response["_proxy"]["response_type"] = expected_response_type

        if not _response_supports_type(response, expected_response_type):
            provider_name = str(response["provider"] or effective_request.provider or "")
            model_id = str(response["model"] or effective_request.model or "")
            route_id = _resolve_local_route_id(provider_name, model_id)
            mismatch_reason = f"response_type_mismatch:{expected_response_type}"
            provider_router.logger.warning(
                "response_type_mismatch expected=%s provider=%s model=%s route_id=%s auto=%s",
                expected_response_type,
                provider_name,
                model_id,
                route_id,
                requested_provider_auto or requested_model_auto,
            )
            if requested_provider_auto or requested_model_auto:
                await _arrest_invalid_resource(
                    provider_name,
                    model_id,
                    reason=mismatch_reason,
                    source="response_type_validation",
                    invalid_minutes=60,
                )
                if selected_route and selected_route.get("resource_id"):
                    excluded_resource_ids.add(str(selected_route["resource_id"]))
                mismatch_errors.append(
                    {
                        "provider": provider_name,
                        "model": model_id,
                        "route_id": route_id,
                        "expected_response_type": expected_response_type,
                        "reason": mismatch_reason,
                    }
                )
                continue

            await _refresh_admin_cache_async()
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "response_type_mismatch",
                    "expected_response_type": expected_response_type,
                    "provider": provider_name,
                    "model": model_id,
                    "route_id": route_id,
                },
            )

        if requested_provider_auto or requested_model_auto:
            response["_proxy"]["requested_provider"] = request.provider
            response["_proxy"]["requested_model"] = request.model
            response["_proxy"]["auto_selected_provider"] = effective_request.provider
            response["_proxy"]["auto_selected_model"] = effective_request.model
            response["_proxy"]["resource_affinity"] = _normalize_resource_affinity(request.resource_affinity)
            response["_proxy"]["selected_resource_id"] = (selected_route or {}).get("resource_id")
            response["_proxy"]["sticky_reused"] = bool((selected_route or {}).get("sticky_reused"))
            response["_proxy"]["client_id"] = (selected_route or {}).get("client_id")
            response["_proxy"]["eligible_resources"] = (selected_route or {}).get("eligible_resources")
            response["_proxy"]["selected_policy"] = (selected_route or {}).get("selection_policy") or "coldest_eligible_round_robin"
            response["_proxy"]["response_type_retry_count"] = len(mismatch_errors)
        await _refresh_admin_cache_async()
        return response


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


@router.post("/v1/audio/transcriptions", tags=["Audio"])
async def create_audio_transcription(
    file: UploadFile | None = File(default=None),
    model: str | None = Form(default=None),
    provider: str | None = Form(default=None),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    response_format: str | None = Form(default=None),
    temperature: str | None = Form(default=None),
) -> dict:
    started_at = time.perf_counter()
    request_payload = await build_audio_transcription_request(
        file=file,
        model=model,
        provider=provider,
        language=language,
        prompt=prompt,
        response_format=response_format,
        temperature=temperature,
    )

    provider_router.logger.info(
        "audio_transcription_started provider=%s model=%s file_name=%s file_size_bytes=%s",
        request_payload.provider or "auto",
        request_payload.model,
        request_payload.filename,
        request_payload.size_bytes,
    )

    try:
        upstream_response = await provider_router.create_audio_transcription(request_payload)
        raw_upstream_response = (
            {key: value for key, value in upstream_response.items() if key != "_proxy"}
            if isinstance(upstream_response, dict)
            else upstream_response
        )
        normalized_response = normalize_audio_transcription_response(raw_upstream_response)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        selected_provider = (
            upstream_response.get("_proxy", {}).get("selected_provider")
            if isinstance(upstream_response, dict)
            else None
        )
        provider_router.logger.info(
            "audio_transcription_finished status=success provider=%s model=%s file_size_bytes=%s duration_ms=%s",
            selected_provider or request_payload.provider or "auto",
            request_payload.model,
            request_payload.size_bytes,
            duration_ms,
        )
        await _refresh_admin_cache_async()
        return normalized_response
    except HTTPException:
        raise
    except ValueError as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        provider_router.logger.warning(
            "audio_transcription_finished status=error provider=%s model=%s file_size_bytes=%s duration_ms=%s detail=%s",
            request_payload.provider or "auto",
            request_payload.model,
            request_payload.size_bytes,
            duration_ms,
            str(exc),
        )
        await _refresh_admin_cache_async()
        raise HTTPException(status_code=502, detail=str(exc))
    except UpstreamProvidersExhausted as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        provider_router.logger.warning(
            "audio_transcription_finished status=error provider=%s model=%s file_size_bytes=%s duration_ms=%s detail=%s",
            request_payload.provider or "auto",
            request_payload.model,
            request_payload.size_bytes,
            duration_ms,
            exc.errors,
        )
        await _refresh_admin_cache_async()
        first_error = exc.errors[0] if exc.errors else {}
        provider_name = str(first_error.get("provider") or request_payload.provider or "")
        model_id = request_payload.model
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_audio_transcription_failed",
                "provider": provider_name or None,
                "model": model_id,
                "resource": f"{provider_name}::{model_id}" if provider_name else model_id,
                "status_code": first_error.get("status_code"),
                "upstream_error": first_error.get("detail"),
                "attempts": exc.errors,
            },
        )
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        provider_router.logger.exception(
            "audio_transcription_finished status=error provider=%s model=%s file_size_bytes=%s duration_ms=%s error=%s",
            request_payload.provider or "auto",
            request_payload.model,
            request_payload.size_bytes,
            duration_ms,
            str(exc),
        )
        await _refresh_admin_cache_async()
        raise HTTPException(status_code=500, detail="Internal proxy error during audio transcription")

