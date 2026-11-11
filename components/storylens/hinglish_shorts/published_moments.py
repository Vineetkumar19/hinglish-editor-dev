"""Source-bound publication history, never another chat's instructions."""
import json
from pathlib import Path


def intervals(root, source):
    from hinglish_publish.store import Store
    from .source import quick_fingerprint
    key=quick_fingerprint(source);found=[];seen=set()
    for job in Store(root).list():
        if not job.get('remote',{}).get('id') or job.get('kind')!='short' or not job.get('campaign'):continue
        preparation=Path(job['campaign'])/'preparation.json'
        if not preparation.is_file():continue
        data=json.loads(preparation.read_text(encoding='utf-8'))
        for entry in data.get('identity',{}).get('sources',[]):
            if entry.get('fingerprint')!=job.get('fingerprint'):continue
            project=Path(entry['video']).parent/'shorts-project.json'
            if project in seen or not project.is_file():continue
            seen.add(project)
            saved=json.loads(project.read_text(encoding='utf-8'))
            original=Path(saved['video']['path'])
            if not original.is_file() or quick_fingerprint(original)!=key:continue
            # This project is the durable extraction record for the published
            # campaign. Exclude its selections before asking for new moments.
            found.extend(tuple(piece) for short in saved.get('shorts',[]) for piece in short.get('pieces',[]))
    return sorted(set(found))
