@echo off
cd /d "%~dp0"
echo Downloading the main models. This is enough to run the app.
".venv\Scripts\python.exe" -m hinglish_cut prepare --config config.cpu.json
pause
