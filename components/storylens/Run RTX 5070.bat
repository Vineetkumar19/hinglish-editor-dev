@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup RTX 5070 first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m hinglish_cut run --config config.rtx5070.json --offline
pause
