@echo off
cd /d "%~dp0"
echo AI Images setup (NVIDIA GPU): picture model Z-Image Turbo, about 21 GB once. Finished steps are skipped if you run it again.
echo To install on another drive: "Setup AI Images (RTX).bat" -Target D:\HinglishEditorModels
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\aigen\setup_aigen.ps1" -Models image %*
pause
