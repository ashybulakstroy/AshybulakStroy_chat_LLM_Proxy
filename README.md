# AshybulakStroy AI HUB

Лёгкий FastAPI-сервис для проксирования запросов к OpenAI-совместимому LLM API.

## Стек

- Python 3.11+
- FastAPI
- HTTPX
- Pydantic

## Что реализовано

- `/health` — проверка работоспособности
- `/health/limits` — сводка по лимитам, startup probe и последним ошибкам провайдеров
- `/health/limits/live` — принудительное обновление startup probe и лимитов по провайдерам
- `/v1/models` — список моделей от подключённого провайдера
- `/v1/chat/completions` — прокси для chat completions
- `/v1/embeddings` — прокси для embeddings

## Текущее состояние

Сейчас проект работает как OpenAI-совместимый прокси и умеет отправлять запрос сразу в несколько провайдеров, выбирая первый успешный ответ:

- `PORT`
- `ENABLE_PROVIDER_LOG`
- `LOG_LEVEL`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `GEMINI_API_KEY`
- `SAMBANOVA_API_KEY`

Поля `provider` и `metadata` уже есть в схемах запросов и могут использоваться при дальнейшем расширении маршрутизации.

## Запуск

1. Установите зависимости:

```bash
python -m pip install -r requirements.txt
```

2. Создайте файл `.env` с переменными:

```env
PORT=8800
ENABLE_PROVIDER_LOG=true
LOG_LEVEL=INFO

GROQ_API_KEY=your_groq_api_key
GROQ_API_BASE=https://api.groq.com/openai/v1

OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_API_BASE=https://openrouter.ai/api/v1

CEREBRAS_API_KEY=your_cerebras_api_key
CEREBRAS_API_BASE=https://api.cerebras.ai/v1

GEMINI_API_KEY=your_gemini_api_key
GEMINI_API_BASE=https://generativelanguage.googleapis.com/v1beta/openai/

SAMBANOVA_API_KEY=your_sambanova_api_key
SAMBANOVA_API_BASE=https://api.sambanova.ai/v1
```

Если заполнено несколько ключей, сервис отправит запрос во все доступные провайдеры и вернёт первый успешный ответ.

В логах видно:

- на каком порту поднялся сервер
- в какой провайдер ушёл запрос
- какой HTTP-код вернулся
- сколько занял запрос
- детали ошибки, если провайдер ответил с ошибкой или не ответил

## Известные лимиты

- `Groq`: `30 RPM`
- `Cerebras`: `30 RPM`
- `OpenRouter` для `:free` моделей: `20 RPM`
- `Gemini 2.5 Flash` на `free tier`: `10 RPM`
- `SambaNova` на `free tier` по рабочей оценке: `20 RPM`
- Если провайдер не присылает rate-limit headers, сервис использует безопасный fallback: `1 RPM`
- При старте приложения сервис автоматически делает probe по провайдерам, чтобы заполнить `/health` лимитами без ручного запроса
- Подробная оценка сохранена в файлах `PROVIDER_LIMITS.md` и `provider_limits.json`

3. Запустите сервис:

```bash
python run.py
```

После запуска можно сразу смотреть:

```bash
curl http://localhost:8800/health
curl http://localhost:8800/health/limits
curl -X POST http://localhost:8800/health/limits/live
```

`/health/limits` показывает:

- какие провайдеры активны
- сколько их всего
- когда был последний startup probe
- какие провайдеры ответили успешно на старте
- какие провайдеры вернули ошибку на старте
- реальные лимиты из response headers, если провайдер их прислал
- fallback `1 RPM`, если провайдер лимиты не прислал

`/health/limits/live` полезен, когда нужно вручную переснять свежие лимиты и статус startup probe без перезапуска сервиса.

## Пример запроса

```bash
curl http://localhost:8800/v1/chat/completions -X POST \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Привет"}]}'
```

## Дальше можно добавить

- маршрутизацию между несколькими провайдерами
- API-ключи клиентов
- ретраи, кеш и логирование
- тесты и CI
