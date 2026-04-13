# Техническая спецификация: AshybulakStroy AI HUB

## Назначение

Проект реализует локальный OpenAI-compatible LLM proxy с несколькими upstream-провайдерами и отдельным P2P debug-слоем.

Текущие цели:

- выполнять локальные LLM-запросы через единый API
- выбирать ресурс исполнения по runtime-состоянию
- отслеживать лимиты и ошибки провайдеров
- поддерживать sticky-affinity клиента к ресурсу
- готовить почву для P2P orchestration

## Реализованные HTTP endpoints

### Health

- `GET /health`
- `GET /health/limits`
- `POST /health/limits/live`
- `GET /health/limits/live/status`

### Models / Chat / Embeddings

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`
- `POST /v1/audio/transcriptions`

### Admin

- `GET /admin`
- `GET /admin/dispatcher/cache`
- `GET /admin/dispatcher/status`
- `GET /admin/models/available`
- `GET /admin/models/validated-llm`
- `POST /admin/models/validate-remaining-llm`
- `GET /admin/models/validate-remaining-llm/status`

### P2P Admin

- `GET /admin/p2p`
- `GET /admin/p2p/status`
- `GET /admin/p2p/peers`
- `POST /admin/p2p/config`
- `POST /admin/p2p/peers/heartbeat`
- `POST /admin/p2p/sessions`
- `POST /admin/p2p/nodes/remove`
- `POST /admin/p2p/dispatch/preview`

### Runtime mutation guard

В проекте введен env-флаг:

- `ALLOW_RUNTIME_ADMIN_MUTATIONS`

Значение по умолчанию:

- `false`

При `false` сервер блокирует mutating runtime/admin endpoints с ответом `403`.

Под блокировку попадают:

- `POST /admin/p2p/config`
- `POST /admin/p2p/peers/heartbeat`
- `POST /admin/p2p/sessions`
- `POST /admin/p2p/nodes/remove`
- `POST /internal/p2p/re-register`
- `POST /admin/invalid-resources`
- `DELETE /admin/invalid-resources`
- `POST /admin/dispatcher/mode`

Наблюдательные и read-only endpoints продолжают работать без ограничений.

## Audio transcription

Реализован базовый OpenAI-compatible endpoint:

- `POST /v1/audio/transcriptions`

Формат запроса:

- `multipart/form-data`
- `file`
- `model`
- `provider` optional
- `language` optional
- `prompt` optional

Формат ответа:

- `{ "text": "..." }`

Ограничения первой версии:

- single-provider execution path
- без auto-routing между несколькими speech providers
- без sticky affinity
- без diarization
- без timestamps
- без streaming

## Основные модули

- [app/main.py](C:\Work\Projects\Prj_8_LLM_Proxy\app\main.py)
  - старт FastAPI
  - startup orchestration
- [app/routes.py](C:\Work\Projects\Prj_8_LLM_Proxy\app\routes.py)
  - HTTP endpoints
  - runtime orchestration
  - invalid resources
  - response type validation
- [app/router_service.py](C:\Work\Projects\Prj_8_LLM_Proxy\app\router_service.py)
  - локальный provider dispatcher
  - history / active sessions
- [app/providers/openai_provider.py](C:\Work\Projects\Prj_8_LLM_Proxy\app\providers\openai_provider.py)
  - OpenAI-compatible upstream transport
- [app/rate_limits.py](C:\Work\Projects\Prj_8_LLM_Proxy\app\rate_limits.py)
  - runtime state лимитов
- [app/admin_ui.py](C:\Work\Projects\Prj_8_LLM_Proxy\app\admin_ui.py)
  - основная админка
- [app/p2p_service.py](C:\Work\Projects\Prj_8_LLM_Proxy\app\p2p_service.py)
  - P2P runtime state
  - peer registry
  - route registry

## Локальный ресурс исполнения

Единица локального исполнения:

`resource = provider + model`

Это не абстрактная модель, а конкретный локальный кандидат для выполнения запроса.

Основная локальная ресурсная витрина:

- `Block #2` основной админки

Дополнительный validated LLM pool:

- `Block #4`

Локальный union этих двух наборов должен рассматриваться как полный локальный ресурсный inventory ноды.

## Логика выбора ресурса для LLM

### Входные параметры клиента

В `ChatCompletionRequest` поддерживаются:

- `provider`
- `model`
- `resource_affinity`
- `response_type`
- `metadata`

### Resource affinity

Поддерживаются:

- `auto`
- `sticky`

`sticky` опирается на:

- `metadata.client_id`

Если у клиента уже есть привязка к ресурсу и ресурс еще пригоден, диспетчер повторно использует его.

### Response type

Поддерживаются:

- `json`
- `text`
- `audio`
- `video`

По умолчанию:

- `json`

После получения ответа upstream сервис валидирует фактический тип ответа.

Если тип не соответствует ожидаемому:

- при auto-dispatch ресурс помечается как bad candidate
- ресурс арестуется как invalid
- диспетчер пробует следующий ресурс
- при исчерпании кандидатов возвращается `response_type_mismatch_exhausted`

### Auto-dispatch

Для `provider=auto` и `model=auto` работает новый слой отбора поверх старого фильтра пригодности.

Приоритеты отбора:

1. ресурс пригоден
2. нет недавней ошибки
3. есть remaining RPM
4. более старое последнее использование
5. меньшее число недавних вызовов
6. bonus за разнообразие провайдеров
7. `round-robin` только среди равных

Это не жесткий круг по таблице. Это cold-resource scheduling с fair tie-break.

## Invalid resources

Файл:

- [invalid_resources.json](C:\Work\Projects\Prj_8_LLM_Proxy\invalid_resources.json)

Используется для:

- исключения плохих ресурсов из локального dispatch
- quarantine после временных ошибок
- quarantine после mismatch response type
- отображения в `Block #6`
- фильтрации локальных P2P route catalogs

Файл должен сохраняться между рестартами.

На старте сервера содержимое `invalid_resources.json` повторно загружается в runtime.

## Session history

`Block #5` строится из completed session history локального dispatcher-а.

Сейчас в UI:

- время старта показывается в `GMT+5`
- вместо “завершено” показывается длительность в секундах
- ошибки должны подсвечиваться как error rows

## Grouped LLM validation

Validation remaining LLM выполняется группами по имени модели:

1. берется весь список доступных моделей
2. исключаются non-LLM
3. модели группируются по `model_id`
4. группы сортируются
5. внутри группы запросы к провайдерам идут параллельно
6. между группами выдерживается пауза

Приоритет порядка:

- сначала LLM из `Block #2`
- затем остальные LLM

## P2P MVP

### Роли ноды

- `peer`
- `master`
- `master_cache`
- `auto`

### Маршрут P2P

Сетевая единица:

- `route_id = sha256(api_key + provider + model)[:12]`

Дополнительные признаки:

- `route_status`
- `direct_provider_access`
- `link-only`
- `health_score`
- `available_slots_per_minute`

### TTL маршрута

Настройка:

- `P2P_ROUTE_TTL_MIN`

Если маршрут не рабочий и TTL истек, маршрут удаляется из route registry.

### Slots

Текущая формула:

`ceil(P2P_MAX_SHARED_SLOTS_PER_MIN / resources_in_node)`

### Что уже есть

- peer registry
- known peers
- master snapshot
- route hashing
- route TTL pruning
- network map
- routing table
- dispatch preview

### Что еще не доведено

- полноценный remote execution между peer-узлами
- production-grade auth между нодами
- signal server / mDNS

## Основные ограничения текущей версии

- основная админка и P2P админка местами еще расходятся по представлению счетчиков
- часть UI еще требует полной очистки по UTF-8 строкам
- sticky-affinity живет в памяти процесса
- live server на `8800` иногда держит старый reload worker дольше ожидаемого

## Следующие инженерные шаги

1. Закрыть расхождения счетчиков `admin` vs `p2p`
2. Полностью очистить UTF-8 в UI-строках
3. Добавить тесты на:
   - auto scheduler
   - sticky affinity
   - response_type fallback
   - invalid resource quarantine
4. Довести P2P dispatch до реального remote execution
