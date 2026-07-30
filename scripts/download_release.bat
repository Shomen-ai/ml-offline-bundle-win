@echo off
rem ===========================================================================
rem  download_release.bat — обёртка для машины A: скачивает весь бандл
rem  из GitHub Release в D:\transfer (или укажите свой путь параметром):
rem     download_release.bat -Dest E:\transfer
rem ===========================================================================
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%download_release.ps1" %*
pause
exit /b %ERRORLEVEL%
