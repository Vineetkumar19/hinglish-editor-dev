"""Windows account tokens are encrypted with the current user's DPAPI key."""
import ctypes
import json
import os
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def crypt(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Account token storage currently requires Windows DPAPI')
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    dll = ctypes.WinDLL('crypt32', use_last_error=True)
    function = dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    function.restype = ctypes.c_int
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel = ctypes.WinDLL('kernel32')
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(target.data)


def save(root, account, data):
    path = Path(root) / 'cache' / 'publisher' / (account + '.dpapi')
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = crypt(json.dumps(data).encode())
    temp = path.with_suffix('.tmp')
    temp.write_bytes(encrypted)
    temp.replace(path)


def load(root, account):
    path = Path(root) / 'cache' / 'publisher' / (account + '.dpapi')
    if not path.exists():
        raise RuntimeError(f'Connect your {account} account first')
    return json.loads(crypt(path.read_bytes(), decrypt=True))
