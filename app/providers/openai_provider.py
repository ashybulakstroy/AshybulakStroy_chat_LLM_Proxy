import logging
import time

import httpx

from app.config import settings
from app.providers.base import ProviderBase
from app.rate_limits import rate_limit_store
from app.schemas import ChatCompletionRequest, EmbeddingRequest


class OpenAIProvider(ProviderBase):
    def __init__(self, provider_name: str, api_key: str, api_base: str = "https://api.openai.com/v1"):
        self.provider_name = provider_name
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.logger = logging.getLogger("ashybulak.proxy")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def request(self, method: str, endpoint: str, json: dict) -> dict:
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        started_at = time.perf_counter()

        if settings.ENABLE_PROVIDER_LOG:
            self.logger.info(
                "provider_request_started provider=%s method=%s endpoint=%s",
                self.provider_name,
                method,
                endpoint,
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                request_kwargs = {"headers": self.headers}
                if method.upper() != "GET":
                    request_kwargs["json"] = json
                response = await client.request(method, url, **request_kwargs)
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                if settings.ENABLE_PROVIDER_LOG:
                    self.logger.info(
                        "provider_request_finished provider=%s method=%s endpoint=%s status_code=%s duration_ms=%s",
                        self.provider_name,
                        method,
                        endpoint,
                        response.status_code,
                        duration_ms,
                    )
                rate_limit_store.update_from_response(
                    provider=self.provider_name,
                    headers=dict(response.headers),
                    status_code=response.status_code,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError:
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                quarantine_activated = rate_limit_store.record_error(
                    provider=self.provider_name,
                    status_code=response.status_code,
                    detail=response.text,
                )
                if quarantine_activated:
                    try:
                        from app.p2p_service import p2p_service

                        await p2p_service.sync_local_route_catalog(reason=f"provider_quarantine:{self.provider_name}")
                    except Exception:
                        self.logger.exception(
                            "provider_quarantine_p2p_sync_failed provider=%s status_code=%s",
                            self.provider_name,
                            response.status_code,
                        )
                if settings.ENABLE_PROVIDER_LOG:
                    self.logger.exception(
                        "provider_request_http_error provider=%s method=%s endpoint=%s status_code=%s duration_ms=%s response_body=%s",
                        self.provider_name,
                        method,
                        endpoint,
                        response.status_code,
                        duration_ms,
                        response.text,
                    )
                raise
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                rate_limit_store.record_error(
                    provider=self.provider_name,
                    status_code=None,
                    detail=str(exc),
                )
                if settings.ENABLE_PROVIDER_LOG:
                    self.logger.exception(
                        "provider_request_failed provider=%s method=%s endpoint=%s duration_ms=%s error=%s",
                        self.provider_name,
                        method,
                        endpoint,
                        duration_ms,
                        str(exc),
                    )
                raise

    async def get_models(self) -> dict:
        return await self.request("GET", "/models", {})

    async def create_chat_completion(self, request: ChatCompletionRequest) -> dict:
        payload = {
            "model": request.model,
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        return await self.request("POST", "/chat/completions", payload)

    async def create_embeddings(self, request: EmbeddingRequest) -> dict:
        payload = {
            "model": request.model,
            "input": request.input,
        }
        return await self.request("POST", "/embeddings", payload)
