@echo off
chcp 65001 >nul
rem === Отдельный сервер с нейронкой (порт 8001) ===
set "VENV=D:\bundle\ml-bundle\.venv"
set "MODELS_DIR=D:\bundle\models"
set "N_GPU_LAYERS=-1"
set "N_CTX=8192"
set "LLM_HOST=127.0.0.1"
set "LLM_PORT=8001"

call "%VENV%\Scripts\activate"
cd /d "%~dp0..\llm-server"
python server.py
pause
