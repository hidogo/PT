@echo off
rem PT scheduled task entry: premarket one-click (no pause; log appended to Logs\oneclick_premarket.log)
rem Deadline: upload must be finished before 09:15; step 3c hard-check blocks upload on rows/date/sha1 mismatch.
setlocal
cd /d "%~dp0"
set "PYDIR=D:\PROJ\PT\Libs\Python\python3"
set "LOGDIR=D:\PROJ\PT\Logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo ===== %date% %time% premarket start ===== >> "%LOGDIR%\oneclick_premarket.log"
"%PYDIR%\python.exe" "%~dp0run_one_click_premarket.py" %* >> "%LOGDIR%\oneclick_premarket.log" 2>&1
set "RC=%errorlevel%"
echo ===== %date% %time% premarket end rc=%RC% ===== >> "%LOGDIR%\oneclick_premarket.log"
endlocal & exit /b %RC%
