"""One collecting B-roll worker per workspace, surviving app-server restarts.

The child process owns the OS lock. A lost server must not start another writer
to the same saved bank while the original child is alive. Process exit releases
the lock automatically; checkpoint logic then returns or resumes saved work.
"""
from contextlib import contextmanager
from pathlib import Path
import errno,os,time

@contextmanager
def worker_lease(root,progress=lambda _:None):
    path=Path(root).resolve()/'cache/app/broll-worker.lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0,2)
        if stream.tell()==0:stream.write(b'\0');stream.flush()
        waiting=False
        while True:
            try:
                if os.name=='nt':
                    import msvcrt
                    stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError as error:
                if error.errno not in (errno.EACCES,errno.EAGAIN,errno.EDEADLK):raise
                if not waiting:progress('Another B-roll worker is finishing saved work. Waiting without starting duplicate searches.');waiting=True
                time.sleep(.2)
        try:yield
        finally:
            if os.name=='nt':
                stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)
