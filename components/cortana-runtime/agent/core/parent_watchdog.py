"""Exit the owned backend if its Windows desktop host disappears.

The virtual-environment Python launcher can introduce an intermediate process,
so the desktop PID is checked against the actual ancestor chain. The wait holds
a Windows process handle, rather than polling a PID that could be reused.
"""

import os
import threading


def _windows_api():
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.SetEvent.argtypes = [wintypes.HANDLE]
    kernel.SetEvent.restype = wintypes.BOOL
    kernel.WaitForMultipleObjects.argtypes = [
        wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL, wintypes.DWORD,
    ]
    kernel.WaitForMultipleObjects.restype = wintypes.DWORD
    return kernel


def _ancestor_pids() -> list[int]:
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel = _windows_api()
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise RuntimeError("Cannot verify the desktop parent process.")
    parents = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        valid = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while valid:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            valid = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    current = os.getpid()
    seen = set()
    chain = []
    while current and current not in seen:
        seen.add(current)
        current = parents.get(current, 0)
        if current:
            chain.append(current)
    return chain


def start_parent_watchdog():
    """Return a cleanup function; manual developer starts may omit the host PID."""
    raw_pid = os.environ.get("CORTANA_DESKTOP_PID")
    if not raw_pid:
        return lambda: None
    if not raw_pid.isdecimal() or int(raw_pid) <= 0 or int(raw_pid) == os.getpid():
        raise RuntimeError("Invalid desktop parent PID.")
    if os.name != "nt":
        raise RuntimeError("Desktop process supervision currently requires Windows.")
    pid = int(raw_pid)
    ancestors = _ancestor_pids()
    if pid not in ancestors:
        raise RuntimeError("The declared desktop host is not an ancestor of this backend.")

    from ctypes import wintypes
    kernel = _windows_api()
    # Monitor the immediate launcher too. Killing a venv wrapper on an
    # assistant restart must terminate its real Python child even while the
    # Electron host remains alive.
    process_handles = []
    for watched_pid in dict.fromkeys([pid, ancestors[0]]):
        process = kernel.OpenProcess(0x00100000, False, watched_pid)  # SYNCHRONIZE only
        if not process:
            for handle in process_handles:
                kernel.CloseHandle(handle)
            raise RuntimeError("The desktop host or Python launcher is no longer available.")
        process_handles.append(process)
    stop_event = kernel.CreateEventW(None, True, False, None)
    if not stop_event:
        for handle in process_handles:
            kernel.CloseHandle(handle)
        raise RuntimeError("Could not create the desktop supervision event.")
    count = 1 + len(process_handles)
    handles = (wintypes.HANDLE * count)(stop_event, *process_handles)

    def wait():
        try:
            result = kernel.WaitForMultipleObjects(count, handles, False, 0xFFFFFFFF)
            if 1 <= result < count:  # Desktop/launcher process signalled (exited).
                os._exit(0)
            if result != 0:  # A broken supervisor must not leave an ambient agent.
                os._exit(1)
        finally:
            kernel.CloseHandle(stop_event)
            for handle in process_handles:
                kernel.CloseHandle(handle)

    worker = threading.Thread(target=wait, name="cortana-desktop-watchdog", daemon=True)
    worker.start()
    stopped = False

    def stop():
        nonlocal stopped
        if not stopped:
            stopped = True
            kernel.SetEvent(stop_event)
            worker.join(timeout=2)
    return stop
