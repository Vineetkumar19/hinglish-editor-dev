@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup CPU first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m hinglish_cut run --config config.cpu.json --offline
if errorlevel 3 goto done
if errorlevel 2 echo The draft is ready for review. Check report.html for flagged lines.
:done
pause
