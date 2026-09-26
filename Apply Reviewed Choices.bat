@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag your downloaded reviewed-choices.json file onto this button.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m hinglish_semantic apply --choices "%~1" --open
set "result=%errorlevel%"
pause
exit /b %result%
