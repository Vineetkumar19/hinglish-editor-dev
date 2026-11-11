@echo off
cd /d "%~dp0"
echo AI Video setup (NVIDIA GPU): video model Wan 2.2 5B, about 24 GB once. Finished steps are skipped if you run it again.
echo For sharp first frames also run "Setup AI Images (RTX).bat" (same folder, the models are shared).
echo To install on another drive: "Setup AI Video (RTX).bat" -Target D:\HinglishEditorModels
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\aigen\setup_aigen.ps1" -Models video %*
pause
