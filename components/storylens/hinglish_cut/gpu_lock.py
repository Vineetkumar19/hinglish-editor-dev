"""A process lock shared by editor jobs and model-upgrade validation."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import threading
import time
import json
import secrets
import hmac

_held = ContextVar('storylens_gpu_locks', default=())
_leases = ContextVar('storylens_gpu_leases', default={})
LEASE_ENV = 'STORYLENS_GPU_CHILD_LEASE'


def _root_key(root):
    return os.path.normcase(str(Path(root).resolve()))


def _lease_path(root):
    return Path(root)/'cache/app/gpu-work-lease.json'


def held_by_current_thread(root):
    return (os.getpid(),threading.get_ident(),_root_key(root)) in _held.get()


def _parent_pid(pid):
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_=[('reserved',ctypes.c_void_p),('peb',ctypes.c_void_p),
                      ('reserved2',ctypes.c_void_p*2),('pid',ctypes.c_size_t),('parent',ctypes.c_size_t)]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        query=ctypes.WinDLL('ntdll').NtQueryInformationProcess
        query.argtypes=[wintypes.HANDLE,wintypes.ULONG,ctypes.c_void_p,wintypes.ULONG,ctypes.c_void_p]
        query.restype=wintypes.LONG
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:raise OSError('Cannot verify the GPU worker parent')
        try:
            data=Basic()
            if query(handle,0,ctypes.byref(data),ctypes.sizeof(data),None)!=0:raise OSError('Cannot verify the GPU worker parent')
            return int(data.parent)
        finally:kernel.CloseHandle(handle)
    stat=(Path('/proc')/str(pid)/'stat').read_text()
    return int(stat.rsplit(')',1)[1].split()[1])


def _descendant_of(owner):
    # Venv redirectors and command launchers may sit between controller/worker.
    current=os.getpid()
    for _ in range(16):
        current=_parent_pid(current)
        if current==owner:return True
        if current<=1:return False
    return False


def child_environment(root, environment=None):
    """Explicitly lend this thread's reservation to a direct, awaited child.

    Do not set this in the process-global environment: unrelated worker threads
    must not inherit a reservation they do not own.
    """
    lease=_leases.get().get(_root_key(root))
    if not lease or lease['owner_pid']!=os.getpid():
        raise RuntimeError('This worker cannot delegate the GPU reservation. Reload Storylens after the current job finishes, then retry.')
    env=dict(os.environ if environment is None else environment)
    env[LEASE_ENV]=json.dumps(lease,separators=(',',':'))
    return env


def _child_lease(root):
    raw=os.environ.get(LEASE_ENV)
    if not raw:return None
    try:
        if len(raw)>4096:raise ValueError()
        value=json.loads(raw)
        if value.get('root')!=_root_key(root):return None
        saved=json.loads(_lease_path(root).read_text('utf8'))
        valid=(type(value.get('owner_pid')) is int and _descendant_of(value['owner_pid'])
               and value==saved and isinstance(value.get('token'),str)
               and hmac.compare_digest(value['token'],saved.get('token','')))
        if not valid:raise ValueError()
        return value
    except (OSError,ValueError,TypeError):
        raise RuntimeError('The parent GPU reservation expired or could not be verified. Saved progress is kept; retry the job.') from None


@contextmanager
def gpu_lock(root, *, timeout=None):
    """Share one slot across processes; nested calls in its owner do not deadlock."""
    deadline = None if timeout is None else time.monotonic() + max(0, timeout)
    root_key=_root_key(root)
    key=(os.getpid(),threading.get_ident(),root_key)
    held=_held.get()
    if key in held:
        yield
        return
    if os.environ.get('HINGLISH_CREATOR_CONTEXT_FILE') and not os.environ.get(LEASE_ENV):
        policy=Path(root)/'config.models.local.json'
        if policy.is_file() and json.loads(policy.read_text('utf-8-sig')).get('heavy_workloads_gpu_only'):
            raise RuntimeError('Finish the current job and reload Storylens to activate the GPU policy safely. This managed worker did not receive its GPU reservation; no CPU fallback was started.')
    borrowed=_child_lease(root)
    # Separate child slot prevents two children of one reservation running GPU
    # work together. Other processes still wait for the parent's main slot.
    with _exclusive(root,'gpu-child-work.lock' if borrowed else 'gpu-work.lock', deadline=deadline):
        if borrowed:_child_lease(root)  # Recheck after waiting for another child.
        else:
            # A child can briefly outlive a crashed controller. Wait for it
            # before a new controller starts GPU work or replaces its lease.
            with _exclusive(root,'gpu-child-work.lock', deadline=deadline):pass
        lease=borrowed or {'root':root_key,'owner_pid':os.getpid(),'token':secrets.token_hex(32)}
        if not borrowed:
            path=_lease_path(root)
            path.write_text(json.dumps(lease),encoding='utf8')
        token=_held.set(held+(key,))
        lease_token=_leases.set(dict(_leases.get(),**{root_key:lease}))
        try:yield
        finally:
            _leases.reset(lease_token)
            _held.reset(token)
            if not borrowed:_lease_path(root).unlink(missing_ok=True)


@contextmanager
def _exclusive(root, filename='gpu-work.lock', *, deadline=None):
    path=Path(root)/'cache/app'/filename
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0,2)
        if stream.tell()==0:
            stream.write(b'\0');stream.flush()
        if os.name=='nt':
            import msvcrt
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                    break
                except OSError as error:
                    if error.errno not in (13,36):raise
                    if deadline is not None and time.monotonic() >= deadline:
                        raise TimeoutError('The GPU is busy with another job.') from error
                    time.sleep(.2 if deadline is None else min(.02, max(0, deadline-time.monotonic())))
            try:yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            while True:
                try:
                    fcntl.flock(stream,fcntl.LOCK_EX | (fcntl.LOCK_NB if deadline is not None else 0))
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('The GPU is busy with another job.') from None
                    time.sleep(min(.02, max(0, deadline-time.monotonic())))
            try:yield
            finally:fcntl.flock(stream,fcntl.LOCK_UN)
