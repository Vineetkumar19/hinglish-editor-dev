@echo off
cd /d "%~dp0"
set "TASK_PS=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
if exist "%TASK_PS%" (
  "%TASK_PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\resume_laptop_setup.ps1"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\resume_laptop_setup.ps1"
)
pause
