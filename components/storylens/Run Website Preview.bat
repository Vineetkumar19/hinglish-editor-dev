@echo off
cd /d "%~dp0"
echo Starting the subscription website preview at http://127.0.0.1:8788
echo Payments and rendering remain disabled until configured.
".venv\Scripts\python.exe" -m hinglish_saas
pause
