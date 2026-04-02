# Техническое задание: AshybulakStroy AI HUB

## Цель
Создать сервис AshybulakStroy AI HUB, который принимает унифицированные API-запросы и проксирует их к OpenAI-совместимым LLM-провайдерам с возможностью дальнейшего расширения.

## Основные возможности

1. API маршрутизации
   - Поддержка `/v1/chat/completions`
   - Поддержка `/v1/embeddings`
   - Поддержка `/v1/models`
   - Легкий переход на новые провайдеры

2. Конфигурация провайдеров
   - Поддержка нескольких провайдеров через конфигурацию
   - Приоритет провайдера по умолчанию
   - Переопределение провайдера в запросе

3. Безопасность
   - Хранение ключей через переменные окружения
   - Ограничение доступа на уровне API-ключей (расширение)

4. Логирование
   - Запросы и ответы
   - Ошибки провайдеров

5. Расширяемость
   - Общий интерфейс для провайдеров
   - Поддержка OpenAI, Azure OpenAI и других API

## Текущий статус реализации

- Реализован FastAPI-сервис с endpoint'ами `/health`, `/v1/models`, `/v1/chat/completions`, `/v1/embeddings`
- Подключён один OpenAI-совместимый провайдер
- Базовая конфигурация идёт через `.env`
- Полноценная маршрутизация между несколькими провайдерами пока не реализована

## Архитектура

- `app/main.py` — инициализация FastAPI
- `app/routes.py` — конечные точки API
- `app/schemas.py` — Pydantic-модели запросов/ответов
- `app/config.py` — настройки и переменные окружения
- `app/providers/` — адаптеры для провайдеров

## Протоколы

- JSON-over-HTTP
- REST API

## Требования

- Python 3.11+
- FastAPI
- HTTPX
- Pydantic
- .env конфигурация

## Дальнейшие шаги

- Добавить поддержку маршрутизации по телеметрии
- Реализовать систему ключей клиентов
- Добавить кеширование и ретраи
- Написать тесты и CI

## Current P2P MVP Status

The project now also includes a P2P orchestration MVP focused on debug visibility and peer selection preparation.

Implemented in MVP:

- runtime node roles:
  - `peer`
  - `master`
  - `master_cache`
  - `auto`
- P2P enable/disable runtime switch
- separate P2P debug admin page
- in-memory peer registry
- peer heartbeat upsert
- peer capability tracking:
  - providers
  - models
  - chat support
  - embeddings support
  - health score
- network map summary
- dispatch preview with capability/health filtering
- P2P event logs with `p2p_...` prefix

Not implemented yet:

- real peer-to-peer remote execution
- peer authentication
- signal server
- mDNS discovery
- distributed cache sync
