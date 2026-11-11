"""Project acoustic direction and explicit recurring-sound identity.

This describes creative intent, not new audio models or DSP capabilities.
"""
import functools
import hashlib
from pathlib import Path


@functools.lru_cache(maxsize=2048)
def _digest(path,size,modified):
    with Path(path).open('rb') as stream:
        return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def source_identity(path):
    """Exact duplicate bytes count as the same source even with another name."""
    p=Path(path)
    try:
        stat=p.stat()
        return _digest(str(p.resolve()),stat.st_size,stat.st_mtime_ns)
    except OSError:
        return 'path:'+str(p.resolve()).casefold()

def palette_schema():
    return {'type':'object','properties':{
        'identity':{'type':'string','maxLength':180,'description':'Positive acoustic character of this project; put exclusions in avoid.'},
        'textures':{'type':'array','maxItems':6,'items':{'type':'string','maxLength':100}},
        'avoid':{'type':'array','maxItems':6,'items':{'type':'string','maxLength':100}}},
        'required':['identity','textures','avoid']}


def project_palette(value, delivery):
    value=value if isinstance(value,dict) else {}
    def strings(key):
        rows=value.get(key,[])
        return [x.strip()[:100] for x in rows if isinstance(x,str) and x.strip()][:6] if isinstance(rows,list) else []
    identity=value.get('identity','')
    authored=isinstance(identity,str) and bool(identity.strip())
    return dict(identity=identity.strip()[:180] if authored else str(delivery)+' delivery; choose context-specific sounds',
        textures=strings('textures'),avoid=strings('avoid'),delivery=delivery,
        source='local story analysis' if authored else 'legacy delivery context; no authored acoustic profile')


def palette_query(profile):
    if not isinstance(profile,dict):return ''
    # This is positive search direction. Exclusions stay in the decision prompt;
    # embedding a forbidden sound's name can otherwise retrieve that very sound.
    return ('Acoustic identity: '+str(profile.get('identity',''))+'. Preferred texture: '+
            ', '.join(profile.get('textures',[])[:3]))[:360]


def reuse_identity(moment):
    key,reason=moment.get('reuse_key'),moment.get('reuse_reason')
    if not isinstance(key,str) or not key.strip() or len(key)>64:return None
    if not isinstance(reason,str) or not reason.strip() or len(reason)>240:return None
    return (key.strip(),moment.get('type'),moment.get('role'))


def reusable(path, moment, history):
    previous=history.get(path,[])
    if not previous:return True,'First use in this video'
    group=moment.get('group_id')
    if any(p.get('group_id')==group for p in previous):return False,'The same source already serves this action group'
    identity=reuse_identity(moment)
    if identity is not None and all(reuse_identity(p)==identity for p in previous):
        return True,'Explicit recurring motif: '+moment['reuse_reason'].strip()
    return False,'Repeated source across contexts needs a matching reuse_key and an explicit narrative reason'


def candidate_slate(hits, moment, offered, limit=6):
    """Diversify already-relevant candidates, not arbitrary sounds or forced selections."""
    if moment.get('type') in ('foley','ambience'):
        from .relevance import _subjects
        requested=_subjects(moment.get('intent',''))
        confirmed=[hit for hit in hits if requested & _subjects(hit[0].name+' '+hit[0].text)]
        if confirmed:hits=confirmed
    unique={}
    for rank,hit in enumerate(hits):
        identity=source_identity(hit[0].path)
        unique.setdefault(identity,(rank,hit))
    recurring=reuse_identity(moment) is not None
    ranked=sorted(unique.items(),key=lambda item:(0 if recurring else offered.get(item[0],0),item[1][0]))
    selected=ranked[:limit]
    if not recurring:
        for identity,_ in selected:offered[identity]=offered.get(identity,0)+1
    return [row[1] for _,row in selected]
