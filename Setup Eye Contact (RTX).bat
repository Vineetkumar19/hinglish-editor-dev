@echo off
cd /d "%~dp0"
echo Eye Contact setup (NVIDIA RTX GPUs only). Finished steps are skipped if you run it again.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\eyecontact\setup_eyecontact.ps1" %*
pause
