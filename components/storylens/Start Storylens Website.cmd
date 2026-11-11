@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -c "import requests; r=requests.get('http://127.0.0.1:8788/api/config',timeout=2); raise SystemExit(0 if r.ok and r.json().get('brand')=='Storylens' else 1)" >nul 2>nul
if not errorlevel 1 (
  start "" "http://127.0.0.1:8788/"
  exit /b
)
".venv\Scripts\python.exe" -m tools.storylens_local --migrate-from "cache\saas\subscriptions.sqlite3"
pause
