"""Resolve calendar literals once; local models select media and destinations."""
from datetime import datetime,timedelta
import re
from .assistant_publishing_context import IST,schedule_literals


def normalize(text):
    text=re.sub(r'\bdont\b',"don't",text,flags=re.I)
    text=re.sub(r'\b(?:tommorow|tommorrow|tomorow)\b','tomorrow',text,flags=re.I)
    text=re.sub(r'\bmins?\b','minutes',text,flags=re.I)
    return re.sub(r'\bsecs?\b','seconds',text,flags=re.I)


def enumerated_slots(text):
    """Count explicitly enumerated releases in a mixed immediate/future request."""
    words={'second':2,'third':3,'fourth':4,'fifth':5,'sixth':6,
           'seventh':7,'eighth':8,'ninth':9,'tenth':10}
    text=normalize(text)
    values=[]
    pattern=r'\b(\d+(?:st|nd|rd|th)|'+ '|'.join(words)+r')\s+(?:(?:video|clip|short|reel)\s+)?(?:on\s+|at\s+)?(?:tomorrow|today|next|in\b|\d)'
    for match in re.finditer(pattern,text,re.I):
        value=match.group(1).lower()
        values.append(words[value] if value in words else int(re.match(r'\d+',value).group()))
    return max(values,default=0)


def explicit_slots(text,now):
    """Resolve ordered per-clip times without inventing a daily cadence."""
    ordinals={'first':1,'second':2,'third':3,'fourth':4,'fifth':5,'sixth':6,
              'seventh':7,'eighth':8,'ninth':9,'tenth':10}
    marker=r'\b('+ '|'.join(ordinals)+r'|\d+(?:st|nd|rd|th))\s+(?:(?:video|clip|short|reel)\s+)?'
    matches=list(re.finditer(marker,text,re.I))
    if len(matches)<2:return []
    # A first-now/second-later pair uses the existing immediate-first contract;
    # the first clause deliberately has no clock to validate as a timed slot.
    if (len(matches)==2 and matches[0][1].lower() in ('first','1st')
        and matches[1][1].lower() in ('second','2nd')
        and re.match(r'(?:right\s+)?now\b',text[matches[0].end():].lstrip(),re.I)):
        return []
    shared=schedule_literals(text,now=now)
    slots=[]
    for i,match in enumerate(matches):
        clause=text[match.end():matches[i+1].start() if i+1<len(matches) else len(text)]
        literal=schedule_literals(clause,now=now)
        if not literal.get('clock'):continue
        value=match[1].lower()
        position=ordinals[value] if value in ordinals else int(re.match(r'\d+',value)[0])
        day=literal.get('first_date') or shared.get('first_date') or now.date().isoformat()
        instant=datetime.fromisoformat(day+'T'+literal['clock']).replace(tzinfo=IST)
        slots.append({'position':position,'publish_at':instant.isoformat()})
    if not slots:return []
    if len(slots)!=len(matches) or sorted(s['position'] for s in slots)!=list(range(1,len(slots)+1)):
        raise ValueError('Give one date and time for each ordered Reel or clip. Nothing was scheduled.')
    slots.sort(key=lambda s:s['position'])
    times=[datetime.fromisoformat(s['publish_at']) for s in slots]
    if any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Each following release must be later than the previous one. Nothing was scheduled.')
    return slots


def contract(text,workflow,now=None):
    text=normalize(text)
    now=now or datetime.now(IST)
    literal=schedule_literals(text,now=now)
    amounts={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
    amount_pattern=r'(\d+|'+'|'.join(amounts)+r')'
    gap=re.search(r'\b'+amount_pattern+r'\s*[- ]?\s*(seconds?|minutes?)\s+(?:apart|gap|between|after\s+(?:the\s+)?first)\b',text,re.I)
    if not gap:gap=re.search(r'\bgap\s+(?:of\s+)?'+amount_pattern+r'\s+(seconds?|minutes?)\b',text,re.I)
    interval=((int(gap[1]) if gap[1].isdigit() else amounts[gap[1].lower()])*(60 if gap[2].lower().startswith('minute') else 1)) if gap else 0
    if gap and not 5<=interval<=86400:raise ValueError('Choose a release interval between 5 seconds and one day.')
    relative=re.search(r'\bin\s+(\d+|one|two|three|five|ten)\s+(seconds?|minutes?|hours?)\b',text,re.I)
    if relative and not literal:
        words={'one':1,'two':2,'three':3,'five':5,'ten':10}
        amount=int(relative[1]) if relative[1].isdigit() else words[relative[1].lower()]
        seconds=amount*(3600 if relative[2].lower().startswith('hour') else 60 if relative[2].lower().startswith('minute') else 1)
        if not 5<=seconds<=30*86400:raise ValueError('Choose a release delay between 5 seconds and 30 days.')
        instant=now+timedelta(seconds=seconds)
        return {'first_date':instant.date().isoformat(),'clock':instant.strftime('%H:%M'),
                'immediate_first':False,'relative_delay_seconds':seconds,
                **({'interval_seconds':interval} if interval else {})}
    slots=explicit_slots(text,now)
    if slots:
        first=datetime.fromisoformat(slots[0]['publish_at'])
        return {'first_date':first.date().isoformat(),'clock':first.strftime('%H:%M'),
                'immediate_first':False,'clip_slots':slots}
    from .publishing_times import window
    random_window=window(text,workflow) if not interval else None
    positive=re.sub(r"\b(?:do not|don't|never|without)\b[^.!?;\n]*",' ',text,flags=re.I)
    immediate=bool(re.search(r'\b(?:one|1|first|1st)\s+(?:(?:video|short|clip|reel)\s+)?(?:right\s+)?now\b',positive,re.I)
        or re.search(r'\b(?:post|upload|publish)\b(?:(?![.!?;\n]|\b(?:tomorrow|later|next|scheduled?)\b).){0,120}\b(?:now|immediately|right away|at once)\b',positive,re.I))
    explicit_now=immediate
    # An undated Instagram upload is an immediate execution request. Daily
    # default times govern later clips, not an unrequested delay of the first.
    if (not random_window and not literal and re.search(r'\b(?:instagram|insta|ig)\b',positive,re.I)
        and re.search(r'\b(?:post|upload|publish)\b',positive,re.I)
        and not re.search(r'\b(?:schedul\w*|tomorrow|later|next|daily|every day|draft|preview|review|hold|wait|tonight|morning|evening|afternoon|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\b(?:after|in)\s+\d+\s+(?:hours?|days?|weeks?)\b',positive,re.I)
        and not re.match(r'\s*(?:how|why|what|is|can i|explain)\b',positive,re.I)):
        immediate=True
    from .publishing_times import match_saved
    saved=match_saved(text)
    if saved and not literal and not immediate:
        return {'first_date':'','clock':'','immediate_first':False}
    no_schedule=bool(re.search(r"\b(?:do not|don't|without)\s+schedul\w*\b",text,re.I))
    first_only=bool(re.search(r'\b(?:first|1st)\s+(?:(?:video|reel|short|clip)\s+)?(?:right\s+)?now\b',positive,re.I))
    immediate_all=bool(immediate and not interval and not literal and not first_only
        and (explicit_now or no_schedule or re.search(r'\b(?:both|all|at once|(?:\d+|two|three|four|five|six|seven|eight|nine|ten)\s+(?:videos|reels|shorts|clips))\b',positive,re.I))
        and not re.search(r'\b(?:tomorrow|later|next|daily|consecutive|every day)\b',positive,re.I))
    if immediate_all:random_window=None
    clock=literal.get('clock') or workflow['daily_time']
    if random_window:clock=random_window['start']
    first=literal.get('first_date')
    if not first:
        hour,minute=map(int,clock.split(':'))
        candidate=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
        boundary=candidate
        if random_window:
            hour,minute=map(int,random_window['end'].split(':'))
            boundary=candidate.replace(hour=hour,minute=minute)
        if immediate or boundary<=now+timedelta(minutes=2):candidate+=timedelta(days=1)
        first=candidate.date().isoformat()
    if random_window and first==now.date().isoformat():
        provisional=(now+timedelta(minutes=3)).replace(second=0,microsecond=0).strftime('%H:%M')
        clock=max(clock,provisional)
    return {'first_date':first,'clock':clock,'immediate_first':immediate,
            **({'immediate_all':True} if immediate_all else {}),
            **({'interval_seconds':interval} if interval else {}),
            **({'random_window':random_window} if random_window else {}),
            **({'end_date':literal['end_date']} if literal.get('end_date') else {})}
