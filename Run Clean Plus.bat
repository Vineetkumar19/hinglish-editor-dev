@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup CPU.bat first.
  pause
  exit /b 1
)
echo CLEAN+ - SILENCE, FILLERS AND RETAKES - NO SCRIPT
echo Put one-speaker recordings in ONE input\phase1 video folder.
".venv\Scripts\python.exe" -m hinglish_semantic clean-plus --open
set "result=%errorlevel%"
pause
exit /b %result%
