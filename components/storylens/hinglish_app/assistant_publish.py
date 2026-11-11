"""Chat-owned YouTube preparation, editable review and explicit private uploads.

Only user attachments and the configured source library can supply paths. The
model writes copy; it never chooses credentials, visibility or authorization.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import uuid


def choose_any(text):
    return bool(re.search(r'\b(any|random|choose|pick|whatever)\b', text, re.I))


def instagram_waiting_message(review):
    pending=[r for r in review.get('instagram_rows',[]) if r.get('status')!='published']
    if not pending:return 'Checking the saved Instagram publication receipts.'
    immediate=sum(bool(r.get('immediate') and not r.get('publish_at')) for r in pending)
    if pending and immediate==len(pending):
        return 'Instagram uploads are ready now. Chrome will post them one at a time; each post is confirmed after verification.'
    if immediate:
        return 'Posting the immediate Instagram Reels as Chrome becomes ready. The remaining Reels keep their scheduled times.'
    return 'Instagram Reels are scheduled locally; waiting for their saved release times.'


def request(text, profile='general'):
    from .assistant_publish_intent import instruction
    text = instruction(text).casefold()
    text = re.sub(r'\byt\b','youtube',text)
    if not re.search(r'\byou\s*tube\b', text):
        return None
    if not re.search(r'\b(upload|post|publish|prepare|draft)\b', text):
        return None
    polite_action = bool(re.match(r'^(?:please\s+)?(?:can|could|would|will) you\s+(?:please\s+)?(?:upload|post|publish|prepare)\b', text))
    if re.search(r'\b(how|why|can i|explain|do not|don.t|never|avoid|schedule)\b', text) or ('?' in text and not polite_action):
        return None
    both = bool(re.search(r'\bboth\s+(?:of\s+)?(?:my\s+)?(?:youtube\s+)?channels?\b|\b(?:two|2)\s+(?:youtube\s+)?channels?\b|\bboth\s+(?:my\s+)?cricket\b.*\bgaming\b', text))
    targets = ['cricket', 'gaming'] if both else [
        'gaming' if re.search(r'\bgaming\b', text) else 'cricket' if re.search(r'\bcricket\b', text) else profile]
    short = bool(re.search(r'\bshorts?\b(?![ -]form\b)', text))
    long = bool(re.search(r'\blong(?:[ -]?form)?\b|\bshort[ -]form\b', text))
    kinds = ['long', 'short'] if long and short else ['short' if short else 'long']
    # Exact finished exports use the draft pipeline directly; an unrelated
    # editor plan or old last_paths must never replace the supplied file.
    if not (both or choose_any(text) or re.search(r'\bprivate\b', text) or len(kinds) > 1):
        from .assistant_artifacts import editing_requested
        from .assistant_publish_intent import platforms
        if editing_requested(text) or platforms(text)!=['youtube']:return None
        return {'profiles':targets,'kinds':[('short' if short else 'long') if (short or long or re.search(r'\bvideos?\b',text)) else 'auto'],
                'any':False,'finished_draft':True,'upload_requested':False}
    if re.search(r'\bpublic\b', text):
        return {'question': 'This chat upload flow currently supports private YouTube uploads. Use Publishing Studio for public publishing.'}
    return {'profiles': targets, 'kinds': kinds, 'any': choose_any(text),
            'upload_requested': bool(re.search(r'\b(upload|post|publish)\b', text)) and not re.search(r'\b(draft|prepare)\b', text),
            'visibility': 'private'}


def library(publisher, profile):
    root = publisher.settings(profile=profile).get('source_root') or publisher.settings().get('source_root')
    found = list(publisher.scan(profile))
    if root:
        base = Path(root).resolve()
        if base.is_dir():
            for number, path in enumerate(sorted(base.rglob('*.mp4'))):
                if number >= 2000:
                    break
                if path.is_file() and path.resolve().is_relative_to(base) and path.stat().st_size and time.time() - path.stat().st_mtime > 10:
                    found.append({'video': str(path.resolve()), 'thumbnail': '', 'name': path.stem})
    return list({item['video']: item for item in found}.values())


def candidates(publisher, profile, kind, attachments=(), used=None):
    from hinglish_shorts.source import open_video
    used = set() if used is None else used
    paths = [{'video': a['path'], 'name': a['name'], 'thumbnail': ''} for a in attachments
             if Path(a['path']).suffix.lower() == '.mp4' and a.get('kind') != 'voice']
    paths = paths or library(publisher, profile)
    # Prefer final exports. No path supplied by the planner is accepted here.
    prior = {j.get('source_video') for j in publisher.store.list()
             if j.get('profile', 'general') == profile and j.get('remote', {}).get('id')}
    paths.sort(key=lambda p: (p['video'] in prior, ('short' in p['video'].casefold()) != (kind == 'short'),
                              'final' not in p['video'].casefold(), p['name'].casefold(), p['video'].casefold()))
    for item in paths:
        if item['video'] in used:
            continue
        try:
            facts = open_video(item['video'])
        except (ValueError, OSError):
            continue
        if facts.duration >= (2 if kind == 'short' else 30) and (facts.height > facts.width) == (kind == 'short'):
            return item, facts
    raise ValueError('I need a ' + ('portrait Short' if kind == 'short' else 'landscape video') +
                     '. Attach one, or choose your source video folder in Publishing Studio. I can choose a file when you say “any video”.')


def excerpt(root, source, facts, kind, progress):
    from hinglish_shorts.source import quick_fingerprint, open_video
    from imageio_ffmpeg import get_ffmpeg_exe
    seconds = min(facts.duration, 15 if kind == 'short' else 90)
    key = hashlib.sha256((quick_fingerprint(source['video']) + ':' + kind + ':' + str(seconds)).encode()).hexdigest()[:24]
    folder = Path(root) / 'cache/publisher/chat-media'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (key + '.mp4')
    if target.exists():
        return target
    if facts.duration <= seconds + .01:
        import shutil
        shutil.copy2(source['video'], target)
        for suffix in ('.txt', '.publish.json'):
            sidecar = Path(source['video']).with_suffix(suffix)
            if sidecar.is_file():
                shutil.copy2(sidecar, target.with_suffix(suffix))
        return target
    partial = target.with_suffix('.partial.mp4')
    progress('Making a ' + str(round(seconds)) + '-second ' + kind + ' excerpt from ' + source['name'])
    size = '1080:1920' if kind == 'short' else '1920:1080'
    subprocess.run([get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', source['video'], '-t', str(seconds), '-map', '0:v:0', '-map', '0:a:0',
        '-vf', 'scale=' + size + ':force_original_aspect_ratio=decrease,pad=' + size + ':(ow-iw)/2:(oh-ih)/2',
        '-r', '30', '-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '25', '-b:v', '0',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', str(partial)], check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert abs(open_video(partial).duration - seconds) < .2
    partial.replace(target)
    return target


def transcripts(root, videos, progress, *, gpu_locked=False, cancelled=None):
    from .publishing_speech import transcribe
    return transcribe(root, videos, progress, gpu_locked=gpu_locked, cancelled=cancelled)


def _transcripts_in_process(root, videos, progress):
    """Load ASR once per batch. Upload descriptions do not need word alignment."""
    if all(Path(v).with_suffix('.txt').is_file() or Path(v).with_suffix('.publish.json').is_file() for v in videos):return
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.media import read_audio
    from hinglish_cut.model_preferences import preferred_device, release_ollama
    from hinglish_cut.recognition_quality import checked_transcript,InvalidRecognitionError
    from hinglish_semantic.core import SemanticSettings
    from hinglish_semantic.speech import speech_engine
    from hinglish_shorts.source import open_video
    release_ollama(root)
    engine = None
    try:
        for video in dict.fromkeys(videos):
            txt = video.with_suffix('.txt')
            if txt.is_file() or video.with_suffix('.publish.json').is_file():
                continue
            cache = Path(root) / 'cache/publisher/chat-audio'
            cache.mkdir(parents=True, exist_ok=True)
            wav = cache / (hashlib.sha256(str(video).encode()).hexdigest() + '.wav')
            if not wav.exists():
                subprocess.run([get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                    '-i', str(video), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if engine is None:
                config = json.loads((Path(root) / 'config.phase2.json').read_text('utf-8-sig'))
                config.update(device=preferred_device(root), speech_backend='swift', matching_backend='word_coverage')
                engine = speech_engine(SemanticSettings(**config), root)
            seconds = open_video(video).duration
            parts = []
            for start in range(0, int(seconds) + 1, 20):
                if start >= seconds:
                    break
                progress('Reading the spoken content: ' + str(start) + '/' + str(round(seconds)) + 's')
                try:
                    text = engine.recognize(read_audio(wav, start, min(seconds, start + 20)))
                    text=checked_transcript(text)
                except InvalidRecognitionError:
                    progress('Skipping an audio section without usable speech.')
                    continue
                if text.strip():parts.append(text)
            if not parts:
                raise InvalidRecognitionError('This Reel has no usable speech for an accurate title and hashtags. Choose another saved Reel or supply its subject.')
            txt.write_text(' '.join(parts), 'utf-8')
    finally:
        if engine is not None:
            engine.close()


def prepare(assistant, session_id, text, selected, spec, progress):
    if spec.get('finished_draft'):
        from .assistant_finished_upload import prepare as finished
        return finished(assistant,session_id,text,selected,spec,progress)
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_shorts.source import open_video
    from hinglish_publish.store import fingerprint
    from hinglish_publish.metadata import generate_youtube
    publisher = assistant.state.publisher
    accounts = {p: publisher.accounts(p)['youtube'] for p in spec['profiles']}
    if any(not a['connected'] for a in accounts.values()):
        raise ValueError('Connect the requested YouTube channel in Publishing Studio first.')
    if len({a['id'] for a in accounts.values()}) != len(accounts):
        raise ValueError('Both profiles point to the same channel. Connect a different channel for each profile first.')
    if not any(Path(a['path']).suffix.lower() == '.mp4' for a in selected) and not spec['any']:
        raise ValueError('Attach the video, or say “choose any video from my source folder”.')
    assistant._update(session_id, status='running', selected='publish', publishing_review=None)
    chosen, used = [], set()
    with assistant.state.work_lock, gpu_lock(assistant.root):
        for profile in spec['profiles']:
            for kind in spec['kinds']:
                try:
                    source, facts = candidates(publisher, profile, kind, selected, used)
                except ValueError:
                    if profile == spec['profiles'][0]:
                        raise
                    source, facts = candidates(publisher, profile, kind, selected)
                used.add(source['video'])
                video = excerpt(assistant.root, source, facts, kind, progress)
                chosen.append((profile, kind, source, video))
        transcripts(assistant.root, [c[3] for c in chosen], progress,
                    gpu_locked=True, cancelled=lambda: assistant._stopped(session_id))
        ids, rows = [], []
        for profile, kind, source, video in chosen:
            if assistant._stopped(session_id):
                assistant._update(session_id, status='stopped', stage='Stopped before any upload.')
                return
            meta, brain = generate_youtube(assistant.root, video, profile=profile, notes=text, progress=progress)
            facts = open_video(video)
            item = {'platform': 'youtube', 'profile': profile, 'kind': kind, 'video': str(video.resolve()),
                    'source_video': source['video'], 'metadata': meta, 'brain': brain, 'visibility': 'private',
                    'thumbnail': '', 'thumbnail_fingerprint': '', 'fingerprint': fingerprint(video),
                    'duration': facts.duration, 'width': facts.width, 'height': facts.height, 'video_url': ''}
            job_id = publisher.store.add_batch([item])[0]
            job = publisher.store.get(job_id)
            ids.append(job_id)
            rows.append({'id': job_id, 'channel': accounts[profile]['name'], 'profile': profile, 'kind': kind,
                         'source': source['name'], 'duration': facts.duration, 'metadata': job['metadata'],
                         'status': job['status'], 'url': job.get('remote', {}).get('url', '')})
    token = uuid.uuid4().hex
    review = {'id': token, 'ids': ids, 'accounts': accounts, 'rows': rows,
              'upload_requested': spec['upload_requested'], 'visibility': 'private', 'state': 'review'}
    from .assistant_preferences import apply
    apply(assistant.root,review)
    if all(row['url'] and row['status'] == 'uploaded_private' for row in rows):
        review['state'] = 'complete'
        assistant._update(session_id, publishing_review=review, status='complete', stage='Existing private uploads found; no duplicate uploads.')
        assistant._message(session_id, 'assistant', 'These videos already have verified private upload receipts on the requested channels. '
                           'I reused the results below instead of uploading duplicates.',
                           publish_results=[{'channel': row['channel'], 'kind': row['kind'], 'title': row['metadata']['title'],
                                             'url': row['url'], 'visibility': 'private'} for row in rows])
        return
    assistant._update(session_id, publishing_review=review, status='needs_review',
                      stage='Review the selected videos and copy here; nothing new has been uploaded.')
    assistant._message(session_id, 'assistant',
        'I chose the videos and prepared private YouTube uploads. Check the titles and descriptions below. '+
        ('Your saved YouTube settings are applied automatically. ' if review.get('declaration_defaults_saved') else
         'Choose the audience and synthetic-media disclosure to upload from this chat. ')+
        'Nothing is posted while this review is open.', publishing_review=review)


def confirmation(text, review, root=None, *, execution=False):
    """A typed reply can provide the same explicit declarations as the chat form."""
    if not review or review['state'] not in ('review','needs_review') or re.search(r'\b(how|why|cancel)\b|\?', text, re.I):
        return None
    if execution:
        # "Do not create clips/schedule" restricts an explicit upload-now
        # request; it does not revoke it. Actual publication refusals remain
        # authoritative, including contradictory requests.
        from .assistant_publish_intent import instruction,positive
        value=instruction(text)
        if re.search(r'\b(?:do not|don.t|never)\b[^.!?\n]{0,100}\b(?:upload|post|publish)\b',value,re.I):return None
        if re.search(r'\b(?:do not|don.t|never)\b',value,re.I) and not re.search(r'\b(?:upload|post|publish)\b',positive(value),re.I):return None
    elif re.search(r'\b(?:do not|don.t|never)\b',text,re.I):
        return None
    if not review.get('upload_requested') and not re.search(r'\b(upload|post|publish)\b', text, re.I):
        return None
    kids = False if re.search(r'\bnot (?:made )?for kids\b', text, re.I) else True if re.search(r'\bmade for kids\b', text, re.I) else None
    synthetic = False if re.search(r'\b(?:no (?:ai|synthetic)(?: media)?|not ai[ -]generated)\b', text, re.I) else True if re.search(r'\b(?:contains synthetic media|ai[ -]generated)\b', text, re.I) else None
    resume=bool(re.match(r'^\s*(?:please\s+)?(?:resume|retry|continue|finish|complete|compelte)\b',text,re.I) and
        not re.search(r'\d|\b(?:edit\w*|extract|create|make|new|another|other|change|instead|different|tomorrow|today)\b',text,re.I))
    if resume and review['state']=='needs_review' and review.get('declarations_confirmed') is True:
        if kids is None:kids=review.get('made_for_kids')
        if synthetic is None:synthetic=review.get('synthetic_media')
    if kids is None or synthetic is None:
        from .assistant_preferences import declarations
        approval=bool(re.fullmatch(r'\s*(?:yes|confirm|approved?|go ahead|proceed|start)'
            r'(?:\s+(?:this|these|the|uploads?|schedules?|batch|please|it|them))*[.! ]*',text,re.I))
        # Saved declarations are preferences, not permission to treat a new
        # platform/date request (or ordinary chat) as confirmation of old work.
        defaults=declarations(root) if root and (execution or approval or resume) else {}
        if kids is None:kids=defaults.get('made_for_kids')
        if synthetic is None:synthetic=defaults.get('synthetic_media')
    if kids is None or synthetic is None:return None
    return {'review': review['id'], 'made_for_kids': kids, 'synthetic_media': synthetic}


def start(assistant, payload, *, internal=False):
    from .assistant import ACTIVE
    from hinglish_publish.metadata import validate
    import threading
    session_id = payload['session']
    from .assistant_preferences import declarations
    payload={**declarations(assistant.root),**payload}
    with assistant.lock:
        session = assistant._get(session_id)
        review = session.get('publishing_review')
        if not review or review['id'] != payload.get('review'):
            raise ValueError('This upload review is unavailable. Prepare the request again.')
        checkpoint=session.get('edit_publish_checkpoint') or {}
        edit_folder=(checkpoint.get('result') or {}).get('folder')
        if edit_folder and review.get('edit_result_folder')!=str(Path(edit_folder).resolve()):
            raise ValueError('This review belongs to an older batch. Ask Storylens to upload these new Shorts to resume the saved edit; the old videos were not changed.')
        if review['state'] not in ('review','needs_review'):
            return assistant.snapshot(session_id)  # Duplicate button presses never upload twice.
        if session['status'] in ACTIVE and not internal:
            raise ValueError('Wait for the current request to finish.')
        if type(payload.get('made_for_kids')) is not bool or type(payload.get('synthetic_media')) is not bool:
            raise ValueError('Choose the audience and realistic synthetic-media disclosure for these videos.')
        from .assistant_schedule import ready
        from .assistant_upload_recovery import present,retryable_rejection
        review=present(assistant,session)
        if review['state']=='needs_review' and not review['retryable']:
            raise ValueError('An upload has an unverified outcome. Check its saved YouTube result before retrying; no duplicate upload was sent.')
        ready(assistant,review)
        caption_edits=payload.get('instagram_captions',{})
        reel_ids={r['id'] for r in review.get('instagram_rows',[])}
        if not isinstance(caption_edits,dict) or set(caption_edits)-reel_ids:
            raise ValueError('Only Instagram captions in this review can be edited.')
        for row in review.get('instagram_rows',[]):
            if row['id'] in caption_edits:
                caption=caption_edits[row['id']]
                if not isinstance(caption,str) or len(caption)>2200:raise ValueError('Instagram caption must be text under 2,200 characters; it may be empty.')
                if row.get('browser_job_id') and caption!=row['caption']:raise ValueError('This Reel is already queued; its caption cannot be silently replaced.')
                row['caption']=caption
        edits = payload.get('metadata', {})
        if not isinstance(edits, dict) or set(edits) - set(review['ids']):
            raise ValueError('Only the videos in this review can be uploaded.')
        for job_id in review['ids']:
            job = assistant.state.publisher.store.get(job_id)
            current = assistant.state.publisher.accounts(job['profile'])['youtube']
            if current['id'] != review['accounts'][job['profile']]['id']:
                raise ValueError('The connected channel changed. Prepare a fresh review.')
            if job['visibility'] != 'private' or job['platform'] != 'youtube':
                raise ValueError('The reviewed private upload changed. Prepare it again.')
            allowed_status=('uploaded_private','scheduled') if review.get('schedule') else ('uploaded_private',)
            already_public=any(r['id']==job_id and r.get('immediate') for r in review['rows']) and job['status']=='published' and job.get('remote',{}).get('publication_verified_at')
            if job.get('remote') and not already_public and (job['status'] not in allowed_status or job['remote'].get('privacy') != 'private'):
                raise ValueError('An earlier upload needs verification. Check its saved YouTube receipt; it will not be uploaded again.')
            if job.get('remote') and job.get('account_id')!=current['id']:
                raise ValueError('The saved upload belongs to a different YouTube channel. No upload or schedule was sent.')
            if not job.get('remote'):
                if job['status'] not in ('draft','blocked') and not retryable_rejection(session,review,job):
                    raise ValueError('This upload has already been attempted. Check the saved result before trying again.')
                if job['status']=='blocked' and not retryable_rejection(session,review,job):
                    raise ValueError('The blocked upload needs verification before retrying.')
                if job['status']=='needs_review':
                    assistant.state.publisher.store.change(job_id,expected_status=('needs_review',),status='blocked',
                        upload_failure={'phase':'initializing','safe_retry':True,'reason':'legacy_initial_rejection'},
                        error='The previous attempt was rejected before transferring video bytes; retry explicitly requested.')
                if job_id in edits:
                    metadata = validate({**job['metadata'], **edits[job_id]})
                    assistant.state.publisher.edit({'id': job_id, 'metadata': metadata})
                    for row in review['rows']:
                        if row['id'] == job_id:
                            row['metadata'] = metadata
        review['request_message_id']=session.get('active_request_message_id') or review.get('request_message_id')
        review['state'] = 'uploading'
        review.update(made_for_kids=payload['made_for_kids'],synthetic_media=payload['synthetic_media'],declarations_confirmed=True)
        new_uploads=any(not assistant.state.publisher.store.get(key).get('remote') for key in review['ids'])
        session.update(status='running', stop=False, stage='Checking YouTube without uploading.' if review.get('youtube_check_only') else
                       'Uploading the reviewed videos privately.' if new_uploads else
                       'Verifying saved uploads and applying the reviewed release dates.', publishing_review=review)
        assistant._save(session)
        from .assistant_pipeline import authorized
        authorized(assistant,session_id,review)
    threading.Thread(target=run, args=(assistant, session_id, review, payload['made_for_kids'], payload['synthetic_media']), daemon=True).start()
    return assistant.snapshot(session_id)


def run(assistant, session_id, review, made_for_kids, synthetic_media):
    from hinglish_publish.worker_lock import acquire
    publisher = assistant.state.publisher
    results = []
    try:
        # Finish model copy repairs before freezing the dispatch intent. Once
        # frozen, a retry cannot silently change any account, file, copy or slot.
        from .pipeline_ledger import freeze
        from .assistant_copy_review import ensure as ensure_copy
        for job_id in review['ids']:
            job=publisher.store.get(job_id)
            if not job.get('remote'):
                ensure_copy(assistant,session_id,review,job)
        freeze(assistant,session_id,review)
        assistant._update(session_id,publishing_review=review)
        if review.get('youtube_check_only'):
            from .assistant_youtube_check import run as check_youtube
            check_youtube(assistant,session_id,review)
        if any(r.get('status')!='published' for r in review.get('instagram_rows',[])):
            from .assistant_distribution import arm
            arm(assistant,session_id,review)
            remaining=[r for r in review['instagram_rows'] if r.get('status')!='published']
            immediate=sum(bool(r.get('immediate')) for r in remaining)
            count=len(remaining)
            assistant._message(session_id,'assistant',
                (f'Posting {immediate} video'+('s' if immediate!=1 else '')+' to Instagram now.' if immediate else
                 f'{count} Instagram video'+('s' if count!=1 else '')+' scheduled locally. Keep Storylens and Chrome running until posting finishes.'))
        if not review['ids'] or review.get('youtube_check_only'):
            review['state']='queued'
            from .assistant_pipeline import change
            change(assistant,session_id,phase='waiting_instagram')
            assistant._update(session_id,publishing_review=review,status='complete',
                stage=('YouTube checked without uploading. ' if review.get('youtube_check_only') else '')+
                instagram_waiting_message(review))
            return
        worker = acquire(assistant.root)
        try:
            for job_id in review['ids']:
                if assistant._stopped(session_id):
                    break
                job = publisher.store.get(job_id)
                if not job.get('remote', {}).get('id'):
                    from hinglish_publish.store import fingerprint
                    if fingerprint(job['video']) != job['fingerprint']:
                        raise ValueError('The reviewed video changed.')
                    publisher.authorize({'ids': [job_id], 'authorize': True, 'made_for_kids': made_for_kids,
                                         'synthetic_media': synthetic_media})
                    publisher.store.change(job_id, expected_status=('ready',), status='uploading',
                        **({} if review.get('schedule') else {'due':time.time()}))
                    job = publisher.store.get(job_id)
                    if job['account_id'] != review['accounts'][job['profile']]['id']:
                        raise ValueError('The reviewed channel changed.')
                    assistant._progress(session_id, 'Uploading ' + job['kind'] + ' to ' + review['accounts'][job['profile']]['name'])
                    try:
                        remote, status = publisher.providers['youtube'](assistant.root, publisher.settings(profile=job['profile'])).publish(
                            job, lambda remote: publisher.store.change(job_id, remote=remote))
                        if status != 'uploaded_private' or remote.get('privacy') != 'private':
                            raise ValueError('YouTube has not confirmed private visibility.')
                        publisher.store.change(job_id, status=status, remote=remote, error='',upload_failure={})
                    except Exception as error:
                        failure=getattr(error,'failure',{})
                        known_rejection=failure.get('phase')=='initializing' and failure.get('safe_retry') is True
                        publisher.store.change(job_id, status='blocked' if known_rejection else 'needs_review',
                            upload_failure=failure or {'phase':'unknown','safe_retry':False},error=str(error) if known_rejection else
                            'Check YouTube before retrying; the saved remote ID is preserved.')
                        raise
                    job = publisher.store.get(job_id)
                results.append({'channel': review['accounts'][job['profile']]['name'], 'kind': job['kind'],
                                'title': job['metadata']['title'], 'url': job['remote']['url'], 'visibility': 'private'})
        finally:
            worker.close()
        if review.get('schedule'):
            if len(results)!=len(review['ids']):raise ValueError('The batch stopped before every export was uploaded; no schedules were started.')
            from .assistant_schedule import run as schedule_batch
            schedule_batch(assistant,session_id,review)
            return
        review['state'] = 'complete' if len(results) == len(review['ids']) else 'stopped'
        # Expose the terminal state only together with its durable chat receipt.
        with assistant.lock:
            assistant._update(session_id, publishing_review=review, status=review['state'],
                              stage='Private uploads complete.' if review['state'] == 'complete' else 'Stopped. Finished uploads are kept.')
            assistant._message(session_id, 'assistant', str(len(results)) + ' private YouTube uploads completed.', publish_results=results)
    except Exception as error:
        review['state'] = 'needs_review'
        from .user_messages import problem
        issue=problem(error)
        detail=issue['message']
        scheduling=bool(review.get('schedule') and len(results)==len(review['ids']))
        uploaded_count=sum(bool(publisher.store.get(key).get('remote',{}).get('id')) for key in review['ids'])
        message=('Scheduling stopped: '+detail.rstrip('.')+'. '
            f'All {len(results)} videos have saved private upload receipts; '
            f'{len(review.get("schedule_results",[]))} requested release dates are verified. '
            'Retry scheduling to reuse these same videos. No new upload is needed.') if scheduling else (
            'Publishing stopped: '+detail.rstrip('.')+'. '+f'{uploaded_count} of {len(review["ids"])} uploads have saved receipts. '
            'Completed uploads are kept. Resume will skip those videos; uncertain outcomes require verification.')
        from .assistant_schedule import UnavailableUploadError
        if isinstance(error,UnavailableUploadError):
            message=('Scheduling stopped: '+detail+' Check this exact video in YouTube Studio before deciding whether it needs replacing. No automatic re-upload or schedule was sent.')
        instagram_only=bool(not review['ids'] and review.get('instagram_rows'))
        if instagram_only:
            from .user_messages import instagram_failure
            message=instagram_failure(review,detail)
        with assistant.lock:
            assistant._update(session_id, publishing_review=review, status='needs_review', stage='Instagram needs attention; existing posts are kept.' if instagram_only else 'Scheduling needs attention; existing uploads are kept.' if scheduling else 'Upload needs review; no automatic retry.')
            assistant._message(session_id, 'assistant', message,
                               publish_results=review.get('schedule_results',results),error=True,
                               error_code=issue['code'],error_details=issue['details'])
            from .assistant_pipeline import failed
            failed(assistant,session_id,error)
