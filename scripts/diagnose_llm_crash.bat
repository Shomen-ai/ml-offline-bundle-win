@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
rem ===========================================================================
rem  diagnose_llm_crash.bat — МАШИНА B (изолированная, Windows x64)
rem
rem  Собирает улики по падению llama-server с кодом 0xC0000005
rem  (access violation — обращение по недопустимому адресу памяти).
rem
rem  Ничего не чинит и не меняет. Только читает и пишет отчёт в файл
rem  diagnose_output.txt рядом со скриптом — его можно вынести на машину A.
rem
rem  Запускать обычным двойным кликом или из cmd. Админ не нужен.
rem ===========================================================================

set "OUT=%~dp0diagnose_output.txt"
call :main > "%OUT%" 2>&1
type "%OUT%"
echo.
echo ===========================================================
echo  Отчёт сохранён: %OUT%
echo  Вынесите этот файл на машину A для разбора.
echo ===========================================================
pause
exit /b 0


:main
echo ############################################################
echo #  ОТЧЁТ О ПАДЕНИИ LLM
echo #  Дата: %DATE% %TIME%
echo #  Машина: %COMPUTERNAME%
echo ############################################################
echo.

echo === 1. КТО ВООБЩЕ ЗАПУЩЕН =================================
echo Ищу процессы ollama / llama-server / python:
tasklist /fi "IMAGENAME eq ollama.exe" 2>nul | findstr /i ollama || echo   ollama.exe не запущен
tasklist /fi "IMAGENAME eq ollama app.exe" 2>nul | findstr /i ollama || echo   ollama app.exe не запущен
tasklist /fi "IMAGENAME eq llama-server.exe" 2>nul | findstr /i llama || echo   llama-server.exe не запущен
tasklist /fi "IMAGENAME eq python.exe" 2>nul | findstr /i python || echo   python.exe не запущен
echo.
echo Версия Ollama (если установлен) — САМОЕ ВАЖНОЕ ПОЛЕ:
where ollama >nul 2>&1 && (ollama --version 2>&1) || echo   ollama не найден в PATH
echo.
echo Список моделей Ollama:
ollama list 2>&1 || echo   не удалось получить список
echo.
echo Как импортирована проблемная модель (Modelfile):
ollama show --modelfile qwen3-14b_Q_4_K_M 2>&1 | findstr /i "FROM PARAMETER TEMPLATE num_gpu num_ctx" || echo   не удалось прочитать Modelfile
echo.
echo Слушающие порты 11434 (ollama) и 8001 (ваш llm-server):
netstat -ano | findstr /r ":11434 :8001" || echo   ни один из портов не слушается
echo.

echo === 2. ГЛАВНАЯ УЛИКА: КАКОЙ МОДУЛЬ УПАЛ ====================
echo Последние 5 записей Application Error из журнала Windows.
echo Смотреть поле "Faulting module name" — оно называет виновника.
echo.
wevtutil qe Application /q:"*[System[(EventID=1000)]]" /c:5 /rd:true /f:text 2>nul || echo   [!] Не удалось прочитать журнал (попробуйте запустить от администратора)
echo.

echo === 3. ВИДЕОКАРТА И ДРАЙВЕР ===============================
set "NVSMI=nvidia-smi"
where nvidia-smi >nul 2>&1 || set "NVSMI=%SystemRoot%\System32\nvidia-smi.exe"
"%NVSMI%" 2>nul || echo   [!] nvidia-smi не найден — драйвер NVIDIA не установлен?
echo.
echo Версия драйвера и свободная память:
"%NVSMI%" --query-gpu=name,driver_version,memory.total,memory.used,memory.free --format=csv 2>nul || echo   [!] не удалось опросить GPU
echo.
echo Что уже занимает VRAM:
"%NVSMI%" --query-compute-apps=pid,process_name,used_memory --format=csv 2>nul || echo   [!] не удалось получить список процессов
echo.

echo === 4. ЛОГ OLLAMA =========================================
set "OLOG=%LOCALAPPDATA%\Ollama\server.log"
if exist "%OLOG%" (
    echo Последние 60 строк %OLOG%:
    echo -----------------------------------------------------------
    powershell -NoProfile -Command "Get-Content -Tail 60 -LiteralPath '%OLOG%'" 2>nul || (
        echo   [!] powershell недоступен, показываю файл целиком:
        type "%OLOG%"
    )
) else (
    echo   %OLOG% не найден — либо Ollama не установлен, либо ни разу не запускался.
)
echo.

echo === 5. PYTHON-ОКРУЖЕНИЕ БАНДЛА ============================
set "PY=D:\bundle\ml-bundle\.venv\Scripts\python.exe"
if exist "%PY%" (
    "%PY%" -c "import sys; print('Python', sys.version)"
    echo.
    echo Установлен ли llama-cpp-python:
    "%PY%" -m pip show llama-cpp-python 2>nul | findstr /i "Name Version Location" || echo   llama-cpp-python НЕ установлен
    echo.
    echo Собран ли llama_cpp с поддержкой CUDA:
    "%PY%" -c "import llama_cpp; print('llama_cpp', llama_cpp.__version__); from llama_cpp import llama_cpp as C; print('GPU offload:', C.llama_supports_gpu_offload())" 2>&1 | findstr /v "Traceback" || echo   llama_cpp не импортируется
) else (
    echo   Виртуальное окружение не найдено: %PY%
    echo   Если бандл лежит в другом месте — поправьте путь PY в начале раздела 5.
)
echo.

echo === 6. ФАЙЛЫ МОДЕЛЕЙ ======================================
for %%D in ("D:\bundle\models" "%LOCALAPPDATA%\Ollama\models") do (
    if exist "%%~D" (
        echo Содержимое %%~D:
        dir /-c "%%~D" 2>nul | findstr /i "gguf part <DIR> File(s)"
    ) else (
        echo %%~D — папки нет
    )
    echo.
)
echo Недосклеенные части модели (если остались .part — сборка не завершалась):
dir /b /s "D:\bundle\*.gguf.part*" 2>nul || echo   частей не найдено — хорошо
echo.

echo === 7. ПАМЯТЬ И ПРОЦЕССОР =================================
wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /value 2>nul | findstr "=" || echo   wmic недоступен
wmic cpu get Name /value 2>nul | findstr "=" || echo   не удалось определить CPU
echo.

echo ############################################################
echo #  КОНЕЦ ОТЧЁТА
echo ############################################################
exit /b 0
