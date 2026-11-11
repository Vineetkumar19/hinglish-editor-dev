"""Only one publishing worker may recover and process this folder's queue."""
import os
from pathlib import Path


def acquire(root):
    path = Path(root) / 'cache' / 'publisher' / 'worker.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    stream.seek(0, 2)
    if not stream.tell():
        stream.write(b'0')
        stream.flush()
    stream.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise RuntimeError('A publisher worker is already running for this project') from None
    return stream
