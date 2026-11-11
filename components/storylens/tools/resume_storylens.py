"""Start the installed local queue at Windows sign-in; never publish directly."""
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen


ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:8765/'


def health():
    try:
        with urlopen(URL+'api/health',timeout=2) as response:return response.status==200
    except OSError:return False


def main():
    if not health():
        logs=ROOT/'output';logs.mkdir(exist_ok=True)
        with (logs/'startup-editor.stdout.log').open('a',encoding='utf-8') as out,(logs/'startup-editor.stderr.log').open('a',encoding='utf-8') as err:
            subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-E','-X','utf8','-m','hinglish_app',
                '--root',str(ROOT),'--port','8765','--no-open','--no-publisher-worker'],cwd=ROOT,
                stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(30):
            if health():break
            time.sleep(1)


if __name__=='__main__':main()
