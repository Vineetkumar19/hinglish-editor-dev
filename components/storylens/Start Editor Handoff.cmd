@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8883/editor-link.html',timeout=2); raise SystemExit(0 if b'Editor Handoff' in r.read(4096) else 1)" >nul 2>nul
if not errorlevel 1 (
  start "" "http://127.0.0.1:8883/editor-link.html"
  exit /b
)
".venv\Scripts\python.exe" -m tools.editor_link.serve
if errorlevel 1 pause
