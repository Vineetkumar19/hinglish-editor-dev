"""Bounded retrieval of reviewed, timestamp-supported sound teaching cards."""
import hashlib
import json
import re
from pathlib import Path


def context(root, query='', limit=6):
    if root is None:
        return None
    path=Path(root)/'hinglish_app/knowledge/sound_design_teaching.json'
    if not path.is_file():
        return None
    guide=json.loads(path.read_text('utf-8'))
    if guide.get('enabled') is not True:
        return None
    text=str(query).casefold()
    def score(row):
        return sum(bool(re.search(r'\b'+re.escape(word.casefold())+r'\b',text)) for word in row.get('topics',[]))
    ranked=sorted(guide.get('lessons',[]),key=score,reverse=True)
    selected=[];used=0
    for card in ranked:
        item={k:card[k] for k in ('id','principle','when','how','avoid','evidence')}
        size=len(json.dumps(item,ensure_ascii=False))
        if used+size>4300:
            continue
        selected.append(item);used+=size
        if len(selected)>=limit:break
    return dict(revision=hashlib.sha256(path.read_bytes()).hexdigest(),
        kind='Reviewed teaching reference retrieval, not model-weight training or tool access',
        core=guide['core'],lessons=selected,
        sources=[{k:s[k] for k in ('id','name','seconds')} for s in guide.get('sources',[])],
        complete_knowledge='hinglish_app/knowledge/sound_design_teaching.json',
        limitations=guide['limitations'])
