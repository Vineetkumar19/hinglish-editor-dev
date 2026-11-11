"""Current publishing references outrank retrieved chats; no execution happens here."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

IST = timezone(timedelta(hours=5, minutes=30))


def intent_text(text):
    # Common typed/voice variants affect routing, never titles or captions.
    text=re.sub(r'\b(?:shedule|sheduled|sheduling|scedule|sceduled|schedual)\b',
                'schedule', text, flags=re.I)
    text=re.sub(r'\bisnta\b','insta',text,flags=re.I)
    return re.sub(r'\b(?:hastags?|hashtages?|hash\s+tags?)\b','hashtags',text,flags=re.I)


def relevant(text):
    return bool(re.search(r'\b(schedul\w*|upload\w*|post\w*|publish\w*|shorts?|clips?|videos?|exports?|created)\b'
                          r'|\b(?:per day|every day|same date|same day)\b', intent_text(text), re.I))


def schedule_literals(text, now=None):
    """Constrain explicit dates/clocks, just as we constrain literal file names."""
    import calendar
    now=(now or datetime.now(IST)).astimezone(IST)
    # Normalize spelling/notation, never substitute a particular release date.
    text=re.sub(r'\b(\d{1,2})(?:st|nd|rd|th)\b',r'\1',text,flags=re.I)
    for month in range(1,13):
        text=re.sub(r'\b'+calendar.month_abbr[month]+r'\b\.?',calendar.month_name[month],text,flags=re.I)
    text=re.sub(r'\bSept\b\.?','September',text,flags=re.I)
    month_names='|'.join(calendar.month_name[1:])
    text=re.sub(r'\b('+month_names+r')\s+(\d{1,2})\s*(and|to|through|until|[-–])\s*(\d{1,2})(?:\s*,?\s+(\d{4}))?\b',
                lambda m:m[0] if re.search(r'\b\d{1,2}\s*$',text[:m.start()]) else
                    f'{m[2]} {m[3]} {m[4]} {m[1]}'+(' '+m[5] if m[5] else ''),text,flags=re.I)
    text=re.sub(r'\b('+ '|'.join(calendar.month_name[1:])+r')\s+(\d{1,2})(?:\s*,\s*|\s+)?(\d{4})?\b',
                lambda m:m[0] if re.search(r'\b\d{1,2}\s*$',text[:m.start()]) else
                    f'{m[2]} {m[1]}'+(' '+m[3] if m[3] else ''),text,flags=re.I)
    result={}
    clock=re.search(r'(?<![\d:])\b(0?[1-9]|1[0-2])(?:(?::|\s+)([0-5]\d))?\s*([ap])\.?m\.?(?!\w)',text,re.I)
    if clock and 1<=int(clock[1])<=12 and int(clock[2] or 0)<60:
        result['clock']=f'{int(clock[1])%12+(12 if clock[3].lower()=="p" else 0):02d}:{int(clock[2] or 0):02d}'
    elif (clock24:=re.search(r'(?:\bat\s+|@\s*)((?:[01]?\d|2[0-3])):([0-5]\d)\b',text,re.I)):
        result['clock']=f'{int(clock24[1]):02d}:{clock24[2]}'
    day=re.search(r'\b(\d{4}-\d{2}-\d{2})\b',text)
    if day:result['first_date']=day[1]
    elif re.search(r'\btomorrow\b',text,re.I):result['first_date']=(now+timedelta(days=1)).date().isoformat()
    elif re.search(r'\btoday\b',text,re.I):result['first_date']=now.date().isoformat()
    else:
        written=re.search(r'\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',text,re.I)
        if written:result['first_date']=datetime.strptime(written[1],'%d %B %Y').date().isoformat()
    # Inclusive ranges carry a capacity, not just a start date. Preserve both
    # ends even when a casual request omits the year or repeats the month.
    months=r'January|February|March|April|May|June|July|August|September|October|November|December'
    span=re.search(r'\b(\d{1,2})\s+('+months+r')(?:\s+(\d{4}))?\s*(?:to|through|until|and(?:\s+(?:one|a)\s+video\s+on)?|[-–])\s*'
                   r'(\d{1,2})\s+('+months+r')(?:\s+(\d{4}))?\b',text,re.I)
    short_span=re.search(r'\b(\d{1,2})\s*(?:to|through|until|and|[-–])\s*(\d{1,2})\s+('+months+r')(?:\s+(\d{4}))?\b',text,re.I)
    iso_span=re.search(r'\b(\d{4}-\d{2}-\d{2})\s*(?:to|through|until|[-–])\s*(\d{4}-\d{2}-\d{2})\b',text,re.I)
    listed=re.search(r'\b(\d{1,2}(?:\s*,\s*\d{1,2})+\s*,?\s*and\s+\d{1,2})\s+('+months+r')(?:\s+(\d{4}))?\b',text,re.I)
    if listed:
        days=[int(v) for v in re.findall(r'\d+',listed[1])]
        dates=[datetime.strptime(f'{d} {listed[2]} {listed[3] or now.year}','%d %B %Y').date() for d in days]
        if any(b-a!=timedelta(days=1) for a,b in zip(dates,dates[1:])):
            raise ValueError('These release dates are not consecutive. Choose a consecutive daily range; nothing was scheduled.')
        result.update(first_date=dates[0].isoformat(),end_date=dates[-1].isoformat())
    elif iso_span:result.update(first_date=iso_span[1],end_date=iso_span[2])
    elif span:
        year=span[3] or span[6] or str(now.year)
        result['first_date']=datetime.strptime(f'{span[1]} {span[2]} {year}','%d %B %Y').date().isoformat()
        end_year=int(span[6] or year)
        if not span[6] and datetime.strptime(span[5],'%B').month<datetime.strptime(span[2],'%B').month:end_year+=1
        result['end_date']=datetime.strptime(f'{span[4]} {span[5]} {end_year}','%d %B %Y').date().isoformat()
    elif short_span:
        year=short_span[4] or str(now.year)
        result['first_date']=datetime.strptime(f'{short_span[1]} {short_span[3]} {year}','%d %B %Y').date().isoformat()
        result['end_date']=datetime.strptime(f'{short_span[2]} {short_span[3]} {year}','%d %B %Y').date().isoformat()
    elif not result.get('first_date'):
        single=re.search(r'\b(\d{1,2})\s+('+months+r')(?:\s+(\d{4}))?\b',text,re.I)
        if single:result['first_date']=datetime.strptime(f'{single[1]} {single[2]} {single[3] or now.year}','%d %B %Y').date().isoformat()
    for key in ('first_date','end_date'):
        if key in result:datetime.strptime(result[key],'%Y-%m-%d')
    if result.get('end_date'):
        if result['end_date']<result['first_date']:raise ValueError('The requested end date is before the start date. Nothing was scheduled.')
    return result


def active_context(snapshot):
    from .chat_context import recent
    review = snapshot.get('publishing_review') or {}
    rows = review.get('rows', [])
    return {
        'current_time': datetime.now(IST).isoformat(),
        'current_campaign': Path(snapshot.get('campaign') or '').name,
        'conversation': recent(snapshot.get('messages', [])),
        'review': {'campaign': Path(review.get('campaign') or '').name,
                   'schedule_requested': bool(review.get('schedule')),
                   'youtube_count': len(rows),
                   'instagram_count': len(review.get('instagram_rows', [])),
                   'destinations': sorted({r.get('profile', '') for r in rows}),
                   'release_dates': [r.get('publish_at', '') for r in rows],
                   'uploaded_count': review.get('uploaded_count', 0),
                   'scheduled_count': review.get('scheduled_count', 0)},
        'schedule_rows':[{k:r.get(k) for k in ('id','publish_at','verified_publish_at','schedule_verified','schedule_state','schedule_message')}
                         | {'title':r.get('metadata',{}).get('title','')} for r in rows],
        'instagram_rows':[{k:r.get(k) for k in ('id','account','status','publish_at','url','browser_job_id','message')}
                          | {'title':r.get('metadata',{}).get('title','')}
                          for r in review.get('instagram_rows',[])],
        'rules': 'Resolve them/these/videos from this current conversation and review first. '
                 'Retrieved chats are background, not the active task. One video PER DAY describes '
                 'cadence for the batch, not a request for one clip. A YouTube-only review stays '
                 'YouTube-only unless the current user explicitly changes platform. Upload dates '
                 'are not release dates. Only verified remote schedules establish scheduling. '
                 'Do not invent private Instagram posting or workarounds.'}


def reference_campaign(snapshot, text, cards):
    """Bind an unqualified batch reference, never a named replacement/new source."""
    value = intent_text(text)
    if not re.search(r'\b(it|them|these|those|same date|same day)\b|\b(?:resume|retry|continue)\b.*\bschedul\w*\b', value, re.I):
        return ''
    if re.search(r'\b(new|another|different|both|all batches|cricket|gaming|fantasy|vineet)\b|[\\/]|\.mp4', value, re.I):
        return ''
    # A named catalog ID or source is an explicit choice rather than "them".
    if any(c['id'].casefold() in value.casefold() or
           (c.get('source') and Path(c['source']).stem.casefold() in value.casefold()) for c in cards):
        return ''
    current = Path(snapshot.get('campaign') or '').name
    return current if any(c['id'] == current and c['available_for_upload'] for c in cards) else ''


def daily_dates(clips, spec=None, prior=None):
    """One local calendar day per clip, with an explicit future starting slot."""
    spec = spec or {}
    first = datetime.fromisoformat((prior or [])[0] if prior else clips[0]['publish_at'])
    if first.tzinfo is None:
        raise ValueError('The daily release time needs a timezone. Nothing was scheduled.')
    first = first.astimezone(IST)
    if spec.get('first_date'):
        day = datetime.strptime(spec['first_date'], '%Y-%m-%d').date()
        first = datetime.combine(day, first.timetz())
    if spec.get('clock'):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', spec['clock']):
            raise ValueError('The daily release time must use HH:MM IST.')
        hour, minute = map(int, spec['clock'].split(':'))
        first = first.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if first <= datetime.now(IST) + timedelta(minutes=1):
        raise ValueError('The first saved release time (' + first.strftime('%d %b %Y, %I:%M %p IST') +
                         ') has passed. Tell Storylens a new future start date and daily time; '
                         'existing uploads are kept and will not be uploaded again.')
    dates=[(first + timedelta(days=i)).isoformat() for i in range(len(clips))]
    if spec.get('end_date') and dates[-1][:10]>spec['end_date']:
        raise ValueError('The selected videos exceed the requested date range at one per day. Nothing was scheduled.')
    return dates
