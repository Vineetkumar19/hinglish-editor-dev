"""Keep native speech loading out of the Publisher's HTTP process."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from .durable_json import write

_cancelled = ContextVar('publishing_speech_cancelled', default=None)


class PublishingSpeechError(ValueError):
    def __init__(self, details):
        super().__init__('The local speech worker stopped while preparing metadata. Check model settings and retry the unfinished preparation; existing results are kept.')
        self.stderr = details


@contextmanager
def cancellation(check):
    token = _cancelled.set(check)
    try:yield
    finally:_cancelled.reset(token)


def command(root, key):
    from hinglish_cut.model_preferences import preferences
    python = Path(preferences(root).get('cuda_runtime_python') or sys.executable)
    if not python.is_file():
        raise ValueError('The local speech runtime is unavailable. Check model settings before preparing this video.')
    return [str(python), '-E', '-X', 'utf8', '-m', 'hinglish_app.publishing_speech_worker',
            '--root', str(root), '--id', key]


def stop_owned(process):
    """Stop only the child we launched, including a Windows venv wrapper."""
    if process.poll() is not None:return
    import psutil
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        try:parent.terminate()
        except psutil.NoSuchProcess:pass
        psutil.wait_procs(children + [parent], timeout=3)
    except psutil.NoSuchProcess:pass
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:process.kill(); process.wait(timeout=3)


def transcribe(root, videos, progress, *, cancelled=None, gpu_locked=False):
    root = Path(root).resolve()
    pending = [Path(v).resolve() for v in dict.fromkeys(videos)
               if not Path(v).with_suffix('.txt').is_file() and not Path(v).with_suffix('.publish.json').is_file()]
    if not pending:return
    from hinglish_publish.store import fingerprint
    key = uuid.uuid4().hex
    folder = root / 'cache/publisher/speech' / key; folder.mkdir(parents=True)
    write(folder / 'request.json', {'videos': [{'path': str(v), 'sha256': fingerprint(v)} for v in pending],
        'gpu_locked_by_parent': bool(gpu_locked)})
    write(folder / 'status.json', {'status': 'queued', 'stage': 'Waiting for the local speech model.'})
    cancelled = cancelled or _cancelled.get()
    process = None
    try:
        with (folder / 'worker.log').open('wb') as log:
            process = subprocess.Popen(command(root, key), cwd=root, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'},
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            previous = ''
            while process.poll() is None:
                if cancelled and cancelled():
                    stop_owned(process)
                    write(folder / 'status.json', {'status': 'cancelled', 'stage': 'Stopped. Completed speech and source videos are kept.'})
                    raise ValueError('Stopped. Completed speech and source videos are kept.')
                try:
                    stage = json.loads((folder / 'status.json').read_text('utf-8'))['stage']
                    if stage != previous:progress(stage); previous = stage
                except (OSError, ValueError, KeyError):pass
                time.sleep(.25)
        state = json.loads((folder / 'status.json').read_text('utf-8'))
        if process.returncode or state.get('status') != 'ready':
            detail = 'Speech worker exit ' + str(process.returncode) + '\n' + (folder / 'worker.log').read_text('utf-8', errors='replace')[-14000:]
            write(folder / 'status.json', {'status': 'failed', 'stage': 'The speech worker stopped. Saved preparation is kept.',
                'exit_code': process.returncode, 'details': detail})
            raise PublishingSpeechError(detail)
        if any(fingerprint(v) != item['sha256'] for v, item in zip(pending, json.loads((folder / 'request.json').read_text('utf-8'))['videos'])):
            raise ValueError('The selected video changed during speech preparation. Select it again before posting.')
        if any(not v.with_suffix('.txt').is_file() or not v.with_suffix('.txt').read_text('utf-8-sig').strip() for v in pending):
            raise PublishingSpeechError('The child exited without complete transcript checkpoints.')
    except Exception as error:
        try:state = json.loads((folder / 'status.json').read_text('utf-8'))
        except (OSError, ValueError):state = {}
        if state.get('status') not in ('failed', 'cancelled'):
            write(folder / 'status.json', {'status': 'failed', 'stage': 'Speech preparation stopped. Check model settings and retry.',
                'details': str(error)})
        raise
    finally:
        if process is not None and process.poll() is None:stop_owned(process)
