@echo off
setlocal
cd /d "%~dp0trading_scanner_service"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 run_server.py
) else (
  python run_server.py
)
