# ml-offline-bundle-win

Офлайн-бандл ML-библиотек для **изолированной Windows-машины** (x64, Python 3.11, NVIDIA RTX A4000): CUDA-сборка `llama-cpp-python`, FastAPI-стек, `faiss-cpu`, `oracledb` + Oracle Instant Client 19, Node.js LTS и GGUF-модель Qwen2.5-7B-Instruct.

Сами бинарники лежат не в git, а в **[Releases](../../releases)** (модель разбита на части по <2 ГБ — лимит GitHub). В репозитории — скрипты, манифест хешей и инструкция. Скрипты — **чистый cmd**, без PowerShell: `curl`, `tar`, `certutil` и `copy /b` встроены в Windows 10/11.

## Быстрый старт

**Машина A (с интернетом, Windows 10/11):**

```bat
curl -fLO https://raw.githubusercontent.com/Shomen-ai/ml-offline-bundle-win/main/scripts/download_release.bat
download_release.bat
```

Скрипт скачает все файлы релиза в `D:\transfer` (докачивает при обрывах — при сбое просто перезапустите), сверит SHA256 по манифесту и распакует колёса. Другой диск: `download_release.bat E:\transfer`. Дальше — вся папка на флешку.

**Машина B (изолированная):** положить папку как `D:\transfer` и запустить

```bat
D:\transfer\scripts\check_and_install.bat
```

Последовательность: сверка SHA256 → распаковка колёс → склейка модели из частей (`copy /b`) и проверка её хеша → распаковка Instant Client в `D:\oracle` → установка пакетов строго офлайн (`pip --no-index`) → проверки: GPU-offload llama.cpp, версия Oracle-клиента, тестовый ответ модели на GPU.

Варианты запуска: `check_and_install.bat E:\transfer`, `check_and_install.bat D:\transfer --skip-model-test`.

**VC++ Redistributable не устанавливается автоматически** — файл лежит в `bin\` на всякий случай. Если при импорте llama_cpp или oracledb появится ошибка про `VCRUNTIME140.dll`, поставьте вручную: `D:\transfer\bin\vc_redist.x64.exe /install /passive /norestart`.

## Состав релиза

| Файл | Что это | Куда кладётся |
|---|---|---|
| `wheels.zip` | все .whl под `win_amd64` / `cp311`; llama-cpp — CUDA-сборка cu118 | `D:\transfer\wheels\` |
| `instantclient19.zip` | Oracle Instant Client 19.31 Basic x64 (для Oracle 11g нужен именно 19.x) | `D:\transfer\bin\` |
| `vc_redist.x64.exe` | Microsoft VC++ Redistributable — про запас, скрипт его НЕ ставит | `D:\transfer\bin\` |
| `node-x64.msi` | Node.js LTS x64 (только если фронт собирается на машине B) | `D:\transfer\bin\` |
| `Qwen2.5-7B-Instruct-Q4_K_M.gguf.part1..3` | модель, разбитая на части | `D:\transfer\models\` |
| `SHA256SUMS.txt` | хеши всех файлов + хеш склеенной модели (строка `ASSEMBLED:`) | `D:\transfer\` |

Python-пакеты в `wheels.zip` (со всеми зависимостями): `llama-cpp-python` (cu118), `oracledb`, `fastapi`, `uvicorn[standard]`, `sse-starlette`, `python-multipart`, `faiss-cpu`, `pypdf`, `python-docx`, `openpyxl`.

## Что лежит в самом репозитории

Помимо ассетов релиза, в репозитории едут файлы, которые нужны на машине B:

| Папка | Что это |
|---|---|
| `llm-chat-app/` | **снимок** исходников чат-приложения (Vue 3 + FastAPI + Oracle + llama.cpp). Оригинал и вся история — в [Shomen-ai/llm-chat-app](https://github.com/Shomen-ai/llm-chat-app); правки вносить там, сюда переносить снимком |
| `guides/` | инструкции: настройка Ruff, офлайн-закачка расширений VS Code, подборка цветовых тем |
| `vsix-offline/` | готовые `.vsix` для установки без интернета: Ruff (win32-x64) и 5 тем |
| `scripts/` | `check_and_install.bat` — установка бандла, `diagnose_llm_crash.bat` — сбор улик при падении LLM |

## Важные оговорки

- **Про cu118 в имени файла.** Старые версии llama-cpp-python помечались `+cu118` в имени колеса — начиная с 0.3.x метки в имени нет, файл называется одинаково с CPU-сборкой. Это колесо скачано напрямую с CUDA-индекса abetlen (внутри — `ggml-cuda.dll` ~750 МБ), а установщик проверяет CUDA по факту: `llama_supports_gpu_offload()` должен вернуть `True`.
- **constraints.txt.** Колёса качались без слепка окружения машины B (шаг 0 исходной инструкции). Если на машине B уже стоит бандл с зафиксированными версиями — снимите там `pip freeze > constraints.txt` и сверьте на конфликты; при необходимости перекачайте колёса с `-c constraints.txt` (раздел A1 в `docs-offline-transfer-setup.txt`).
- **uvloop-ловушка.** `pip download` для чужой платформы оценивает маркеры зависимостей по своей ОС, поэтому качать `uvicorn[standard]` с macOS/Linux нельзя — список для скачивания развёрнут в [`requirements-download.txt`](requirements-download.txt) (+ явная `colorama`, она win-only). На машине B ставится обычный [`requirements-new.txt`](requirements-new.txt).
- **pip freeze не запоминает CUDA-сборку** — поэтому установщик сохраняет само колесо в `D:\bundle\wheels\` на будущее.
- Полная исходная инструкция со всеми запасными командами и разбором частых ошибок: [`docs-offline-transfer-setup.txt`](docs-offline-transfer-setup.txt).

## Как это скачивалось

Колёса добывались на macOS с явным указанием целевой платформы — поэтому подходят только для Windows x64 + CPython 3.11:

```
pip download -r requirements-download.txt \
  --only-binary=:all: \
  --platform win_amd64 --python-version 311 --implementation cp --abi cp311 \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu118 \
  --dest wheels
```

## Лицензии

Репозиторий зеркалирует только свободно распространяемые компоненты; подробности — в [LICENSES.md](LICENSES.md). Скрипты этого репозитория — MIT.
