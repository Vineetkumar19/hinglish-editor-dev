"""Start the installed loopback-only model runtime when the editor needs it.

No installation, model download, login, administrator access or startup task.
"""
import os
from pathlib import Path
import subprocess
import threading
import time

LOCK = threading.Lock()


def ensure(root, session, url):
    if url != 'http://127.0.0.1:11434' or os.name != 'nt':
        return False
    from .model_storage import configuration
    selection = configuration(root)
    if not selection.get('active') or not selection.get('root'):
        return False
    executable = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Ollama/ollama.exe'
    store = Path(selection['root']) / 'ollama'
    if not executable.is_file() or not store.is_dir():
        return False
    def ready():
        try:
            return session.get(url + '/api/tags', timeout=2).ok
        except Exception:
            return False
    with LOCK:
        if ready():
            return True
        env = os.environ.copy()
        env.update(OLLAMA_MODELS=str(store), OLLAMA_HOST='127.0.0.1:11434',
                   OLLAMA_NO_CLOUD='1', OLLAMA_MAX_LOADED_MODELS='1', OLLAMA_NUM_PARALLEL='1',
                   OLLAMA_VULKAN='0', CUDA_VISIBLE_DEVICES='0',
                   CUDA_CACHE_PATH=str(Path(selection['root']) / 'cache/cuda'))
        folder = Path(root) / 'cache/app'
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / 'ollama-autostart.log').open('ab') as log:
            subprocess.Popen([str(executable), 'serve'], cwd=str(root), env=env,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if ready():
                return True
            time.sleep(.5)
        return False
