import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

import httpx

from app.config import ProviderConfig, settings
from app.providers.openai_provider import OpenAIProvider
from app.rate_limits import DEFAULT_FALLBACK_RPM, rate_limit_store


class UpstreamProvidersExhausted(Exception):
    def __init__(self, errors: list[dict[str, Any]]):
        super().__init__("All upstream providers failed")
        self.errors = errors


class ProviderRequestError(Exception):
    def __init__(self, provider: str, status_code: int | None, detail: str):
        super().__init__(detail)
        self.provider = provider
        self.status_code = status_code
        self.detail = detail


class ProviderRouter:
    def __init__(self) -> None:
        self.provider_configs = settings.get_provider_configs()
        self.logger = logging.getLogger("ashybulak.proxy")
        self.proxy_mode = settings.PROXY_MODE if settings.PROXY_MODE in ("FAST", "LOAD_BALANCE") else "LOAD_BALANCE"
        self._active_proxy_sessions: dict[str, dict[str, Any]] = {}
        self._active_proxy_sessions_lock = asyncio.Lock()
        self._completed_proxy_sessions: list[dict[str, Any]] = []
        self._completed_proxy_sessions_lock = asyncio.Lock()
        self._completed_sessions_limit = 100

    def list_available_providers(self) -> list[str]:
        return list(self.provider_configs.keys())

    def get_provider(self, provider_name: str) -> OpenAIProvider:
        provider_config = self.provider_configs[provider_name]
        return self._build_provider(provider_config)

    def get_target_providers(self, requested_provider: str | None = None) -> list[str]:
        if not self.provider_configs:
            raise ValueError("No providers are configured")
        if requested_provider:
            if requested_provider not in self.provider_configs:
                raise ValueError(f"Provider '{requested_provider}' is not configured")
            return [requested_provider]
        return self.list_available_providers()

    def get_proxy_mode(self) -> str:
        return self.proxy_mode

    def set_proxy_mode(self, mode: str) -> str:
        cleaned = str(mode or "").strip().upper()
        if cleaned not in ("FAST", "LOAD_BALANCE"):
            raise ValueError("Proxy mode must be FAST or LOAD_BALANCE")
        self.proxy_mode = cleaned
        return self.proxy_mode

    async def get_completed_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._completed_proxy_sessions_lock:
            return list(self._completed_proxy_sessions[-limit:][::-1])

    async def get_dispatcher_status(self) -> dict[str, Any]:
        return {
            "proxy_mode": self.proxy_mode,
            "active_sessions": await self._get_active_sessions(),
            "completed_sessions": await self.get_completed_sessions(10),
        }

    async def race_chat_completion(self, request: Any) -> dict[str, Any]:
        return await self._dispatch_providers(
            requested_provider=getattr(request, "provider", None),
            model=getattr(request, "model", None),
            operation=lambda provider: provider.create_chat_completion(request),
        )

    async def race_embeddings(self, request: Any) -> dict[str, Any]:
        return await self._dispatch_providers(
            requested_provider=getattr(request, "provider", None),
            model=getattr(request, "model", None),
            operation=lambda provider: provider.create_embeddings(request),
        )

    async def get_models(self, requested_provider: str | None = None) -> dict[str, Any]:
        target_providers = self.get_target_providers(requested_provider)
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for provider_name in target_providers:
            provider = self.get_provider(provider_name)
            try:
                response = await provider.get_models()
                models = response.get("data", [])
                for model in models:
                    if isinstance(model, dict):
                        enriched = dict(model)
                        enriched["provider"] = provider_name
                        results.append(enriched)
            except httpx.HTTPStatusError as exc:
                errors.append(
                    {
                        "provider": provider_name,
                        "status_code": exc.response.status_code,
                        "detail": exc.response.text,
                    }
                )
            except Exception as exc:
                errors.append(
                    {
                        "provider": provider_name,
                        "status_code": None,
                        "detail": str(exc),
                    }
                )

        if results:
            return {"object": "list", "data": results, "errors": errors}
        raise UpstreamProvidersExhausted(errors)

    async def probe_provider_limits(self) -> dict[str, Any]:
        target_providers = self.get_target_providers()
        successful: list[str] = []
        failed: list[dict[str, Any]] = []

        async def probe(provider_name: str) -> tuple[str, str | None, dict[str, Any] | None]:
            provider = self.get_provider(provider_name)
            try:
                await provider.get_models()
                return provider_name, None, None
            except httpx.HTTPStatusError as exc:
                return provider_name, "error", {
                    "provider": provider_name,
                    "status_code": exc.response.status_code,
                    "detail": exc.response.text,
                }
            except Exception as exc:
                return provider_name, "error", {
                    "provider": provider_name,
                    "status_code": None,
                    "detail": str(exc),
                }

        results = await asyncio.gather(*(probe(provider_name) for provider_name in target_providers))

        for provider_name, status, error in results:
            if status is None:
                successful.append(provider_name)
            elif error is not None:
                failed.append(error)

        return {
            "successful": successful,
            "failed": failed,
        }

    def _build_provider(self, provider_config: ProviderConfig) -> OpenAIProvider:
        return OpenAIProvider(
            provider_name=provider_config.name,
            api_key=provider_config.api_key,
            api_base=provider_config.api_base,
        )

    async def _register_active_session(self, provider_name: str, model: str | None) -> str:
        session_id = uuid4().hex
        async with self._active_proxy_sessions_lock:
            self._active_proxy_sessions[session_id] = {
                "provider": provider_name,
                "model": model,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        return session_id

    async def _unregister_active_session(self, session_id: str) -> None:
        async with self._active_proxy_sessions_lock:
            self._active_proxy_sessions.pop(session_id, None)

    async def _get_active_sessions(self) -> list[dict[str, Any]]:
        async with self._active_proxy_sessions_lock:
            return list(self._active_proxy_sessions.values())

    async def _record_completed_session(self, session: dict[str, Any]) -> None:
        async with self._completed_proxy_sessions_lock:
            self._completed_proxy_sessions.append(session)
            if len(self._completed_proxy_sessions) > self._completed_sessions_limit:
                self._completed_proxy_sessions.pop(0)
        self._log_completed_session(session)

    def _log_completed_session(self, session: dict[str, Any]) -> None:
        status = session.get("status") or "unknown"
        provider = session.get("provider") or "unknown"
        model = session.get("model") or "unknown"
        mode = session.get("mode") or self.proxy_mode
        status_code = session.get("status_code")
        detail = (session.get("detail") or "").strip()
        safe_detail = " ".join(detail.split())[:400] if detail else ""

        if status == "success":
            self.logger.info(
                "proxy_session_completed status=success mode=%s provider=%s model=%s status_code=%s started_at=%s finished_at=%s",
                mode,
                provider,
                model,
                status_code,
                session.get("started_at"),
                session.get("finished_at"),
            )
            return

        self.logger.warning(
            "proxy_session_completed status=%s mode=%s provider=%s model=%s status_code=%s detail=%s started_at=%s finished_at=%s",
            status,
            mode,
            provider,
            model,
            status_code,
            safe_detail,
            session.get("started_at"),
            session.get("finished_at"),
        )

    def _sort_providers(self, provider_names: list[str]) -> list[str]:
        def provider_key(provider_name: str) -> tuple[int, int, int, str]:
            state = rate_limit_store._state.get(provider_name)
            has_error = bool(state and state.last_error)
            rpm_limit = state.requests_minute.limit if state and state.requests_minute.limit is not None else DEFAULT_FALLBACK_RPM
            rpm_remaining = state.requests_minute.remaining if state and state.requests_minute.remaining is not None else rpm_limit
            no_resources = rpm_remaining == 0
            last_observed_at = state.last_observed_at if state and state.last_observed_at else "0000-00-00T00:00:00+00:00"
            return (
                1 if has_error else 0,
                1 if no_resources else 0,
                -rpm_limit,
                last_observed_at,
            )

        return sorted(provider_names, key=provider_key)

    async def _execute_provider_operation(
        self,
        provider_name: str,
        model: str | None,
        operation: Callable[[OpenAIProvider], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        session_id = await self._register_active_session(provider_name, model)
        started_at = datetime.now(timezone.utc).isoformat()
        provider = self.get_provider(provider_name)
        try:
            response = await operation(provider)
            return {
                "provider": provider_name,
                "model": model,
                "success": True,
                "response": response,
                "status_code": None,
                "detail": None,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            status_code = None
            detail = str(exc)
            if isinstance(exc, httpx.HTTPStatusError):
                status_code = exc.response.status_code
                detail = exc.response.text
            return {
                "provider": provider_name,
                "model": model,
                "success": False,
                "response": None,
                "status_code": status_code,
                "detail": detail,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            await self._unregister_active_session(session_id)

    async def _dispatch_providers(
        self,
        requested_provider: str | None,
        model: str | None,
        operation: Callable[[OpenAIProvider], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        if self.proxy_mode == "FAST":
            return await self._parallel_race_providers(requested_provider, model, operation)
        return await self._sequential_race_providers(requested_provider, model, operation)

    async def _parallel_race_providers(
        self,
        requested_provider: str | None,
        model: str | None,
        operation: Callable[[OpenAIProvider], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        target_providers = self.get_target_providers(requested_provider)
        ordered_providers = self._sort_providers(target_providers)
        errors: list[dict[str, Any]] = []
        attempted: list[dict[str, Any]] = []
        tasks = [
            asyncio.create_task(self._execute_provider_operation(provider_name, model, operation))
            for provider_name in ordered_providers
        ]

        try:
            for task in asyncio.as_completed(tasks):
                result = await task
                if result["success"]:
                    await self._record_completed_session(
                        {
                            "session_id": uuid4().hex,
                            "provider": result["provider"],
                            "model": result["model"],
                            "status": "success",
                            "status_code": result["status_code"],
                            "detail": result["detail"],
                            "started_at": result["started_at"],
                            "finished_at": result["finished_at"],
                            "mode": self.proxy_mode,
                        }
                    )
                    response = result["response"]
                    response.setdefault("_proxy", {})
                    response["_proxy"]["selected_provider"] = result["provider"]
                    response["_proxy"]["selected_model"] = result["model"]
                    response["_proxy"]["active_sessions"] = await self._get_active_sessions()
                    response["_proxy"]["attempted_providers"] = attempted + [
                        {"provider": result["provider"], "status": "success"}
                    ]
                    if settings.ENABLE_PROVIDER_LOG:
                        self.logger.info("provider_selected policy=fast provider=%s", result["provider"])
                    for pending in tasks:
                        if not pending.done():
                            pending.cancel()
                    await asyncio.gather(*[t for t in tasks if not t.done()], return_exceptions=True)
                    return response

                attempted.append(
                    {
                        "provider": result["provider"],
                        "status": "error",
                        "status_code": result["status_code"],
                        "detail": result["detail"],
                    }
                )
                errors.append(
                    {
                        "provider": result["provider"],
                        "status_code": result["status_code"],
                        "detail": result["detail"],
                    }
                )
                await self._record_completed_session(
                    {
                        "session_id": uuid4().hex,
                        "provider": result["provider"],
                        "model": result["model"],
                        "status": "error",
                        "status_code": result["status_code"],
                        "detail": result["detail"],
                        "started_at": result["started_at"],
                        "finished_at": result["finished_at"],
                        "mode": self.proxy_mode,
                    }
                )

            raise UpstreamProvidersExhausted(errors)
        finally:
            for pending in tasks:
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(*[t for t in tasks if not t.done()], return_exceptions=True)

    async def _sequential_race_providers(
        self,
        requested_provider: str | None,
        model: str | None,
        operation: Callable[[OpenAIProvider], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        target_providers = self.get_target_providers(requested_provider)
        ordered_providers = self._sort_providers(target_providers)
        errors: list[dict[str, Any]] = []
        attempted: list[dict[str, Any]] = []

        for provider_name in ordered_providers:
            result = await self._execute_provider_operation(provider_name, model, operation)
            if result["success"]:
                await self._record_completed_session(
                    {
                        "session_id": uuid4().hex,
                        "provider": result["provider"],
                        "model": result["model"],
                        "status": "success",
                        "status_code": result["status_code"],
                        "detail": result["detail"],
                        "started_at": result["started_at"],
                        "finished_at": result["finished_at"],
                        "mode": self.proxy_mode,
                    }
                )
                response = result["response"]
                response.setdefault("_proxy", {})
                response["_proxy"]["selected_provider"] = provider_name
                response["_proxy"]["selected_model"] = result["model"]
                response["_proxy"]["active_sessions"] = await self._get_active_sessions()
                response["_proxy"]["attempted_providers"] = attempted + [
                    {"provider": provider_name, "status": "success"}
                ]
                if settings.ENABLE_PROVIDER_LOG:
                    self.logger.info("provider_selected policy=load_balance provider=%s", provider_name)
                return response

            attempted.append(
                {
                    "provider": provider_name,
                    "status": "error",
                    "status_code": result["status_code"],
                    "detail": result["detail"],
                }
            )
            errors.append(
                {
                    "provider": provider_name,
                    "status_code": result["status_code"],
                    "detail": result["detail"],
                }
            )
            await self._record_completed_session(
                {
                    "session_id": uuid4().hex,
                    "provider": result["provider"],
                    "model": result["model"],
                    "status": "error",
                    "status_code": result["status_code"],
                    "detail": result["detail"],
                    "started_at": result["started_at"],
                    "finished_at": result["finished_at"],
                    "mode": self.proxy_mode,
                }
            )

        raise UpstreamProvidersExhausted(errors)
