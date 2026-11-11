"""Stream optional MuseTalk frames without adding work to the voice reply."""
import atexit
from pathlib import Path
import struct
import subprocess
from threading import Event, Lock, Thread, Timer
from time import monotonic


_LOCK = Lock()
_PROCESS = None
_IDLE_TIMER = None
_IDLE_UNTIL = 0.0
_READY = None


def _stop(process):
    if not process or process.poll() is not None:
        return
    # The Windows venv shim owns an interpreter child. Reap that exact worker
    # too so an interrupted request cannot leave the CUDA model resident.
    import psutil
    try:
        children = psutil.Process(process.pid).children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def _expire(process):
    with _LOCK:
        if _PROCESS is process and monotonic() >= _IDLE_UNTIL:
            _stop(process)


def _idle(process):
    global _IDLE_TIMER, _IDLE_UNTIL
    if _IDLE_TIMER is not None:
        _IDLE_TIMER.cancel()
    _IDLE_UNTIL = monotonic() + 45
    _IDLE_TIMER = Timer(45, _expire, (process,))
    _IDLE_TIMER.daemon = True
    _IDLE_TIMER.start()


@atexit.register
def _cleanup():
    _stop(_PROCESS)


def _wait_ready(process, ready):
    if process.stdout.readline(32).strip() == b"ready":
        ready.set()


def _ensure(root):
    global _PROCESS, _READY
    if _PROCESS is not None and _PROCESS.poll() is None:
        return _PROCESS
    folder = Path(root) / "tools" / "storylens-avatar"
    weights = folder / "models" / "musetalk" / "musetalkV15" / "unet_fp16.safetensors"
    if not weights.is_file():
        return None
    _READY = Event()
    log = folder / "musetalk-worker.log"
    with log.open("ab") as errors:
        _PROCESS = subprocess.Popen(
            [str(Path(root) / ".venv" / "Scripts" / "python.exe"), "-u",
             str(folder / "musetalk_renderer.py"), "--stream"],
            cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    Thread(target=_wait_ready, args=(_PROCESS, _READY), daemon=True).start()
    return _PROCESS


def yield_to_voice():
    if _LOCK.acquire(blocking=False):
        try:
            if _PROCESS is not None and not _READY.is_set():
                _stop(_PROCESS)
        finally:
            _LOCK.release()


def handle(handler, root, *, warm):
    try:
        size = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        size = -1
    if (warm and size != 0) or (not warm and (not 44 <= size <= 3_000_000 or
                                               handler.headers.get_content_type() != "audio/wav")):
        return handler._json(400, {"error": "Invalid avatar request."})
    if not _LOCK.acquire(blocking=False):
        return handler._json(409, {"error": "Avatar renderer is busy."})
    try:
        process = _ensure(root)
        if process is None:
            return handler._json(503, {"error": "Avatar model is unavailable."})
        if warm:
            _idle(process)
            return handler._json(200, {"ready": _READY.is_set()})

        if not _READY.is_set():
            _idle(process)
            return handler._json(503, {"error": "Avatar renderer is warming up."})
        deadline = Timer(35, _stop, (process,))
        deadline.daemon = True
        deadline.start()
        try:
            handler.connection.settimeout(3)
            wav = handler.rfile.read(size)
            if len(wav) != size or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
                return handler._json(400, {"error": "Invalid avatar audio."})
            process.stdin.write(struct.pack("<I", size))
            process.stdin.write(wav)
            process.stdin.flush()
            handler.close_connection = True
            handler.send_response(200)
            handler._cors()
            handler.send_header("Content-Type", "application/x-ndjson")
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("Connection", "close")
            handler.end_headers()
            while line := process.stdout.readline(128_000):
                if line.strip() == b"end":
                    break
                handler.wfile.write(line)
        except OSError:
            _stop(process)
        finally:
            deadline.cancel()
            _idle(process)
    finally:
        _LOCK.release()
