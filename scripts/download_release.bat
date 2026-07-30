@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
rem ===========================================================================
rem  download_release.bat — МАШИНА A (с интернетом, Windows 10/11)
rem  Чистый cmd, без PowerShell. curl и tar встроены в Windows 10 1803+.
rem
rem  Скачивает все файлы GitHub Release и раскладывает в структуру,
rem  которую ждёт check_and_install.bat:
rem      D:\transfer\wheels\*.whl        (из wheels.zip)
rem      D:\transfer\bin\*.zip .exe .msi
rem      D:\transfer\models\*.gguf.part1..3
rem      D:\transfer\requirements-new.txt, SHA256SUMS.txt, scripts\
rem
rem  Докачивает с места обрыва (curl -C -). Запуск:
rem    download_release.bat                (в D:\transfer)
rem    download_release.bat E:\transfer    (в другое место)
rem ===========================================================================

set "REPO=Shomen-ai/ml-offline-bundle-win"
set "TAG=v1.0.0"
set "DEST=D:\transfer"
if not "%~1"=="" set "DEST=%~1"
set "BASE=https://github.com/%REPO%/releases/download/%TAG%"
set "RAW=https://raw.githubusercontent.com/%REPO%/main"
set FAIL=0

for %%d in ("%DEST%" "%DEST%\wheels" "%DEST%\bin" "%DEST%\models" "%DEST%\scripts") do if not exist %%d mkdir %%d

echo.
echo === 1/4: манифест и сопроводительные файлы ===
call :get "%BASE%/SHA256SUMS.txt"                    "%DEST%\SHA256SUMS.txt"
call :get "%RAW%/requirements-new.txt"               "%DEST%\requirements-new.txt"
call :get "%RAW%/scripts/check_and_install.bat"      "%DEST%\scripts\check_and_install.bat"
if !FAIL! gtr 0 goto :bad

echo.
echo === 2/4: файлы релиза по манифесту ===
for /f "usebackq tokens=1,2" %%a in ("%DEST%\SHA256SUMS.txt") do (
    set "N=%%b"
    if not "!N:~0,10!"=="ASSEMBLED:" call :route_get "!N!"
)
if !FAIL! gtr 0 goto :bad

echo.
echo === 3/4: сверка SHA256 ===
for /f "usebackq tokens=1,2" %%a in ("%DEST%\SHA256SUMS.txt") do (
    set "N=%%b"
    if not "!N:~0,10!"=="ASSEMBLED:" call :verify "%%a" "!N!"
)
if !FAIL! gtr 0 (
    echo.
    echo Часть файлов скачалась битой — просто перезапустите скрипт: докачает и перепроверит.
    goto :bad
)

echo.
echo === 4/4: распаковка wheels.zip ===
tar -xf "%DEST%\wheels.zip" -C "%DEST%\wheels"
set WHL=0
for /f %%c in ('dir /b "%DEST%\wheels\*.whl" 2^>nul ^| find /c /v ""') do set WHL=%%c
echo   колёс: !WHL!

echo.
echo ГОТОВО. Скопируйте всю папку %DEST% на флешку и на рабочей машине запустите:
echo   D:\transfer\scripts\check_and_install.bat
pause
exit /b 0

:bad
echo.
echo ЗАВЕРШЕНО С ОШИБКАМИ: !FAIL! — смотрите вывод выше.
pause
exit /b 1

rem ---------------------------------------------------------------------------
:get
rem %1 = url, %2 = куда
echo   ^<- %~nx2
curl -fL --retry 5 --retry-delay 5 -C - -o "%~2" "%~1"
if errorlevel 1 (echo   [FAIL] не скачалось: %~1 & set /a FAIL+=1)
goto :eof

:route_get
rem %1 = имя файла из манифеста; раскладка как в check_and_install.bat
set "F=%~1"
echo %F% | findstr /i ".gguf.part" >nul
if not errorlevel 1 (set "OUT=%DEST%\models\%F%") else (
    if /i "%F%"=="wheels.zip" (set "OUT=%DEST%\wheels.zip") else (set "OUT=%DEST%\bin\%F%")
)
call :get "%BASE%/%F%" "!OUT!"
goto :eof

:verify
rem %1 = ожидаемый хеш, %2 = имя
set "H=%~1"
set "F=%~2"
echo %F% | findstr /i ".gguf.part" >nul
if not errorlevel 1 (set "P=%DEST%\models\%F%") else (
    if /i "%F%"=="wheels.zip" (set "P=%DEST%\wheels.zip") else (set "P=%DEST%\bin\%F%")
)
certutil -hashfile "!P!" SHA256 | findstr /i /c:"%H%" >nul
if errorlevel 1 (echo   [FAIL] %F% & set /a FAIL+=1) else (echo   [OK]   %F%)
goto :eof
