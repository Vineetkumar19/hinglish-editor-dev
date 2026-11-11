@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m tools.stop_storylens_local
pause
