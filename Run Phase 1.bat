@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup CPU.bat first.
  pause
  exit /b 1
)
echo PHASE 1 - REMOVE SILENCE - NO SCRIPT NEEDED
echo Put videos in input\phase1\videos, or use one of the format folders.
echo Each video gets a cleaned MP4 and Premiere XML.
echo.
".venv\Scripts\python.exe" -m hinglish_clean --open
set "clean_result=%errorlevel%"
if not "%clean_result%"=="0" echo Check the message above or the results page before using the edit.
pause
exit /b %clean_result%
