"""Read-only answers from the current review and its per-video receipts."""
from datetime import datetime
import re

from .assistant_publishing_context import IST


def requested(text,snapshot,has_image=False):
    review=snapshot.get('publishing_review') or {}
    if review.get('youtube_check_only'):return False  # Draft checks are not YouTube schedules.
    if not review.get('schedule') or not review.get('rows'):return False
    value=text.casefold().strip()
    if re.match(r'^(?:please\s+)?(?:schedule|reschedule|preview|post|upload|publish|queue|change|move)\b',value):
        return False  # "Instagram only" is an execution scope, not a status question.
    if has_image and re.fullmatch(r'(?:see|look|check this|here|see this)[.! ]*',value):
        previous=next((m.get('text','') for m in reversed(snapshot.get('messages',[])) if m.get('role')=='user'),'')
        return requested(previous,snapshot)
    return bool(re.search(r'\b(what|which|why|check|status|progress|only)\b',value) and
                re.search(r'\b(dates?|schedul\w*|releases?|videos?|other|remaining)\b',value) and
                not re.search(r'\b(?:then|and)\s+(?:re)?schedule\b',value))


def date_text(value):
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(IST).strftime('%d %b %Y, %H:%M IST')
    except (ValueError,AttributeError):return 'unavailable'


def report(assistant,session_id,*,keep_running=False):
    snapshot=assistant.snapshot(session_id);review=snapshot['publishing_review']
    rows=review['rows'];verified=sum(r.get('schedule_verified',False) for r in rows)
    lines=[f'Saved progress: {verified} of {len(rows)} requested release dates are verified.']
    states={'submitted':'submitted to Studio; awaiting verification','not_started':'not started for this request',
            'queued':'waiting for Chrome','running':'being prepared in Studio','sharing':'submission in progress',
            'needs_review':'needs attention','blocked':'blocked','cancelled':'cancelled','verified':'verified by YouTube'}
    for row in rows:
        line=f'{row["metadata"]["title"]}: requested {date_text(row.get("publish_at",""))}; '+states.get(row.get('schedule_state'), 'not yet verified')+'.'
        if row.get('verified_publish_at') and not row.get('schedule_verified'):
            line+=' Last verified release: '+date_text(row['verified_publish_at'])+'.'
        if row.get('schedule_state') in ('needs_review','blocked') and row.get('schedule_message'):
            line+=' '+row['schedule_message']
        lines.append(line)
    if verified<len(rows):
        lines.append('The existing uploads are kept. A resume first verifies submitted changes, then continues unfinished videos; no new upload is needed.')
    assistant._message(session_id,'assistant','\n\n'.join(lines),publishing_review=review)
    if not keep_running:
        assistant._update(session_id,status='complete' if verified==len(rows) else 'needs_review',
                          stage='All requested release dates verified.' if verified==len(rows) else 'Saved schedule progress; unfinished videos remain.')


def followup(assistant,session_id,text,snapshot,attachments=()):
    has_image=any(str(a.get('path','')).lower().endswith(('.png','.jpg','.jpeg','.webp')) for a in attachments)
    if not requested(text,snapshot,has_image):return False
    report(assistant,session_id)
    return True
