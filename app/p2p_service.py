from __future__ import annotations

import json
import logging
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

    def _local_direct_provider_access(self, node_mode: str | None = None) -> bool:
        effective_mode = str(node_mode or self._runtime_node_mode).strip().lower()
        return bool(self._local_provider_names()) and effective_mode != "master_cache"

    def _should_persist_network(self, runtime_p2p_enabled: bool, runtime_node_mode: str) -> bool:
        return runtime_p2p_enabled and runtime_node_mode in {"master", "master_cache"}

    def _parse_csv_list(self, value: str | None) -> list[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _to_bool(self, value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _peer_status(self, peer: dict[str, Any]) -> str:
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
        normalized["accept_remote_tasks"] = self._to_bool(peer.get("accept_remote_tasks"), True)
        normalized["share_capacity"] = self._to_bool(peer.get("share_capacity"), True)
        normalized["direct_provider_access"] = self._to_bool(peer.get("direct_provider_access"), True)
        normalized["supports_chat"] = self._to_bool(peer.get("supports_chat"), True)
        normalized["supports_embeddings"] = self._to_bool(peer.get("supports_embeddings"), True)
        normalized["providers"] = list(peer.get("providers") or [])
        normalized["models"] = list(peer.get("models") or [])
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
                "note": str(note).strip() or None,
                "accept_remote_tasks": bool(accept_remote_tasks),
                "share_capacity": bool(share_capacity),
                "direct_provider_access": bool(direct_provider_access),
                "supports_chat": bool(supports_chat),
                "supports_embeddings": bool(supports_embeddings),
                "providers": self._parse_csv_list(providers),
                "models": self._parse_csv_list(models),
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
        self.save_network_snapshot()
        return dict(peer)

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

        status = self.get_status()
        payload = {
            "saved_at": self._now().isoformat(),
            "node": status.get("node", {}),
            "master": status.get("master", {}),
            "network_map": status.get("network_map", {}),
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
        loaded_count = 0
        with self._lock:
            self._known_peers = {}
            for peer in peers:
                if not isinstance(peer, dict):
                    continue
                peer_id = str(peer.get("peer_id") or "").strip()
                if not peer_id:
                    continue
                self._known_peers[peer_id] = dict(peer)
                loaded_count += 1

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

    async def send_local_heartbeat(self, *, master_url: str | None = None, reason: str = "manual") -> dict[str, Any]:
        target_master = str(master_url or settings.P2P_MASTER_URL or "").strip().rstrip("/")
        if not target_master:
            return {"status": "skipped", "reason": "missing_master_url"}
        if not self._runtime_p2p_enabled:
            return {"status": "skipped", "reason": "p2p_disabled"}

        providers = self._local_provider_names()
        direct_provider_access = self._local_direct_provider_access()
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
            "models": "",
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
        with self._lock:
            sessions = asdict(self._sessions)
            peers = [self._normalize_peer(dict(item)) for item in self._known_peers.values()]
            runtime_p2p_enabled = self._runtime_p2p_enabled
            runtime_node_mode = self._runtime_node_mode

        peers.sort(key=lambda item: (item.get("node_name") or "", item.get("peer_id") or ""))
        peer_status_summary = {
            "total_known_peers": len(peers),
            "online": sum(1 for peer in peers if self._peer_status(peer) == "online"),
            "stale": sum(1 for peer in peers if self._peer_status(peer) == "stale"),
            "avg_health_score": round(sum(peer.get("health_score", 0.0) for peer in peers) / len(peers), 3) if peers else 0.0,
        }

        self._ensure_runtime_events_logged(peers, runtime_p2p_enabled, runtime_node_mode)

        is_master_mode = runtime_node_mode == "master"
        is_master_cache_mode = runtime_node_mode == "master_cache"
        provider_configs = settings.get_provider_configs()
        local_direct_provider_access = self._local_direct_provider_access(runtime_node_mode)
        local_provider_count = 0
        direct_provider_links: set[str] = set()
        local_role = "master" if is_master_mode else "master_cache" if is_master_cache_mode else runtime_node_mode
        if runtime_p2p_enabled and is_master_mode and local_direct_provider_access:
            local_provider_count = len(provider_configs)
            for provider_name in provider_configs.keys():
                direct_provider_links.add(f"{settings.P2P_NODE_NAME or 'master-node'}::{provider_name}")

        master_count = 1 if runtime_p2p_enabled and is_master_mode else 0
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

        network_map = {
            "master_nodes": {
                "count": master_count,
                "direct_provider_count": local_provider_count,
                "direct_provider_access": local_direct_provider_access,
                "role": local_role,
            },
            "peer_nodes": {
                "count": peer_count,
                "direct_provider_count": peer_provider_count,
                "direct_peer_count": direct_peer_count,
                "link_only_peer_count": link_only_peer_count,
            },
            "routes": {
                "direct_provider_links": len(direct_provider_links),
            },
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
            },
            "limits": {
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
            "heartbeat": peer_status_summary,
            "network_map": network_map,
            "notes": {
                "mvp_stage": True,
                "execution": "Peer transport is still not implemented. This runtime state is for debug/admin visibility and manual MVP testing.",
            },
        }


p2p_service = P2PService()
