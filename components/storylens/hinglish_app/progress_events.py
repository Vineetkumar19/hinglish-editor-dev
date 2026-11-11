"""Small private status-boundary timestamps; no request/header metadata."""
import json
import math
import os
from pathlib import Path
import re
import threading
import time

_lock=threading.Lock()


def record(root,kind,key,**values):
    if kind not in ('job','assistant') or not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key):return False
    fields={}
    if isinstance(values.get('status'),str):fields['status']=values['status'][:40]
    if isinstance(values.get('stage'),str):
        stage=re.sub(r'https?://\S+','[source link]',values['stage'])
        fields['stage']=' '.join(stage.split())[:250]
    progress=values.get('progress')
    if type(progress) in (int,float) and math.isfinite(progress) and 0<=progress<=100:fields['progress']=progress
    if not fields:return False
    event={'kind':kind,'id':key,'pid':os.getpid(),'wall_time_ns':time.time_ns(),'monotonic_ns':time.monotonic_ns(),**fields}
    try:
        path=Path(root)/'cache/app/progress-events'/(kind+'-'+key+'.jsonl')
        with _lock:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(event,ensure_ascii=False)+'\n')
        return True
    except OSError:return False  # Diagnostics must not replace the real job outcome.

