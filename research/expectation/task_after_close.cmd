@echo off
chcp 65001 >nul
rem PT scheduled task entry: after-close one-click (no pause; log appended to Logs\oneclick_after_close.log)
rem Used as a fallback only: if the AXquant review chain already ran today, --skip-if-done exits rc=0 immediately.
setlocal
cd /d "%~dp0"
set "PYDIR=D:\PROJ\PT\Libs\Python\python3"
set "LOGDIR=D:\PROJ\PT\Logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo ===== %date% %time% after_close start ===== >> "%LOGDIR%\oneclick_after_close.log"
"%PYDIR%\python.exe" "%~dp0run_one_click_after_close.py" --skip-if-done %* >> "%LOGDIR%\oneclick_after_close.log" 2>&1
set "RC=%errorlevel%"
echo ===== %date% %time% after_close end rc=%RC% ===== >> "%LOGDIR%\oneclick_after_close.log"
endlocal & exit /b %RC%
