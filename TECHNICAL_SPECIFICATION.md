# Техническая спецификация

## Назначение проекта

Локальная копия проекта `AshybulakStroy_chat_LLM_Proxy` используется для дальнейшей доработки LLM proxy gateway.

## API-ключи и провайдеры

Для дальнейшей работы проекту нужны API-ключи внешних LLM-провайдеров. По рабочей версии `https://price.ashybulakstroy.kz:22000/docs` и локальному `app/config.py` поддерживаются следующие переменные окружения:

- `OPENAI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `GEMINI_API_KEY`
- `SAMBANOVA_API_KEY`
- `EDENAI_API_KEY`
- `FIREWORKS_API_KEY`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Рабочая версия показывает опубликованные модели провайдеров `groq`, `cerebras`, `gemini`, `sambanova`, `fireworks`. В dispatcher cache также видны `openrouter` и `edenai`, но они находятся в карантине из-за ошибки 402, то есть требуют пополнения баланса или корректного ключа.

Cloudflare Workers AI подключается как OpenAI-compatible provider `cloudflare` через base URL вида `https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1`. Так как endpoint `/ai/v1/models` у Workers AI не используется как обычный OpenAI models endpoint, локальный provider возвращает статический список поддержанных chat-моделей; первично проверена модель `@cf/meta/llama-3.1-8b-instruct`.

## Локальный запуск сервера

Сервер должен запускаться через готовый скрипт `start_server.ps1` или `start_server.bat`. Скрипт запускает `run.py` через локальное виртуальное окружение `.venv`, показывает консольную сессию сервера на экране и оставляет окно открытым после остановки, чтобы можно было видеть вывод и ошибки.

## Клиентская настройка авто-баланса и failover

Клиенты должны отправлять chat-запросы на `/v1/chat/completions` с `provider="auto"` и `model="auto"`. Для обычной балансировки используется `resource_affinity="auto"`, для привязки клиента к одному ресурсу используется `resource_affinity="sticky"` вместе с `metadata.client_id`.

Серверный режим диспетчера задается через `PROXY_MODE`. Рекомендуемый режим для штатной работы: `LOAD_BALANCE`. Режим `FAST` запускает провайдеров параллельно и возвращает первый успешный ответ.

Auto-routing должен использовать только провайдеров, реально настроенных в локальном `.env`. Устаревшие записи из cache/snapshot не должны попадать в пул кандидатов, если соответствующего API-ключа нет в текущей конфигурации.

Все ошибки класса `40x` на уровне `provider + model` считаются основанием для quarantine ресурса. Ошибки `429 Too Many Requests` отправляют ресурс в quarantine на 1 час. Остальные `40x` отправляют ресурс в quarantine на 1 день. Ошибки `401`, `402`, `403` дополнительно считаются проблемой доступа/ключа провайдера и временно исключают провайдера из маршрутизации на 1 день.

Локальные ошибки chat proxy (`400`, `404`, `409`, `502`) должны логироваться как `chat_proxy_error` с причиной, requested/effective provider/model, `client_id`, `route_id`, выбранным route и подробным `detail`, чтобы консольные логи позволяли понять причину отказа без повторного воспроизведения запроса.

Если клиент запрашивает конкретную модель с `provider="auto"`, но живого маршрута нет, proxy должен возвращать diagnostic detail по известным маршрутам модели, включая provider/resource quarantine и причины из `invalid_resources.json`. Старые записи `4xx` в `invalid_resources.json` нормализуются в blocking quarantine на 1 день.

Временная upstream-ошибка `503 Service Unavailable` должна отправлять ресурс в quarantine минимум на 60 минут. Остальные временные network/5xx ошибки стартуют с 10 минут и далее увеличиваются backoff-ом.

Если `503 Service Unavailable` содержит признаки обслуживания модели (`maintenance`, `undergoing maintenance`, `back online shortly`), ошибка считается временной недоступностью конкретного маршрута `provider + model` с причиной `model_maintenance`, а не общей недоступностью провайдера. Startup/live probe должны применять такой resource quarantine к probe-модели.

Если маршрут `provider + model` недоступен из-за исчерпанных лимитов (`rpm_remaining=0`, `rpd_remaining=0` или `tpm_remaining=0`), proxy должен отправлять этот ресурс в quarantine с причиной `no_resource` и источником `limit_exhausted`. Длительность quarantine берется из ближайшего `reset_seconds` лимитного окна, если оно известно; если нет, используется короткий дефолт 10 минут.

Timeout-ы внешних запросов увеличены в 2 раза: обычные OpenAI-compatible HTTP-запросы к провайдерам ждут до 60 секунд, multipart/audio-запросы до 120 секунд, P2P HTTP-вызовы до 20 секунд, дефолт `P2P_SESSION_TIMEOUT_SEC` равен 180 секундам.
