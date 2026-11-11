"""Use the native panel's own disk catalogue, without a live editor dependency."""
from pathlib import Path
import json
import shutil
import subprocess
import threading
import time

READS={'animationPresets':{'catalog'},'effectsLibrary':{'catalog'},'cinematicText':{'catalog'},
       'presetLibrary':{'categories','catalog','motionCatalog','toolkitCatalog','gallery','galleryStatus'}}
_lock=threading.Lock();_cache={}

def read(action,payload):
    if not isinstance(payload,dict) or payload.get('action') not in READS.get(action,set()):
        raise ValueError('This action needs the connected After Effects panel.')
    key=json.dumps([action,payload],sort_keys=True)
    with _lock:
        saved=_cache.get(key)
        if saved and time.monotonic()-saved[0]<30 and not payload.get('refresh'):return saved[1]
        node=shutil.which('node')
        if not node:raise ValueError('The local catalogue reader is unavailable. Restore Node.js, then refresh.')
        root=Path(__file__).resolve().parents[1]
        proc=subprocess.run([node,'--max-old-space-size=192',str(root/'tools/native_library_catalog.cjs')],
            input=json.dumps({'action':action,'payload':payload}),encoding='utf-8',capture_output=True,
            timeout=90,cwd=root,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:value=json.loads(proc.stdout)
        except ValueError:raise ValueError('The local library could not be read. Check drive A and refresh.') from None
        if proc.returncode or value.get('error'):raise ValueError(value.get('error','The local library is unavailable.'))
        if len(proc.stdout)<2_000_000:
            if len(_cache)>=8:_cache.pop(next(iter(_cache)))
            _cache[key]=(time.monotonic(),value)
        return value
