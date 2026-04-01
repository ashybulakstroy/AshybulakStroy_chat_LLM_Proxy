import asyncio
import logging
from typing import Any, Awaitable, Callable

import httpx

from app.config import ProviderConfig, settings
from app.providers.openai_provider import OpenAIProvider


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

    async def race_chat_completion(self, request: Any) -> dict[str, Any]:
        return await self._race_providers(
            requested_provider=getattr(request, "provider", None),
            operation=lambda provider: provider.create_chat_completion(request),
        )

    async def race_embeddings(self, request: Any) -> dict[str, Any]:
        return await self._race_providers(
            requested_provider=getattr(request, "provider", None),
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

    async def _race_providers(
        self,
        requested_provider: str | None,
        operation: Callable[[OpenAIProvider], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        target_providers = self.get_target_providers(requested_provider)
        errors: list[dict[str, Any]] = []

        async def invoke(provider_name: str) -> tuple[str, dict[str, Any]]:
            provider = self.get_provider(provider_name)
            try:
                response = await operation(provider)
                return provider_name, response
            except httpx.HTTPStatusError as exc:
                raise ProviderRequestError(
                    provider=provider_name,
                    status_code=exc.response.status_code,
                    detail=exc.response.text,
                ) from exc
            except Exception as exc:
                raise ProviderRequestError(
                    provider=provider_name,
                    status_code=None,
                    detail=str(exc),
                ) from exc

        tasks = [asyncio.create_task(invoke(provider_name)) for provider_name in target_providers]

        try:
            for completed_task in asyncio.as_completed(tasks):
                try:
                    winner_name, response = await completed_task
                    response.setdefault("_proxy", {})
                    response["_proxy"]["selected_provider"] = winner_name
                    if settings.ENABLE_PROVIDER_LOG:
                        self.logger.info("provider_selected policy=fastest provider=%s", winner_name)

                    for task in tasks:
                        if task is not completed_task and not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    return response
                except ProviderRequestError as exc:
                    errors.append(
                        {
                            "provider": exc.provider,
                            "status_code": exc.status_code,
                            "detail": exc.detail,
                        }
                    )
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        raise UpstreamProvidersExhausted(errors)
