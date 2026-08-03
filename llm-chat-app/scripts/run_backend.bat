@echo off
chcp 65001 >nul
rem === Backend FastAPI (порт 8000). Если frontend\dist собран — отдаёт и фронт ===
set "VENV=D:\bundle\ml-bundle\.venv"

call "%VENV%\Scripts\activate"
cd /d "%~dp0..\backend"
if not exist ".env" (
    echo [!] Нет backend\.env — копирую из .env.example, ЗАПОЛНИТЕ реквизиты Oracle!
    copy .env.example .env >nul
)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
