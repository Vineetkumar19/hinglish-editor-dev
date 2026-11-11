"""Windows user-bound DPAPI storage; never exposed as a model tool."""
import base64
import json
import os
import re
import threading
from pathlib import Path
from uuid import uuid4
from core.config import settings

_lock = threading.RLock()
_entropy = b'Cortana.LocalArchitecture.Secrets.v1'


def _path():
    return Path(settings.memory_dir) / 'private' / 'secrets.dpapi.json'


def _read():
    path = _path()
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'version':1,'entries':{}}


def save(name, value):
    if not re.fullmatch(r'[a-z0-9._-]{1,100}',name) or not isinstance(value,str) or not value:
        raise ValueError('Provide a named nonempty secret.')
    import win32crypt
    protected = win32crypt.CryptProtectData(value.encode('utf-8'),'Cortana local secret',_entropy,None,None,1)
    with _lock:
        data = _read()
        data['entries'][name] = base64.b64encode(protected).decode('ascii')
        destination = _path()
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary = destination.with_name(destination.name+'.'+uuid4().hex+'.tmp')
        try:
            temporary.write_text(json.dumps(data),encoding='utf-8')
            os.replace(temporary,destination)
        finally:
            temporary.unlink(missing_ok=True)


def read(name):
    import win32crypt
    with _lock:
        encoded = _read()['entries'].get(name)
    if encoded is None:
        return None
    _, value = win32crypt.CryptUnprotectData(base64.b64decode(encoded),_entropy,None,None,1)
    return value.decode('utf-8')


def names():
    with _lock:
        return sorted(_read()['entries'])
