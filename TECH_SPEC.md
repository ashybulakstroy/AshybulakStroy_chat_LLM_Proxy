# Техническое задание: AshybulakStroy AI HUB

## Цель

Построить OpenAI-совместимый LLM proxy, который:

- принимает унифицированные API-запросы
- маршрутизирует их к нескольким upstream-провайдерам
- показывает живое состояние ресурсов в админке
- служит основой для будущей P2P-сети

## Основные функции

1. LLM proxy
   - `/v1/chat/completions`
   - `/v1/embeddings`
   - `/v1/models`

2. Мультипровайдерность
   - Groq
   - OpenRouter
   - Cerebras
   - Gemini
   - SambaNova
   - EdenAI
   - Fireworks

3. Живая телеметрия
   - live-limit probe
   - remaining RPM / RPD / TPM
   - last error
   - last observed timestamps

4. Основная админка
   - обзор по сервису
   - Block #2 с локальными LLM-ресурсами
   - блок рекомендаций
   - блок истории proxy-сессий

5. P2P debug admin
   - network map
   - known peers
   - routing table
   - dispatch preview

## Текущая архитектура

### Локальный proxy

- `app/main.py` — старт FastAPI
- `app/routes.py` — HTTP endpoints и runtime orchestration
- `app/router_service.py` — dispatch к upstream providers
- `app/providers/openai_provider.py` — OpenAI-compatible transport
- `app/rate_limits.py` — live rate-limit state
- `app/admin_ui.py` — основная админка

### P2P MVP

- `app/p2p_service.py` — P2P runtime state и route logic
- `app/p2p_admin_ui.py` — P2P debug admin

## Логика локального выбора LLM-ресурса

### Старый слой

Старый слой сохраняется как фильтр пригодных ресурсов:

- validation
- live limits
- last error
- runtime/admin filtering

### Новый слой

Новый слой работает поверх уже пригодных ресурсов.

Для `provider=auto` и `model=auto`:

1. Строится пул пригодных `provider + model`
2. Отсекаются ресурсы:
   - с недавней ошибкой
   - без remaining RPM
3. Применяется cold-resource scheduling:
   - меньше недавних вызовов лучше
   - более старое последнее использование лучше
   - разнообразие провайдеров лучше
4. `round-robin` используется только среди равных кандидатов

## Sticky affinity

В `ChatCompletionRequest` добавлено поле:

```json
{
  "resource_affinity": "auto | sticky"
}
```

Если клиент передает:

```json
{
  "provider": "auto",
  "model": "auto",
  "resource_affinity": "sticky",
  "metadata": {
    "client_id": "user-123"
  }
}
```

то сервис:

- сохраняет внутреннюю привязку `client_id -> resource`
- повторно использует тот же ресурс при следующем запросе
- перепривязывает клиента, если старый ресурс перестал быть пригодным

## Block #2

Block #2 основной админки — это:

`Local Executable LLM Resource Inventory`

То есть локальная таблица ресурсов исполнения:

- каждая строка = `provider + model`
- каждый такой ресурс может принять локальный LLM-запрос

## P2P route model

P2P использует отдельную сетевую сущность маршрута:

- `route_id = sha256(api_key + provider + model)[:12]`
- `route_status`
- `direct_provider_access`
- `link-only`
- `slots`

### TTL

Для нерабочих маршрутов:

- `P2P_ROUTE_TTL_MIN = 1440`

После истечения TTL невалидный маршрут удаляется из P2P route registry.

### Slots

Слоты считаются как:

`ceil(P2P_MAX_SHARED_SLOTS_PER_MIN / resources_in_node)`

## Ограничения текущего MVP

- P2P remote execution еще не реализован
- peer authentication еще не реализован
- signal server и mDNS еще не реализованы
- sticky-affinity сейчас опирается на `metadata.client_id`

## Следующие шаги

1. Добавить проверку `response_type` (`json`, `text`, `audio`, `video`)
2. При mismatch response type помечать ресурс как ошибочный и переходить к следующему
3. Добавить TTL/наблюдаемость для sticky bindings
4. Довести P2P до полноценного remote execution
5. Написать автотесты на scheduler и affinity
