@echo off
rem 盘前一键：生成今日待上传文件 + 校验 + 上传勾选清单（无需登录）
rem  T-1 收盘已跑 run_one_click_after_close 的前提下，T 日 09:20 前运行
rem  run_one_click_premarket.cmd [--date 2026-10-16 --next-date 2026-10-19]
set PYDIR=D:\PROJ\PT\Libs\Python\python3
"%PYDIR%\python.exe" "%~dp0run_one_click_premarket.py" %*
echo exit_code=%errorlevel%
pause
