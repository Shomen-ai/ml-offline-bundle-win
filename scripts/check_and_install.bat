@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
rem ===========================================================================
rem  check_and_install.bat — МАШИНА B (изолированная, Windows x64, Python 3.11)
rem  Чистый cmd, без PowerShell.
rem
rem  Делает по шагам:
rem    1. Проверяет структуру D:\transfer
rem    2. Сверяет SHA256 всех файлов с манифестом (certutil)
rem    3. Распаковывает wheels.zip (tar), склеивает модель из частей (copy /b)
rem       и сверяет хеш склейки
rem    4. Распаковывает Oracle Instant Client в D:\oracle
rem       (vc_redist НЕ устанавливается — файл просто лежит в bin\ на случай
rem        ошибки про VCRUNTIME140.dll: bin\vc_redist.x64.exe /install /passive)
rem    5. Ставит python-пакеты СТРОГО ОФЛАЙН: pip --no-index из wheels
rem    6. Проверки: GPU-offload llama.cpp, версия Oracle-клиента,
rem       тестовый ответ модели на GPU
rem    7. pip freeze + сохраняет CUDA-колесо llama-cpp в D:\bundle\wheels
rem
rem  Запуск:
rem    check_and_install.bat                          (всё по умолчанию)
rem    check_and_install.bat E:\transfer              (флешка не в D:)
rem    check_and_install.bat D:\transfer --skip-model-test
rem ===========================================================================

set "TRANSFER=D:\transfer"
if not "%~1"=="" set "TRANSFER=%~1"
set SKIP_MODEL_TEST=0
if /i "%~2"=="--skip-model-test" set SKIP_MODEL_TEST=1

set "BUNDLE=D:\bundle"
set "ORACLE=D:\oracle"
set "VENV=%BUNDLE%\ml-bundle\.venv"
set "WHEELS=%TRANSFER%\wheels"
set "BIN=%TRANSFER%\bin"
set "MODELS=%TRANSFER%\models"
set "REQ=%TRANSFER%\requirements-new.txt"
set "SUMS=%TRANSFER%\SHA256SUMS.txt"
set FAIL=0

echo.
echo === 1. Структура %TRANSFER% ===
for %%d in ("%WHEELS%" "%BIN%" "%MODELS%") do (
    if exist %%d (echo   [OK]   %%~d) else (echo   [FAIL] нет папки %%~d & set /a FAIL+=1)
)
if not exist "%REQ%" (echo   [FAIL] нет %REQ% & set /a FAIL+=1)
if !FAIL! gtr 0 (
    echo.
    echo Структура неполная — сначала выполните download_release.bat на машине с интернетом.
    goto :done_fail
)

echo.
echo === 2. Сверка SHA256 (пару минут, файлы большие) ===
if not exist "%SUMS%" (
    echo   [WARN] SHA256SUMS.txt не найден — сверку пропускаю
    goto :unzip_wheels
)
set MODEL_NAME=
set MODEL_HASH=
for /f "usebackq tokens=1,2" %%a in ("%SUMS%") do (
    set "N=%%b"
    if "!N:~0,10!"=="ASSEMBLED:" (
        set "MODEL_HASH=%%a"
        set "MODEL_NAME=!N:~10!"
    ) else (
        call :verify_one "%%a" "!N!"
    )
)
if !FAIL! gtr 0 (
    echo.
    echo Есть побитые файлы — скопируйте их заново и перезапустите.
    goto :done_fail
)

:unzip_wheels
echo.
echo === 3a. Колёса ===
if exist "%TRANSFER%\wheels.zip" (
    dir /b "%WHEELS%\*.whl" >nul 2>&1
    if errorlevel 1 (
        echo   Распаковываю wheels.zip ...
        tar -xf "%TRANSFER%\wheels.zip" -C "%WHEELS%"
    )
)
set WHL_COUNT=0
for /f %%c in ('dir /b "%WHEELS%\*.whl" 2^>nul ^| find /c /v ""') do set WHL_COUNT=%%c
echo   [OK]   колёс в папке: !WHL_COUNT!
if !WHL_COUNT!==0 (echo   [FAIL] колёс нет & set /a FAIL+=1 & goto :done_fail)

echo.
echo === 3b. Модель GGUF ===
if "%MODEL_NAME%"=="" (
    rem манифеста нет — ищем любую готовую .gguf
    for %%f in ("%MODELS%\*.gguf") do set "MODEL_NAME=%%~nxf"
)
if "%MODEL_NAME%"=="" (
    echo   [WARN] модель не найдена — шаг пропущен
    set "MODEL_PATH="
    goto :oracle
)
set "MODEL_FULL=%MODELS%\%MODEL_NAME%"
if exist "%MODEL_FULL%" (
    echo   [OK]   модель уже целая: %MODEL_NAME%
    goto :model_hash
)
dir /b "%MODELS%\%MODEL_NAME%.part*" >nul 2>&1
if errorlevel 1 (
    echo   [WARN] нет ни модели, ни её частей — шаг пропущен
    set "MODEL_PATH="
    goto :oracle
)
echo   Склеиваю части в %MODEL_NAME% (5+ ГБ, подождите)...
set CONCAT=
for /f "delims=" %%f in ('dir /b /on "%MODELS%\%MODEL_NAME%.part*"') do (
    if defined CONCAT (set "CONCAT=!CONCAT!+"%MODELS%\%%f"") else (set "CONCAT="%MODELS%\%%f"")
)
copy /b !CONCAT! "%MODEL_FULL%" >nul
if errorlevel 1 (echo   [FAIL] склейка не удалась & set /a FAIL+=1 & goto :done_fail)
echo   [OK]   склеено

:model_hash
if not "%MODEL_HASH%"=="" (
    echo   Проверяю SHA256 склеенной модели...
    certutil -hashfile "%MODEL_FULL%" SHA256 | findstr /i /c:"%MODEL_HASH%" >nul
    if errorlevel 1 (
        echo   [FAIL] SHA256 модели НЕ совпал — части побились или их не хватает
        set /a FAIL+=1
        goto :done_fail
    )
    echo   [OK]   SHA256 модели совпал
)
if not exist "%BUNDLE%\models" mkdir "%BUNDLE%\models"
copy /y "%MODEL_FULL%" "%BUNDLE%\models\" >nul
set "MODEL_PATH=%BUNDLE%\models\%MODEL_NAME%"
echo   [OK]   модель скопирована в %MODEL_PATH%

:oracle
echo.
echo === 4. Oracle Instant Client (vc_redist НЕ ставим) ===
if exist "%BIN%\vc_redist.x64.exe" echo   [i]    vc_redist лежит в bin\ — ставить только если будет ошибка VCRUNTIME140.dll
set "ICDIR="
if exist "%BIN%\instantclient19.zip" (
    if not exist "%ORACLE%" mkdir "%ORACLE%"
    dir /b /ad "%ORACLE%\instantclient*" >nul 2>&1
    if errorlevel 1 (
        echo   Распаковываю Instant Client...
        tar -xf "%BIN%\instantclient19.zip" -C "%ORACLE%"
    )
) else (
    echo   [WARN] instantclient19.zip не найден
)
for /f "delims=" %%d in ('dir /b /ad "%ORACLE%\instantclient*" 2^>nul') do set "ICDIR=%ORACLE%\%%d"
if defined ICDIR (echo   [OK]   Instant Client: !ICDIR!) else (echo   [WARN] каталога instantclient_* нет — проверка Oracle будет пропущена)

echo.
echo === 5. Python-пакеты (строго офлайн) ===
set "PY=%VENV%\Scripts\python.exe"
if not exist "%PY%" (
    echo   [WARN] venv не найден: %VENV%
    where py >nul 2>&1
    if errorlevel 1 (
        echo   [FAIL] нет ни venv, ни py-launcher. Установите Python 3.11 и перезапустите.
        set /a FAIL+=1
        goto :done_fail
    )
    echo   Создаю venv через "py -3.11"...
    py -3.11 -m venv "%VENV%"
    if not exist "%PY%" (echo   [FAIL] venv не создался — установлен ли Python 3.11? & set /a FAIL+=1 & goto :done_fail)
)
"%PY%" -c "import sys; open(r'%TEMP%\pyver.txt','w').write('%%d.%%d' %% sys.version_info[:2])" 2>nul
set /p PYVER=<"%TEMP%\pyver.txt"
if not "%PYVER%"=="3.11" (
    echo   [FAIL] venv на Python %PYVER%, а колёса под 3.11 — ставиться не будут
    set /a FAIL+=1
    goto :done_fail
)
echo   [OK]   Python %PYVER%

"%PY%" -m pip uninstall -y ollama langchain-ollama >nul 2>&1
echo   pip install --no-index --find-links="%WHEELS%" -r "%REQ%"
"%PY%" -m pip install --no-index --find-links="%WHEELS%" -r "%REQ%"
if errorlevel 1 (
    echo   [FAIL] pip install упал. Обычно это значит: какой-то зависимости нет в wheels.
    echo   Запишите имя пакета из ошибки и докачайте на машине с интернетом:
    echo   pip download ИМЯ --only-binary=:all: --platform win_amd64 --python-version 311 --implementation cp --abi cp311 --dest wheels
    set /a FAIL+=1
    goto :done_fail
)
echo   [OK]   пакеты установлены офлайн

echo.
echo === 6. Проверки работоспособности ===
rem -- 6a. CUDA у llama.cpp (проверка по факту: имя файла с 0.3.x больше не содержит cu118)
"%PY%" -c "from llama_cpp import llama_cpp; print('GPU offload:', llama_cpp.llama_supports_gpu_offload())" > "%TEMP%\gpu.txt" 2>&1
findstr /c:"GPU offload: True" "%TEMP%\gpu.txt" >nul
if errorlevel 1 (
    echo   [FAIL] llama.cpp: GPU offload НЕ поддерживается — приехало CPU-колесо?
    type "%TEMP%\gpu.txt"
    set /a FAIL+=1
) else (
    echo   [OK]   llama.cpp: GPU offload поддерживается
)

rem -- 6b. Oracle Instant Client
if defined ICDIR (
    "%PY%" -c "import oracledb; oracledb.init_oracle_client(lib_dir=r'!ICDIR!'); print('Oracle client:', oracledb.clientversion())" > "%TEMP%\ora.txt" 2>&1
    findstr /c:"Oracle client: (19" "%TEMP%\ora.txt" >nul
    if errorlevel 1 (
        echo   [FAIL] oracledb / Instant Client:
        type "%TEMP%\ora.txt"
        set /a FAIL+=1
    ) else (
        echo   [OK]   Oracle Instant Client 19.x подхватился
    )
)

rem -- 6c. Модель на GPU (можно пропустить: второй аргумент --skip-model-test)
if "%SKIP_MODEL_TEST%"=="1" goto :freeze
if not defined MODEL_PATH goto :freeze
echo   Тестовая загрузка модели на GPU (около минуты, смотрите nvidia-smi)...
"%PY%" -c "from llama_cpp import Llama; l=Llama(model_path=r'%MODEL_PATH%', n_gpu_layers=-1, n_ctx=2048, verbose=False); print('MODEL SAYS:', l.create_chat_completion(messages=[{'role':'user','content':'2+2?'}], max_tokens=16)['choices'][0]['message']['content'])" > "%TEMP%\mdl.txt" 2>&1
findstr /c:"MODEL SAYS:" "%TEMP%\mdl.txt" >nul
if errorlevel 1 (
    echo   [FAIL] модель не загрузилась:
    type "%TEMP%\mdl.txt"
    set /a FAIL+=1
) else (
    for /f "delims=" %%l in ('findstr /c:"MODEL SAYS:" "%TEMP%\mdl.txt"') do echo   [OK]   %%l
)

:freeze
echo.
echo === 7. Фиксация результата ===
"%PY%" -m pip freeze > "%BUNDLE%\ml-bundle\requirements.txt" 2>nul && echo   [OK]   pip freeze -^> %BUNDLE%\ml-bundle\requirements.txt
if not exist "%BUNDLE%\wheels" mkdir "%BUNDLE%\wheels"
copy /y "%WHEELS%\llama_cpp_python*.whl" "%BUNDLE%\wheels\" >nul 2>&1 && echo   [OK]   CUDA-колесо llama-cpp сохранено в %BUNDLE%\wheels (pip freeze не помнит про CUDA!)

echo.
if !FAIL!==0 (
    echo ГОТОВО: все проверки пройдены.
    pause
    exit /b 0
)

:done_fail
echo.
echo ЗАВЕРШЕНО С ОШИБКАМИ: !FAIL! проблем(ы), смотрите вывод выше.
pause
exit /b 1

rem ---------------------------------------------------------------------------
:verify_one
rem %1 = ожидаемый хеш, %2 = имя файла из манифеста
set "H=%~1"
set "F=%~2"
rem раскладка: части модели -> models\, wheels.zip -> корень, остальное -> bin\
echo %F% | findstr /i ".gguf.part" >nul
if not errorlevel 1 (set "P=%MODELS%\%F%") else (
    if /i "%F%"=="wheels.zip" (set "P=%TRANSFER%\%F%") else (set "P=%BIN%\%F%")
)
if not exist "!P!" (
    echo   [WARN] нет файла: %F% — пропускаю
    goto :eof
)
certutil -hashfile "!P!" SHA256 | findstr /i /c:"%H%" >nul
if errorlevel 1 (
    echo   [FAIL] %F% — хеш не совпал, файл побился при копировании
    set /a FAIL+=1
) else (
    echo   [OK]   %F%
)
goto :eof
