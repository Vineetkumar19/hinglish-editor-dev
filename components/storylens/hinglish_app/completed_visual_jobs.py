"""Retain completed Smart Visuals application receipts; never start research.

These are local application records, not signatures or semantic/native approval.
Every raw image still goes through VisualSourceTransport's current binding checks.
"""
import copy
import json
from pathlib import Path
import re


def projects(root,job):
    if (not isinstance(job,dict) or job.get('mode')!='visuals' or job.get('status')!='complete'
            or not isinstance(job.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',job['id'])):
        raise ValueError('Choose a completed Smart Visuals review.')
    parent=Path(root).resolve()/'output/visuals';result=job['result'];folder=Path(result['folder']).resolve(strict=True)
    page=Path(result['page']).resolve(strict=True)
    if not folder.is_relative_to(parent) or folder==parent or page.parent!=folder:
        raise ValueError('The review is outside this application result.')
    if page.name=='report.html':files=[folder/'visuals-project.json']
    elif page.name=='index.html':
        receipt=folder/'result.json'
        if receipt.stat().st_size>1024**2:raise ValueError('This review index is too large.')
        rows=json.loads(receipt.read_text('utf-8'))['results'];files=[]
        if not isinstance(rows,list) or not rows:raise ValueError('Choose a finished review.')
        for row in rows:
            name=row['folder']
            if not isinstance(name,str) or name in ('.','..') or any(c in name for c in '/\\:'):
                raise ValueError('Choose a bound review project.')
            files.append(folder/name/'visuals-project.json')
    else:raise ValueError('Choose the saved review page.')
    resolved=[f.resolve(strict=True) for f in files]
    if len(set(resolved))!=len(resolved) or any(not p.is_relative_to(folder) or not p.is_file() for p in resolved):
        raise ValueError('The review project moved outside its result.')
    return resolved


def save(root,port,job):
    try:projects(root,job)
    except (KeyError,TypeError,ValueError,OSError):return False
    kept={k:copy.deepcopy(job[k]) for k in ('id','mode','status','created','device','progress','stage','logs','result') if k in job}
    from hinglish_clean.detection import write_json
    write_json(Path(root)/'cache/app/completed-visual-jobs'/str(port)/(job['id']+'.json'),kept)
    return True


def load(root,port):
    jobs={}
    for file in (Path(root)/'cache/app/completed-visual-jobs'/str(port)).glob('*.json'):
        try:
            if file.stat().st_size>4*1024**2:continue
            job=json.loads(file.read_text('utf-8'));projects(root,job)
            if file.stem!=job['id']:continue
            jobs[job['id']]=job
        except (KeyError,TypeError,ValueError,OSError):continue
    return jobs


def results(root,jobs):
    rows=[]
    for job in jobs:
        try:
            for file in projects(root,job):
                if file.stat().st_size>16*1024**2:continue
                project=json.loads(file.read_text('utf-8'))
                rows.append({'job_id':job['id'],'project_path':str(file),
                    'name':str(project.get('timeline',{}).get('name') or file.parent.name),
                    'created':job.get('created',0)})
        except (KeyError,TypeError,ValueError,OSError):continue
    return sorted(rows,key=lambda r:r['created'],reverse=True)[:80]
