@echo off
chcp 65001 >nul
rem === Dev-сервер фронта (порт 5173) — только для разработки.
rem === На машине B обычно не нужен: соберите dist и его отдаст backend.
cd /d "%~dp0..\frontend"
rem ВНИМАНИЕ: внутри блока в круглых скобках cmd принимает любую закрывающую
rem скобку за конец блока — в текстах echo ниже их быть не должно.
if not exist "node_modules" (
    echo [!] Нет node_modules. На машине с интернетом: npm install
    echo     На изолированной: скопируйте node_modules целиком — см. README.
    pause
    exit /b 1
)
npm run dev
pause
