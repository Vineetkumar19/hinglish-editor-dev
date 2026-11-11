"""A bounded local-model tool. Account identity and publication intent are checked outside the LLM."""
import re
import time
from pathlib import Path

from hinglish_publish.local_browser import TERMINAL, handle, explicit_handles


def chrome_caption(value):
    # Instagram's Lexical composer removes raw newlines from insertText. Keep word boundaries
    # explicit for this transport; preserve the original formatted metadata elsewhere.
    return ' '.join(value.split())


def upload_intent(text):
    # Model output alone cannot authorize a publication. Drafting, scheduling and negation do not post.
    if re.search(r"\b(?:don['’]?t|do not|not now|never|without|avoid|draft|schedule|mat|nahi|nahin)\b", text, re.I):
        return False
    return bool(re.search(r'\b(upload|publish|post|share|daal|dalo|daalo)\b', text, re.I))


def execute(assistant, session_id, text, selected, snapshot, options, progress):
    bridge = assistant.state.local_browser
    action = options.get('instagram_action', 'inspect')
    if action == 'story':
        raise ValueError('Story uploads are not verified in Instagram desktop. I have not posted a Reel instead. You can share an existing Reel to Your Story in the Instagram mobile app.')
    profile = snapshot.get('profile', 'general')
    requested_profile = options.get('instagram_profile', profile)
    if requested_profile != profile and not re.search(r'\b' + requested_profile + r'\b', text, re.I):
        requested_profile = profile  # Ignore a model-inferred topic; it is not destination authorization.
    destination = bridge.snapshot()['accounts'].get(requested_profile, '')
    explicit = explicit_handles(text)
    requested = options.get('instagram_account', '')
    if explicit:
        if len(set(h.lower() for h in explicit)) != 1:
            raise ValueError('Choose one Instagram username for this upload.')
        destination = handle(explicit[0])
    elif requested:
        proposed = handle(requested)
        if proposed != destination:
            raise ValueError('Confirm the destination by writing @' + proposed + ', or save the account in Publishing Studio → Chrome connection.')
    if not bridge.snapshot()['connected']:
        assistant._message(session_id, 'assistant', 'Connect the Storylens Local Publisher extension once in Chrome. Then this local chat can check accounts and upload Reels without OpenAI. Open Chrome connection for the setup steps.', browser_setup=True)
        assistant._update(session_id, status='needs_review', stage='Connect the local Chrome extension', pending=None)
        return
    video = caption = ''
    if action in ('reel', 'preview'):
        if action == 'preview' and (not re.search(r'\b(preview|draft|prepare|stage)\b', text, re.I) or
                                    re.search(r"\b(?:do not|don['’]?t|never|avoid)\s+(?:prepare|preview|stage|upload)\b", text, re.I)):
            raise ValueError('No video preview was requested. Ask me to prepare a preview when you want the video loaded into Instagram.')
        if action == 'reel' and not upload_intent(text):
            raise ValueError('No publication requested. Write “Upload this video to Instagram @username” when you want it posted.')
        if not destination:
            raise ValueError('Which Instagram account? Include its exact @username, or save a destination for this creator profile in Chrome connection.')
        videos = [a['path'] for a in selected if Path(a['path']).suffix.lower() == '.mp4'] or snapshot.get('last_paths', [])
        if not videos:
            # Reuse a user attachment from this chat, never an LLM-generated filesystem path.
            prior = next((m.get('attachments', []) for m in reversed(snapshot['messages'])
                          if m.get('profile', 'general') == snapshot.get('profile', 'general') and m.get('attachments')), [])
            videos = [a['path'] for a in prior if Path(a['path']).suffix.lower() == '.mp4']
        if not videos:
            from .assistant_publish import choose_any, candidates, excerpt
            if choose_any(text):
                from hinglish_cut.gpu_lock import gpu_lock
                with assistant.state.work_lock, gpu_lock(assistant.root):
                    source, facts = candidates(assistant.state.publisher, snapshot.get('profile', 'general'), 'short')
                    videos = [str(excerpt(assistant.root, source, facts, 'short', progress))]
        if len(videos) != 1:
            raise ValueError('Attach one finished MP4, or finish one edit, then ask me to upload it to Instagram.')
        video = videos[0]
        from hinglish_shorts.source import open_video
        facts = open_video(video)
        if facts.width >= facts.height or facts.duration > 180:
            raise ValueError('This Reel upload tool needs a portrait MP4 up to 3 minutes. Finish a vertical export first.')
        from hinglish_publish.metadata import generate_instagram
        script = '\n'.join(Path(a['path']).read_text('utf-8-sig') for a in selected if Path(a['path']).suffix.lower() == '.txt')
        from hinglish_niche.profiles import Profiles, use
        with assistant.state.work_lock, use(Profiles(assistant.root).context(snapshot.get('profile', 'general'))):
            meta, brain = generate_instagram(assistant.root, video, transcript=script or None, notes=text, progress=progress)
        caption = chrome_caption(meta['instagram_caption'])
        assistant._update(session_id, brain=brain)
    if assistant._stopped(session_id):
        assistant._update(session_id, status='stopped', stage='Stopped before the Chrome task was queued.')
        return
    job = bridge.enqueue(action, destination, video, caption, session_id, authorized=action in ('reel', 'preview'))
    assistant._update(session_id, status='running', browser_job_id=job['id'], stage=job['message'])
    message = ('Uploading the attached video to @' + destination + ' through local Chrome.' if action == 'reel' else
               'Preparing an Instagram preview for @' + destination + '; I will not click Share.' if action == 'preview' else
               'Checking Instagram in your local Chrome profile.')
    assistant._message(session_id, 'assistant', message, browser_task=job['id'])
    monitor(assistant, session_id, job, progress)


def monitor(assistant, session_id, job, progress):
    bridge, action = assistant.state.local_browser, job['action']
    deadline = time.monotonic() + 1200
    while job['status'] not in TERMINAL:
        if assistant._stopped(session_id):
            bridge.cancel(job['id'])
            assistant._update(session_id, status='stopped', stage='Stop requested. A submission already sent to Instagram cannot be recalled.')
            return
        if time.monotonic() > deadline:
            bridge.cancel(job['id'])
            raise ValueError('Chrome did not finish in time. Check the browser before uploading this video again.')
        progress(bridge.get(job['id'])['message'])
        time.sleep(.5)
        job = bridge.get(job['id'])
    if job['status'] == 'published':
        assistant._message(session_id, 'assistant', 'Published to @' + job['account'] + '.', browser_url=job['url'])
        assistant._update(session_id, status='complete', stage='Instagram publication verified')
    elif job['status'] == 'complete':
        assistant._message(session_id, 'assistant', job['message'])
        assistant._update(session_id, status='complete', stage=(
            'Instagram preview ready; nothing published' if action == 'preview' else 'Instagram account checked'))
    else:
        from .user_messages import problem
        raw=job.get('message') or 'Check the open Chrome tab before trying again.'
        assistant._message(session_id, 'assistant', raw,error=True,
                           browser_setup=not bool(re.search(r'login|sign.in|verification',raw,re.I)))
        assistant._update(session_id, status='needs_review', stage=problem(raw)['message'])
