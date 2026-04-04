from __future__ import annotations

import json
import logging
import hashlib
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

from app.config import settings


VALID_NODE_MODES = {"peer", "auto", "master_cache", "master"}
VALID_DISPATCH_MODES = {"FAST", "LOAD_BALANCE", "LOCAL_FIRST", "COST_EFFECTIVE"}
P2P_NETWORK_FILE = Path(__file__).resolve().parent.parent / "p2p_network_snapshot.json"
ADMIN_CACHE_FILE = Path(__file__).resolve().parent.parent / "admin_dashboard_cache.json"


@dataclass
class P2PSessionCounters:
    active_incoming_sessions: int = 0
    active_outgoing_sessions: int = 0
    queued_tasks: int = 0
    total_incoming_accepted: int = 0
    total_outgoing_dispatched: int = 0


class P2PService:
    def __init__(self) -> None:
        self._logger = logging.getLogger("ashybulak.proxy")
        self._lock = Lock()
        self._sessions = P2PSessionCounters()
        self._known_peers: dict[str, dict[str, Any]] = {}
        self._known_masters: dict[str, dict[str, Any]] = {}
        self._network_file = P2P_NETWORK_FILE
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._runtime_p2p_enabled: bool = settings.P2P_ENABLED
        self._runtime_node_mode: str = settings.NODE_MODE
        self._last_master_active_logged: bool | None = None
        self._stale_logged_peers: set[str] = set()
        self._logger.info(
            "p2p_service_initialized enabled=%s node_mode=%s scope=%s node_name=%s",
            self._runtime_p2p_enabled,
            self._runtime_node_mode,
            settings.P2P_SCOPE,
            settings.P2P_NODE_NAME,
        )

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _safe_ratio(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def _safe_health(self, value: float | None) -> float:
        if value is None:
            return 0.0
        return max(0.0, min(1.0, float(value)))

    def _local_base_url(self) -> str:
        configured = str(settings.P2P_BASE_URL or "").strip().rstrip("/")
        if configured:
            return configured
        return f"http://127.0.0.1:{settings.PORT}"

    def _local_peer_id(self) -> str:
        return str(settings.P2P_NODE_ID or settings.P2P_NODE_NAME or f"node-{settings.PORT}").strip()

    def _local_provider_names(self) -> list[str]:
        return list(settings.get_provider_configs().keys())

    def _provider_api_key(self, provider_name: str) -> str:
        config = settings.get_provider_configs().get(str(provider_name or "").strip().lower())
        return str(config.api_key if config else "").strip()

    def _local_direct_provider_access(self, node_mode: str | None = None) -> bool:
        effective_mode = str(node_mode or self._runtime_node_mode).strip().lower()
        return bool(self._local_provider_names()) and effective_mode != "master_cache"

    def _should_persist_network(self, runtime_p2p_enabled: bool, runtime_node_mode: str) -> bool:
        return runtime_p2p_enabled

    def _parse_csv_list(self, value: str | None) -> list[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _parse_json_list(self, value: str | None) -> list[dict[str, Any]]:
        raw = str(value or "").strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _route_hash_id(self, *, api_key: str, provider: str, model: str) -> str:
        seed = f"{api_key.strip()}|{provider.strip().lower()}|{model.strip()}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]

    def _url_hash_id(self, value: str, length: int = 6) -> str:
        raw = str(value or "").strip().rstrip("/")
        if not raw:
            return ""
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[: max(1, length)]

    def _route_ttl_delta(self) -> timedelta:
        return timedelta(minutes=max(1, int(settings.P2P_ROUTE_TTL_MIN)))

    def _is_route_expired(self, route: dict[str, Any]) -> bool:
        route_status = str(route.get("route_status") or "").strip().lower()
        if route_status == "online":
            return False
        last_seen_raw = str(route.get("last_heartbeat_at") or route.get("created_at") or "").strip()
        if not last_seen_raw:
            return True
        try:
            last_seen = datetime.fromisoformat(last_seen_raw)
        except ValueError:
            return True
        return self._now() - last_seen > self._route_ttl_delta()

    def _prune_expired_routes(self) -> int:
        removed = 0
        local_master_route_id = self._route_id_from_url(self._local_base_url(), "master")
        with self._lock:
            peer_keys_to_remove = [
                peer_id
                for peer_id, peer in self._known_peers.items()
                if self._is_route_expired(peer)
            ]
            master_keys_to_remove = [
                route_id
                for route_id, master in self._known_masters.items()
                if route_id != local_master_route_id and self._is_route_expired(master)
            ]
            for peer_id in peer_keys_to_remove:
                self._known_peers.pop(peer_id, None)
                removed += 1
            for route_id in master_keys_to_remove:
                self._known_masters.pop(route_id, None)
                removed += 1
        if removed:
            self._logger.info(
                "p2p_routes_pruned removed=%s ttl_min=%s",
                removed,
                settings.P2P_ROUTE_TTL_MIN,
            )
        return removed

    def _load_local_admin_cache(self) -> dict[str, Any]:
        if not ADMIN_CACHE_FILE.exists():
            return {}
        try:
            return json.loads(ADMIN_CACHE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _to_bool(self, value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _peer_status(self, peer: dict[str, Any]) -> str:
        route_status = str(peer.get("route_status") or "").strip().lower()
        if route_status == "cache":
            return "cache"
        if route_status in {"error", "offline"}:
            return route_status
        last_heartbeat_at = peer.get("last_heartbeat_at")
        if not last_heartbeat_at:
            return "unknown"
        try:
            last_seen = datetime.fromisoformat(last_heartbeat_at)
        except ValueError:
            return "unknown"
        stale_after = max(1, settings.P2P_PEER_STALE_AFTER_SEC)
        if self._now() - last_seen > timedelta(seconds=stale_after):
            return "stale"
        return peer.get("status") or "online"

    def _compute_health_score(self, peer: dict[str, Any], runtime_status: str) -> float:
        base_score = self._safe_health(peer.get("health_score"))
        if base_score == 0.0:
            base_score = 1.0 if runtime_status == "online" else 0.2
        if runtime_status == "stale":
            return 0.0
        if peer.get("status") == "degraded":
            base_score -= 0.35
        if peer.get("status") == "paused":
            base_score -= 0.5
        if peer.get("last_error"):
            base_score -= 0.2
        if not peer.get("accept_remote_tasks", True):
            base_score -= 0.25
        return self._safe_health(base_score)

    def _normalize_peer(self, peer: dict[str, Any]) -> dict[str, Any]:
        runtime_status = self._peer_status(peer)
        normalized = dict(peer)
        normalized["runtime_status"] = runtime_status
        normalized["route_status"] = str(peer.get("route_status") or runtime_status or "unknown").strip().lower()
        normalized["accept_remote_tasks"] = self._to_bool(peer.get("accept_remote_tasks"), True)
        normalized["share_capacity"] = self._to_bool(peer.get("share_capacity"), True)
        normalized["direct_provider_access"] = self._to_bool(peer.get("direct_provider_access"), True)
        normalized["supports_chat"] = self._to_bool(peer.get("supports_chat"), True)
        normalized["supports_embeddings"] = self._to_bool(peer.get("supports_embeddings"), True)
        normalized["providers"] = list(peer.get("providers") or [])
        normalized["models"] = list(peer.get("models") or [])
        normalized["route_catalog"] = list(peer.get("route_catalog") or [])
        normalized["shared_rpm_ratio"] = self._safe_ratio(peer.get("shared_rpm_ratio", 1.0))
        normalized["shared_tpm_ratio"] = self._safe_ratio(peer.get("shared_tpm_ratio", 1.0))
        normalized["active_sessions"] = max(0, int(peer.get("active_sessions", 0)))
        normalized["health_score"] = self._compute_health_score(normalized, runtime_status)
        return normalized

    def _peer_supports_task(self, peer: dict[str, Any], task_type: str) -> bool:
        if task_type == "chat_completion":
            return bool(peer.get("supports_chat"))
        if task_type == "embeddings":
            return bool(peer.get("supports_embeddings"))
        return False

    def _select_peer(self, eligible_peers: list[dict[str, Any]], mode: str) -> dict[str, Any] | None:
        if not eligible_peers:
            return None

        if mode == "FAST":
            ranked = sorted(
                eligible_peers,
                key=lambda item: (-item["health_score"], item["active_sessions"], item["peer_id"]),
            )
        elif mode == "LOAD_BALANCE":
            ranked = sorted(
                eligible_peers,
                key=lambda item: (item["active_sessions"], -item["health_score"], item["peer_id"]),
            )
        elif mode == "COST_EFFECTIVE":
            ranked = sorted(
                eligible_peers,
                key=lambda item: (-item["shared_rpm_ratio"], -item["shared_tpm_ratio"], -item["health_score"], item["peer_id"]),
            )
        else:
            ranked = sorted(
                eligible_peers,
                key=lambda item: (-item["health_score"], item["active_sessions"], item["peer_id"]),
            )
        return ranked[0]

    def _ensure_runtime_events_logged(self, peers: list[dict[str, Any]], runtime_p2p_enabled: bool, runtime_node_mode: str) -> None:
        master_active = runtime_p2p_enabled and runtime_node_mode == "master"
        if self._last_master_active_logged is None or self._last_master_active_logged != master_active:
            self._logger.info(
                "p2p_master_mode_active active=%s node_mode=%s p2p_enabled=%s node_name=%s",
                master_active,
                runtime_node_mode,
                runtime_p2p_enabled,
                settings.P2P_NODE_NAME,
            )
            self._last_master_active_logged = master_active

        current_stale_peers = set()
        for peer in peers:
            peer_id = str(peer.get("peer_id") or "").strip()
            if not peer_id:
                continue
            runtime_status = self._peer_status(peer)
            if runtime_status == "stale":
                current_stale_peers.add(peer_id)
                if peer_id not in self._stale_logged_peers:
                    self._logger.warning(
                        "p2p_peer_became_stale peer_id=%s node_name=%s last_heartbeat_at=%s stale_after_sec=%s",
                        peer_id,
                        peer.get("node_name"),
                        peer.get("last_heartbeat_at"),
                        settings.P2P_PEER_STALE_AFTER_SEC,
                    )

        self._stale_logged_peers = current_stale_peers

    def _build_route_pairs(self, providers: list[str], models: list[str]) -> list[dict[str, str]]:
        clean_providers = [item for item in providers if item]
        clean_models = [item for item in models if item]
        if not clean_providers:
            return []
        if not clean_models:
            return [{"provider": provider, "model": "auto", "route_id": ""} for provider in clean_providers]
        if len(clean_providers) == 1:
            return [{"provider": clean_providers[0], "model": model, "route_id": ""} for model in clean_models]
        if len(clean_models) == 1:
            return [{"provider": provider, "model": clean_models[0], "route_id": ""} for provider in clean_providers]
        if len(clean_providers) == len(clean_models):
            return [
                {"provider": provider, "model": model, "route_id": ""}
                for provider, model in zip(clean_providers, clean_models)
            ]
        return [{"provider": provider, "model": "auto", "route_id": ""} for provider in clean_providers]

    def _local_llm_route_pairs(self) -> list[dict[str, str]]:
        cache = self._load_local_admin_cache()
        validated = ((cache.get("validated_llm") or {}).get("data") or [])
        if validated:
            routes = [
                {
                    "provider": str(item.get("provider") or "").strip(),
                    "model": str(item.get("id") or "").strip(),
                    "route_id": self._route_hash_id(
                        api_key=self._provider_api_key(str(item.get("provider") or "").strip()),
                        provider=str(item.get("provider") or "").strip(),
                        model=str(item.get("id") or "").strip(),
                    ),
                }
                for item in validated
                if isinstance(item, dict) and item.get("provider") and item.get("id")
            ]
            return [item for item in routes if item["provider"] and item["model"] and item["route_id"]]

        block_two = ((cache.get("block_two") or {}).get("data") or [])
        routes = []
        for item in block_two:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip()
            model_id = str(item.get("id") or "").strip()
            category = str(item.get("category") or "").strip().lower()
            if provider and model_id and category == "llm":
                routes.append(
                    {
                        "provider": provider,
                        "model": model_id,
                        "route_id": self._route_hash_id(
                            api_key=self._provider_api_key(provider),
                            provider=provider,
                            model=model_id,
                        ),
                    }
                )
        return routes

    def _build_owner_route_pairs(self, owner: dict[str, Any]) -> list[dict[str, str]]:
        if owner.get("kind") == "master" and str(owner.get("base_url") or "").rstrip("/") == self._local_base_url().rstrip("/"):
            local_routes = self._local_llm_route_pairs()
            if local_routes:
                return local_routes
        route_catalog = list(owner.get("route_catalog") or [])
        if route_catalog:
            return [
                {
                    "provider": str(item.get("provider") or "").strip(),
                    "model": str(item.get("model") or "").strip(),
                    "route_id": str(item.get("route_id") or "").strip(),
                }
                for item in route_catalog
                if str(item.get("provider") or "").strip()
                and str(item.get("model") or "").strip()
                and str(item.get("route_id") or "").strip()
            ]
        return self._build_route_pairs(
            list(owner.get("providers") or []),
            list(owner.get("models") or []),
        )

    def _route_slot_values(self, route_owner: dict[str, Any], route_count: int) -> list[int]:
        route_total = max(1, route_count)
        shared_ratio = self._safe_ratio(route_owner.get("shared_rpm_ratio", 1.0))
        shared_slots_budget = max(0, round(settings.P2P_MAX_SHARED_SLOTS_PER_MIN * shared_ratio))
        slots_per_route = max(0, math.ceil(shared_slots_budget / route_total))
        return [slots_per_route] * route_total

    def _build_routing_table(
        self,
        *,
        masters: list[dict[str, Any]],
        peers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        routing_rows: list[dict[str, Any]] = []
        owner_rows = [
            *[
                {
                    "mode": "master",
                    "owner_id": master.get("route_id") or master.get("base_url") or "master",
                    "owner_name": master.get("node_name") or "master",
                    **master,
                }
                for master in masters
            ],
            *[
                {
                    "mode": "peer",
                    "owner_id": peer.get("peer_id") or peer.get("node_name") or "peer",
                    "owner_name": peer.get("node_name") or peer.get("peer_id") or "peer",
                    **peer,
                }
                for peer in peers
            ],
        ]
        for owner in owner_rows:
            if owner.get("route_status") != "online" or not owner.get("direct_provider_access"):
                continue
            route_pairs = self._build_owner_route_pairs(owner)
            route_count = len(route_pairs) or max(1, len(owner.get("providers") or []))
            slot_values = self._route_slot_values(owner, route_count)
            for index, pair in enumerate(route_pairs):
                route_id = str(pair.get("route_id") or "").strip()
                if not route_id:
                    fallback_seed = str(owner.get("owner_id") or owner.get("base_url") or owner.get("owner_name") or "")
                    route_id = hashlib.sha256(
                        f"{fallback_seed}|{pair['provider']}|{pair['model']}".encode("utf-8")
                    ).hexdigest()[:12]
                routing_rows.append(
                    {
                        "mode": owner["mode"],
                        "owner_id": owner["owner_id"],
                        "owner_name": owner["owner_name"],
                        "route_id": route_id,
                        "resource_name": f"{pair['provider']} + {pair['model']}",
                        "available_slots_per_minute": slot_values[index] if index < len(slot_values) else 0,
                        "route_status": owner.get("route_status"),
                        "runtime_status": owner.get("runtime_status"),
                        "direct_provider_access": owner.get("direct_provider_access"),
                    }
                )
        routing_rows.sort(
            key=lambda item: (
                item.get("owner_name") or "",
                item.get("route_id") or "",
            )
        )
        return routing_rows

    def dispatch_preview(
        self,
        *,
        requested_provider: str | None = None,
        requested_model: str | None = None,
        requested_mode: str | None = None,
        task_type: str = "chat_completion",
    ) -> dict[str, Any]:
        with self._lock:
            peers = [dict(item) for item in self._known_peers.values()]
            runtime_p2p_enabled = self._runtime_p2p_enabled
            runtime_node_mode = self._runtime_node_mode

        mode = str(requested_mode or settings.PROXY_MODE or "LOAD_BALANCE").strip().upper()
        if mode not in VALID_DISPATCH_MODES:
            raise ValueError(f"Unsupported dispatch mode '{mode}'")

        normalized_provider = (requested_provider or "auto").strip() or "auto"
        normalized_model = (requested_model or "auto").strip() or "auto"

        eligible_peers = []
        skipped_peers = []
        for peer in peers:
            peer_payload = self._normalize_peer(peer)
            skip_reason = None
            if peer_payload["runtime_status"] != "online":
                skip_reason = f"runtime_status={peer_payload['runtime_status']}"
            elif not peer_payload["accept_remote_tasks"]:
                skip_reason = "accept_remote_tasks=false"
            elif not peer_payload["share_capacity"]:
                skip_reason = "share_capacity=false"
            elif not peer_payload["direct_provider_access"]:
                skip_reason = "direct_provider_access=false"
            elif not self._peer_supports_task(peer_payload, task_type):
                skip_reason = f"task_not_supported={task_type}"
            elif peer_payload["health_score"] < 0.5:
                skip_reason = f"health_score_too_low={peer_payload['health_score']}"
            elif peer_payload["active_sessions"] >= settings.P2P_MAX_REMOTE_SESSIONS:
                skip_reason = "max_remote_sessions_reached"

            if skip_reason:
                peer_payload["skip_reason"] = skip_reason
                skipped_peers.append(peer_payload)
                continue
            eligible_peers.append(peer_payload)

        decision = {
            "task_type": task_type,
            "requested_provider": normalized_provider,
            "requested_model": normalized_model,
            "requested_mode": mode,
            "local_node": {
                "name": settings.P2P_NODE_NAME,
                "mode": runtime_node_mode,
                "p2p_enabled": runtime_p2p_enabled,
            },
            "selected_peer": None,
            "selected_strategy": None,
            "eligible_peers": eligible_peers,
            "skipped_peers": skipped_peers,
            "reason": None,
        }

        if not runtime_p2p_enabled:
            decision["selected_strategy"] = "local_only"
            decision["reason"] = "p2p_disabled"
        elif runtime_node_mode in {"master", "master_cache"} and eligible_peers:
            selected_peer = self._select_peer(eligible_peers, mode)
            decision["selected_peer"] = selected_peer
            decision["selected_strategy"] = mode.lower()
            decision["reason"] = "capabilities_health_selection"
        else:
            decision["selected_strategy"] = "local_fallback"
            decision["reason"] = "no_eligible_peers_or_non_master_mode"

        self._logger.info(
            "p2p_dispatch_preview_selected task_type=%s requested_provider=%s requested_model=%s requested_mode=%s selected_peer_id=%s selected_strategy=%s eligible_peers=%s skipped_peers=%s",
            task_type,
            normalized_provider,
            normalized_model,
            mode,
            (decision["selected_peer"] or {}).get("peer_id"),
            decision["selected_strategy"],
            len(eligible_peers),
            len(skipped_peers),
        )
        return decision

    def update_runtime_config(self, *, p2p_enabled: bool | None = None, node_mode: str | None = None) -> dict[str, Any]:
        with self._lock:
            old_enabled = self._runtime_p2p_enabled
            old_node_mode = self._runtime_node_mode
            if p2p_enabled is not None:
                self._runtime_p2p_enabled = bool(p2p_enabled)
            if node_mode is not None:
                cleaned = str(node_mode).strip().lower()
                if cleaned not in VALID_NODE_MODES:
                    raise ValueError(f"Unsupported NODE_MODE '{node_mode}'")
                self._runtime_node_mode = cleaned
        self._logger.info(
            "p2p_runtime_config_updated old_enabled=%s new_enabled=%s old_node_mode=%s new_node_mode=%s",
            old_enabled,
            self._runtime_p2p_enabled,
            old_node_mode,
            self._runtime_node_mode,
        )
        self.save_network_snapshot()
        return self.get_status()

    def _route_id_from_url(self, base_url: str, role: str) -> str:
        cleaned = str(base_url or "").strip().rstrip("/")
        if not cleaned:
            return f"{role}-unknown"
        return f"{role}::{cleaned}"

    def _ensure_local_master_record(self) -> None:
        if self._runtime_node_mode not in {"master", "master_cache"}:
            return
        route_id = self._route_id_from_url(self._local_base_url(), "master")
        local_routes = self._local_llm_route_pairs()
        with self._lock:
            existing = self._known_masters.get(route_id, {})
            self._known_masters[route_id] = {
                "route_id": route_id,
                "node_name": settings.P2P_NODE_NAME,
                "node_mode": self._runtime_node_mode,
                "scope": settings.P2P_SCOPE,
                "base_url": self._local_base_url(),
                "status": "online",
                "route_status": "online",
                "providers": self._local_provider_names(),
                "models": sorted({item.get("model") for item in local_routes if item.get("model")}),
                "route_catalog": local_routes,
                "direct_provider_access": self._local_direct_provider_access(),
                "accept_remote_tasks": settings.P2P_ACCEPT_REMOTE_TASKS,
                "share_capacity": settings.P2P_SHARE_CAPACITY,
                "supports_chat": True,
                "supports_embeddings": True,
                "health_score": 1.0,
                "active_sessions": 0,
                "last_error": None,
                "created_at": existing.get("created_at") or self._now().isoformat(),
                "last_heartbeat_at": self._now().isoformat(),
            }

    def ensure_master_route_from_config(self) -> None:
        master_url = str(settings.P2P_MASTER_URL or "").strip().rstrip("/")
        if not master_url:
            return
        route_id = self._route_id_from_url(master_url, "master")
        with self._lock:
            existing = self._known_masters.get(route_id, {})
            self._known_masters[route_id] = {
                "route_id": route_id,
                "node_name": existing.get("node_name") or "master",
                "node_mode": "master",
                "scope": settings.P2P_SCOPE,
                "base_url": master_url,
                "status": existing.get("status") or "unknown",
                "route_status": existing.get("route_status") or "cache",
                "providers": list(existing.get("providers") or []),
                "models": list(existing.get("models") or []),
                "route_catalog": list(existing.get("route_catalog") or []),
                "direct_provider_access": self._to_bool(existing.get("direct_provider_access"), True),
                "accept_remote_tasks": True,
                "share_capacity": True,
                "supports_chat": True,
                "supports_embeddings": True,
                "health_score": self._safe_health(existing.get("health_score", 0.0)),
                "active_sessions": max(0, int(existing.get("active_sessions", 0))),
                "last_error": existing.get("last_error"),
                "created_at": existing.get("created_at") or self._now().isoformat(),
                "last_heartbeat_at": existing.get("last_heartbeat_at"),
                "route_catalog": list(existing.get("route_catalog") or []),
            }

    def _network_changed(self, before: dict[str, Any], after: dict[str, Any]) -> bool:
        watched_keys = (
            "base_url",
            "status",
            "route_status",
            "node_mode",
            "direct_provider_access",
            "providers",
            "route_catalog",
            "health_score",
            "last_error",
        )
        return any(before.get(key) != after.get(key) for key in watched_keys)

    def register_or_update_peer(
        self,
        *,
        peer_id: str,
        node_name: str,
            node_mode: str = "peer",
        scope: str = "private",
        base_url: str = "",
        status: str = "online",
        note: str = "",
        accept_remote_tasks: bool = True,
        share_capacity: bool = True,
        direct_provider_access: bool = True,
        supports_chat: bool = True,
        supports_embeddings: bool = True,
        providers: str | None = None,
        models: str | None = None,
        route_catalog: str | None = None,
        health_score: float | None = None,
        active_sessions: int = 0,
        last_error: str = "",
        shared_rpm_ratio: float = 1.0,
        shared_tpm_ratio: float = 1.0,
    ) -> dict[str, Any]:
        cleaned_peer_id = str(peer_id).strip()
        if not cleaned_peer_id:
            raise ValueError("peer_id is required")

        with self._lock:
            existing = self._known_peers.get(cleaned_peer_id, {})
            peer = {
                "peer_id": cleaned_peer_id,
                "node_name": str(node_name).strip() or cleaned_peer_id,
                "node_mode": str(node_mode).strip().lower() or "peer",
                "scope": str(scope).strip().lower() or "private",
                "base_url": str(base_url).strip() or None,
                "status": str(status).strip().lower() or "online",
                "route_status": "online",
                "note": str(note).strip() or None,
                "accept_remote_tasks": bool(accept_remote_tasks),
                "share_capacity": bool(share_capacity),
                "direct_provider_access": bool(direct_provider_access),
                "supports_chat": bool(supports_chat),
                "supports_embeddings": bool(supports_embeddings),
                "providers": self._parse_csv_list(providers),
                "models": self._parse_csv_list(models),
                "route_catalog": self._parse_json_list(route_catalog),
                "health_score": self._safe_health(health_score if health_score is not None else existing.get("health_score", 1.0)),
                "active_sessions": max(0, int(active_sessions)),
                "last_error": str(last_error).strip() or None,
                "shared_rpm_ratio": self._safe_ratio(shared_rpm_ratio),
                "shared_tpm_ratio": self._safe_ratio(shared_tpm_ratio),
                "created_at": existing.get("created_at") or self._now().isoformat(),
                "last_heartbeat_at": self._now().isoformat(),
            }
            self._known_peers[cleaned_peer_id] = peer
            peer_count = len(self._known_peers)
            network_changed = self._network_changed(existing, peer)
        self._logger.info(
            "p2p_peer_upserted peer_id=%s node_name=%s node_mode=%s scope=%s status=%s direct_provider_access=%s health_score=%s supports_chat=%s supports_embeddings=%s providers=%s models=%s base_url=%s total_known_peers=%s",
            cleaned_peer_id,
            peer["node_name"],
            peer["node_mode"],
            peer["scope"],
            peer["status"],
            peer["direct_provider_access"],
            peer["health_score"],
            peer["supports_chat"],
            peer["supports_embeddings"],
            len(peer["providers"]),
            len(peer["models"]),
            peer["base_url"],
            peer_count,
        )
        if network_changed:
            self.save_network_snapshot()
        return dict(peer)

    def remove_known_node(self, *, mode: str, node_key: str) -> dict[str, Any]:
        normalized_mode = str(mode or "").strip().lower()
        normalized_key = str(node_key or "").strip()
        if normalized_mode not in {"peer", "master"}:
            raise ValueError("mode must be 'peer' or 'master'")
        if not normalized_key:
            raise ValueError("node_key is required")

        removed: dict[str, Any] | None = None
        with self._lock:
            if normalized_mode == "peer":
                removed = self._known_peers.pop(normalized_key, None)
            else:
                local_master_route_id = self._route_id_from_url(self._local_base_url(), "master")
                if normalized_key == local_master_route_id:
                    raise ValueError("cannot remove local master node")
                removed = self._known_masters.pop(normalized_key, None)

        if removed is None:
            raise ValueError(f"{normalized_kind} node '{normalized_key}' not found")

        self._logger.info(
            "p2p_node_removed mode=%s node_key=%s node_name=%s base_url=%s",
            normalized_mode,
            normalized_key,
            removed.get("node_name"),
            removed.get("base_url"),
        )
        self.save_network_snapshot()
        return {
            "status": "ok",
            "removed_mode": normalized_mode,
            "removed_key": normalized_key,
            "removed_node_name": removed.get("node_name"),
        }

    def set_session_counters(
        self,
        *,
        active_incoming_sessions: int | None = None,
        active_outgoing_sessions: int | None = None,
        queued_tasks: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if active_incoming_sessions is not None:
                self._sessions.active_incoming_sessions = max(0, int(active_incoming_sessions))
            if active_outgoing_sessions is not None:
                self._sessions.active_outgoing_sessions = max(0, int(active_outgoing_sessions))
            if queued_tasks is not None:
                self._sessions.queued_tasks = max(0, int(queued_tasks))
            snapshot = asdict(self._sessions)
        self._logger.info(
            "p2p_session_counters_updated active_incoming=%s active_outgoing=%s queued_tasks=%s total_incoming_accepted=%s total_outgoing_dispatched=%s",
            snapshot["active_incoming_sessions"],
            snapshot["active_outgoing_sessions"],
            snapshot["queued_tasks"],
            snapshot["total_incoming_accepted"],
            snapshot["total_outgoing_dispatched"],
        )
        return self.get_status()

    def save_network_snapshot(self) -> dict[str, Any]:
        with self._lock:
            runtime_p2p_enabled = self._runtime_p2p_enabled
            runtime_node_mode = self._runtime_node_mode
        if not self._should_persist_network(runtime_p2p_enabled, runtime_node_mode):
            return {"status": "skipped", "reason": "not_master_mode"}

        self._ensure_local_master_record()
        self.ensure_master_route_from_config()
        status = self.get_status()
        payload = {
            "saved_at": self._now().isoformat(),
            "node": status.get("node", {}),
            "master": status.get("master", {}),
            "network_map": status.get("network_map", {}),
            "masters": status.get("masters", []),
            "peers": status.get("peers", []),
        }
        self._network_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._logger.info(
            "p2p_network_snapshot_saved path=%s peers=%s direct_provider_links=%s",
            self._network_file,
            len(payload["peers"]),
            (payload.get("network_map", {}).get("routes", {}) or {}).get("direct_provider_links", 0),
        )
        return {
            "status": "ok",
            "path": str(self._network_file),
            "peers": len(payload["peers"]),
        }

    def load_network_snapshot(self) -> dict[str, Any]:
        if not self._network_file.exists():
            return {"status": "missing", "loaded_peers": 0, "path": str(self._network_file)}

        try:
            payload = json.loads(self._network_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._logger.warning("p2p_network_snapshot_load_failed path=%s error=%s", self._network_file, str(exc))
            return {"status": "error", "loaded_peers": 0, "path": str(self._network_file), "error": str(exc)}

        peers = payload.get("peers") or []
        masters = payload.get("masters") or []
        loaded_count = 0
        with self._lock:
            self._known_peers = {}
            self._known_masters = {}
            for peer in peers:
                if not isinstance(peer, dict):
                    continue
                peer_id = str(peer.get("peer_id") or "").strip()
                if not peer_id:
                    continue
                cached_peer = dict(peer)
                cached_peer["route_status"] = "cache"
                cached_peer["status"] = "cache"
                self._known_peers[peer_id] = cached_peer
                loaded_count += 1
            for master in masters:
                if not isinstance(master, dict):
                    continue
                route_id = str(master.get("route_id") or "").strip()
                if not route_id:
                    continue
                cached_master = dict(master)
                cached_master["route_status"] = "cache"
                cached_master["status"] = "cache"
                self._known_masters[route_id] = cached_master

        self._ensure_local_master_record()
        self.ensure_master_route_from_config()

        self._logger.info(
            "p2p_network_snapshot_loaded path=%s loaded_peers=%s saved_at=%s",
            self._network_file,
            loaded_count,
            payload.get("saved_at"),
        )
        return {
            "status": "ok",
            "loaded_peers": loaded_count,
            "path": str(self._network_file),
            "saved_at": payload.get("saved_at"),
        }

    def import_network_map(self, payload: dict[str, Any]) -> dict[str, Any]:
        peers = payload.get("peers") or []
        masters = payload.get("masters") or []
        imported_peers = 0
        imported_masters = 0
        changed = False
        with self._lock:
            for peer in peers:
                if not isinstance(peer, dict):
                    continue
                peer_id = str(peer.get("peer_id") or "").strip()
                if not peer_id:
                    continue
                existing = self._known_peers.get(peer_id, {})
                candidate = dict(peer)
                candidate["route_status"] = "cache"
                candidate["status"] = "cache"
                if self._network_changed(existing, candidate):
                    changed = True
                self._known_peers[peer_id] = candidate
                imported_peers += 1
            for master in masters:
                if not isinstance(master, dict):
                    continue
                route_id = str(master.get("route_id") or "").strip()
                if not route_id:
                    continue
                existing = self._known_masters.get(route_id, {})
                candidate = dict(master)
                candidate["route_status"] = "cache"
                candidate["status"] = "cache"
                if self._network_changed(existing, candidate):
                    changed = True
                self._known_masters[route_id] = candidate
                imported_masters += 1

        self._ensure_local_master_record()
        self.ensure_master_route_from_config()
        if changed:
            self.save_network_snapshot()
        return {
            "status": "ok",
            "imported_peers": imported_peers,
            "imported_masters": imported_masters,
            "changed": changed,
        }

    def export_network_map(self) -> dict[str, Any]:
        self._ensure_local_master_record()
        self.ensure_master_route_from_config()
        with self._lock:
            masters = [self._normalize_peer(dict(item)) for item in self._known_masters.values()]
            peers = [self._normalize_peer(dict(item)) for item in self._known_peers.values()]
        masters.sort(key=lambda item: (item.get("base_url") or "", item.get("route_id") or ""))
        peers.sort(key=lambda item: (item.get("node_name") or "", item.get("peer_id") or ""))
        return {
            "status": "ok",
            "exported_at": self._now().isoformat(),
            "masters": masters,
            "peers": peers,
        }

    async def pull_network_map(self, *, master_url: str | None = None) -> dict[str, Any]:
        target_master = str(master_url or settings.P2P_MASTER_URL or "").strip().rstrip("/")
        if not target_master:
            return {"status": "skipped", "reason": "missing_master_url"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{target_master}/internal/p2p/network-map")
            response.raise_for_status()
            payload = response.json()

        imported = self.import_network_map(payload)
        self._logger.info(
            "p2p_network_map_pulled master_url=%s imported_peers=%s imported_masters=%s changed=%s",
            target_master,
            imported.get("imported_peers", 0),
            imported.get("imported_masters", 0),
            imported.get("changed", False),
        )
        return imported

    async def send_local_heartbeat(self, *, master_url: str | None = None, reason: str = "manual") -> dict[str, Any]:
        target_master = str(master_url or settings.P2P_MASTER_URL or "").strip().rstrip("/")
        if not target_master:
            return {"status": "skipped", "reason": "missing_master_url"}
        if not self._runtime_p2p_enabled:
            return {"status": "skipped", "reason": "p2p_disabled"}

        providers = self._local_provider_names()
        direct_provider_access = self._local_direct_provider_access()
        local_routes = self._local_llm_route_pairs()
        payload = {
            "peer_id": self._local_peer_id(),
            "node_name": settings.P2P_NODE_NAME,
            "node_mode": self._runtime_node_mode,
            "scope": settings.P2P_SCOPE,
            "base_url": self._local_base_url(),
            "status": "online",
            "accept_remote_tasks": settings.P2P_ACCEPT_REMOTE_TASKS,
            "share_capacity": settings.P2P_SHARE_CAPACITY,
            "direct_provider_access": direct_provider_access,
            "supports_chat": True,
            "supports_embeddings": True,
            "providers": ",".join(providers),
            "models": ",".join(sorted({item["model"] for item in local_routes if item.get("model")})),
            "route_catalog": json.dumps(local_routes, ensure_ascii=False),
            "shared_rpm_ratio": self._safe_ratio(settings.P2P_SHARED_RPM_RATIO),
            "shared_tpm_ratio": self._safe_ratio(settings.P2P_SHARED_TPM_RATIO),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{target_master}/admin/p2p/peers/heartbeat", params=payload)
            response.raise_for_status()
            body = response.json()

        self._logger.info(
            "p2p_local_heartbeat_sent reason=%s peer_id=%s master_url=%s direct_provider_access=%s providers=%s",
            reason,
            payload["peer_id"],
            target_master,
            direct_provider_access,
            len(providers),
        )
        return {
            "status": "ok",
            "master_url": target_master,
            "peer_id": payload["peer_id"],
            "response": body,
        }

    async def validate_cached_routes(self) -> dict[str, Any]:
        self._ensure_local_master_record()
        self.ensure_master_route_from_config()
        changes = 0
        validated = 0
        failed = 0

        async def _validate_entry(mode: str, route_key: str, route: dict[str, Any]) -> None:
            nonlocal changes, validated, failed
            base_url = str(route.get("base_url") or "").strip().rstrip("/")
            before = dict(route)
            if not base_url:
                route["route_status"] = "error"
                route["status"] = "error"
                route["last_error"] = "missing_base_url"
                failed += 1
                if self._network_changed(before, route):
                    changes += 1
                return
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{base_url}/admin/p2p/status")
                    response.raise_for_status()
                    payload = response.json()
                route["route_status"] = "online"
                route["status"] = "online"
                route["last_error"] = None
                route["last_heartbeat_at"] = self._now().isoformat()
                route["node_name"] = payload.get("node", {}).get("name") or route.get("node_name")
                route["node_mode"] = payload.get("node", {}).get("mode") or route.get("node_mode")
                validated += 1
            except Exception as exc:
                route["route_status"] = "error"
                route["status"] = "error"
                route["last_error"] = str(exc)
                failed += 1
                self._logger.warning("p2p_route_validation_failed mode=%s route_key=%s error=%s", mode, route_key, str(exc))
            if self._network_changed(before, route):
                changes += 1

        with self._lock:
            masters = [(route_id, self._known_masters[route_id]) for route_id in list(self._known_masters.keys())]
            peers = [(peer_id, self._known_peers[peer_id]) for peer_id in list(self._known_peers.keys())]

        for route_id, route in masters:
            await _validate_entry("master", route_id, route)
        for peer_id, route in peers:
            await _validate_entry("peer", peer_id, route)

        if changes:
            self.save_network_snapshot()
        self._logger.info(
            "p2p_routes_validated validated=%s failed=%s changed=%s",
            validated,
            failed,
            changes,
        )
        return {
            "status": "ok",
            "validated": validated,
            "failed": failed,
            "changed": changes,
        }

    async def request_peers_reregister(self) -> dict[str, Any]:
        with self._lock:
            runtime_p2p_enabled = self._runtime_p2p_enabled
            runtime_node_mode = self._runtime_node_mode
            peers = [dict(item) for item in self._known_peers.values()]

        if not self._should_persist_network(runtime_p2p_enabled, runtime_node_mode):
            return {"status": "skipped", "reason": "not_master_mode", "requested": 0}

        master_url = self._local_base_url()
        requested = 0
        failures: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for peer in peers:
                base_url = str(peer.get("base_url") or "").strip().rstrip("/")
                peer_id = str(peer.get("peer_id") or "").strip() or "peer"
                if not base_url:
                    failures.append({"peer_id": peer_id, "error": "missing_base_url"})
                    continue
                try:
                    response = await client.post(
                        f"{base_url}/internal/p2p/re-register",
                        params={"master_url": master_url, "reason": "master_startup_recovery"},
                    )
                    response.raise_for_status()
                    requested += 1
                    self._logger.info(
                        "p2p_peer_reregister_requested peer_id=%s peer_url=%s master_url=%s",
                        peer_id,
                        base_url,
                        master_url,
                    )
                except Exception as exc:
                    failures.append({"peer_id": peer_id, "error": str(exc)})
                    self._logger.warning(
                        "p2p_peer_reregister_request_failed peer_id=%s peer_url=%s error=%s",
                        peer_id,
                        base_url,
                        str(exc),
                    )

        return {
            "status": "ok",
            "requested": requested,
            "failed": len(failures),
            "failures": failures,
        }

    def get_status(self) -> dict[str, Any]:
        pruned_count = self._prune_expired_routes()
        if pruned_count:
            self.save_network_snapshot()
        self._ensure_local_master_record()
        self.ensure_master_route_from_config()
        with self._lock:
            sessions = asdict(self._sessions)
            peers = [self._normalize_peer(dict(item)) for item in self._known_peers.values()]
            masters = [self._normalize_peer(dict(item)) for item in self._known_masters.values()]
            runtime_p2p_enabled = self._runtime_p2p_enabled
            runtime_node_mode = self._runtime_node_mode

        peers.sort(key=lambda item: (item.get("node_name") or "", item.get("peer_id") or ""))
        masters.sort(key=lambda item: (item.get("base_url") or "", item.get("route_id") or ""))
        for peer in peers:
            peer["peer_id6"] = self._url_hash_id(peer.get("base_url") or peer.get("peer_id") or "")
            peer["mode"] = "peer"
        for master in masters:
            master["peer_id6"] = self._url_hash_id(master.get("base_url") or master.get("route_id") or "")
            master["mode"] = "master"
        peer_status_summary = {
            "total_known_peers": len(peers),
            "online": sum(1 for peer in peers if self._peer_status(peer) == "online"),
            "stale": sum(1 for peer in peers if self._peer_status(peer) == "stale"),
            "cache": sum(1 for peer in peers if self._peer_status(peer) == "cache"),
            "error": sum(1 for peer in peers if self._peer_status(peer) == "error"),
            "avg_health_score": round(sum(peer.get("health_score", 0.0) for peer in peers) / len(peers), 3) if peers else 0.0,
        }

        self._ensure_runtime_events_logged(peers, runtime_p2p_enabled, runtime_node_mode)

        is_master_mode = runtime_node_mode == "master"
        is_master_cache_mode = runtime_node_mode == "master_cache"
        provider_configs = settings.get_provider_configs()
        local_direct_provider_access = self._local_direct_provider_access(runtime_node_mode)
        direct_provider_links: set[str] = set()
        local_role = "master" if is_master_mode else "master_cache" if is_master_cache_mode else runtime_node_mode

        master_count = sum(1 for master in masters if master.get("route_status") == "online")
        peer_count = sum(1 for peer in peers if peer.get("node_mode") == "peer")
        direct_peer_count = sum(
            1
            for peer in peers
            if peer.get("node_mode") == "peer"
            and peer.get("runtime_status") == "online"
            and peer.get("direct_provider_access")
        )
        link_only_peer_count = sum(
            1
            for peer in peers
            if peer.get("node_mode") == "peer"
            and peer.get("runtime_status") == "online"
            and not peer.get("direct_provider_access")
        )
        peer_provider_count = sum(
            len(peer.get("providers") or [])
            for peer in peers
            if peer.get("runtime_status") == "online" and peer.get("direct_provider_access")
        )
        for peer in peers:
            if peer.get("runtime_status") != "online" or not peer.get("direct_provider_access"):
                continue
            peer_id = peer.get("peer_id") or peer.get("node_name") or "peer"
            for provider_name in peer.get("providers") or []:
                direct_provider_links.add(f"{peer_id}::{provider_name}")
        for master in masters:
            if master.get("route_status") != "online" or not master.get("direct_provider_access"):
                continue
            route_id = master.get("route_id") or master.get("node_name") or "master"
            for provider_name in master.get("providers") or []:
                direct_provider_links.add(f"{route_id}::{provider_name}")

        routing_table = self._build_routing_table(masters=masters, peers=peers)
        route_ids = [str(row.get("route_id") or "").strip() for row in routing_table if str(row.get("route_id") or "").strip()]
        unique_route_ids = set(route_ids)
        redundant_route_count = max(0, len(route_ids) - len(unique_route_ids))
        network_map = {
            "master_nodes": {
                "count": master_count,
                "direct_provider_count": sum(
                    len(master.get("providers") or [])
                    for master in masters
                    if master.get("route_status") == "online" and master.get("direct_provider_access")
                ),
                "route_count": sum(
                    1 for row in routing_table if row.get("mode") == "master" and row.get("route_status") == "online"
                ),
                "direct_provider_access": local_direct_provider_access,
                "role": local_role,
            },
            "peer_nodes": {
                "count": peer_count,
                "direct_provider_count": peer_provider_count,
                "route_count": sum(
                    1 for row in routing_table if row.get("mode") == "peer" and row.get("route_status") == "online"
                ),
                "direct_peer_count": direct_peer_count,
                "link_only_peer_count": link_only_peer_count,
            },
            "routes": {
                "direct_provider_links": len(direct_provider_links),
                "online_route_count": sum(1 for row in routing_table if row.get("route_status") == "online"),
                "unique_route_count": len(unique_route_ids),
                "redundant_route_count": redundant_route_count,
            },
        }
        ready_routes = sum(1 for row in routing_table if row.get("route_status") == "online")
        routes_with_slots = sum(
            1
            for row in routing_table
            if row.get("route_status") == "online" and (row.get("available_slots_per_minute") or 0) > 0
        )
        shared_slots_total = int(settings.P2P_MAX_SHARED_SLOTS_PER_MIN)
        routes_without_free_slots = max(0, ready_routes - routes_with_slots)
        busy_slots = min(
            shared_slots_total,
            max(0, int(self._sessions.active_incoming_sessions) + int(self._sessions.active_outgoing_sessions)),
        )
        online_resource_summary = {
            "ready_routes": ready_routes,
            "routes_with_slots": routes_with_slots,
            "routes_without_free_slots": routes_without_free_slots,
            "shared_slots_total": shared_slots_total,
            "busy_slots": busy_slots,
        }

        return {
            "status": "ok",
            "started_at": self._started_at,
            "p2p_enabled": runtime_p2p_enabled,
            "node": {
                "mode": runtime_node_mode,
                "scope": settings.P2P_SCOPE,
                "name": settings.P2P_NODE_NAME,
                "node_id": settings.P2P_NODE_ID or None,
                "cluster_name": settings.P2P_CLUSTER_NAME,
                "base_url": self._local_base_url(),
                "master_url": settings.P2P_MASTER_URL or None,
                "allow_master": settings.P2P_ALLOW_MASTER,
                "accept_remote_tasks": settings.P2P_ACCEPT_REMOTE_TASKS,
                "share_capacity": settings.P2P_SHARE_CAPACITY,
                "direct_provider_access": local_direct_provider_access,
                "shared_rpm_ratio": self._safe_ratio(settings.P2P_SHARED_RPM_RATIO),
                "shared_tpm_ratio": self._safe_ratio(settings.P2P_SHARED_TPM_RATIO),
            },
            "master": {
                "active": runtime_p2p_enabled and is_master_mode,
                "cache_only": runtime_p2p_enabled and is_master_cache_mode,
                "accepts_registrations": runtime_p2p_enabled and settings.P2P_ALLOW_MASTER and (is_master_mode or is_master_cache_mode),
                "dispatch_mode": settings.PROXY_MODE,
                "master_url": settings.P2P_MASTER_URL or None,
                "cluster_name": settings.P2P_CLUSTER_NAME,
                "known_peers_count": len(peers),
                "network_snapshot_file": str(self._network_file),
                "route_ttl_min": settings.P2P_ROUTE_TTL_MIN,
            },
            "limits": {
                "max_client_slots_per_min": settings.P2P_MAX_CLIENT_SLOTS_PER_MIN,
                "max_shared_slots_per_min": settings.P2P_MAX_SHARED_SLOTS_PER_MIN,
                "max_remote_sessions": settings.P2P_MAX_REMOTE_SESSIONS,
                "max_outgoing_sessions": settings.P2P_MAX_OUTGOING_SESSIONS,
                "max_queue_size": settings.P2P_MAX_QUEUE_SIZE,
                "session_timeout_sec": settings.P2P_SESSION_TIMEOUT_SEC,
                "per_peer_rpm_limit": settings.P2P_PER_PEER_RPM_LIMIT,
                "per_target_peer_rpm_limit": settings.P2P_PER_TARGET_PEER_RPM_LIMIT,
                "global_incoming_rpm_limit": settings.P2P_GLOBAL_INCOMING_RPM_LIMIT,
                "global_outgoing_rpm_limit": settings.P2P_GLOBAL_OUTGOING_RPM_LIMIT,
                "heartbeat_interval_sec": settings.P2P_HEARTBEAT_INTERVAL_SEC,
                "peer_stale_after_sec": settings.P2P_PEER_STALE_AFTER_SEC,
            },
            "sessions": sessions,
            "peers": peers,
            "masters": masters,
            "heartbeat": peer_status_summary,
            "network_map": network_map,
            "online_resource_summary": online_resource_summary,
            "routing": {
                "rows": routing_table,
                "total_rows": len(routing_table),
                "online_rows": sum(1 for row in routing_table if row.get("route_status") == "online"),
            },
            "notes": {
                "mvp_stage": True,
                "execution": "Peer transport is still not implemented. This runtime state is for debug/admin visibility and manual MVP testing.",
            },
        }


p2p_service = P2PService()
