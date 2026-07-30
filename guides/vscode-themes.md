# Цветовые темы VS Code — подборка

Визуальное сравнение всех тем на одном фрагменте Python-кода (с фильтрами
по типу и насыщенности): https://claude.ai/code/artifact/65d16892-a2a8-4b76-95c2-ee41f1b16ff6

Уже скачаны для офлайн-установки (лежат в `vsix-offline/`): One Dark Pro,
GitHub Theme, Tokyo Night, Catppuccin, Nord.

## Как переключать и устанавливать

- Переключение темы: `Cmd+K Cmd+T` (Mac) / `Ctrl+K Ctrl+T` (Windows) —
  список листается стрелками с живым предпросмотром на вашем коде.
- Установка при наличии интернета: `Cmd/Ctrl+Shift+X` → имя темы → Install,
  либо `code --install-extension <id>`.
- Установка офлайн: см. `vscode-extensions-offline.md`.

## Приглушённые тёмные (если яркая тема утомляет)

| Тема | ID расширения | Характер |
|---|---|---|
| Nord | `arcticicestudio.nord-visual-studio-code` | Самая спокойная: 16 низконасыщенных «арктических» цветов |
| Tokyo Night | `enkia.tokyo-night` | Сине-фиолетовая, мягкая; вариант Storm чуть светлее |
| Catppuccin (Mocha) | `Catppuccin.catppuccin-vsc` | Пастельная; 4 варианта от светлого Latte до тёмного Mocha |
| GitHub Dark / Dark Dimmed | `GitHub.github-vscode-theme` | Нейтральная «рабочая»; Dimmed — самый мягкий вариант |
| One Dark Pro | `zhuangtongfa.material-theme` | Классика из Atom, сбалансированная, самая популярная тёмная |
| Night Owl | `sdras.night-owl` | Для ночной работы, проверена на дальтонизм |
| Gruvbox Dark | `jdinhlife.gruvbox` | Тёплые землистые тона, ретро из мира Vim |

## Яркие тёмные (контрастные)

| Тема | ID расширения | Характер |
|---|---|---|
| Dracula | `dracula-theme.theme-dracula` | Неоновые розовый/зелёный/фиолетовый |
| Monokai Pro | `monokai.theme-monokai-pro-vscode` | Классика Sublime Text; платная ~10 $ |

## Светлые

| Тема | ID расширения | Характер |
|---|---|---|
| GitHub Light | `GitHub.github-vscode-theme` | Строгая нейтральная, «офисная» |
| Catppuccin Latte | `Catppuccin.catppuccin-vsc` | Пастель на молочном фоне, теплее белых |
| Solarized Light | встроена в VS Code | Низкоконтрастная колориметрическая классика 2011 г. |

## Дополнительно

- Встроенная тёмная **Dark Modern** (по умолчанию с 2023 г.) — неплохая
  отправная точка без установки чего-либо.
- Иконки файлов: **Material Icon Theme** (`pkief.material-icon-theme`) —
  стоит почти у всех, сильно улучшает читаемость дерева файлов.
- Совет по выбору: поставить 2–3 кандидата и пожить на каждой день-два,
  переключаясь через `Ctrl+K Ctrl+T`, — по скриншотам не выбрать.
