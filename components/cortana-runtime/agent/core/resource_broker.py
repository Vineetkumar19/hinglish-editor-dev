"""Join the existing StoryLens GPU file locks without loading its application."""
from contextlib import contextmanager
from pathlib import Path
import os
import threading
import time

_lock = threading.Lock()
SHARED_ROOT = Path('D:/Full Drive/remove silence/cache/app')
_streams = []
_warm_until = 0.0
_janitor = None


def _release_streams():
    if os.name == 'nt':
        import msvcrt
        for stream in reversed(_streams):
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            stream.close()
    _streams.clear()


def _unload_owned():
    # Retained weights must be gone BEFORE another project gets the lease.
    import sys
    import httpx
    from core.config import settings
    from core.model_profiles import PROFILES
    speech = sys.modules.get('core.stt')
    if speech:
        speech._release_gpu_models()
    owned = {p['tag'] for p in PROFILES.values()}
    with httpx.Client(base_url=settings.ollama_host, timeout=5, trust_env=False) as client:
        state = client.get('/api/ps'); state.raise_for_status()
        for model in state.json().get('models', []):
            if model['name'] in owned:
                response = client.post('/api/generate', json={'model':model['name'], 'keep_alive':0})
                response.raise_for_status()


def _expire_warm_lease():
    global _warm_until, _janitor
    from core.config import ROOT_DIR
    while True:
        time.sleep(.25)
        if not _lock.acquire(blocking=False):
            continue
        try:
            if not _streams:
                _janitor = None
                return
            if time.monotonic() < _warm_until and not (ROOT_DIR/'memory/pause_model_work').exists():
                continue
            try:
                _unload_owned()
            except Exception:
                # Do not release a reservation while ownership is uncertain.
                # Ollama's own short keep_alive also bounds stale residency.
                continue
            _warm_until = 0
            _release_streams()
            _janitor = None
            return
        finally:
            _lock.release()


def retain_for_next_turn():
    """Keep a short warm interval, still reserved from other GPU workloads."""
    global _warm_until, _janitor
    if not _streams:
        return
    _warm_until = time.monotonic() + 60
    if _janitor is None:
        _janitor = threading.Thread(target=_expire_warm_lease, daemon=True,
                                    name='cortana-gpu-idle-release')
        _janitor.start()


def release_when_idle():
    """Stop extends no warm reservation; active work retains its safety lease."""
    global _warm_until
    _warm_until = 0


def shutdown_owned_gpu():
    global _warm_until
    with _lock:
        _warm_until = 0
        if _streams:
            _unload_owned()
            _release_streams()


class GPUUnavailable(RuntimeError):
    """Expected resource waiting state, not an internal server failure."""


@contextmanager
def gpu_slot():
    if not _lock.acquire(blocking=False):
        raise GPUUnavailable('Waiting for Cortana speech/model work to release the GPU slot.')
    try:
        from core.config import ROOT_DIR
        if (ROOT_DIR/'memory/pause_model_work').exists():
            raise GPUUnavailable('Model work is paused for StoryLens priority. Cortana GPU tests will wait.')
        if os.name == 'nt' and not SHARED_ROOT.exists():
            raise GPUUnavailable('The shared GPU coordinator is not ready. No GPU job was started.')
        if not _streams and os.name == 'nt' and SHARED_ROOT.exists():
            import msvcrt
            for filename in ('gpu-work.lock', 'gpu-child-work.lock'):
                path = SHARED_ROOT / filename
                if not path.exists():
                    raise GPUUnavailable('The shared GPU coordinator is not ready. No GPU job was started.')
                stream = path.open('r+b')
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    stream.close()
                    raise GPUUnavailable('Waiting for StoryLens GPU work. It retains first priority.') from None
                _streams.append(stream)
        yield
    finally:
        if time.monotonic() >= _warm_until:
            try:
                if _streams and _janitor is not None:
                    _unload_owned()
                _release_streams()
            except Exception:
                # The janitor retries cleanup while keeping the reservation.
                pass
        _lock.release()
