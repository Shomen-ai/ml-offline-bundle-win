# llm-chat-app

Чат с локальной нейронкой для изолированной Windows-машины: **Vue 3 + FastAPI + Oracle 11g + llama.cpp (CUDA)**. Авторизация, список диалогов, выбор модели, стриминг ответов. Все зависимости — из офлайн-бандла [ml-offline-bundle-win](https://github.com/Shomen-ai/ml-offline-bundle-win) (или уже стоят в бандле машины B — см. `constraints-machine-b.txt` там же), докачивать ничего не нужно.

## Архитектура

```
Vue 3 (hash-router)          FastAPI :8000                 LLM-сервер :8001
  dev: vite :5173   ──/api──▶  auth (PBKDF2 + сессии в БД)   FastAPI + llama-cpp-python
  prod: статика dist           диалоги/сообщения    ──SSE──▶ грузит .gguf из MODELS_DIR
  отдаётся backend'ом          SSE-прокси ответа             /models /load /chat
                                    │
                               Oracle 11g (thick, Instant Client 19)
                               users · sessions · dialogs · messages
```

- **Отдельный сервер с нейронкой** (`llm-server/server.py`): один процесс — одна загруженная модель; `/models` — список .gguf из папки, `/load` — переключение (с выгрузкой из VRAM), `/chat` — SSE-стрим. Генерация однопоточная: второй запрос ждёт первого.
- **Настройки LLM общие** и лежат в таблице `dpis_settings`: модель, размер контекста, число слоёв на GPU, температура, потолок длины ответа и системный промпт. Правятся в панели `/#/admin`. Первые три параметра заданы при создании `Llama`, поэтому их сохранение перезагружает веса в видеопамяти — панель предупреждает об этом до сохранения. Прав доступа пока нет: стенд тестовый, панель открыта любому вошедшему.
- **Системный промпт** уходит первым сообщением в каждом запросе и в базе не хранится — правка промпта действует сразу во всех диалогах, включая старые.
- **Контекст режется по токенам, а не по числу сообщений.** История набирается с конца, пока влезает в бюджет (`n_ctx` минус место под ответ), длины считает сам LLM-сервер ручкой `/tokenize`. Что не влезло — сжимается моделью в сводку, она хранится в `dpis_dialogs.summary`, а `summary_upto` помнит, до какого сообщения она диалог покрывает. Системный промпт и сводка закреплены и не выбрасываются. Сжатие — отдельная генерация, поэтому чат в этот момент показывает «сжимаю историю». Сообщение, которое не влезает в контекст целиком, отвергается с ошибкой **до** записи в базу.
- **Авторизация** без внешних зависимостей: PBKDF2-SHA256 (200k итераций) + opaque-токены в таблице `sessions` (Bearer). Работает офлайн.
- **Oracle 11g**: только thick-режим (`oracledb.init_oracle_client`, Instant Client 19.x); id — сиквенсы (в 11g нет IDENTITY); тексты сообщений — CLOB.

## Запуск на рабочей машине (B)

Предполагается бандл из `ml-offline-bundle-win`: venv `D:\bundle\ml-bundle\.venv` (Python 3.11), модели в `D:\bundle\models`, Instant Client в `D:\oracle\instantclient_19_31`. Пути правятся в начале каждого `.bat` и в `backend\.env`.

```bat
:: 1) один раз: реквизиты Oracle
copy backend\.env.example backend\.env  &&  notepad backend\.env

:: 2) один раз: таблицы
scripts\apply_schema.bat

:: 3) два окна:
scripts\run_llm.bat        :: сервер с нейронкой, :8001
scripts\run_backend.bat    :: API + собранный фронт, :8000
```

Открыть `http://127.0.0.1:8000` — логин/регистрация → чат.

## Разработка (машина с интернетом)

```bat
cd frontend && npm install && npm run dev   :: фронт на :5173, /api проксируется на :8000
```

Backend и LLM-сервер запускаются так же (venv с теми же пакетами). Для машины B фронт собирается `npm run build` — папку `frontend/dist` отдаст сам backend (порт 8000, ничего настраивать не надо). Перенос фронта без интернета: скопировать `node_modules` целиком (обе машины — Windows x64) или переносить готовый `dist`.

## Структура

```
backend/
  app/main.py        создание приложения, lifespan, CORS, статика dist
  app/config.py      .env: Oracle, LDAP, LLM_URL, TTL сессий
  app/db.py          пул oracledb (thick), CLOB->str, RETURNING id
  app/deps.py        зависимости FastAPI: current_user, owned_dialog
  app/api/           маршруты: auth, dialogs, messages, models
  app/schemas/       pydantic-модели запросов и ответов
  app/services/      логика: auth, dialogs, messages, context, settings, ldap_auth, llm_client
  schema.sql         DDL под 11g (sequences, CLOB), объекты с приставкой dpis_
  migrations/        доработки схемы для баз, где таблицы уже созданы
  apply_schema.py    применяет schema.sql (--drop = пересоздать)
llm-server/server.py отдельный сервер с нейронкой
frontend/            Vue 3 + Vite (vue-router, hash-режим), без UI-библиотек
scripts/*.bat        запуск: чистый cmd, без PowerShell
```

## API кратко

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/api/auth/register` · `/login` · `/logout` | авторизация, Bearer-токен |
| GET/PUT | `/api/admin/settings` | настройки LLM: модель, контекст, температура, системный промпт |
| GET | `/api/admin/models` | список моделей LLM-сервера |
| GET | `/api/llm/health` | поднят ли LLM-сервер (баннер в чате) |
| GET/POST | `/api/dialogs` | список / создать диалог |
| PATCH/DELETE | `/api/dialogs/{id}` | переименовать / удалить |
| GET | `/api/dialogs/{id}/messages` | история |
| POST | `/api/dialogs/{id}/messages` | отправить; ответ — SSE: `start`/`delta`/`done`/`error` |

## Частые проблемы

- **DPI-1047 (нет Oracle Client)** — проверьте `ORACLE_CLIENT_DIR` в `.env`: каталог должен существовать и быть 64-битным Instant Client 19.x.
- **«LLM-сервер недоступен» в шапке чата** — не запущен `scripts\run_llm.bat`, либо порт занят (`LLM_PORT`).
- **Первый ответ в диалоге очень долгий** — грузится модель (~30–60 с для 7B на RTX A4000); смотрите окно run_llm.bat и `nvidia-smi`.
- **ORA-00001 при регистрации** — логин занят, это нормальное поведение (фронт покажет «Такой пользователь уже есть»).
