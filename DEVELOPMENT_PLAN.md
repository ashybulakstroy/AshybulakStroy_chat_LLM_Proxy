# План развития и разработки

План основан на `TECHNICAL_SPECIFICATION.md`.

## Ближайшие шаги

- Подготовить `.env` для локального запуска на основе `.env.example`.
- Добавить рабочие API-ключи для нужных провайдеров.
- Проверить запуск локального сервера на порту `8800`.
- Проверить `/health`, `/v1/models` и тестовый `/v1/chat/completions`.
- Сверить поведение локальной версии с рабочей версией `https://price.ashybulakstroy.kz:22000`.
- Использовать видимый запуск сервера через `start_server.ps1` или `start_server.bat`, чтобы консольные логи оставались доступны на экране.
- Поддерживать правило quarantine для исчерпанных лимитов: маршруты с `rpm/rpd/tpm remaining == 0` должны фиксироваться как `no_resource`.
- Поддерживать отдельную политику для `429 Too Many Requests`: quarantine ресурса на 1 час, а не на 1 день.
- Проверять влияние увеличенных timeout-ов на пользовательскую задержку: provider HTTP 60 секунд, multipart/audio 120 секунд, P2P HTTP 20 секунд, P2P session 180 секунд.
- Поддерживать route-level quarantine для `503` с maintenance-текстом: блокировать конкретный `provider + model`, не весь provider.

## Провайдеры для настройки

- Основные активные по рабочей версии: `groq`, `cerebras`, `gemini`, `sambanova`, `fireworks`.
- Дополнительные, требующие проверки баланса/ключей: `openrouter`, `edenai`.
- Новый локально проверенный provider: `cloudflare` / Workers AI с моделью `@cf/meta/llama-3.1-8b-instruct`.
