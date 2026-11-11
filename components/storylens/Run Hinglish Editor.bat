@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup CPU.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m hinglish_app
if errorlevel 1 pause

