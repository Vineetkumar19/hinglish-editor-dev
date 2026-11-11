"""Choose exact daily release minutes once, and persist them before publishing."""
from datetime import datetime,timedelta
import hashlib
import json
from pathlib import Path
import re
import secrets
import threading
from .assistant_publishing_context import IST,schedule_literals

_LOCK=threading.RLock()


def match_saved(text):
    return bool(re.search(r'\b(?:same|match|matching)\b.{0,45}\b(?:youtube|dates|schedule|times)\b|'
        r'\b(?:keep|use)\s+(?:the\s+)?(?:saved|existing|same|youtube)\b.{0,30}\b(?:dates|schedule|times)\b|'
        r'\bkeep\s+(?:the\s+)?(?:dates|times|schedule)\b',text,re.I))


def window(text,workflow):
    config=workflow.get('short_release_window') or {}
    if not config.get('enabled') or not text:return None
    # Explicit clocks, testing intervals, immediate releases and "match saved"
    # instructions retain their exact existing contract. Later daily clips in
    # a first-now batch can still use the default window.
    from .distribution_schedule import normalize
    value=normalize(text)
    if re.search(r'\brandom\w*\b',value,re.I):
        span=re.search(r'\b(?:between|from)\s+(\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?)\s*(?:and|to|[-–])\s*(\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?)',value,re.I)
        if span and [schedule_literals('at '+v).get('clock') for v in span.groups()]==[config.get('start','17:00'),config.get('end','21:00')]:
            value=value[:span.start()]+value[span.end():]
    if schedule_literals(value).get('clock'):return None
    if re.search(r'\b(?:seconds?|minutes?|hours?)\s+(?:apart|gap|between)|\bgap\s+(?:of\s+)?\w+\s+(?:seconds?|minutes?)|\bin\s+\w+\s+(?:seconds?|minutes?|hours?)',value,re.I):return None
    if match_saved(value):return None
    start=config.get('start','17:00');end=config.get('end','21:00')
    if not all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',v) for v in (start,end)) or start>=end:
        raise ValueError('The posting window is invalid. Set a start before the end, such as 17:00–21:00 IST.')
    return {'start':start,'end':end}


def choose(folder,key,day,policy,now=None):
    """Reusing this media/profile/platform/day reuses its saved minute on retry."""
    now=(now or datetime.now(IST)).astimezone(IST)
    first=datetime.fromisoformat(day+'T'+policy['start']).replace(tzinfo=IST)
    last=datetime.fromisoformat(day+'T'+policy['end']).replace(tzinfo=IST)
    identity=hashlib.sha256(json.dumps([key,day,policy],sort_keys=True).encode()).hexdigest()
    path=Path(folder)/'release-times.json'
    from .durable_json import write
    with _LOCK:
        saved=json.loads(path.read_text('utf-8')) if path.exists() else {'version':1,'slots':{}}
        if identity in saved['slots']:return datetime.fromisoformat(saved['slots'][identity]['publish_at'])
        earliest=max(first,now+timedelta(minutes=2))
        earliest=earliest.replace(second=0,microsecond=0)+(timedelta(minutes=1) if earliest.second or earliest.microsecond else timedelta())
        if earliest>last:
            raise ValueError('The 5–9 p.m. IST posting window for that day has passed. Choose a future date; saved posts and uploads are preserved.')
        options=[earliest+timedelta(minutes=i) for i in range(int((last-earliest).total_seconds()//60)+1)]
        used={slot['publish_at'][11:16] for slot in saved['slots'].values()}
        unique=[instant for instant in options if instant.strftime('%H:%M') not in used]
        options=unique or options
        instant=options[secrets.randbelow(len(options))]
        saved['slots'][identity]={'publish_at':instant.isoformat(),'key':key,'window':policy}
        path.parent.mkdir(parents=True,exist_ok=True)
        write(path,saved)
        return instant
