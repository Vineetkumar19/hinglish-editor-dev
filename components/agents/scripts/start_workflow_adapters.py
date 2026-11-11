"""Start/reuse narrow authenticated project receivers. Never starts job workers."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {
    'storylens': (Path('D:/Full Drive/remove silence'), Path('D:/Full Drive/remove silence/.venv/Scripts/python.exe')),
    'cortana': (Path('D:/Cortana'), Path('D:/Cortana/agent/.venv/Scripts/python.exe')),
    'repository': (ROOT, ROOT / '.venv/Scripts/python.exe'),
}


def main():
    config = {}
    secret_dir = ROOT / 'data/integration-secrets'
    secret_dir.mkdir(parents=True, exist_ok=True)
    for name, (root, python) in TARGETS.items():
        folder = ROOT / 'data/receivers' / name
        folder.mkdir(parents=True, exist_ok=True)
        secret_file = secret_dir / (name + '.token')
        if not secret_file.exists():
            with secret_file.open('x',encoding='utf-8') as stream:
                stream.write(secrets.token_urlsafe(48))
        token = secret_file.read_text(encoding='utf-8').strip()
        connection_file = folder / 'connection.json'
        def ready():
            if not connection_file.exists():
                return False
            try:
                connection = json.loads(connection_file.read_text(encoding='utf-8'))
                req = urllib.request.Request(connection['base_url']+'/capabilities',headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(req,timeout=2) as response:
                    caps=json.load(response)
                return caps.get('project') == name and caps.get('contract_version') == 1
            except (OSError,ValueError):
                return False
        if not ready():
            if not python.is_file():
                raise RuntimeError(name + ': configured project runtime is unavailable')
            with (folder/'output.log').open('ab') as log:
                process = subprocess.Popen([str(python),str(ROOT/'adapters/receiver.py'),'--project',name,
                    '--root',str(root),'--storage',str(folder)],cwd=root,
                    env={**os.environ,'SUITE_RECEIVER_TOKEN':token,'PYTHONUTF8':'1'},
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            deadline=time.monotonic()+30
            while not ready():
                if process.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError(name + ': receiver failed; inspect '+str(folder/'output.log'))
                time.sleep(.2)
        config[name]={'connection_file':str(connection_file),'token_file':str(secret_file),'device_id':'local'}
        print(name + ': authenticated receiver ready',flush=True)
    path=ROOT/'profiles/workflow_integrations.json'
    pending=path.with_suffix('.tmp')
    pending.write_text(json.dumps(config,indent=2),encoding='utf-8')
    pending.replace(path)


if __name__ == '__main__':
    main()
