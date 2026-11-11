@echo off
setlocal
cd /d "%~dp0desktop"
if not exist "node_modules\electron\dist\electron.exe" (
  echo Cortana desktop runtime is missing. See docs\MILESTONE_1_STATUS.md.
  pause
  exit /b 1
)
start "" "node_modules\electron\dist\electron.exe" "%~dp0desktop" %*
