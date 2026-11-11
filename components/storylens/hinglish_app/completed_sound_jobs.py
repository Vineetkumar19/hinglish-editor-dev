"""Retain actual completed recommendation receipts without resuming analysis."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace


def valid(root,job):
    from .panel_sound_review import _bound
    state=SimpleNamespace(root=root,snapshot=lambda key:job if key==job.get('id') else None)
    _bound(state,job.get('id'))


def save(root,port,job):
    try:valid(root,job)
    except (KeyError,TypeError,ValueError,OSError):return False
    kept={key:copy.deepcopy(job[key]) for key in ('id','mode','status','created','device','progress','stage','logs','result') if key in job}
    from hinglish_clean.detection import write_json
    write_json(Path(root)/'cache/app/completed-sound-jobs'/str(port)/(job['id']+'.json'),kept)
    return True


def load(root,port):
    jobs={}
    for file in (Path(root)/'cache/app/completed-sound-jobs'/str(port)).glob('*.json'):
        try:
            if file.stat().st_size>4*1024**2:continue
            job=json.loads(file.read_text('utf-8'));valid(root,job)
            if job['id']!=file.stem:continue
            jobs[job['id']]=job
        except (KeyError,TypeError,ValueError,OSError):continue
    return jobs
