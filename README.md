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
- `POST /v1/audio/transcriptions`
- `GET /admin`
- `GET /admin/p2p`

## Upstream API

Прокси сейчас использует только OpenAI-compatible upstream endpoints:

- `GET /models`
- `POST /chat/completions`
- `POST /embeddings`
- `POST /audio/transcriptions`

Image / video upstream calls в текущем коде не реализованы как отдельные transport-ветки.

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

### Как клиенту включить авто-баланс и failover

Для обычного клиента достаточно отправлять запрос в локальный proxy endpoint:

- `POST http://127.0.0.1:8800/v1/chat/completions`

и передавать в JSON:

```json
{
  "provider": "auto",
  "model": "auto",
  "messages": [
    {
      "role": "user",
      "content": "Привет!"
    }
  ],
  "max_tokens": 128,
  "temperature": 0.7,
  "resource_affinity": "auto",
  "response_type": "json"
}
```

Что делают параметры:

- `provider: "auto"` — proxy сам выбирает доступного провайдера.
- `model: "auto"` — proxy сам выбирает подходящую LLM-модель.
- `resource_affinity: "auto"` — балансировка между пригодными ресурсами.
- `resource_affinity: "sticky"` — удерживать одного клиента на одном `provider + model`, если ресурс доступен.
- `metadata.client_id` — идентификатор клиента для sticky-режима.
- `response_type: "json"` — ожидаемый тип ответа. При несовпадении в auto-режиме proxy пробует следующий ресурс.

Пример sticky-запроса:

```json
{
  "provider": "auto",
  "model": "auto",
  "resource_affinity": "sticky",
  "metadata": {
    "client_id": "user-123"
  },
  "messages": [
    {
      "role": "user",
      "content": "Продолжим мой диалог"
    }
  ],
  "max_tokens": 128
}
```

Failover работает автоматически: если выбранный upstream `provider + model` возвращает ошибку, уходит в quarantine, исчерпал лимиты или не подходит по типу ответа, proxy исключает этот ресурс и пробует следующий доступный кандидат.

Правила качества маршрутизации:

- auto-routing использует только провайдеров, настроенных в текущем `.env`;
- устаревшие модели из cache/snapshot игнорируются, если их провайдер не настроен локально;
- любой `40x` от upstream отправляет ресурс `provider + model` в quarantine на 1 день;
- `401`, `402`, `403` дополнительно временно исключают провайдера на 1 день, потому что это ошибка доступа/ключа/баланса;
- если клиент передал конкретную `model`, но не передал `provider`, proxy ищет только реальные маршруты для этой модели, а не пробует модель у всех провайдеров подряд.
- локальные ошибки `POST /v1/chat/completions` логируются как `chat_proxy_error` с `status_code`, `reason`, requested/effective provider/model, `client_id`, `route_id`, выбранным route и `detail`.
- если клиент запрашивает конкретную модель через `provider=auto`, но живого маршрута нет, proxy возвращает diagnostic detail со статусом известных маршрутов: `provider_quarantined`, `resource_quarantined`, `provider_not_configured`, `not_chat_capable`.
- временная upstream-ошибка `503` отправляет ресурс в quarantine минимум на 60 минут; остальные временные network/5xx ошибки стартуют с 10 минут и дальше растут backoff-ом.

Серверный режим диспетчера задается переменной:

```env
PROXY_MODE=LOAD_BALANCE
```

Поддерживаемые значения:

- `LOAD_BALANCE` — последовательный выбор пригодного ресурса с учетом лимитов, ошибок и недавнего использования.
- `FAST` — параллельная гонка провайдеров, первый успешный ответ возвращается клиенту.

Для штатной работы рекомендуется `PROXY_MODE=LOAD_BALANCE`.

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

## Серверы и URL

### Локальный сервер

Используется для разработки и проверки доработок:

- Base URL: `http://127.0.0.1:8800`
- Swagger/OpenAPI docs: `http://127.0.0.1:8800/docs`
- Health: `http://127.0.0.1:8800/health`
- Models: `http://127.0.0.1:8800/v1/models`
- Chat completions: `http://127.0.0.1:8800/v1/chat/completions`
- Основная админка: `http://127.0.0.1:8800/admin`
- P2P debug admin: `http://127.0.0.1:8800/admin/p2p`

### Боевой сервер

Используется как рабочий эталон для сверки поведения:

- Base URL: `https://price.ashybulakstroy.kz:22000`
- Swagger/OpenAPI docs: `https://price.ashybulakstroy.kz:22000/docs`
- Health: `https://price.ashybulakstroy.kz:22000/health`
- Models: `https://price.ashybulakstroy.kz:22000/v1/models`
- Chat completions: `https://price.ashybulakstroy.kz:22000/v1/chat/completions`
- Основная админка: `https://price.ashybulakstroy.kz:22000/admin`
- P2P debug admin: `https://price.ashybulakstroy.kz:22000/admin/p2p`

### Upstream-провайдеры

Локальная конфигурация поддерживает такие внешние base URL:

| Провайдер | Base URL | Переменная ключа | Текущий статус |
| --- | --- | --- | --- |
| Groq | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | настроен локально |
| Cerebras | `https://api.cerebras.ai/v1` | `CEREBRAS_API_KEY` | настроен локально |
| SambaNova | `https://api.sambanova.ai/v1` | `SAMBANOVA_API_KEY` | настроен локально |
| Fireworks | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` | настроен локально |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_API_KEY` | ключ еще не добавлен |
| OpenRouter | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | на боевом сервере 402/quarantine |
| Eden AI | `https://api.edenai.run/v3/llm` | `EDENAI_API_KEY` | на боевом сервере 402/quarantine |
| OpenAI | `https://api.openai.com/v1` | `OPENAI_API_KEY` | опционально |

## Конфигурация

Минимально важные переменные:

```env
PORT=8800
ENABLE_PROVIDER_LOG=true
LOG_LEVEL=INFO
PROXY_MODE=LOAD_BALANCE
ALLOW_RUNTIME_ADMIN_MUTATIONS=false

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

### Защита runtime-изменений

По умолчанию live-изменение runtime-параметров сервера запрещено:

- `ALLOW_RUNTIME_ADMIN_MUTATIONS=false`

Это поведение рекомендуется сохранять для production.

При выключенном флаге сервер возвращает `403` для mutating endpoints:

- `POST /admin/p2p/config`
- `POST /admin/p2p/peers/heartbeat`
- `POST /admin/p2p/sessions`
- `POST /admin/p2p/nodes/remove`
- `POST /internal/p2p/re-register`
- `POST /admin/invalid-resources`
- `DELETE /admin/invalid-resources`
- `POST /admin/dispatcher/mode`

Чтобы временно разрешить online-изменения:

```env
ALLOW_RUNTIME_ADMIN_MUTATIONS=true
```

После изменения `.env` требуется перезапуск сервера.

### Рекомендация для production

Для production-площадки базовая позиция должна быть такой:

- `ALLOW_RUNTIME_ADMIN_MUTATIONS=false`
- P2P runtime-конфигурация меняется только через `.env` + restart
- ручные runtime-mutations через admin UI не использовать как штатный канал конфигурации
- `invalid_resources.json` и `p2p_network_snapshot.json` сохранять между рестартами

## Запуск

1. Установить зависимости:

```bash
python -m pip install -r requirements.txt
```

2. Настроить `.env`
3. Запустить сервер в видимой консоли:

```powershell
.\start_server.ps1
```

или:

```bat
start_server.bat
```

Проверка:

```bash
curl http://localhost:8800/health
curl http://localhost:8800/health/limits
curl http://localhost:8800/admin
curl http://localhost:8800/admin/p2p
```

Пример transcription request:

```bash
curl -X POST http://localhost:8800/v1/audio/transcriptions \
  -F "file=@voice.ogg" \
  -F "model=whisper-large-v3-turbo" \
  -F "provider=groq"
```

Практический smoke-test уже выполнялся на русском audio sample:

- источник: Wikimedia Commons
- файл: `Russian_sayings.ogg`
- provider: `groq`
- model: `whisper-large-v3-turbo`
- результат: endpoint вернул `200 OK` и нормализованный ответ `{ "text": "..." }`

## Статус проекта

Сервис рабочий как локальный LLM proxy.

P2P часть находится на стадии MVP:

- route registry уже есть
- peer snapshot уже есть
- network debug admin уже есть
- remote execution между узлами еще не доведено до production-уровня
