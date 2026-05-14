from app import routes


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


def test_429_uses_one_day_resource_quarantine() -> None:
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
    assert classification["invalid_minutes"] == 24 * 60


def test_503_temporary_quarantine_starts_at_60_minutes() -> None:
    assert routes.SERVICE_UNAVAILABLE_QUARANTINE_MINUTES == 60


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
