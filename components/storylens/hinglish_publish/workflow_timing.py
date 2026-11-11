"""Explicit request-bound dates; no global scheduling setting is changed."""
import re
import time
from datetime import datetime, timedelta, date
from .store import IST

def parse_request(text):
    result={}
    long=re.search(r'\blong(?: video)?\s+on\s+(\d{4}-\d{2}-\d{2})\s+at\s+(\d{2}:\d{2})\s+IST\b',text,re.I)
    daily=re.search(r'\bShorts\s+daily\s+from\s+(\d{4}-\d{2}-\d{2})\b',text,re.I)
    interval=re.search(r'\bInstagram\s+(?:Reels\s+)?(?:test\s+)?(?:every|at)\s+(\d+)\s+minute(?:s)?\b',text,re.I)
    if long:result['long_at']=datetime.fromisoformat(long[1]+'T'+long[2]).replace(tzinfo=IST).isoformat()
    if daily:result['shorts_start']=date.fromisoformat(daily[1]).isoformat()
    if interval:result['instagram_interval']=int(interval[1])*60
    # Human requests may include the destination between Long and its date.
    if not long:
        months='January February March April May June July August September October November December'.split()
        named=re.search(r'\blong(?:[ -]form)?(?: video| content)?\b[^.!?\n]{0,100}?\b(?:for|on)\s+(\d{1,2})\s+('+'|'.join(months)+r')\s+(\d{4})\s*(?:,|at)?\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s+IST\b',text,re.I)
        if named:
            day,month,year,hour,minute,period=named.groups();hour=int(hour)
            if not 1<=hour<=12:raise ValueError('Choose a valid long-video release time.')
            hour=hour%12+(12 if period.upper()=='PM' else 0)
            result['long_at']=datetime(int(year),next(i+1 for i,m in enumerate(months) if m.lower()==month.lower()),int(day),hour,int(minute or 0),tzinfo=IST).isoformat()
    if not interval:
        words={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
        gap=re.search(r'\bInstagram\s+(?:test\s+)?Reels?\s+(\d+|'+'|'.join(words)+r')\s+minutes?\s+apart\b',text,re.I)
        if gap:result['instagram_interval']=(int(gap[1]) if gap[1].isdigit() else words[gap[1].lower()])*60
    return validate(result)

def validate(timing,now=None):
    now=time.time() if now is None else now
    if not isinstance(timing,dict) or set(timing)-{'long_at','shorts_start','instagram_interval'}:raise ValueError('Invalid request-bound release timing.')
    timing=dict(timing)
    if 'long_at' in timing:
        value=datetime.fromisoformat(timing['long_at'])
        if value.tzinfo is None or value.timestamp()<=now+60:raise ValueError('Choose a future long-video release time with its timezone.')
    if 'shorts_start' in timing and date.fromisoformat(timing['shorts_start'])<datetime.fromtimestamp(now,IST).date():raise ValueError('The requested first Shorts date has passed. No date was silently moved.')
    if 'instagram_interval' in timing and (type(timing['instagram_interval']) is not int or not 60<=timing['instagram_interval']<=3600):raise ValueError('Choose a Reel test interval between one and sixty minutes.')
    return timing

def apply(engine,draft,role,platform,timing,now=None):
    if not timing or draft.get('jobs_by_platform',{}).get(platform):return
    now=time.time() if now is None else now
    saved=draft.setdefault('requested_release_slots',{})
    if platform in saved:return
    slots=None
    if role=='long' and timing.get('long_at'):
        slots=[datetime.fromisoformat(timing['long_at']).timestamp()]
    elif role=='shorts' and platform=='youtube' and timing.get('shorts_start'):
        start=date.fromisoformat(timing['shorts_start']);today=datetime.fromtimestamp(now,IST).date()
        # The request date is the earliest day. Existing daily Shorts take
        # precedence: a later batch appends after their last reserved day.
        start=max(start,today)
        account=draft.get('bindings',{}).get('youtube',{}).get('id')
        occupied=[]
        for job in engine.publisher.store.list():
            if (job.get('profile')!=draft.get('profile') or job.get('platform')!='youtube'
                    or job.get('kind')!='short' or job.get('prepare_post_id')==draft.get('id')
                    or job.get('status') in ('cancelled','published','failed','blocked')
                    or not job.get('authorized_at') or account and job.get('account_id')!=account):continue
            due=job.get('due',0)
            if due>now:occupied.append(datetime.fromtimestamp(due,IST).date())
        if occupied:start=max(start,max(occupied)+timedelta(days=1))
        slots=[]
        for n in range(draft['count']):
            day=start+timedelta(days=n);instant=datetime(day.year,day.month,day.day,19,tzinfo=IST).timestamp()
            if day==today:instant=max(instant,now+120)
            if datetime.fromtimestamp(instant,IST).date()!=day:raise ValueError('The first Shorts release cannot fit the requested day.')
            slots.append(instant)
    elif role=='shorts' and platform=='instagram' and timing.get('instagram_interval'):
        slots=[now+timing['instagram_interval']*(n+1) for n in range(draft['count'])]
    elif role=='shorts' and platform=='instagram' and 'youtube' in saved:
        slots=list(saved['youtube'])
    if slots is not None:
        if len(slots)!=draft['count'] or any(t<=now+30 for t in slots):raise ValueError('The requested release time passed during preparation. Saved work was kept.')
        saved[platform]=slots;engine._save(draft)
