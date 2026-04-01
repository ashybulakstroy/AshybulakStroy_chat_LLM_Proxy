from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_FALLBACK_RPM = 1
LIMITS_FILE = Path(__file__).resolve().parent.parent / "provider_limits.json"
SNAPSHOT_FILE = Path(__file__).resolve().parent.parent / "rate_limits_snapshot.json"


def _to_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_reset_seconds(value: str | None) -> int | None:
    if value is None or value == "":
        return None

    normalized = value.strip().lower()
    if normalized.endswith("ms"):
        milliseconds = _to_int(normalized[:-2])
        return None if milliseconds is None else max(0, milliseconds // 1000)
    if normalized.endswith("s"):
        return _to_int(normalized[:-1])
    if normalized.endswith("m"):
        minutes = _to_int(normalized[:-1])
        return None if minutes is None else minutes * 60
    if normalized.endswith("h"):
        hours = _to_int(normalized[:-1])
        return None if hours is None else hours * 3600

    raw_value = _to_int(normalized)
    if raw_value is None:
        return None

    # Some providers return an epoch timestamp instead of a duration.
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    if raw_value > now_epoch:
        return max(0, raw_value - now_epoch)

    return raw_value


def _to_reset_at(value: str | None) -> str | None:
    if value is None or value == "":
        return None

    reset_seconds = _to_reset_seconds(value)
    if reset_seconds is None:
        return None

    now = datetime.now(timezone.utc)
    return datetime.fromtimestamp(now.timestamp() + reset_seconds, tz=timezone.utc).isoformat()


@dataclass
class WindowLimit:
    limit: int | None = None
    remaining: int | None = None
    reset_seconds: int | None = None
    reset_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_seconds": self.reset_seconds,
            "reset_at": self.reset_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "WindowLimit":
        payload = payload or {}
        return cls(
            limit=payload.get("limit"),
            remaining=payload.get("remaining"),
            reset_seconds=payload.get("reset_seconds"),
            reset_at=payload.get("reset_at"),
        )


@dataclass
class ProviderLimitState:
    provider: str
    requests_minute: WindowLimit | None = None
    requests_hour: WindowLimit | None = None
    requests_day: WindowLimit | None = None
    tokens_minute: WindowLimit | None = None
    tokens_hour: WindowLimit | None = None
    tokens_day: WindowLimit | None = None
    last_status_code: int | None = None
    last_error: str | None = None
    headers_seen: bool = False
    last_observed_at: str | None = None

    def __post_init__(self) -> None:
        self.requests_minute = self.requests_minute or WindowLimit()
        self.requests_hour = self.requests_hour or WindowLimit()
        self.requests_day = self.requests_day or WindowLimit()
        self.tokens_minute = self.tokens_minute or WindowLimit()
        self.tokens_hour = self.tokens_hour or WindowLimit()
        self.tokens_day = self.tokens_day or WindowLimit()

    def as_dict(self) -> dict[str, Any]:
        if self.headers_seen:
            return {
                "provider": self.provider,
                "limits": {
                    "requests": {
                        "minute": self.requests_minute.as_dict(),
                        "hour": self.requests_hour.as_dict(),
                        "day": self.requests_day.as_dict(),
                    },
                    "tokens": {
                        "minute": self.tokens_minute.as_dict(),
                        "hour": self.tokens_hour.as_dict(),
                        "day": self.tokens_day.as_dict(),
                    },
                    # Backward-compatible shortcuts used by the old payload.
                    "rpm": self.requests_minute.limit,
                    "rpm_remaining": self.requests_minute.remaining,
                    "rpm_reset": self.requests_minute.reset_seconds,
                    "rpd": self.requests_day.limit,
                    "rpd_remaining": self.requests_day.remaining,
                    "rpd_reset": self.requests_day.reset_seconds,
                    "source": "response_headers",
                },
                "last_observed_at": self.last_observed_at,
                "last_status_code": self.last_status_code,
                "last_error": self.last_error,
            }

        return {
            "provider": self.provider,
            "limits": {
                "requests": {
                    "minute": {
                        "limit": DEFAULT_FALLBACK_RPM,
                        "remaining": None,
                        "reset_seconds": None,
                        "reset_at": None,
                    },
                    "hour": {"limit": None, "remaining": None, "reset_seconds": None, "reset_at": None},
                    "day": {"limit": None, "remaining": None, "reset_seconds": None, "reset_at": None},
                },
                "tokens": {
                    "minute": {"limit": None, "remaining": None, "reset_seconds": None, "reset_at": None},
                    "hour": {"limit": None, "remaining": None, "reset_seconds": None, "reset_at": None},
                    "day": {"limit": None, "remaining": None, "reset_seconds": None, "reset_at": None},
                },
                "rpm": DEFAULT_FALLBACK_RPM,
                "rpm_remaining": None,
                "rpm_reset": None,
                "rpd": None,
                "rpd_remaining": None,
                "rpd_reset": None,
                "source": "fallback_default",
                "note": "Provider did not expose rate-limit headers; using safe fallback of 1 RPM.",
            },
            "last_observed_at": self.last_observed_at,
            "last_status_code": self.last_status_code,
            "last_error": self.last_error,
        }

    @classmethod
    def from_snapshot_dict(cls, payload: dict[str, Any]) -> "ProviderLimitState":
        limits = payload.get("limits", {})
        requests = limits.get("requests", {})
        tokens = limits.get("tokens", {})
        source = limits.get("source")
        return cls(
            provider=payload["provider"],
            requests_minute=WindowLimit.from_dict(requests.get("minute")),
            requests_hour=WindowLimit.from_dict(requests.get("hour")),
            requests_day=WindowLimit.from_dict(requests.get("day")),
            tokens_minute=WindowLimit.from_dict(tokens.get("minute")),
            tokens_hour=WindowLimit.from_dict(tokens.get("hour")),
            tokens_day=WindowLimit.from_dict(tokens.get("day")),
            last_status_code=payload.get("last_status_code"),
            last_error=payload.get("last_error"),
            headers_seen=source == "response_headers",
            last_observed_at=payload.get("last_observed_at"),
        )


class RateLimitStore:
    def __init__(self) -> None:
        self._state: dict[str, ProviderLimitState] = {}
        self.last_probe_at: str | None = None
        self.last_probe_summary: dict[str, Any] = {"successful": [], "failed": []}

    def ensure_provider(self, provider: str) -> None:
        self._state.setdefault(provider, ProviderLimitState(provider=provider))

    def load_snapshot(self, providers: list[str]) -> None:
        if not SNAPSHOT_FILE.exists():
            self._create_snapshot_file(providers)
            return

        try:
            payload = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._create_snapshot_file(providers)
            return

        self.last_probe_at = payload.get("last_probe_at")
        self.last_probe_summary = payload.get("last_probe_summary", {"successful": [], "failed": []})
        snapshot_state = payload.get("state", {})

        for provider in providers:
            provider_payload = snapshot_state.get(provider)
            if provider_payload:
                self._state[provider] = ProviderLimitState.from_snapshot_dict(provider_payload)
            else:
                self.ensure_provider(provider)

    def save_snapshot(self, providers: list[str] | None = None) -> None:
        if providers is None:
            providers = list(self._state.keys())
        payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "last_probe_at": self.last_probe_at,
            "last_probe_summary": self.last_probe_summary,
            "state": self.get_snapshot(providers),
        }
        try:
            SNAPSHOT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            return

    def update_from_response(self, provider: str, headers: dict[str, str], status_code: int) -> None:
        state = self._state.setdefault(provider, ProviderLimitState(provider=provider))
        state.last_status_code = status_code
        state.last_error = None
        state.last_observed_at = datetime.now(timezone.utc).isoformat()

        normalized_headers = {key.lower(): value for key, value in headers.items()}

        observed = [
            self._update_window(
                state.requests_minute,
                normalized_headers,
                limit_keys=["x-ratelimit-limit-requests-minute", "x-ratelimit-limit-requests"],
                remaining_keys=["x-ratelimit-remaining-requests-minute", "x-ratelimit-remaining-requests"],
                reset_keys=["x-ratelimit-reset-requests-minute", "x-ratelimit-reset-requests"],
            ),
            self._update_window(
                state.requests_hour,
                normalized_headers,
                limit_keys=["x-ratelimit-limit-requests-hour"],
                remaining_keys=["x-ratelimit-remaining-requests-hour"],
                reset_keys=["x-ratelimit-reset-requests-hour"],
            ),
            self._update_window(
                state.requests_day,
                normalized_headers,
                limit_keys=["x-ratelimit-limit-requests-day"],
                remaining_keys=["x-ratelimit-remaining-requests-day"],
                reset_keys=["x-ratelimit-reset-requests-day"],
            ),
            self._update_window(
                state.tokens_minute,
                normalized_headers,
                limit_keys=["x-ratelimit-limit-tokens-minute", "x-ratelimit-limit-tokens"],
                remaining_keys=["x-ratelimit-remaining-tokens-minute", "x-ratelimit-remaining-tokens"],
                reset_keys=["x-ratelimit-reset-tokens-minute", "x-ratelimit-reset-tokens"],
            ),
            self._update_window(
                state.tokens_hour,
                normalized_headers,
                limit_keys=["x-ratelimit-limit-tokens-hour"],
                remaining_keys=["x-ratelimit-remaining-tokens-hour"],
                reset_keys=["x-ratelimit-reset-tokens-hour"],
            ),
            self._update_window(
                state.tokens_day,
                normalized_headers,
                limit_keys=["x-ratelimit-limit-tokens-day"],
                remaining_keys=["x-ratelimit-remaining-tokens-day"],
                reset_keys=["x-ratelimit-reset-tokens-day"],
            ),
        ]

        if any(observed):
            state.headers_seen = True
            self._sync_estimated_limits_file(provider, state)
        self.save_snapshot()

    def record_error(self, provider: str, status_code: int | None, detail: str) -> None:
        state = self._state.setdefault(provider, ProviderLimitState(provider=provider))
        state.last_status_code = status_code
        state.last_error = detail
        state.last_observed_at = datetime.now(timezone.utc).isoformat()
        self.save_snapshot()

    def record_probe_summary(self, successful: list[str], failed: list[dict[str, Any]]) -> None:
        self.last_probe_at = datetime.now(timezone.utc).isoformat()
        self.last_probe_summary = {
            "successful": successful,
            "failed": failed,
        }
        self.save_snapshot()

    def get_snapshot(self, providers: list[str]) -> dict[str, Any]:
        for provider in providers:
            self.ensure_provider(provider)
        return {provider: self._state[provider].as_dict() for provider in providers}

    def get_health_payload(self, providers: list[str]) -> dict[str, Any]:
        limits = self.get_snapshot(providers)
        return {
            "providers_count": len(providers),
            "startup_probe": {
                "last_probe_at": self.last_probe_at,
                "summary": self.last_probe_summary,
            },
            "limits": limits,
        }

    @staticmethod
    def _first_present(headers: dict[str, str], keys: list[str]) -> str | None:
        for key in keys:
            value = headers.get(key)
            if value not in (None, ""):
                return value
        return None

    def _update_window(
        self,
        window: WindowLimit,
        headers: dict[str, str],
        limit_keys: list[str],
        remaining_keys: list[str],
        reset_keys: list[str],
    ) -> bool:
        limit_raw = self._first_present(headers, limit_keys)
        remaining_raw = self._first_present(headers, remaining_keys)
        reset_raw = self._first_present(headers, reset_keys)

        observed = False

        limit = _to_int(limit_raw)
        if limit is not None:
            window.limit = limit
            observed = True

        remaining = _to_int(remaining_raw)
        if remaining is not None:
            window.remaining = remaining
            observed = True

        reset_seconds = _to_reset_seconds(reset_raw)
        if reset_seconds is not None:
            window.reset_seconds = reset_seconds
            observed = True

        reset_at = _to_reset_at(reset_raw)
        if reset_at is not None:
            window.reset_at = reset_at
            observed = True

        return observed

    def _sync_estimated_limits_file(self, provider: str, state: ProviderLimitState) -> None:
        if not LIMITS_FILE.exists():
            return

        try:
            payload = json.loads(LIMITS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        providers = payload.setdefault("providers", {})
        provider_data = providers.setdefault(
            provider,
            {
                "estimated_rpm": None,
                "estimated_rpd": None,
                "tier": "observed_live",
                "notes": "Auto-synced from live provider headers.",
            },
        )

        changed = False

        if state.requests_minute.limit is not None and provider_data.get("estimated_rpm") != state.requests_minute.limit:
            provider_data["estimated_rpm"] = state.requests_minute.limit
            changed = True

        if state.requests_day.limit is not None and provider_data.get("estimated_rpd") != state.requests_day.limit:
            provider_data["estimated_rpd"] = state.requests_day.limit
            changed = True

        if changed:
            provider_data["tier"] = "observed_live"
            provider_data["notes"] = "Auto-synced from live provider headers."
            payload["snapshot_date"] = datetime.now(timezone.utc).date().isoformat()
            try:
                LIMITS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except OSError:
                return

    def _create_snapshot_file(self, providers: list[str]) -> None:
        for provider in providers:
            self.ensure_provider(provider)
        self.save_snapshot(providers)


rate_limit_store = RateLimitStore()
