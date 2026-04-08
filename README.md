# AshybulakStroy AI HUB

OpenAI-compatible LLM proxy on FastAPI.

Сервис объединяет несколько upstream-провайдеров, выполняет `chat/completions`, `embeddings` и `models`, ведет живую телеметрию лимитов, показывает локальную админку и отдельную P2P debug-админку.

## Реализовано

- `GET /health`
- `GET /health/limits`
- `POST /health/limits/live`
- `GET /health/limits/live/status`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`
- `GET /admin`
- `GET /admin/p2p`

## Upstream API

Прокси сейчас использует только OpenAI-compatible upstream endpoints:

- `GET /models`
- `POST /chat/completions`
- `POST /embeddings`

Audio / image / video upstream calls в текущем коде не реализованы как отдельные transport-ветки.

## Основная логика LLM proxy

### Auto-маршрутизация

Если клиент передает:

- `provider = auto`
- `model = auto`

то сервис строит локальный пул пригодных ресурсов `provider + model` и выбирает ресурс по холодности, а не по жесткому фиксированному порядку.

Текущий порядок отбора для `auto`:

1. пригодность ресурса
2. отсутствие недавней ошибки
3. наличие remaining RPM
4. более старое последнее использование
5. меньшее число недавних запросов
6. бонус за разнообразие провайдеров
7. `round-robin` только среди равных кандидатов

### Sticky affinity

В `ChatCompletionRequest` поддерживается:

```json
{
  "resource_affinity": "auto | sticky"
}
```

Если клиент использует:

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

то сервис старается удерживать этого клиента на одном и том же внутреннем ресурсе, пока ресурс остается пригодным.

### Response type validation

В `ChatCompletionRequest` поддерживается:

```json
{
  "response_type": "json | text | audio | video"
}
```

По умолчанию:

- `response_type = json`

После ответа upstream сервис проверяет соответствие фактического типа ответа требуемому типу.

Если ответ не соответствует:

- при `auto` текущий ресурс помечается как ошибочный
- ресурс попадает в исключение для текущего запроса
- диспетчер пробует следующий ресурс

Если исчерпаны все кандидаты:

- возвращается ошибка `response_type_mismatch_exhausted`

## Invalid resources

Сервис ведет локальный список ошибочных ресурсов в:

- `invalid_resources.json`

Этот список используется для:

- исключения плохих `provider + model` из локального выбора
- временной quarantine логики
- отображения в `Блоке №6` основной админки
- фильтрации локального route catalog для P2P

## Админка

### Основная админка `/admin`

Основные блоки:

- `Блок №1` — сводка сервиса
- `Блок №1.5` — активные proxy-сессии
- `Блок №2` — локальный inventory моделей и лимитов
- `Блок №3` — рекомендации
- `Блок №4` — отдельная LLM validation
- `Блок №5` — история proxy-сессий
- `Блок №6` — invalid resources

Карточка `Модели` в `Блоке №1` должна трактоваться как локальный union:

- `Block #2`
- `Block #4`

с дедупликацией по `provider + model`.

### P2P debug admin `/admin/p2p`

Показывает:

- runtime state ноды
- network map
- known peers
- routing table
- dispatch preview
- route ids
- route TTL / pruning

## P2P MVP

Текущий P2P слой уже реализует:

- режимы ноды:
  - `peer`
  - `master`
  - `master_cache`
  - `auto`
- peer registry
- heartbeat
- snapshot сети
- route hashing
- route TTL cleanup
- direct / link-only semantics
- P2P routing table
- P2P admin UI

### Route ID

Для прямых локальных маршрутов используется:

`route_id = sha256(api_key + provider + model)[:12]`

### TTL

Для нерабочих маршрутов:

- `P2P_ROUTE_TTL_MIN = 1440`

После истечения TTL невалидный маршрут удаляется из P2P route registry.

### Slots

Слоты в P2P routing table сейчас считаются так:

`ceil(P2P_MAX_SHARED_SLOTS_PER_MIN / resources_in_node)`

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

Проверка:

```bash
curl http://localhost:8800/health
curl http://localhost:8800/health/limits
curl http://localhost:8800/admin
curl http://localhost:8800/admin/p2p
```

## Статус проекта

Сервис рабочий как локальный LLM proxy.

P2P часть находится на стадии MVP:

- route registry уже есть
- peer snapshot уже есть
- network debug admin уже есть
- remote execution между узлами еще не доведено до production-уровня
