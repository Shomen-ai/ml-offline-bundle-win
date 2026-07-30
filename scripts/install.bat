@echo off
rem ===========================================================================
rem  install.bat — обёртка для машины B: проверка и установка одним кликом.
rem  Параметры пробрасываются в check_and_install.ps1, например:
rem     install.bat -TransferDir E:\transfer -SkipModelTest
rem ===========================================================================
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%check_and_install.ps1" %*
set CODE=%ERRORLEVEL%
echo.
if %CODE%==0 (echo Установка завершена успешно.) else (echo Завершено с ошибками, смотрите вывод выше.)
pause
exit /b %CODE%
