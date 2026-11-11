"""Talk to the generator worker in the separate AI environment (tools/aigen/worker.py)."""
from pathlib import Path
import json
import os
import subprocess

from .settings import load_config

WORKER = Path(__file__).resolve().parent.parent / 'tools' / 'aigen' / 'worker.py'


def install_folder(root):
    folder = load_config(root).get('install') or str(Path(root) / 'tools' / 'aigen' / 'install')
    return Path(folder)


def worker_python(root):
    return install_folder(root) / 'venv' / 'Scripts' / 'python.exe'


def doctor(root):
    """{'ready', 'gpu', 'vram_gb', 'mode', 'image_model', 'video_model', 'problem'} without loading any model."""
    python = worker_python(root)
    if not python.is_file():
        return {'ready': False, 'problem': 'Not set up yet: run "Setup AI Images (RTX).bat" or "Setup AI Video (RTX).bat" once.'}
    try:
        done = subprocess.run([str(python), str(WORKER), '--install', str(install_folder(root)), '--doctor'],
                              capture_output=True, text=True, timeout=120,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        facts = json.loads([l for l in done.stdout.splitlines() if l.startswith('{')][-1])
    except Exception as error:
        return {'ready': False, 'problem': f'The AI generator could not start ({error}). Run the setup again.'}
    problem = ''
    if not facts.get('cuda'):
        problem = 'PyTorch cannot see the NVIDIA GPU (update the driver, run the setup again).'
    elif not facts.get('image_model'):
        problem = 'The picture model is not downloaded yet: run "Setup AI Images (RTX).bat".'
    facts.update(ready=not problem, problem=problem)
    return facts


def free_ollama(progress=print, url='http://127.0.0.1:11434'):
    """Ollama keeps its models in GPU memory for minutes after the planning. On a 12 GB card that leaves too little
    room for the picture / video model, so they are unloaded first (they load again by themselves when needed)."""
    try:
        import requests
        session = requests.Session()
        session.trust_env = False
        loaded = [m['name'] for m in session.get(url + '/api/ps', timeout=5).json().get('models', [])]
        for name in loaded:
            session.post(url + '/api/generate', json={'model': name, 'keep_alive': 0}, timeout=60)
        if loaded:
            progress(f'  Freed GPU memory used by Ollama ({", ".join(loaded)})')
    except Exception:
        pass                                   # Ollama not running: nothing to free


def _worker_lines(process,path):
    with Path(path).open('w',encoding='utf8') as log:
        for line in process.stdout:
            log.write(line);log.flush()
            yield line.strip()


def generate(root, items, jobs_file, progress=print, mode='auto'):
    """Run the worker on `items`; returns {id: {'out', 'seconds', ...} or {'error'}}."""
    free_ollama(progress)
    python = worker_python(root)
    if not python.is_file():
        raise RuntimeError('Not set up: run "Setup AI Images (RTX).bat" or "Setup AI Video (RTX).bat" once')
    Path(jobs_file).write_text(json.dumps({'items': items}, ensure_ascii=False, indent=1), encoding='utf-8')
    command = [str(python), '-u', str(WORKER), '--install', str(install_folder(root)), '--jobs', str(jobs_file),
               '--mode', mode]
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONFAULTHANDLER':'1', 'HF_HUB_OFFLINE': '1', 'PYTORCH_CUDA_ALLOC_CONF': 'expandable_segments:True'}
    for key in ('PYTHONPATH', 'VIRTUAL_ENV', 'PYTHONHOME'):      # never mix the editor's Python into it
        env.pop(key, None)
    results, total = {}, len(items)
    names = {i['id']: i.get('label', i['id']) for i in items}
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                               errors='replace', env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    fatal, last_step = None, {}
    log_path=Path(jobs_file).with_suffix('.worker.log')
    for line in _worker_lines(process,log_path):
        if not line.startswith('{'):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get('event')
        if kind == 'start':
            progress(f'  GPU: {event["gpu"]} ({event["vram_gb"]} GB), memory mode: {event["mode"]}')
        elif kind == 'loading':
            progress(f'  Loading {event["model"]} (first time takes a minute)')
        elif kind == 'step':
            # one progress line per item at 1/3 and 2/3 (videos take minutes)
            share = event['step'] / max(1, event['steps'])
            mark = int(share * 3)
            if mark and last_step.get(event['id']) != mark and mark < 3:
                last_step[event['id']] = mark
                progress(f'    {names.get(event["id"], event["id"])}: {round(share * 100)}%')
        elif kind == 'done':
            results[event['id']] = event
            progress(f'  Made {len(results)}/{total}: {names.get(event["id"], event["id"])} ({event["seconds"]:.0f}s)')
        elif kind == 'error':
            results[event['id']] = event
            progress(f'  Could not make {names.get(event["id"], event["id"])}: {event["error"][:160]}')
        elif kind == 'note':
            progress('  ' + event.get('text', '')[:200])
        elif kind == 'fatal':
            fatal = event.get('error', 'unknown error')
    code = process.wait()
    if fatal or (code and not results):
        raise RuntimeError(f'The AI generator stopped: {fatal or f"exit code {code}"}. Technical details: {log_path}')
    return results
