@echo off
chcp 65001 >nul
rem === Создание таблиц в Oracle (однократно). apply_schema.bat --drop = пересоздать ===
set "VENV=D:\bundle\ml-bundle\.venv"

call "%VENV%\Scripts\activate"
cd /d "%~dp0..\backend"
python apply_schema.py %*
pause
