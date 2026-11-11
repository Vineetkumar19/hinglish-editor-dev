@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup CPU.bat first.
  pause
  exit /b 1
)
set "HF_HUB_DISABLE_XET=1"
".venv\Scripts\python.exe" -m hinglish_semantic prepare
set "result=%errorlevel%"
pause
exit /b %result%
