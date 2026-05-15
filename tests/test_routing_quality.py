import pytest

from app.config import ProviderConfig
from app.router_service import ProviderRouter
from app import routes
from app.providers.cloudflare_provider import CloudflareWorkersAIProvider


def test_runtime_chat_models_ignores_unconfigured_providers(monkeypatch) -> None:
    routes._set_runtime_dispatcher_cache(
        {
            "validated_llm": {
                "data": [
                    {
                        "provider": "groq",
                        "id": "llama-3.1-8b-instant",
                        "category": "llm",
                    },
                    {
                        "provider": "openrouter",
                        "id": "qwen/qwen3.6-plus-preview:free",
                        "category": "llm",
                    },
                ]
            },
            "block_two": {"data": []},
        }
    )
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"groq": object()})
    monkeypatch.setattr(routes.rate_limit_store, "is_provider_quarantined", lambda provider: False)
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)

    models = routes._runtime_chat_models()

    assert [model["provider"] for model in models] == ["groq"]


@pytest.mark.asyncio
async def test_cloudflare_provider_static_models_are_chat_capable() -> None:
    provider = CloudflareWorkersAIProvider(
        provider_name="cloudflare",
        api_key="token",
        api_base="https://api.cloudflare.com/client/v4/accounts/account/ai/v1",
    )

    models = await provider.get_models()

    assert models["data"][0]["id"] == "@cf/meta/llama-3.1-8b-instruct"
    assert models["data"][0]["supports_chat"] is True


def test_provider_router_builds_cloudflare_provider() -> None:
    router = ProviderRouter()
    provider = router._build_provider(
        ProviderConfig(
            "cloudflare",
            "token",
            "https://api.cloudflare.com/client/v4/accounts/account/ai/v1",
        )
    )

    assert isinstance(provider, CloudflareWorkersAIProvider)


def test_runtime_chat_models_includes_ready_routes_when_primary_pools_exist(monkeypatch) -> None:
    routes._set_runtime_dispatcher_cache(
        {
            "validated_llm": {"data": []},
            "block_two": {
                "data": [
                    {
                        "provider": "cerebras",
                        "id": "llama3.1-8b",
                        "category": "llm",
                    }
                ]
            },
            "routes": [
                {
                    "provider": "fireworks",
                    "model_id": "accounts/fireworks/models/glm-5p1",
                    "category": "llm",
                }
            ],
        }
    )
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"cerebras": object(), "fireworks": object()})
    monkeypatch.setattr(routes.rate_limit_store, "is_provider_quarantined", lambda provider: False)
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)

    models = routes._runtime_chat_models()

    assert [(model["provider"], model["id"]) for model in models] == [
        ("cerebras", "llama3.1-8b"),
        ("fireworks", "accounts/fireworks/models/glm-5p1"),
    ]


def test_runtime_chat_models_reclassifies_stale_route_categories(monkeypatch) -> None:
    routes._set_runtime_dispatcher_cache(
        {
            "validated_llm": {"data": []},
            "block_two": {"data": []},
            "routes": [
                {
                    "provider": "gemini",
                    "model_id": "models/gemini-2.5-flash-image",
                    "category": "llm",
                },
                {
                    "provider": "fireworks",
                    "model_id": "accounts/fireworks/models/flux-kontext-pro",
                    "category": "llm",
                },
                {
                    "provider": "fireworks",
                    "model_id": "accounts/fireworks/models/glm-5p1",
                    "category": "llm",
                },
            ],
        }
    )
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"gemini": object(), "fireworks": object()})
    monkeypatch.setattr(routes.rate_limit_store, "is_provider_quarantined", lambda provider: False)
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)

    models = routes._runtime_chat_models()

    assert [(model["provider"], model["id"]) for model in models] == [
        ("fireworks", "accounts/fireworks/models/glm-5p1"),
    ]


def test_known_model_catalog_includes_routes() -> None:
    routes._set_runtime_dispatcher_cache(
        {
            "validated_llm": {"data": []},
            "block_two": {"data": []},
            "routes": [
                {
                    "provider": "fireworks",
                    "model_id": "accounts/fireworks/models/glm-5p1",
                    "category": "llm",
                }
            ],
        }
    )

    known = routes._find_known_model("fireworks", "accounts/fireworks/models/glm-5p1")

    assert known["provider"] == "fireworks"
    assert known["id"] == "accounts/fireworks/models/glm-5p1"


def test_auto_route_falls_back_to_ready_route_when_primary_pools_are_limited(monkeypatch) -> None:
    routes.AUTO_RESOURCE_USAGE.clear()
    routes.CLIENT_RESOURCE_AFFINITY.clear()
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"cerebras": object(), "fireworks": object()})
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)
    monkeypatch.setattr(routes.rate_limit_store, "is_provider_quarantined", lambda provider: False)
    monkeypatch.setattr(
        routes.rate_limit_store,
        "get_snapshot",
        lambda providers: {
            "cerebras": {
                "limits": {"source": "response_headers", "requests": {"minute": {"remaining": 0}, "day": {"remaining": 100}}},
                "quarantine": {"active": False},
            },
            "fireworks": {
                "limits": {"source": "response_headers", "requests": {"minute": {"remaining": 59}, "day": {"remaining": None}}},
                "quarantine": {"active": False},
            },
        },
    )
    routes._set_runtime_dispatcher_cache(
        {
            "validated_llm": {"data": []},
            "block_two": {"data": [{"provider": "cerebras", "id": "llama3.1-8b", "category": "llm"}]},
            "routes": [{"provider": "fireworks", "model_id": "accounts/fireworks/models/glm-5p1", "category": "llm"}],
        }
    )

    selected = routes._pick_auto_route(
        routes._runtime_chat_models(),
        routes.ChatCompletionRequest(
            provider="auto",
            model="auto",
            messages=[{"role": "user", "content": "ping"}],
        ),
    )

    assert selected is not None
    assert selected["provider"] == "fireworks"


@pytest.mark.asyncio
async def test_no_resource_routes_are_quarantined_with_no_resource_reason(monkeypatch) -> None:
    arrested = []

    async def fake_arrest(provider_name, model_id, **kwargs):
        item = {"provider": provider_name, "model": model_id, **kwargs}
        arrested.append(item)
        return item

    async def fake_sync(reason):
        return {"status": "ok", "reason": reason}

    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"cerebras": object()})
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)
    monkeypatch.setattr(routes.rate_limit_store, "get_snapshot", lambda providers: {
        "cerebras": {
            "limits": {
                "source": "response_headers",
                "requests": {
                    "minute": {"remaining": 0, "reset_seconds": 125},
                    "day": {"remaining": 100},
                },
                "tokens": {"minute": {"remaining": 1000}},
            },
            "quarantine": {"active": False},
        }
    })
    monkeypatch.setattr(routes, "_arrest_invalid_resource", fake_arrest)
    monkeypatch.setattr(routes, "_sync_p2p_route_catalog", fake_sync)

    result = await routes._arrest_no_resource_routes(
        [{"provider": "cerebras", "id": "llama3.1-8b", "category": "llm"}],
        routes.ChatCompletionRequest(
            provider="auto",
            model="llama3.1-8b",
            messages=[{"role": "user", "content": "ping"}],
        ),
    )

    assert result == arrested
    assert arrested[0]["provider"] == "cerebras"
    assert arrested[0]["model"] == "llama3.1-8b"
    assert arrested[0]["reason"] == "no_resource"
    assert arrested[0]["source"] == "limit_exhausted"
    assert arrested[0]["invalid_minutes"] == 3
    assert arrested[0]["blocking"] is True


def test_auto_route_unavailable_detail_reports_no_resource(monkeypatch) -> None:
    routes._set_runtime_dispatcher_cache(
        {
            "validated_llm": {"data": []},
            "block_two": {"data": [{"provider": "cerebras", "id": "llama3.1-8b", "category": "llm"}]},
            "routes": [],
        }
    )
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"cerebras": object()})
    monkeypatch.setattr(routes, "_find_invalid_resource", lambda provider, model_id: {})
    monkeypatch.setattr(routes, "_resolve_local_route_id", lambda provider, model_id: "route-id")
    monkeypatch.setattr(routes.rate_limit_store, "get_snapshot", lambda providers: {
        "cerebras": {
            "last_status_code": 200,
            "limits": {
                "source": "response_headers",
                "requests": {
                    "minute": {"remaining": 0},
                    "day": {"remaining": 2394},
                },
                "tokens": {"minute": {"remaining": 26122}},
            },
            "quarantine": {"active": False},
        }
    })

    status_code, detail = routes._auto_route_unavailable_detail(
        routes.ChatCompletionRequest(
            provider="auto",
            model="llama3.1-8b",
            messages=[{"role": "user", "content": "ping"}],
        )
    )

    assert status_code == 409
    assert detail["routes"][0]["status"] == "no_resource"
    assert detail["routes"][0]["rpm_remaining"] == 0


def test_auto_route_unavailable_detail_includes_no_resource_quarantine_reason(monkeypatch) -> None:
    routes._set_runtime_dispatcher_cache(
        {
            "validated_llm": {"data": []},
            "block_two": {"data": [{"provider": "cerebras", "id": "llama3.1-8b", "category": "llm"}]},
            "routes": [],
        }
    )
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"cerebras": object()})
    monkeypatch.setattr(routes, "_find_invalid_resource", lambda provider, model_id: {
        "reason": "no_resource",
        "status_code": None,
        "invalid_until": "2026-05-15T01:25:00+00:00",
    })
    monkeypatch.setattr(routes, "_resolve_local_route_id", lambda provider, model_id: "route-id")
    monkeypatch.setattr(routes.rate_limit_store, "get_snapshot", lambda providers: {
        "cerebras": {
            "last_status_code": 200,
            "limits": {"requests": {"minute": {"remaining": 0}, "day": {"remaining": 2394}}},
            "quarantine": {"active": False},
        }
    })

    status_code, detail = routes._auto_route_unavailable_detail(
        routes.ChatCompletionRequest(
            provider="auto",
            model="llama3.1-8b",
            messages=[{"role": "user", "content": "ping"}],
        )
    )

    assert status_code == 409
    assert detail["routes"][0]["status"] == "resource_quarantined"
    assert detail["routes"][0]["reason"] == "no_resource"


def test_any_40x_resource_error_is_quarantinable() -> None:
    classification = routes._classify_resource_error(
        [
            {
                "provider": "groq",
                "status_code": 401,
                "detail": '{"error":{"message":"Invalid API Key"}}',
            }
        ]
    )

    assert classification["action"] == "invalid_resource"
    assert classification["retry_auto"] is True
    assert classification["invalid_minutes"] == 24 * 60


def test_429_uses_one_hour_resource_quarantine() -> None:
    classification = routes._classify_resource_error(
        [
            {
                "provider": "cerebras",
                "status_code": 429,
                "detail": '{"code":"queue_exceeded"}',
            }
        ]
    )

    assert classification["action"] == "invalid_resource"
    assert classification["invalid_minutes"] == 60


def test_503_temporary_quarantine_starts_at_60_minutes() -> None:
    assert routes.SERVICE_UNAVAILABLE_QUARANTINE_MINUTES == 60


def test_503_model_maintenance_has_specific_resource_reason() -> None:
    reason = routes._temporary_error_reason(
        503,
        "The requested model (DeepSeek-V3.2) is currently undergoing maintenance. It will be back online shortly.",
    )

    assert reason.startswith("model_maintenance:")
    assert "DeepSeek-V3.2" in reason


@pytest.mark.asyncio
async def test_probe_failed_resource_quarantine_uses_failed_model(monkeypatch) -> None:
    applied = []

    async def fake_apply(model_id, attempted):
        applied.append((model_id, attempted))

    monkeypatch.setattr(routes, "_apply_attempted_provider_quarantine", fake_apply)

    await routes._apply_probe_failed_resource_quarantine(
        [
            {
                "provider": "sambanova",
                "model": "DeepSeek-V3.2",
                "status": "error",
                "status_code": 503,
                "detail": "The requested model is currently undergoing maintenance.",
            },
            {
                "provider": "gemini",
                "model": "",
                "status": "error",
                "status_code": 429,
                "detail": "quota",
            },
        ]
    )

    assert applied == [
        (
            "DeepSeek-V3.2",
            [
                {
                    "provider": "sambanova",
                    "model": "DeepSeek-V3.2",
                    "status": "error",
                    "status_code": 503,
                    "detail": "The requested model is currently undergoing maintenance.",
                }
            ],
        )
    ]


def test_auto_route_keeps_provider_with_recent_error_as_fallback(monkeypatch) -> None:
    routes.AUTO_RESOURCE_USAGE.clear()
    routes.CLIENT_RESOURCE_AFFINITY.clear()
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"cerebras": object()})
    monkeypatch.setattr(
        routes.rate_limit_store,
        "get_snapshot",
        lambda providers: {
            "cerebras": {
                "last_error": {"status_code": 503},
                "limits": {"source": "response_headers", "requests": {"minute": {"remaining": 10}, "day": {"remaining": 100}}},
                "quarantine": {"active": False},
            }
        },
    )
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)

    selected = routes._pick_auto_route(
        [{"provider": "cerebras", "id": "llama3.1-8b", "category": "llm"}],
        routes.ChatCompletionRequest(
            provider="auto",
            model="auto",
            messages=[{"role": "user", "content": "ping"}],
        ),
    )

    assert selected is not None
    assert selected["provider"] == "cerebras"


def test_auto_route_uses_unknown_limit_resource_as_last_resort(monkeypatch) -> None:
    routes.AUTO_RESOURCE_USAGE.clear()
    routes.CLIENT_RESOURCE_AFFINITY.clear()
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"sambanova": object()})
    monkeypatch.setattr(
        routes.rate_limit_store,
        "get_snapshot",
        lambda providers: {
            "sambanova": {
                "limits": {},
                "quarantine": {"active": False},
            }
        },
    )
    monkeypatch.setattr(routes, "_estimated_provider_limits", lambda provider: (-1, -1))
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)

    selected = routes._pick_auto_route(
        [{"provider": "sambanova", "id": "DeepSeek-V3.1", "category": "llm"}],
        routes.ChatCompletionRequest(
            provider="auto",
            model="auto",
            messages=[{"role": "user", "content": "ping"}],
        ),
    )

    assert selected is not None
    assert selected["provider"] == "sambanova"


def test_auto_route_skips_estimated_limit_exhausted_resource(monkeypatch) -> None:
    routes.AUTO_RESOURCE_USAGE.clear()
    routes.CLIENT_RESOURCE_AFFINITY.clear()
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"cerebras": object()})
    monkeypatch.setattr(
        routes.rate_limit_store,
        "get_snapshot",
        lambda providers: {
            "cerebras": {
                "limits": {},
                "quarantine": {"active": False},
            }
        },
    )
    monkeypatch.setattr(routes, "_estimated_provider_limits", lambda provider: (0, 100))
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)

    selected = routes._pick_auto_route(
        [{"provider": "cerebras", "id": "llama3.1-8b", "category": "llm"}],
        routes.ChatCompletionRequest(
            provider="auto",
            model="auto",
            messages=[{"role": "user", "content": "ping"}],
        ),
    )

    assert selected is None


def test_auto_affinity_does_not_reuse_existing_sticky_binding(monkeypatch) -> None:
    routes.AUTO_RESOURCE_USAGE.clear()
    routes.CLIENT_RESOURCE_AFFINITY.clear()
    bound_at_ts = routes._utc_now().timestamp()
    routes.CLIENT_RESOURCE_AFFINITY["law-kz-app"] = {
        "resource_id": "sambanova::Meta-Llama-3.3-70B-Instruct",
        "provider": "sambanova",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "bound_at_ts": bound_at_ts,
    }
    monkeypatch.setattr(routes.settings, "get_provider_configs", lambda: {"sambanova": object()})
    monkeypatch.setattr(
        routes.rate_limit_store,
        "get_snapshot",
        lambda providers: {
            "sambanova": {
                "limits": {"source": "response_headers", "requests": {"minute": {"remaining": 10}, "day": {"remaining": 100}}},
                "quarantine": {"active": False},
            }
        },
    )
    monkeypatch.setattr(routes, "_is_invalid_resource", lambda provider, model_id: False)

    selected = routes._pick_auto_route(
        [{"provider": "sambanova", "id": "Meta-Llama-3.3-70B-Instruct", "category": "llm"}],
        routes.ChatCompletionRequest(
            provider="auto",
            model="auto",
            resource_affinity="auto",
            metadata={"client_id": "law-kz-app"},
            messages=[{"role": "user", "content": "ping"}],
        ),
    )

    assert selected is not None
    assert selected["selection_policy"] == "coldest_eligible_round_robin"
    assert selected["sticky_reused"] is False
    assert routes.CLIENT_RESOURCE_AFFINITY["law-kz-app"]["bound_at_ts"] == bound_at_ts
