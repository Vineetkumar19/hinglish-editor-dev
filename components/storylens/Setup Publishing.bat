@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup CPU.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-publish.txt
if errorlevel 1 (
  pause
  exit /b 1
)
echo Publishing clients installed. Open Publishing Studio in Hinglish Editor.
pause
