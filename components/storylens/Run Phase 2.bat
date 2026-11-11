@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup CPU.bat first.
  pause
  exit /b 1
)
echo PHASE 2 - MATCH SPOKEN MEANING AND KEEP COMPLETE PHRASES
echo Natural pacing keeps breathing room between sentences and paragraphs.
echo Put your script in input\phase2\script.txt. Paragraphs can use multiple videos.
echo Put the source videos in ONE input\phase2 video folder.
".venv\Scripts\python.exe" -m hinglish_semantic assemble --open
set "result=%errorlevel%"
if "%result%"=="2" echo Open the result folder: play preview.mp4 or import EDITED_SEQUENCE.xml into Premiere.
pause
exit /b %result%
