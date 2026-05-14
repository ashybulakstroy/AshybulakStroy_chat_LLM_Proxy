# Прогресс

## 2026-05-14

- Репозиторий `AshybulakStroy_chat_LLM_Proxy` успешно склонирован в `C:\Work\Prj_25_LLM_Proxy`.
- Создано виртуальное окружение `.venv`.
- Установлены зависимости из `requirements.txt`.
- Проверены импорты ключевых пакетов `fastapi`, `uvicorn`, `httpx`, `pydantic`.
- Подтвержден локальный порт по умолчанию: `8800`.
- Проверена рабочая версия `https://price.ashybulakstroy.kz:22000/docs`.
- Зафиксированы поддерживаемые API-ключи и провайдеры для дальнейшей настройки.
- Повторно проверен боевой сервер: живые провайдеры `groq`, `cerebras`, `gemini`, `sambanova`, `fireworks`; `openrouter` и `edenai` в карантине из-за 402.
- Проверен и добавлен локальный API-ключ `FIREWORKS_API_KEY`; Fireworks API вернул статус 200 и список моделей.
- Проверен и добавлен локальный API-ключ `GROQ_API_KEY`; Groq API вернул статус 200 и список моделей.
- Проверен и добавлен локальный API-ключ `SAMBANOVA_API_KEY`; SambaNova API вернул статус 200 и список моделей.
- Проверен и добавлен локальный API-ключ `CEREBRAS_API_KEY`; Cerebras API вернул статус 200 и список моделей.
- Локальный сервер запущен на порту `8800`; `/health` вернул статус 200, startup probe успешно проверил 4 провайдера.
- Скрипты `start_server.ps1` и `start_server.bat` переделаны под видимый запуск сервера с консольным выводом на экране; сервер перезапущен в видимом окне.
- В `README.md` добавлен раздел с локальным сервером, боевым сервером и upstream base URL провайдеров.
- В `README.md` и `TECHNICAL_SPECIFICATION.md` добавлена инструкция для клиента по авто-балансу и failover через `provider=auto`, `model=auto`, `resource_affinity`.
- Выполнен аудит логов и исправлены проблемы маршрутизации: stale-провайдеры из cache больше не попадают в auto-routing, явная модель без provider не пробуется у всех провайдеров подряд, `40x` ошибки отправляют ресурс в quarantine, `401/402/403` временно исключают провайдера.
- Startup probe усилен: теперь проверяет не только `/models`, но и короткий `/chat/completions` на выбранной chat-модели провайдера.
- Добавлены регрессионные тесты маршрутизации; полный набор тестов проходит: `5 passed`.
- Правило quarantine уточнено: все `4xx` ошибки отправляют ресурс в quarantine на 1 день; `401/402/403` дополнительно исключают провайдера на 1 день.
- Проверен и добавлен локальный API-ключ `GEMINI_API_KEY`; Gemini API вернул статус 200 на `/models` и `/chat/completions`.
- Локальный сервер перезапущен после добавления Gemini; `/health` показывает провайдеры `groq`, `cerebras`, `gemini`, `sambanova`, `fireworks`, startup probe успешно проверил `cerebras`, `gemini`, `sambanova`, `fireworks`.
- Добавлено логирование `chat_proxy_error` для локальных ошибок `POST /v1/chat/completions`, включая `400/404/409/502`, с подробным `detail` и контекстом маршрута.
- Улучшена диагностика `auto_route_unavailable`: для конкретной запрошенной модели proxy теперь показывает известные маршруты и причины недоступности из runtime cache и `invalid_resources.json`.
- Старые записи `4xx` в `invalid_resources.json` нормализуются в blocking quarantine на 1 день; старые provider quarantine `401/402/403` из snapshot ограничиваются новым правилом 1 день.
- Для временной upstream-ошибки `503 Service Unavailable` минимальный quarantine увеличен с 10 до 60 минут.
- Проверен и добавлен локальный API-ключ `OPENROUTER_API_KEY`; OpenRouter API вернул статус 200 на `/models` и `/chat/completions` с моделью `openrouter/free`.
