import logging

from fastapi import FastAPI

from app.config import settings
from app.rate_limits import rate_limit_store
from app.router_service import ProviderRouter
from app.routes import _refresh_admin_cache, router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="AshybulakStroy AI HUB",
    description="Lightweight OpenAI-compatible proxy gateway for LLM requests.",
    version="0.1.0",
)

app.include_router(router)
provider_router = ProviderRouter()
logger = logging.getLogger("ashybulak.proxy")


@app.on_event("startup")
async def startup_probe_limits() -> None:
    logger.info(
        "server_started host=0.0.0.0 port=%s health_url=http://127.0.0.1:%s/health",
        settings.PORT,
        settings.PORT,
    )
    provider_names = list(settings.get_provider_configs().keys())
    rate_limit_store.load_snapshot(provider_names)
    _refresh_admin_cache()
    try:
        summary = await provider_router.probe_provider_limits()
        rate_limit_store.record_probe_summary(
            successful=summary["successful"],
            failed=summary["failed"],
        )
        _refresh_admin_cache()
    except ValueError:
        rate_limit_store.record_probe_summary(successful=[], failed=[])
        _refresh_admin_cache()


@app.get("/health", tags=["Health"])
async def health() -> dict:
    provider_names = list(settings.get_provider_configs().keys())
    payload = rate_limit_store.get_health_payload(provider_names)
    return {
        "status": "ok",
        "providers": provider_names,
        "providers_count": payload["providers_count"],
        "startup_probe": payload["startup_probe"],
        "limits": payload["limits"],
    }
