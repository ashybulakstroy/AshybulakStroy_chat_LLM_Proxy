import asyncio
import logging

from fastapi import FastAPI

from app.config import settings
from app.p2p_service import p2p_service
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


async def _run_startup_probe_background() -> None:
    try:
        summary = await provider_router.probe_provider_limits()
        rate_limit_store.record_probe_summary(
            successful=summary["successful"],
            failed=summary["failed"],
        )
        _refresh_admin_cache()
        logger.info(
            "startup_probe_completed successful=%s failed=%s",
            len(summary["successful"]),
            len(summary["failed"]),
        )
    except ValueError:
        rate_limit_store.record_probe_summary(successful=[], failed=[])
        _refresh_admin_cache()
        logger.warning("startup_probe_skipped no providers configured")
    except Exception as exc:
        logger.exception("startup_probe_failed error=%s", str(exc))


async def _run_p2p_recovery_background() -> None:
    try:
        result = await p2p_service.request_peers_reregister()
        logger.info(
            "p2p_recovery_completed requested=%s failed=%s",
            result.get("requested", 0),
            result.get("failed", 0),
        )
    except Exception as exc:
        logger.exception("p2p_recovery_failed error=%s", str(exc))


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
    snapshot_result = p2p_service.load_network_snapshot()
    logger.info(
        "p2p_network_snapshot_bootstrap status=%s loaded_peers=%s path=%s",
        snapshot_result.get("status"),
        snapshot_result.get("loaded_peers", 0),
        snapshot_result.get("path"),
    )
    asyncio.create_task(_run_startup_probe_background())
    asyncio.create_task(_run_p2p_recovery_background())


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
