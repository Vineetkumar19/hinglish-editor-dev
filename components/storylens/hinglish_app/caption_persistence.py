"""Atomic caption receipts tolerate short Windows readers without losing progress."""
import json,os,time,uuid
from pathlib import Path

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf8')
        for attempt in range(50):
            try:os.replace(temporary,path);break
            except PermissionError:
                if attempt==49:raise
                time.sleep(.02)
    finally:
        if temporary.exists():temporary.unlink()
