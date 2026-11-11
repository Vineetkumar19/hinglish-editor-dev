@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run Setup CPU.bat ^(or Setup RTX 5070.bat^) first, then run this again.
  if /I not "%~1"=="--quiet" pause
  exit /b 1
)

set "APP_CONFIG=%LOCALAPPDATA%\Hinglish Editor"
if not exist "%APP_CONFIG%" mkdir "%APP_CONFIG%"
".venv\Scripts\python.exe" -c "import json,os; from pathlib import Path; Path(os.environ['APP_CONFIG']).joinpath('install.json').write_text(json.dumps({'root':os.getcwd()}),encoding='utf-8')"

echo Installing Hinglish Editor for Premiere Pro 2024...
set "CEP_DEST=%APPDATA%\Adobe\CEP\extensions\com.hinglish.editor"
if not exist "%CEP_DEST%" mkdir "%CEP_DEST%"
xcopy /E /I /Y "editor_plugins\premiere-cep\*" "%CEP_DEST%\" >nul

rem Allow this local development panel. A signed commercial build will not need this switch.
reg add "HKCU\Software\Adobe\CSXS.11" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul
reg add "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul

echo Installing the DaVinci Resolve Studio launcher...
set "RESOLVE_DEST=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
if not exist "%RESOLVE_DEST%" mkdir "%RESOLVE_DEST%"
copy /Y "editor_plugins\davinci-resolve-studio\Hinglish Editor.py" "%RESOLVE_DEST%\Hinglish Editor.py" >nul

echo.
echo Installed.
echo Premiere Pro 2024: Window ^> Extensions ^> Hinglish Editor
echo Resolve Studio: Workspace ^> Scripts ^> Hinglish Editor
echo Restart the editor if it was open.
if /I not "%~1"=="--quiet" pause
