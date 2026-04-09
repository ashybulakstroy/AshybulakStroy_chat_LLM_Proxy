# P2P Subproject Specification

## Назначение

Документ фиксирует текущее состояние и целевую архитектуру P2P-подпроекта внутри `AshybulakStroy AI HUB`.

Это отдельный слой поверх локального provider proxy.

Локальный proxy отвечает за upstream providers.
P2P слой отвечает за сеть нод, peer registry и сетевые маршруты.

## Текущая модель

### Node

`Node` — установленный экземпляр AI HUB на конкретной машине.

Нода может иметь:

- собственные API-ключи
- собственный пул локальных `provider + model`
- собственные лимиты
- собственную политику участия в сети

### Peer

`Peer` — нода, которая в текущий момент:

- зарегистрирована в сети
- прошла heartbeat
- разрешает remote tasks
- делится своей локальной емкостью

### Master

`Master` — координатор P2P сети.

Он отвечает за:

- route registry
- peer registry
- network snapshot
- heartbeat state
- network map
- route pruning
- dispatch preview

### Master Cache

`master_cache` — режим ноды, в котором узел выполняет orchestration и cache-функции, но не обязан быть полноценным direct executor.

## Локальные ресурсы и P2P маршруты

Важно различать:

### Local resource

Локальный ресурс:

`provider + model`

Это единица локального исполнения для обычного proxy.

### P2P route

Сетевой маршрут:

- привязан к конкретной ноде
- имеет `route_id`
- имеет `route_status`
- имеет `direct_provider_access`
- участвует в network map

## Route ID

Для direct-маршрутов используется:

`route_id = sha256(api_key + provider + model)[:12]`

Для peer/master rows в `Known Peers` короткий идентификатор ноды строится отдельно:

`peer_id6 = sha256(url)[:6]`

## Route status

Ключевые состояния:

- `online`
- `cache`
- `error`

Смысл:

- `online` — маршрут прошел валидацию и может участвовать в routing
- `cache` — маршрут загружен из snapshot/file cache, но еще не подтвержден онлайн
- `error` — маршрут известен, но сейчас невалиден

## TTL

Настройка:

- `P2P_ROUTE_TTL_MIN = 1440`

Правило:

- если маршрут не `online`
- и TTL истек
- маршрут удаляется из runtime route registry и snapshot

## Snapshot

Файл:

- [p2p_network_snapshot.json](C:\Work\Projects\Prj_8_LLM_Proxy\p2p_network_snapshot.json)

Назначение:

- пережить рестарт master/peer
- восстановить известную карту сети
- повторно валидировать cached-маршруты после старта

## Runtime mutation guard

P2P runtime-изменения не должны быть открыты по умолчанию.

ENV-флаг:

- `ALLOW_RUNTIME_ADMIN_MUTATIONS=false`

При таком значении запрещены:

- `POST /admin/p2p/config`
- `POST /admin/p2p/peers/heartbeat`
- `POST /admin/p2p/sessions`
- `POST /admin/p2p/nodes/remove`
- `POST /internal/p2p/re-register`

Сервер должен возвращать `403`.

Это сделано для того, чтобы production-узел не менял сетевое runtime-состояние через admin HTTP без явного разрешения.

Если нужен controlled maintenance window:

- временно выставить `ALLOW_RUNTIME_ADMIN_MUTATIONS=true`
- выполнить нужные изменения
- вернуть `false`
- перезапустить сервис

## Route catalog

Каждая нода может экспортировать `route_catalog`.

Элементы route catalog:

- `provider`
- `model`
- `route_id`

Если нода direct, этот catalog может участвовать в P2P routing table.

## Direct vs link-only

### Direct

Нода имеет собственные ключи и сама может выполнить upstream вызов.

### Link-only

Нода только знает о другом узле или маршруте, но сама не является прямым исполнителем.

В route capacity и direct provider links link-only маршруты не должны считаться как полная вычислительная емкость.

## Network Map

`/admin/p2p` показывает агрегированный срез сети:

- masters
- peers
- direct provider links
- unique routes
- redundant routes

### Unique Routes

Количество уникальных `route_id`.

### Redundant Routes

Количество дублирующих route rows по одному и тому же `route_id`.

## Routing table

P2P `Маршрутизация` — это не просто список моделей.
Это список сетевых маршрутов исполнения.

Каждая строка содержит:

- mode ноды
- node name
- route id
- resource (`provider + model`)
- slots / min
- route status

## Slots

Текущая формула:

`ceil(P2P_MAX_SHARED_SLOTS_PER_MIN / resources_in_node)`

Где:

- `P2P_MAX_SHARED_SLOTS_PER_MIN` — сколько нода готова отдать сети
- `resources_in_node` — количество direct-маршрутов этой ноды

## Known Peers

`Known Peers` — это таблица сетевых записей нод.

Она показывает:

- mode
- peer id
- name
- run
- route status
- route type
- health
- heartbeat age
- url

Красные строки должны означать проблемную ноду:

- `health = 0`
- `run = error`

Для таких строк разрешено ручное удаление из runtime/snapshot.

## Что уже работает

- peer heartbeat
- snapshot load/save
- cached route import
- online route validation
- route pruning by TTL
- known peers admin
- routing table admin
- network map admin

## Что еще не finished

- полноценный P2P remote execution
- production auth между нодами
- signal server
- автоматический mDNS discovery

## Архитектурная граница

Важно сохранить разделение:

- локальный dispatcher выбирает локальный `provider + model`
- P2P dispatcher выбирает ноду / сетевой маршрут

Их нельзя смешивать в один слой, иначе исчезнет понятная граница между:

- local execution
- network orchestration
