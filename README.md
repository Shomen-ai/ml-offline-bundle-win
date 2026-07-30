# ml-offline-bundle-win

Офлайн-бандл ML-библиотек для **изолированной Windows-машины** (x64, Python 3.11, NVIDIA RTX A4000): CUDA-сборка `llama-cpp-python`, FastAPI-стек, `faiss-cpu`, `oracledb` + Oracle Instant Client 19, VC++ Redistributable, Node.js LTS и GGUF-модель Qwen2.5-7B-Instruct.

Сами бинарники лежат не в git, а в **[Releases](../../releases)** (модель разбита на части по <2 ГБ — лимит GitHub). В репозитории — скрипты, манифест хешей и инструкция.

## Быстрый старт

**Машина A (с интернетом, Windows 10/11):**

```bat
curl -fLO https://raw.githubusercontent.com/Shomen-ai/ml-offline-bundle-win/main/scripts/download_release.ps1
powershell -ExecutionPolicy Bypass -File download_release.ps1
```

Скрипт скачает все файлы релиза в `D:\transfer` (докачивает при обрывах), сверит SHA256 и распакует колёса. Дальше — вся папка `D:\transfer` на флешку.

**Машина B (изолированная):** положить папку как `D:\transfer` и запустить

```bat
D:\transfer\scripts\install.bat
```

Скрипт: сверит хеши → склеит модель из частей и проверит её SHA256 → поставит VC++ Redist → распакует Instant Client в `D:\oracle` → установит пакеты строго офлайн (`pip --no-index`) → прогонит проверки (GPU-offload llama.cpp, версия Oracle-клиента, тестовый ответ модели на GPU). Ключи: `-TransferDir`, `-BundleDir`, `-OracleDir`, `-SkipSystem`, `-SkipModelTest`, `-SkipChecksums`.

## Состав релиза

| Файл | Что это | Куда кладётся |
|---|---|---|
| `wheels.zip` | все .whl под `win_amd64` / `cp311`, llama-cpp — сборка **cu118** | `D:\transfer\wheels\` |
| `instantclient19.zip` | Oracle Instant Client 19.31 Basic x64 (для Oracle 11g нужен именно 19.x) | `D:\transfer\bin\` |
| `vc_redist.x64.exe` | Microsoft VC++ Redistributable (нужен llama.cpp и Instant Client) | `D:\transfer\bin\` |
| `node-x64.msi` | Node.js LTS x64 (только если фронт собирается на машине B) | `D:\transfer\bin\` |
| `Qwen2.5-7B-Instruct-Q4_K_M.gguf.part1..3` | модель, разбитая на части | `D:\transfer\models\` |
| `SHA256SUMS.txt` | хеши всех файлов + хеш склеенной модели (`ASSEMBLED:`) | `D:\transfer\` |

Python-пакеты в `wheels.zip` (со всеми зависимостями): `llama-cpp-python` (cu118), `oracledb`, `fastapi`, `uvicorn[standard]`, `sse-starlette`, `python-multipart`, `faiss-cpu`, `pypdf`, `python-docx`, `openpyxl`.

## Важные оговорки

- **constraints.txt.** Колёса качались без слепка окружения машины B (шаг 0 исходной инструкции). Если на машине B уже стоит бандл с зафиксированными версиями — снимите там `pip freeze > constraints.txt` и проверьте на конфликты; при необходимости перекачайте колёса с `-c constraints.txt` (команда — в `docs-offline-transfer-setup.txt`, раздел A1).
- **cu118.** Установщик сам проверяет, что колесо `llama_cpp_python` содержит `cu118` в имени, и предупредит, если приехала CPU-сборка.
- **pip freeze не запоминает cu118** — поэтому установщик сохраняет само CUDA-колесо в `D:\bundle\wheels\` на будущее.
- Полная исходная инструкция со всеми запасными командами и разбором частых ошибок: [`docs-offline-transfer-setup.txt`](docs-offline-transfer-setup.txt).

## Как это скачивалось

Колёса добывались на macOS с явным указанием целевой платформы — поэтому подходят только для Windows x64 + CPython 3.11:

```
pip download -r requirements-new.txt \
  --only-binary=:all: \
  --platform win_amd64 --python-version 311 --implementation cp --abi cp311 \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu118 \
  --dest wheels
```

## Лицензии

Репозиторий распространяет только свободно распространяемые компоненты; подробности и ссылки — в [LICENSES.md](LICENSES.md). Скрипты этого репозитория — MIT.
