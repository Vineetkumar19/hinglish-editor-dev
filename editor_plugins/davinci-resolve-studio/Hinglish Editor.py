"""DaVinci Resolve Workspace > Scripts launcher for Hinglish Editor."""
from pathlib import Path
import json
import os
import subprocess
import time
import urllib.request
import webbrowser


CONFIG = Path(os.environ.get("LOCALAPPDATA", "")) / "Hinglish Editor" / "install.json"
APP_ROOT = Path(json.loads(CONFIG.read_text(encoding="utf-8"))["root"])
URL = "http://127.0.0.1:8766/"  # DEV copy port (original app uses 8765)


def running():
    try:
        with urllib.request.urlopen(URL + "api/health", timeout=.6) as response:
            return json.load(response).get("ok") is True
    except Exception:
        return False


if not running():
    python = APP_ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        raise RuntimeError("Run Setup CPU.bat in Hinglish Editor first")
    subprocess.Popen(
        [str(python), "-m", "hinglish_app", "--root", str(APP_ROOT), "--no-open"],
        cwd=str(APP_ROOT),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(20):
        if running():
            break
        time.sleep(.25)

webbrowser.open(URL + "?host=resolve")
