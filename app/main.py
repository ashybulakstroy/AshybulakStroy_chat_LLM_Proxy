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

STARTUP_BANNER = r"""
================================================================================
================================================================================

   ##       ##       ###      ###         ######     #####     ###### 
   ##       ##       ####    ####         ##   ##   ##   ##    ##   ##
   ##       ##       ## ##  ## ##         ##   ##        ##    ##   ##
   ##       ##       ##  ## ## ##         ######        ##     ###### 
   ##       ##       ##   ###  ##         ##           ##      ##     
   ##       ##       ##        ##         ##          ##       ##     
   #######  #######  ##        ##         ##         ######    ##     

               ##   ##  ##   ##  ######                 
               ##   ##  ##   ##  ##   ##                
               ##   ##  ##   ##  ##   ##                
               #######  ##   ##  ######                 
               ##   ##  ##   ##  ##   ##                
               ##   ##  ##   ##  ##   ##                
               ##   ##   #####   ######                 

================================================================================
================ [ ASHYBULAKSTROY AI HUB v1.0 ] ================
================================================================================
""".strip("\n")


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


async def _run_p2p_validation_background() -> None:
    try:
        result = await p2p_service.validate_cached_routes()
        logger.info(
            "p2p_validation_completed validated=%s failed=%s changed=%s",
            result.get("validated", 0),
            result.get("failed", 0),
            result.get("changed", 0),
        )
    except Exception as exc:
        logger.exception("p2p_validation_failed error=%s", str(exc))


async def _run_p2p_peer_sync_background() -> None:
    try:
        if settings.P2P_ENABLED and settings.NODE_MODE == "peer" and settings.P2P_MASTER_URL:
            heartbeat = await p2p_service.send_local_heartbeat(reason="peer_startup")
            logger.info(
                "p2p_peer_startup_heartbeat status=%s master_url=%s",
                heartbeat.get("status"),
                heartbeat.get("master_url"),
            )
            pulled = await p2p_service.pull_network_map()
            logger.info(
                "p2p_peer_network_map_sync imported_peers=%s imported_masters=%s changed=%s",
                pulled.get("imported_peers", 0),
                pulled.get("imported_masters", 0),
                pulled.get("changed", False),
            )
    except Exception as exc:
        logger.exception("p2p_peer_sync_failed error=%s", str(exc))


@app.on_event("startup")
async def startup_probe_limits() -> None:
    logger.info("\n%s", STARTUP_BANNER)
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
    p2p_service.ensure_master_route_from_config()
    asyncio.create_task(_run_startup_probe_background())
    asyncio.create_task(_run_p2p_peer_sync_background())
    asyncio.create_task(_run_p2p_validation_background())
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
