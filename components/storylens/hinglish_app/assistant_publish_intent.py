"""Small publishing vocabulary and missing-input questions, before model planning.

This stores only an unfinished question in the current chat. It never selects
media, queues work, or treats another chat's outputs as a source.
"""
import re

TERMINOLOGY = ('Owner terminology: Reels mean Instagram Reels; Shorts mean YouTube Shorts; '
    'videos mean ordinary long-form videos, including 10–15 minute highlights. '
    'An explicitly named platform overrides the noun (for example saved Shorts on Instagram). '
    'Folder/file names do not establish a platform. Ask for genuinely missing source files '
    'or destination; retain the count and channel already supplied. Do not add publishing '
    'to an extraction-only request. Work one stage at a time when requested.')


def instruction(text):
    from .assistant_sources import literal_locations
    from .assistant_publishing_context import intent_text
    _, value = literal_locations(intent_text(text))
    return value


def positive(text):
    return re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*', ' ', text, flags=re.I)


def publishing(text):
    value = positive(text)
    if re.match(r'^\s*(?:how|why|what|where|explain|can i|did|does|is|are)\b', value, re.I):return False
    return bool(re.search(r'\b(?:upload|post|publish|queue|schedule)\b', value, re.I))


def fresh_upload(text):
    """A new undated upload-now command must not inherit expired release dates."""
    value=positive(instruction(text))
    from .assistant_publishing_context import schedule_literals
    from .publishing_times import match_saved
    return bool(publishing(value) and re.search(r'\b(?:now|immediately|right away|at once)\b',value,re.I)
        and re.search(r'\b(?:upload|post|publish)\b',value,re.I)
        and not match_saved(value)
        and not schedule_literals(value))


def platforms(text):
    """Explicit platform words win; otherwise use media nouns outside paths."""
    value = positive(instruction(text))
    explicit = [key for key, pattern in (
        ('youtube', r'\b(?:you\s*tube|yt)\b'),
        ('instagram', r'\b(?:instagram|insta|ig)\b')) if re.search(pattern, value, re.I)]
    if explicit:return explicit
    if re.search(r'\bboth platforms\b', value, re.I):return ['youtube', 'instagram']
    inferred=[]
    if re.search(r'\bshorts?\b(?![ -]form\b)', value, re.I):inferred.append('youtube')
    if re.search(r'\breels?\b', value, re.I):inferred.append('instagram')
    if not inferred and re.search(r'\bvideos?\b|\bshort[ -]form\b', value, re.I):inferred=['youtube']
    return inferred


def execution_text(text):
    value=instruction(text)
    if not publishing(value):return text
    scope=platforms(text)
    if len(scope)!=1:return text
    if re.search(r'\b(?:you\s*tube|yt|instagram|insta|ig)\b',positive(value),re.I):return text
    # A concrete routing constraint, not extra permission. Keep the raw owner
    # message intact in the UI and use this only for the execution request.
    suffix={'instagram':'Instagram only.', 'youtube':'YouTube only.'}[scope[0]]
    if scope==['youtube'] and re.search(r'\bvideos?\b|\bshort[ -]form\b', value, re.I) and not re.search(r'\bshorts?\b(?![ -]form\b)',value,re.I):
        suffix+=' Media type: long-form video.'
    return text+'\nPublishing platform: '+suffix


def preflight(assistant, session_id, text, snapshot, selected):
    """Return resolved execution text, or None after a normal missing-input question."""
    from .assistant_distribution import context
    from .delivery_request import profiles
    from .assistant_sources import literal_locations, MEDIA, named_sources
    from .assistant_artifacts import editing_requested, catalog
    from pathlib import Path
    workflow=context(assistant.root)
    pending=snapshot.get('publishing_inputs_pending') or {}
    locations,value=literal_locations(text)
    destination=profiles(value,workflow)
    has_attachment=any(a.get('kind')!='voice' and Path(a.get('path','')).suffix.lower() in MEDIA for a in selected)
    # A folder/account-only answer continues this question, never an unrelated
    # request or a new complete command. No cross-chat history is consulted.
    answer=bool(locations or has_attachment or destination or platforms(text)) and not publishing(value) and not editing_requested(value)
    if pending and answer:
        if not has_attachment:
            retained=set(pending.get('attachment_ids',[]))
            selected.extend(a for a in snapshot.get('attachments',[]) if a.get('id') in retained and a.get('kind')!='voice' and Path(a.get('path','')).suffix.lower() in MEDIA)
            has_attachment=bool(selected)
        text=pending['request']+'\n'+text
        locations,value=literal_locations(text)
        destination=profiles(value,workflow)
    elif pending:
        assistant._update(session_id,publishing_inputs_pending=None)
    if not publishing(value) or editing_requested(value):return text
    # Status, retry, metadata and scheduling continuations keep their existing
    # receipt-aware handlers rather than becoming new source questions.
    media=bool(re.search(r'\b(?:reels?|shorts?|videos?|clips?)\b',positive(value),re.I))
    if not media and not locations and not has_attachment:return text
    reference=bool(re.search(r'\b(?:it|them|this|these|those|same|existing|saved|old|finished|completed|memory|already)\b',value,re.I))
    current=bool(snapshot.get('publishing_review') or snapshot.get('campaign') or catalog(assistant,snapshot))
    if current and not pending and not locations and re.search(r'\b(?:reschedule|move|change)\b|^\s*schedule\b',value,re.I):return execution_text(text)
    if reference and current and not pending and not locations and not has_attachment and platforms(text):return execution_text(text)
    known=[a['path'] for a in snapshot.get('attachments',[]) if a.get('kind')!='voice']
    source=bool(locations or has_attachment or named_sources(text,known))
    # "Any saved Reels" explicitly authorizes saved-library selection. A bare
    # command does not silently reuse an unrelated old batch.
    source=source or bool(reference and re.search(r'\b(?:saved|existing|old|finished|completed|memory|already)\b',value,re.I))
    missing=[]
    if not source:missing.append('source')
    if not destination:missing.append('destination')
    if not platforms(text):missing.append('platform')
    if not missing:
        # Exact-file binding belongs to the finished YouTube route. Instagram
        # plural/folder requests retain their own receipt-aware media selection.
        if platforms(text)==['youtube'] and not has_attachment and (locations or named_sources(text,known)):
            from .assistant_finished_upload import source_paths
            selected.extend(assistant.attach(session_id,p) for p in source_paths(text,known))
        assistant._update(session_id,publishing_inputs_pending=None)
        return execution_text(text)
    from .assistant_saved_reels import clip_count
    count=clip_count(value)
    scope=platforms(text)
    label='Instagram Reel' if scope==['instagram'] else 'YouTube Short' if scope==['youtube'] and re.search(r'\bshorts?\b(?![ -]form\b)',value,re.I) else 'YouTube video' if scope==['youtube'] else 'video'
    target=', '.join(f'{key} '+('Instagram (@'+workflow['destinations'][key]['instagram']+')' if scope==['instagram'] else 'YouTube ('+workflow['destinations'][key]['youtube']+')' if scope==['youtube'] else 'account') for key in destination)
    summary=(f'You want to post {count} {label}'+('s' if count!=1 else '') if count else f'You want to post a {label}')+(' to '+target if target else '')+'.'
    questions=[]
    if 'source' in missing:questions.append('Paste the full folder path containing the finished files, or attach the video'+('s' if count!=1 else '')+' you want to use.')
    if 'destination' in missing:questions.append('Which account should I use: cricket or gaming?')
    if 'platform' in missing:questions.append('Should I post on Instagram or YouTube?')
    assistant._update(session_id,publishing_inputs_pending={'request':text,'missing':missing,'attachment_ids':[a['id'] for a in selected if a.get('id') and a.get('kind')!='voice']},status='idle',stage='',workflow_retrieval=None)
    assistant._message(session_id,'assistant',summary+' '+' '.join(questions)+' No upload has started.',question=True)
    return None
