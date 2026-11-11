"""Ask routes intent; Prepare/Post owns saved stages, models and transports.

No general chat history enters the engine. A continuation carries one durable
preparation ID, never another chat's artifacts or an inferred upload permission.
"""
import re
from pathlib import Path

MEDIA = {'.mp4', '.mov', '.mkv', '.webm', '.mxf', '.avi'}
IMAGES = {'.png', '.jpg', '.jpeg', '.webp'}
NUMBERS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
           'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'पाँच': 5, 'एक': 1}


def _positive(text):
    return re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*', '', text, flags=re.I)


def _request(text):
    if _help(text):
        return False
    value = _positive(text)
    publishing = re.search(r'\b(?:prepare|upload|post|publish|schedule)\b|तैयार|अपलोड|पोस्ट', value, re.I)
    extraction = re.search(r'\b(?:extract|generate|make|create)\b', value, re.I) and re.search(r'\b(?:shorts?|reels?|highlights?)\b', value, re.I)
    if not publishing and re.search(r'\b(?:captions?|subtitles?|b[ -]?roll|sound design|motion graphics)\b', value, re.I):return False
    return bool((publishing or extraction)
                and re.search(r'\b(?:video|shorts?|reels?|highlights?|prepare and post)\b|\.(?:mp4|mov|mkv|webm|mxf|avi)\b|वीडियो|शॉर्ट|रील', value, re.I))


def _help(text):
    return bool(re.match(r'^\s*(?:(?:can|could|would) you\s+)?(?:how|why|what|where|explain|tell me how|show me how|can i|does|did|is|are|open|show)\b', text, re.I))


def _scope(text, fallback):
    found = [p for p, pattern in [('youtube', r'\b(?:youtube|yt)\b'),
                                 ('instagram', r'\b(?:instagram|insta|ig)\b')]
             if re.search(pattern, _positive(text), re.I)]
    return found or list(fallback)


def _channels(text):
    return [p for p, pattern in [('cricket', r'\bcricket\b|क्रिकेट'),
                                 ('gaming', r'\bgaming\b|गेमिंग')] if re.search(pattern, text, re.I)]


def _release(text):
    value = _positive(text)
    # Conditional instructions need review; do not guess whether their condition
    # has occurred. The supported direct action can be confirmed independently.
    if re.search(r'\b(?:after|if|when|once|until|unless)\b', value, re.I):return None
    if re.search(r'\b(?:prepare|draft|review)\b', value, re.I) and not re.search(
            r'\b(?:then|and)\s+(?:upload|post|publish|schedule)\b|\b(?:upload|post|publish)\s+(?:it\s+|them\s+)?now\b', value, re.I):return None
    # Routing can recognize Hindi, but publication permission must be explicit
    # in the supported action vocabulary; an unclear intent stays in review.
    if not re.search(r'\b(?:post|upload|publish|schedule)\b', value, re.I):return None
    if re.search(r'\b(?:private|privately)\b', value, re.I):return 'private'
    return 'schedule' if re.search(r'\bschedul', value, re.I) else 'post_now'


def followup(assistant, session_id, text, snapshot, selected, progress, message_id):
    saved = snapshot.get('prepare_post_bridge') or {}
    pending = snapshot.get('prepare_post_inputs') or {}
    continuation = saved and not selected and not re.search(r'[A-Za-z]:[\\/]', text) and bool(re.search(
        r'\b(?:resume|retry|continue|stop|cancel|status|progress|post|upload|schedule)\b', text, re.I))
    # Questions about a saved job may report status; other questions remain chat.
    status = bool(continuation and re.search(r'\b(?:status|progress)\b', text, re.I))
    if _help(text) and not status:return False
    if not status and not continuation and not pending and not _request(text):return False
    if continuation and not status and not _positive(text).strip():return False

    def say(message, question=False):
        assistant._message(session_id, 'assistant', message, question=question)
        assistant._update(session_id, status='idle', stage='')

    def report(draft, message=None):
        stopped = draft.get('status') == 'stopped'
        failed = draft.get('status') == 'failed'
        message = message or draft.get('message') or (
            'Prepared. Review the saved platform text before posting.' if draft.get('status') == 'prepared'
            else 'Preparation status: ' + draft.get('status', 'saved') + '.')
        assistant._update(session_id, status='stopped' if stopped else 'needs_review', selected='publish', stage=message)
        assistant._message(session_id, 'assistant', message, navigate='publisher',
            publisher_profile=draft['profile'], publish_ids=[draft['id']],
            prepare_post_id=draft['id'], error=failed,
            error_details='\n'.join(str(v.get('error_details', '')) for v in draft.get('errors', {}).values() if isinstance(v, dict)))

    try:
        if continuation:
            if snapshot.get('profile') != saved['profile'] or any(p != saved['profile'] for p in _channels(text)):
                say('Open the ' + saved['profile'].title() + ' profile to continue this saved preparation.', True)
                return True
            from .prepare_post_http import service
            engine = service(assistant.state, recover_delivery=False)
            key, profile = saved['id'], saved['profile']
            draft = engine.get(key, profile)
            if status:
                report(draft); return True
            if re.search(r'\b(?:stop|cancel)\b', text, re.I):
                report(engine.cancel(key, profile)); return True
            if _release(text):
                return _post(assistant, session_id, engine, draft, text, say, report)
            if re.search(r'\b(?:post|upload|publish|schedule)\b', text, re.I):
                report(draft, 'Your preparation is saved. Posting has not been authorized by this message.'); return True
            if not re.search(r'\b(?:resume|retry|continue)\b', text, re.I):return False
            engine.resume(key, profile)
        else:
            # Carry only this unanswered input request, never the conversation.
            if pending:
                from .assistant_publish_intent import publishing
                if _request(text) or publishing(_positive(text)):
                    pending = {}
                else:
                    selected = selected + [a for a in snapshot.get('attachments', [])
                        if a.get('id') in pending.get('attachment_ids', []) and a not in selected]
                    text = pending['request'] + '\n' + text
                    message_id = pending['message_id']
            from .assistant_sources import literal_locations
            locations, words = literal_locations(text)
            channels = _channels(words)
            profile = channels[0] if len(channels) == 1 else snapshot.get('profile')
            if len(channels) > 1 or profile not in ('cricket', 'gaming'):
                say('Choose Cricket or Gaming for this preparation.', True); return True
            mode = 'highlights' if re.search(r'\bhighlights?\b', words, re.I) else (
                'shorts' if re.search(r'\b(?:shorts?|reels?)\b|शॉर्ट|रील', words, re.I) else 'long')
            if mode == 'shorts' and re.search(r'\b(?:existing|finished|already)\b', words, re.I) and not re.search(r'\b(?:extract|make|generate|create)\b', words, re.I):
                say('This is a finished Short. The Prepare and Post adapter currently extracts Shorts from a source; it has not re-extracted or uploaded your finished Short.', True)
                return True
            if mode == 'highlights' and profile != 'gaming':
                say('Highlights are available for Gaming. Cricket uses a finished video or Shorts.', True); return True
            if re.search(r'\b(?:with|add)\s+(?:captions?|subtitles?|b[ -]?roll|sound design|motion graphics)\b', words, re.I):
                say('That request includes an extra editing step. Finish that edit first, then prepare its finished source here; no part of the request was silently omitted.', True)
                return True
            paths = list(dict.fromkeys([Path(a['path']).resolve() for a in selected if a.get('kind') != 'voice' and a.get('path')] + locations))
            videos = [p for p in paths if p.is_file() and p.suffix.lower() in MEDIA]
            thumbnails = [p for p in paths if p.is_file() and p.suffix.lower() in IMAGES]
            parent_id = None
            engine = None
            if not videos and not locations and mode == 'shorts' and saved.get('profile') == profile and re.search(r'\bsame\b', words, re.I):
                from .prepare_post_http import service
                engine = service(assistant.state, recover_delivery=False)
                parent = engine.get(saved['id'], profile)
                if parent['mode'] == 'long':
                    videos = [Path(parent['source']['path'])]
                    parent_id = parent['id']
            if len(videos) != 1 or mode != 'shorts' and len(thumbnails) != 1:
                assistant._update(session_id, prepare_post_inputs={'request': text, 'message_id': message_id,
                    'profile': profile, 'attachment_ids': [a['id'] for a in selected if a.get('id')]})
                say('Choose one exact video file' + (' and its thumbnail' if mode != 'shorts' else '') + '; a folder alone is not an exact selection.', True)
                return True
            match = re.search(r'\b(\d+|' + '|'.join(NUMBERS) + r')\s+(?:shorts?|reels?)\b', words, re.I)
            count = (int(match[1]) if match and match[1].isdigit() else NUMBERS[match[1].lower()] if match else 5)
            spec = {'profile': profile, 'mode': mode, 'count': count,
                    'video': str(videos[0]), 'thumbnail': str(thumbnails[0]) if thumbnails and mode != 'shorts' else '',
                    'request_id': 'ask-' + session_id + '-' + message_id}
            spec.update(discovery_review=True, discovery_research=True)
            if parent_id:spec['source_preparation'] = parent_id
            if re.search(r'\bprivate(?:ly)?\b', words, re.I):spec['visibility'] = 'private'
            release = _release(words)
            if mode != 'shorts' and 'instagram' in _scope(words, ['youtube']):
                say('Instagram needs a Reel. Prepare Shorts from this source for paired YouTube and Instagram posting.', True); return True
            from .prepare_post_http import service
            if engine is None:engine = service(assistant.state, recover_delivery=False)
            draft = engine.create(spec); key = draft['id']
            saved = {'id': key, 'profile': profile, 'platforms': _scope(words, draft['platforms']),
                     'request': text, 'release': release}
            assistant._update(session_id, prepare_post_bridge=saved, prepare_post_inputs=None, profile=profile)
        assistant._update(session_id, status='running', selected='publish', stage='Preparing saved stages in Prepare and Post.')
        def step(message):
            if assistant._stopped(session_id):engine.cancel(key, profile)
            progress(message)
        with assistant.state.work_lock:
            draft = engine.run(key, profile, step)
        # Resume cannot add permission that was absent from the original request.
        if draft['status'] == 'prepared' and saved.get('release') and not assistant._stopped(session_id):
            return _post(assistant, session_id, engine, draft, saved['request'], say, report)
        report(draft)
    except Exception as error:
        from .user_messages import failure
        issue = failure(error, feature='Prepare and Post')
        assistant._update(session_id, status='needs_review', stage=issue['error'])
        assistant._message(session_id, 'assistant', issue['error'], error=True, error_details=issue.get('error_details', ''), error_code=issue.get('error_code'))
    return True


def _post(assistant, session_id, engine, draft, text, say, report):
    if draft['status'] != 'prepared':
        report(draft, 'Preparation is not complete. Resume its saved stages before posting.'); return True
    from .assistant_preferences import declarations
    from .assistant_publishing_context import schedule_literals
    from .assistant_publish_intent import instruction
    if schedule_literals(instruction(text)):
        say('The exact release date or time needs the Schedule controls in Prepare and Post. Your prepared video and request are saved; no new post was authorized.', True)
        return True
    values = declarations(assistant.root)
    if len(values) != 2:
        say('Choose audience and altered-content declarations in Prepare and Post before posting. Your preparation is saved.', True)
        return True
    platforms = _scope(text, draft['platforms'])
    if any(p not in draft['platforms'] for p in platforms):
        say('That platform is not part of this saved preparation. Open Prepare and Post to review its destinations.', True)
        return True
    action = _release(text)
    if action == 'private' and 'youtube' in platforms and draft.get('visibility') != 'private':
        say('This preparation is not set to Private. Choose Private in Prepare and Post before uploading; no new post was authorized.', True)
        return True
    for platform in platforms:
        engine.post(draft['id'], draft['profile'], platform, values, None if action == 'private' else action)
    report(draft, 'Posting authorized for ' + ' and '.join(platforms) + '. Prepare and Post will show the verified platform results.')
    return True
