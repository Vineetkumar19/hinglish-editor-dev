@echo off
cd /d "%~dp0"
echo Optional: this downloads a large 3 GB meaning-check model.
echo It is not needed for your first test.
".venv\Scripts\python.exe" -m hinglish_cut prepare --config config.evaluator.json
pause
