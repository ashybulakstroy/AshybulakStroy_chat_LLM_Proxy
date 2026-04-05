# AshybulakStroy AI HUB

Легкий OpenAI-совместимый LLM proxy на FastAPI. Сервис объединяет несколько upstream-провайдеров, умеет работать с `chat/completions`, `embeddings` и `models`, ведет живую телеметрию лимитов и дает две админки:

- основную админку локального proxy
- отдельную P2P debug admin для будущей распределенной сети

## Что уже реализовано

- `/health` — проверка работоспособности сервиса
- `/health/limits` — сводка по лимитам провайдеров
- `/health/limits/live` — фоновое обновление live-лимитов
- `/v1/models` — список моделей
- `/v1/chat/completions` — прокси для LLM chat
- `/v1/embeddings` — прокси для embeddings
- `/admin` — основная админка
- `/admin/p2p` — P2P debug admin

## Основная логика proxy

Сервис работает с OpenAI-compatible upstream API:

- `GET /models`
- `POST /chat/completions`
- `POST /embeddings`

Для LLM-запросов доступны:

- `provider=auto`
- `model=auto`
- `resource_affinity=auto|sticky`

### Auto-маршрутизация

При `provider=auto` и `model=auto` сервис:

1. Строит пул пригодных `provider + model` ресурсов из текущего runtime/admin filter.
2. Исключает ресурсы с ошибками и исчерпанными минутными лимитами.
3. Выбирает более холодный ресурс по сочетанию:
   - нет недавней ошибки
   - есть remaining RPM
   - ресурс использовался реже
   - ресурс использовался позже всех
   - есть бонус за разнообразие провайдеров
4. Применяет `round-robin` только среди равных кандидатов.

### Sticky resource affinity

Если клиент присылает:

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

то proxy старается держать этого клиента на одном и том же внутреннем ресурсе `provider + model`, пока ресурс остается пригодным.

В ответе сервис возвращает служебные поля:

- `_proxy.selected_resource_id`
- `_proxy.resource_affinity`
- `_proxy.sticky_reused`
- `_proxy.client_id`
- `_proxy.eligible_resources`
- `_proxy.selected_policy`

## Block #2 и P2P

В основной админке `Блок №2` — это локальная таблица исполняемых LLM-ресурсов ноды.

В P2P admin `Маршрутизация` — это уже сетевая маршрутная таблица поверх локальных ресурсов:

- с `route_id`
- с `route_status`
- со слотами
- с учетом direct/link-only semantics

## P2P MVP

В репозитории уже есть отдельный P2P MVP-слой для будущих ролей `MASTER` и `PEER`.

Текущий объем MVP:

- роли ноды:
  - `peer`
  - `master`
  - `master_cache`
  - `auto`
- peer registry в памяти
- heartbeat и known peers
- network map
- dispatch preview
- route hashing:
  - `route_id = sha256(api_key + provider + model)[:12]`
- TTL для нерабочих маршрутов:
  - `P2P_ROUTE_TTL_MIN=1440`
- direct/link-only классификация
- P2P logs с префиксом `p2p_...`

### Slots в P2P

Слоты сейчас считаются по простой формуле:

`ceil(P2P_MAX_SHARED_SLOTS_PER_MIN / resources_in_node)`

### Ключевые P2P endpoint-ы

- `/admin/p2p`
- `/admin/p2p/status`
- `/admin/p2p/peers`
- `/admin/p2p/dispatch/preview`

## Конфигурация

Минимально важные переменные:

```env
PORT=8800
ENABLE_PROVIDER_LOG=true
LOG_LEVEL=INFO
PROXY_MODE=LOAD_BALANCE

GROQ_API_KEY=
OPENROUTER_API_KEY=
CEREBRAS_API_KEY=
GEMINI_API_KEY=
SAMBANOVA_API_KEY=
EDENAI_API_KEY=
FIREWORKS_API_KEY=
```

Для P2P:

```env
P2P_ENABLED=false
NODE_MODE=peer
P2P_SCOPE=private
P2P_NODE_NAME=home-node
P2P_ROUTE_TTL_MIN=1440
P2P_MAX_CLIENT_SLOTS_PER_MIN=1
P2P_MAX_SHARED_SLOTS_PER_MIN=5
```

## Запуск

1. Установить зависимости:

```bash
python -m pip install -r requirements.txt
```

2. Настроить `.env`
3. Запустить:

```bash
python run.py
```

После старта полезно проверить:

```bash
curl http://localhost:8800/health
curl http://localhost:8800/health/limits
curl http://localhost:8800/admin
curl http://localhost:8800/admin/p2p
```

## Что дальше

- добавить проверку `response_type` для LLM-запросов
- расширить sticky-affinity TTL и admin visibility
- довести P2P до реального remote execution
- добавить тесты и CI
