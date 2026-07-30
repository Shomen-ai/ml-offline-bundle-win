# Офлайн-закачка расширений VS Code

Как скачать расширение на машине с интернетом (A) и установить на машине
без интернета (B). Проверено на переносе Ruff и тем на рабочую Windows-машину
(июль 2026). Готовые файлы лежат в `vsix-offline/`, там же `README-INSTALL.txt`
для машины B.

## Главное в двух словах

Расширения VS Code — это файлы `.vsix` (обычные zip-архивы). Их можно скачать
прямой ссылкой с маркетплейса и установить офлайн. **Просто скопировать файл в
папку `extensions` нельзя** — его нужно установить командой или через меню,
тогда VS Code сам распакует и зарегистрирует расширение.

## Шаг 1. Узнать идентификатор расширения

На странице расширения в [маркетплейсе](https://marketplace.visualstudio.com) —
поле **Unique Identifier**, формат `издатель.имя`:

- Ruff → `charliermarsh.ruff`
- One Dark Pro → `zhuangtongfa.material-theme`
- GitHub Theme → `GitHub.github-vscode-theme`

## Шаг 2. Скачать .vsix

### Универсальные расширения (темы, сниппеты — без бинарников)

Работает `latest`, версию знать не нужно:

```bash
curl -sL --compressed -o тема.vsix \
  "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/{ИЗДАТЕЛЬ}/vsextensions/{ИМЯ}/latest/vspackage"
```

### Платформо-зависимые (Ruff, Python, Pylance — содержат exe/dll)

Два отличия: нужен параметр `targetPlatform` и **точная версия** —
`latest` с `targetPlatform` маркетплейс не принимает.

Узнать последнюю версию через API:

```bash
curl -s -X POST "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json;api-version=3.0-preview.1" \
  -d '{"filters":[{"criteria":[{"filterType":7,"value":"charliermarsh.ruff"}]}],"flags":17}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); \
    [print(v['version'], v.get('targetPlatform','universal')) \
     for v in d['results'][0]['extensions'][0]['versions'][:8]]"
```

Скачать нужную сборку (для рабочей машины — `win32-x64`):

```bash
curl -sL --compressed -o ruff-win32-x64.vsix \
  "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/charliermarsh/vsextensions/ruff/{ВЕРСИЯ}/vspackage?targetPlatform=win32-x64"
```

Возможные платформы: `win32-x64`, `win32-arm64`, `linux-x64`, `linux-arm64`,
`darwin-x64`, `darwin-arm64`, `alpine-x64`.

### Проверить, что скачался архив, а не ошибка

```bash
file файл.vsix        # должно быть: Zip archive data
ls -lh файл.vsix      # ошибка = крохотный файл с JSON внутри
```

Посмотреть версию и требуемый VS Code, не распаковывая:

```bash
unzip -p файл.vsix extension/package.json | python3 -m json.tool | grep -E '"version"|vscode'
```

### Запасной источник

[open-vsx.org](https://open-vsx.org) — альтернативный реестр с прямыми
кнопками скачивания; большинство популярных расширений публикуются и там.

## Шаг 3. Установить на машине B

Требование: версия VS Code на машине B не ниже указанной в `engines.vscode`
пакета (Help → About).

Через консоль:

```
code --install-extension D:\transfer\vsix-offline\файл.vsix
```

Или мышкой: `Ctrl+Shift+X` → меню «...» в углу панели → **Install from VSIX...**

После установки перезапустить VS Code.

## Частые грабли

| Симптом | Причина |
|---|---|
| Файл 400 байт с JSON | `latest` + `targetPlatform` — нужна точная версия |
| «has no support for targetPlatform» | То же самое, либо опечатка в платформе |
| Расширение не появилось после копирования в `extensions` | .vsix нельзя копировать — только устанавливать (см. Шаг 3) |
| «is not compatible with VS Code» | VS Code на машине B старее, чем требует расширение — скачать более старую версию расширения |
| Ruff не работает на Windows | Скачана сборка не той платформы (например, darwin вместо win32-x64) |
