"""Checkpointed Prepare/Post orchestration. No inference or upload on import.

Source bytes stay in place. Every expensive stage commits independently. The
existing Publisher remains the sole owner of queue authorization and transport.
"""
import hashlib
import copy
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .store import IST, fingerprint
from hinglish_app.user_messages import failure

VIDEO = {'.mp4', '.mov', '.mkv', '.webm', '.mxf', '.avi'}
IMAGE = {'.png', '.jpg', '.jpeg', '.webp'}


def candidates(value, query=''):
    path = Path(str(value).strip().strip('"')).resolve()
    if path.is_file():
        paths = [path]
    elif path.is_dir():
        # Deliberately bounded to this folder; no whole-drive recursive search.
        paths = sorted((p for p in path.iterdir() if p.is_file()), key=lambda p: p.name.casefold())
    else:
        raise ValueError('Check the video path or choose an existing folder.')
    paths = [p for p in paths if p.suffix.lower() in VIDEO and query.casefold() in p.stem.casefold()]
    return {'candidates': [{'path': str(p), 'name': p.name, 'bytes': p.stat().st_size} for p in paths[:200]],
            'truncated': len(paths) > 200, 'selection_required': True}


def file_identity(value, extensions=None):
    path = Path(str(value).strip().strip('"')).resolve()
    if not path.is_file() or extensions and path.suffix.lower() not in extensions:
        raise ValueError('Choose the exact supported file from the candidates; a folder cannot be prepared.')
    before = path.stat()
    if before.st_size <= 0:
        raise ValueError('The selected file is empty. Choose a finished file.')
    digest = fingerprint(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('The selected file is changing. Wait for its export to finish, then select it again.')
    return {'path': str(path), 'sha256': digest, 'bytes': after.st_size, 'mtime_ns': after.st_mtime_ns}


def verify_identity(saved):
    if saved and file_identity(saved['path']) != saved:
        raise ValueError('The selected file changed after preparation. Choose it again in a new preparation; saved results are kept.')


def text_chunks(text, limit=6000):
    """Keep source excerpts bounded; never silently truncate the full source."""
    chunks, words = [], []
    length = 0
    for word in text.split():
        if words and length + len(word) + 1 > limit:
            chunks.append(' '.join(words))
            words, length = [], 0
        words.append(word)
        length += len(word) + 1
    if words:
        chunks.append(' '.join(words))
    return chunks


def buffer_status(jobs, profile, now=None):
    now = time.time() if now is None else now
    days = {datetime.fromtimestamp(j['due'], IST).date().isoformat() for j in jobs
            if j.get('profile') == profile and j.get('platform') == 'instagram' and j.get('kind') == 'short'
            and j.get('due', 0) > now and j.get('status') in ('ready', 'scheduled')}
    return {'minimum_days': 5, 'days': len(days), 'shortfall': max(0, 5 - len(days)),
            'dates': sorted(days), 'basis': 'authorized local schedules; not remote publication receipts'}


class Stopped(Exception):
    pass


class PreparePost:
    def __init__(self, publisher, runtime=None):
        self.publisher = publisher
        self.root = Path(publisher.root)
        self.folder = self.root / 'output' / 'publisher-prepare-post' / 'preparations'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.db_path = self.folder / 'preparations.sqlite3'
        self.lock = threading.RLock()
        self.runtime = runtime
        self.delivery = None
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS preparations(id TEXT PRIMARY KEY, request_key TEXT UNIQUE, data TEXT NOT NULL)')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _save(self, draft):
        draft['updated'] = time.time()
        with self.db() as db:
            db.execute('UPDATE preparations SET data=? WHERE id=?', (json.dumps(draft, ensure_ascii=False), draft['id']))

    def get(self, key, profile):
        with self.db() as db:
            row = db.execute('SELECT data FROM preparations WHERE id=?', (key,)).fetchone()
        if not row:
            raise ValueError('Select an existing preparation.')
        draft = json.loads(row[0])
        if draft['profile'] != profile:
            raise ValueError('Select this preparation’s original channel profile.')
        return draft

    def list(self, profile):
        with self.db() as db:
            drafts = [json.loads(row[0]) for row in db.execute('SELECT data FROM preparations ORDER BY rowid DESC')]
        result = []
        for draft in drafts:
            if draft['profile'] != profile:
                continue
            from .description_policy import apply as description_policy
            for name, copy_stage in draft['stages'].items():
                if name.startswith('copy:youtube:') and not draft['jobs_by_platform'].get('youtube'):
                    try:
                        copy_stage['metadata'] = description_policy(self.root, profile, copy_stage['metadata'])
                    except ValueError as error:
                        draft['errors']['description-links'] = failure(error, feature='YouTube description')
            if draft['status'] in ('working', 'queued') and not self._alive(draft.get('owner')):
                draft.update(status='interrupted', message='Storylens stopped during this stage. Resume the unfinished stage; completed work is saved.')
            draft['jobs'] = [self.publisher.store.get(key) for ids in draft['jobs_by_platform'].values() for key in ids]
            result.append(draft)
        return result

    @staticmethod
    def _alive(owner):
        if not owner:
            return False
        import psutil
        try:
            return abs(psutil.Process(owner['pid']).create_time() - owner['started']) < .01
        except (psutil.Error, KeyError):
            return False

    def create(self, payload):
        profile, mode = payload.get('profile'), payload.get('mode', 'long')
        if profile not in ('cricket', 'gaming'):
            raise ValueError('Choose Cricket or Gaming.')
        if mode not in ('long', 'shorts', 'highlights') or mode == 'highlights' and profile != 'gaming':
            raise ValueError('Choose Long, Shorts, or Gaming Highlights.')
        count = payload.get('count', 5) if mode == 'shorts' else 1
        if type(count) is not int or not 1 <= count <= 40:
            raise ValueError('Choose between 1 and 40 Shorts.')
        platforms = ['youtube', 'instagram'] if mode == 'shorts' else ['youtube']
        request_id = str(payload.get('request_id', ''))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', request_id):
            raise ValueError('Refresh this page to create a new preparation request.')
        # Fast idempotency lookup happens before hashing a large file a second time.
        key = profile + ':' + request_id
        intent = {k: payload.get(k) for k in ('profile', 'mode', 'count', 'video', 'thumbnail', 'visibility', 'minutes')}
        # Opt in only on new requests. Old workflows retain their saved intent.
        for flag in ('discovery_review', 'discovery_research'):
            if flag in payload:
                if type(payload[flag]) is not bool:
                    raise ValueError('Choose whether to include the SEO and thumbnail review.')
                intent[flag] = payload[flag]
        if payload.get('source_preparation'):
            intent['source_preparation'] = payload['source_preparation']
        with self.db() as db:
            existing = db.execute('SELECT data FROM preparations WHERE request_key=?', (key,)).fetchone()
        if existing:
            draft = json.loads(existing[0])
            if draft['intent'] != intent:
                raise ValueError('This request already belongs to another selection. Start a new preparation.')
            return draft
        source = file_identity(payload.get('video', ''), VIDEO)
        thumbnail = file_identity(payload['thumbnail'], IMAGE) if mode != 'shorts' and payload.get('thumbnail') else None
        accounts = self.publisher.accounts(profile)
        bindings = {p: {'id': accounts.get(p, {}).get('id', ''), 'transport': 'browser' if p == 'instagram' else 'oauth'} for p in platforms}
        visibility = payload.get('visibility') or self.publisher.settings(profile=profile).get('visibility', 'private')
        if visibility not in ('private', 'public'):
            raise ValueError('Choose Schedule / private or Public explicitly.')
        minutes = payload.get('minutes', 15)
        if type(minutes) is not int or not 1 <= minutes <= 60:
            raise ValueError('Choose a highlights length between 1 and 60 minutes.')
        draft = {'id': uuid.uuid4().hex, 'version': 1, 'profile': profile, 'mode': mode, 'count': count,
                 'minutes': minutes, 'platforms': platforms, 'source': source, 'thumbnail': thumbnail,
                 'bindings': bindings, 'visibility': visibility, 'intent': intent, 'stages': {}, 'errors': {},
                 'status': 'saved', 'message': 'Selection saved. Ready to prepare.', 'created': time.time(),
                 'updated': time.time(), 'jobs_by_platform': {}, 'slots': [], 'cancel_requested': False}
        draft.update({flag: payload.get(flag) is True for flag in ('discovery_review', 'discovery_research')})
        if payload.get('source_preparation'):
            parent = self.get(payload['source_preparation'], profile)
            if mode != 'shorts':
                raise ValueError('Choose a saved video on this channel for these Shorts.')
            if parent['mode'] == 'long' and parent['source'] == source and all(stage in parent['stages'] for stage in ('inspect', 'speech')):
                draft['stages'] = {stage: copy.deepcopy(parent['stages'][stage]) for stage in ('inspect', 'speech')}
                draft['reused_speech_from'] = parent['id']
            elif profile == 'gaming' and parent['mode'] == 'highlights' and parent['stages'].get('highlights', {}).get('video') == source:
                output = parent['stages']['highlights']
                draft['stages']['inspect'] = {k: output[k] for k in ('duration', 'width', 'height')}
                draft['source_highlights_from'] = parent['id']
                # The finished highlight has its own timebase. Transcribe that
                # short output; original stream word times must not be copied.
            else:
                raise ValueError('Choose this channel’s saved Long video or finished Highlights for these Shorts.')
        with self.db() as db:
            try:
                db.execute('INSERT INTO preparations VALUES(?,?,?)', (draft['id'], key, json.dumps(draft)))
            except sqlite3.IntegrityError:
                other = json.loads(db.execute('SELECT data FROM preparations WHERE request_key=?', (key,)).fetchone()[0])
                if other['intent'] != intent:
                    raise ValueError('The selection changed. Start a new preparation.')
                return other
        return draft

    def authorize_source(self, payload):
        """One explicit Long button authorizes preparation and this YouTube release."""
        if payload.get('authorize') is not True or payload.get('mode') != 'long':
            raise ValueError('Choose Post now or Schedule for this Long video.')
        action = payload.get('release_action')
        if action not in ('post_now', 'schedule'):
            raise ValueError('Choose Post now or Schedule.')
        declarations = {k: payload.get(k) for k in ('made_for_kids', 'synthetic_media')}
        if not all(type(v) is bool for v in declarations.values()):
            raise ValueError('Choose the audience and altered-content declarations first.')
        with self.lock:
            if payload.get('id'):
                draft = self.get(payload['id'], payload['profile'])
                if (draft['mode'] != 'long' or file_identity(payload.get('video', ''), VIDEO) != draft['source']
                        or (file_identity(payload['thumbnail'], IMAGE) if payload.get('thumbnail') else None) != draft['thumbnail']):
                    raise ValueError('This saved Long video or thumbnail changed. Choose a new selection; the saved progress is kept.')
            else:
                draft = self.create(payload)
            authorization = {'action': action, 'declarations': declarations,
                             'source_sha256': draft['source']['sha256'],
                             'account_id': draft['bindings']['youtube']['id']}
            previous = draft.get('automatic_release')
            if previous and previous != authorization:
                raise ValueError('This saved request already has a release choice. Review its existing upload; no second upload was started.')
            draft['automatic_release'] = authorization
            self._save(draft)
            return draft

    def _claim(self, key, profile):
        import psutil
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT data FROM preparations WHERE id=?', (key,)).fetchone()
            if not row:
                raise ValueError('Select a saved preparation.')
            draft = json.loads(row[0])
            if draft['profile'] != profile:
                raise ValueError('Select the original profile.')
            if draft['status'] in ('working', 'cancelling') and self._alive(draft.get('owner')):
                raise ValueError('This preparation is still running. Wait for its current stage.')
            draft.update(status='working', errors={},
                         owner={'pid': os.getpid(), 'started': psutil.Process().create_time()})
            db.execute('UPDATE preparations SET data=? WHERE id=?', (json.dumps(draft), key))
        return draft

    def _checkpoint(self, draft):
        with self.lock:
            current = self.get(draft['id'], draft['profile'])
            draft['cancel_requested'] = current['cancel_requested']
            draft['cancel_immediately'] = current.get('cancel_immediately', False)
            self._save(draft)

    def _stage(self, draft, stage, progress):
        if self.get(draft['id'], draft['profile'])['cancel_requested']:
            raise Stopped()
        if stage in draft['stages']:
            return draft['stages'][stage]
        draft.update(current_stage=stage, message='Preparing ' + stage.replace(':', ' · '))
        draft.setdefault('stage_timings',{})[stage]={'started':time.time()}
        self._checkpoint(draft)
        progress(draft['message'])
        def check_cancel():
            saved = self.get(draft['id'], draft['profile'])
            if saved.get('cancel_immediately') and saved.get('cancel_requested'):
                raise Stopped()
        def stage_progress(message):
            check_cancel()
            progress(message)
        stage_progress.check_cancel = check_cancel
        try:
            result = self.runtime.stage(stage, draft, stage_progress)
        finally:
            timing=draft['stage_timings'][stage];timing['finished']=time.time()
            timing['elapsed']=max(0,timing['finished']-timing['started'])
        if stage.startswith('copy:youtube:'):
            from .description_policy import apply as description_policy
            result = {**result, 'metadata': description_policy(self.root, draft['profile'], result['metadata'])}
        # Complete the checkpoint before honoring cancellation at a boundary.
        draft['stages'][stage] = result
        timing=draft['stage_timings'][stage];timing['finished']=time.time()
        timing['elapsed']=max(0,timing['finished']-timing['started'])
        draft['errors'].pop(stage, None)
        self._checkpoint(draft)
        return result

    def run(self, key, profile, progress=lambda message: None):
        draft = self._claim(key, profile)
        if draft.get('cancel_immediately') and draft['cancel_requested']:
            draft.update(status='cancelled', message='Cancelled. Completed work stays saved.')
            self._checkpoint(draft)
            return draft
        if self.runtime is None:
            from .prepare_post_runtime import IsolatedRuntime
            self.runtime = IsolatedRuntime(self.root)
        try:
            verify_identity(draft['source'])
            verify_identity(draft['thumbnail'])
            self._stage(draft, 'inspect', progress)
            self._stage(draft, 'speech', progress)
            if draft['mode'] == 'highlights':
                self._stage(draft, 'highlight-signals', progress)
                self._stage(draft, 'highlight-selection', progress)
                self._stage(draft, 'highlights', progress)
            if draft['mode'] == 'shorts':
                plan = self._stage(draft, 'selection', progress)
                if len(plan.get('clips', [])) != draft['count']:
                    raise ValueError(f"Only {len(plan.get('clips', []))} complete moments were found; {draft['count']} were requested. Keep this saved plan and choose a longer source or a new count.")
                for n in range(1, draft['count'] + 1):
                    self._stage(draft, f'render:{n}', progress)
            else:
                text = draft['stages'].get('highlights', draft['stages']['speech'])['transcript']
                chunks = text_chunks(text)
                if len(chunks) > 1:
                    for n in range(1, len(chunks) + 1):
                        self._stage(draft, f'context:{n}', progress)
            # One platform can finish while another fails. Never parallel inference.
            for platform in draft['platforms']:
                for n in range(1, draft['count'] + 1):
                    stage = f'copy:{platform}:{n}'
                    try:
                        self._stage(draft, stage, progress)
                    except Stopped:
                        raise
                    except Exception as error:
                        draft['errors'][stage] = failure(error, feature=f'{platform.title()} copy')
                        self._checkpoint(draft)
                        break
            verify_identity(draft['source'])
            verify_identity(draft['thumbnail'])
            if self.get(key, profile)['cancel_requested']:
                raise Stopped()
            draft.update(status='failed' if draft['errors'] else 'prepared',
                         message='Some copy needs a retry. Completed stages are saved.' if draft['errors'] else 'Prepared. Review each platform before posting.')
        except Stopped:
            immediate = self.get(key, profile).get('cancel_immediately')
            draft.update(status='cancelled' if immediate else 'stopped', message='Cancelled. Completed work stays saved.' if immediate else 'Stopped after the current stage. Resume to keep going.')
        except Exception as error:
            issue = failure(error, feature='Preparation')
            draft['errors'][draft.get('current_stage', 'source')] = issue
            draft.update(status='failed', message=issue['error'])
        self._checkpoint(draft)
        authorization = draft.get('automatic_release')
        if draft['status'] == 'prepared' and authorization:
            try:
                if (draft['mode'] != 'long' or draft['source']['sha256'] != authorization['source_sha256']
                        or draft['bindings']['youtube']['id'] != authorization['account_id']):
                    raise ValueError('The saved release no longer matches this video and channel.')
                self.post(key, profile, 'youtube', authorization['declarations'], authorization['action'])
                draft = self.get(key, profile)
                draft['message'] = 'YouTube upload authorized. Its verified result will appear here.'
            except Exception as error:
                draft = self.get(key, profile)
                issue = failure(error, feature='YouTube posting')
                draft['errors']['posting'] = issue
                draft.update(status='failed', message=issue['error'])
            self._checkpoint(draft)
        return draft

    def cancel(self, key, profile, *, immediate=False):
        with self.lock:
            draft = self.get(key, profile)
            if immediate and any(draft['jobs_by_platform'].values()):
                raise ValueError('This preparation has already been submitted. Check its saved upload or schedule; cancelling preparation cannot remove a platform post.')
            draft['cancel_requested'] = True
            if immediate:
                draft['cancel_immediately'] = True
                working = draft['status'] in ('working', 'cancelling') and self._alive(draft.get('owner'))
                draft['status'] = 'cancelling' if working else 'cancelled'
                draft['message'] = 'Cancelling this preparation…' if working else 'Cancelled. Completed work stays saved.'
            elif draft['status'] != 'working':
                draft['status'] = 'stopped'
            if not immediate:draft['message'] = 'Stopping after this stage; completed work stays saved.'
            self._save(draft)
            return draft

    def resume(self, key, profile):
        import psutil
        with self.lock:
            draft = self.get(key, profile)
            if draft['status'] in ('working', 'cancelling') and self._alive(draft.get('owner')):
                raise ValueError('This preparation is still running. Wait for the current stage.')
            draft.update(cancel_requested=False, cancel_immediately=False, status='queued', message='Waiting for the shared local work queue.',
                         owner={'pid': os.getpid(), 'started': psutil.Process().create_time()})
            self._save(draft)
            return draft

    def review_discovery(self, key, profile, index, live_research=True, progress=print, *, weeks=None):
        """Refresh optional suggestions only, preserving the prepared media/copy."""
        if type(index) is not int or type(live_research) is not bool:
            raise ValueError('Choose a prepared video and a valid search-suggestions setting.')
        stage = f'copy:youtube:{index}'
        if weeks is not None:
            from .weekly_seo_plan import schema
            schema(weeks)
        target = 'weekly_seo' if weeks is not None else 'discovery'
        with self.lock:
            draft = self.get(key, profile)
            if draft['status'] != 'prepared' or stage not in draft['stages'] or draft.get('cancel_requested'):
                raise ValueError('Finish this video preparation before refreshing its SEO review.')
            if weeks is not None and draft['mode']=='shorts':
                raise ValueError('Weekly SEO plans are for full YouTube videos and finished Highlights, not Shorts or Reels.')
            if weeks is None and any(draft.get('jobs_by_platform', {}).values()):
                raise ValueError('This batch was already submitted. Its saved publishing copy is kept.')
            verify_identity(draft['source'])
            import psutil
            runtime_stage=f'weekly:youtube:{index}' if weeks is not None else f'discovery:youtube:{index}'
            draft.update(status='working', current_stage=runtime_stage,
                message='Reviewing SEO and thumbnail wording',
                owner={'pid':os.getpid(),'started':psutil.Process().create_time()})
            self._save(draft)
        try:
            from .prepare_post_runtime import IsolatedRuntime
            runtime = self.runtime or IsolatedRuntime(self.root)
            def step(message):
                progress(message)
            def check_cancel():
                if self.get(key, profile).get('cancel_requested'):
                    raise Stopped()
            step.check_cancel = check_cancel
            check_cancel()
            result = runtime.stage(runtime_stage,
                {**draft, 'discovery_research':live_research, 'weekly_weeks':weeks}, step)
            plan = result[target]
        except Exception as error:
            issue = failure(error, feature='SEO and thumbnail review')
            retry = 'Generate weekly packages again.' if weeks is not None else 'Try Refresh review.'
            plan = {'status':'needs_review','message':'The SEO review could not finish. Your prepared text and media are kept. '+retry,
                    'technical_details':issue.get('error_details') or str(error)}
        with self.lock:
            saved = self.get(key, profile)
            saved['stages'][stage][target] = plan
            label='Weekly SEO plan' if weeks is not None else 'SEO review'
            saved.update(status='cancelled' if saved.get('cancel_requested') else 'prepared',
                message=(label+' saved. Review every set before enabling changes.' if plan.get('status')=='ready'
                         else label+' could not be verified. Your prepared video and publishing text are kept.'))
            saved.pop('current_stage', None)
            self._save(saved)
            return saved

    def edit_thumbnail(self, key, profile, path):
        """Bind a reviewed cover to an idle draft before its first upload."""
        if not isinstance(path, str):
            raise ValueError('Choose an image file for this prepared video.')
        with self.lock:
            draft = self.get(key, profile)
            if draft['mode'] == 'shorts':
                raise ValueError('Shorts and Reels keep their existing no-cover workflow.')
            if draft['status'] != 'prepared' or draft.get('cancel_requested'):
                raise ValueError('Wait for this preparation to finish before changing its thumbnail.')
            if any(draft.get('jobs_by_platform', {}).values()):
                raise ValueError('This video was already submitted. Its saved upload and thumbnail are kept.')
            verify_identity(draft['source'])
            try:
                thumbnail = file_identity(path, IMAGE) if path.strip() else None
            except ValueError as error:
                raise ValueError('Choose an existing PNG, JPEG or WebP thumbnail file. Your prepared text and previous thumbnail are kept.') from error
            draft['thumbnail'] = thumbnail
            draft['thumbnail_edited'] = time.time()
            self._save(draft)
            return draft

    def edit(self, key, profile, platform, index, value):
        from .metadata import validate
        with self.lock:
            draft = self.get(key, profile)
            stage = f'copy:{platform}:{index}'
            if draft['status'] == 'working' or stage not in draft['stages']:
                raise ValueError('Wait for this copy stage to finish before editing it.')
            if draft['jobs_by_platform'].get(platform):
                raise ValueError('This platform already has saved queue items. Edit its unstarted drafts in Publishing Studio.')
            previous = draft['stages'][stage]['metadata']
            if platform == 'instagram':
                caption = str(value.get('instagram_caption', '')).strip()
                if not caption or len(caption) > 2200:
                    raise ValueError('Enter an Instagram caption under 2,200 characters.')
                from .prepare_post_source import instagram_word_count
                if instagram_word_count(caption)>10:
                    raise ValueError('Keep the Instagram caption to 10 words maximum, excluding hashtags.')
                updated = {**previous, 'instagram_caption': caption}
            else:
                updated = validate({**previous, **{k: value[k] for k in ('title', 'description', 'tags') if k in value}, 'instagram_caption': previous.get('instagram_caption', '')})
                from .description_policy import apply as description_policy
                updated = description_policy(self.root, profile, updated)
            draft['stages'][stage]['metadata'] = updated
            if platform == 'youtube':
                draft['errors'].pop('description-links', None)
            draft['stages'][stage]['edited'] = time.time()
            self._save(draft)
            return draft

    def _slots(self, draft):
        if draft['slots']:
            return draft['slots']
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            saved = json.loads(db.execute('SELECT data FROM preparations WHERE id=?', (draft['id'],)).fetchone()[0])
            if saved['slots']:
                return saved['slots']
            now = time.time()
            if draft['mode'] != 'shorts':
                slots = [now]
            else:
                existing = [j['due'] for j in self.publisher.store.list() if j.get('profile') == draft['profile'] and j.get('kind') == 'short' and j['status'] != 'cancelled']
                for row in db.execute('SELECT data FROM preparations'):
                    other = json.loads(row[0])
                    if other['profile'] == draft['profile'] and other['mode'] == 'shorts':
                        existing.extend(other['slots'])
                day = datetime.fromtimestamp(now, IST).date()
                if existing:
                    day = max(day, datetime.fromtimestamp(max(existing), IST).date() + timedelta(days=1))
                slots = []
                for n in range(draft['count']):
                    while True:
                        minute = 17 * 60 + int(hashlib.sha256(f"{draft['id']}:{n}:{day}".encode()).hexdigest()[:8], 16) % 241
                        due = datetime(day.year, day.month, day.day, minute // 60, minute % 60, tzinfo=IST).timestamp()
                        if due > now:
                            break
                        day += timedelta(days=1)
                    slots.append(due)
                    day += timedelta(days=1)
            saved['slots'] = slots
            db.execute('UPDATE preparations SET data=? WHERE id=?', (json.dumps(saved), draft['id']))
        return slots

    def queue(self, key, profile, platform):
        """Create only draft queue rows; called by the explicit Post path before authorize."""
        from hinglish_niche.profiles import account_key
        with self.lock:
            draft = self.get(key, profile)
            if draft.get('cancel_requested'):
                raise ValueError('This preparation was cancelled. Start a new preparation before posting.')
            if draft['status'] in ('working', 'cancelling') or platform not in draft['platforms']:
                raise ValueError('Wait for preparation to finish and choose its platform.')
            current = self.publisher.accounts(profile).get(platform, {})
            binding = draft['bindings'][platform]
            if not binding['id'] or not current.get('connected') or current.get('id') != binding['id']:
                raise ValueError('The saved account is missing or changed. Check Publishing Studio and prepare a new draft for the intended account.')
            if platform == 'instagram' and current.get('transport') != 'browser':
                raise ValueError('Connect Instagram through the existing Chrome connector in Publishing Studio.')
            verify_identity(draft['source'])
            verify_identity(draft['thumbnail'])
            stages = draft['stages']
            for n in range(1, draft['count'] + 1):
                if f'copy:{platform}:{n}' not in stages:
                    raise ValueError('Finish this platform’s copy before posting.')
                if platform == 'instagram':
                    from .prepare_post_source import instagram_word_count
                    if instagram_word_count(stages[f'copy:{platform}:{n}']['metadata']['instagram_caption'])>10:
                        raise ValueError('An older Instagram paragraph needs rewriting to 10 words maximum before posting. The video is saved.')
            if draft['jobs_by_platform'].get(platform):
                return [self.publisher.store.get(i) for i in draft['jobs_by_platform'][platform]]
            draft['slots'] = self._slots(draft)
            action = draft.get('release_actions', {}).get(platform)
            slots = draft.get('release_slots', {}).get(platform, draft['slots'])
            items = []
            for n in range(1, draft['count'] + 1):
                output = stages[f'render:{n}'] if draft['mode'] == 'shorts' else stages.get('highlights', {'video': draft['source'], **stages['inspect']})
                video = output['video']
                verify_identity(video)
                thumb = ''
                if draft['thumbnail']:
                    thumb = self.publisher.prepared_thumbnail(draft['thumbnail']['path'])
                    verify_identity(draft['thumbnail'])
                meta = stages[f'copy:{platform}:{n}']['metadata']
                from .description_policy import apply as description_policy
                meta = description_policy(self.root, profile, meta, platform)
                stages[f'copy:{platform}:{n}']['metadata'] = meta
                ref = account_key(platform, profile)
                item = {'profile': profile, 'platform': platform, 'kind': 'short' if draft['mode'] == 'shorts' else 'long',
                        'video': video['path'], 'fingerprint': video['sha256'], 'thumbnail': thumb,
                        'thumbnail_fingerprint': fingerprint(thumb) if thumb else '', 'visibility': 'private' if action else draft['visibility'],
                        'metadata': meta, 'brain': stages[f'copy:{platform}:{n}'].get('model', ''),
                        'account_id': binding['id'], 'connection_ref': ref, 'prepare_post_id': key, 'prepare_post_index': n,
                        'destination': {'profile_id': profile, 'platform': platform, 'account_id': binding['id'], 'connection_ref': ref, 'verified': True},
                        **{k: output[k] for k in ('width', 'height', 'duration') if k in output}}
                if action:
                    item.update(release_action=action, release_authorized_at=time.time())
                if platform == 'instagram':
                    item['transport'] = 'browser'
                from .test_mode import enabled as repeat_uploads
                if repeat_uploads(self.root, profile):
                    item['test_repeat_scope'] = draft['id']
                items.append(item)
            ids = self.publisher.store.add_batch(items, daily_window=True)
            jobs = []
            for n, job_id in enumerate(ids):
                job = self.publisher.store.get(job_id)
                if job.get('account_id') != binding['id'] or job['video'] != items[n]['video']:
                    raise ValueError('An existing post for this video has a different account or path. Review its saved receipt; no duplicate was created.')
                if job.get('prepare_post_id') != key and any(job.get(field) != items[n].get(field) for field in ('visibility', 'thumbnail_fingerprint', 'metadata')):
                    raise ValueError('This video already has a saved post with different copy, thumbnail or visibility. Review that post in Publishing Studio; no duplicate was created.')
                if job.get('prepare_post_id') == key and job['status'] == 'draft' and not job.get('remote'):
                    self.publisher.store.change(job_id, expected_status=('draft',), due=slots[n])
                    job = self.publisher.store.get(job_id)
                # Existing queue identity always wins; never rewrite an older post.
                jobs.append(job)
            draft['jobs_by_platform'][platform] = ids
            self._save(draft)
            return jobs

    def post(self, key, profile, platform, declarations, release_action=None):
        # Serialize both repeated clicks through authorization, not just queue creation.
        with self.lock:
            if self.get(key, profile).get('cancel_requested'):
                raise ValueError('This preparation was cancelled. Start a new preparation before posting.')
            if release_action is not None:
                from .prepare_post_release import set_action
                set_action(self, key, profile, platform, release_action)
            return self._post(key, profile, platform, declarations)

    def _post(self, key, profile, platform, declarations):
        jobs = self.queue(key, profile, platform)
        for job in jobs:
            if fingerprint(job['video']) != job['fingerprint'] or job.get('thumbnail') and fingerprint(job['thumbnail']) != job['thumbnail_fingerprint']:
                raise ValueError('A prepared video or thumbnail changed. Check the saved draft before posting.')
        pending = [j['id'] for j in jobs if j['status'] in ('draft', 'blocked') and not j.get('remote')]
        uncertain = [j for j in jobs if j['status'] == 'needs_review']
        if uncertain:
            raise ValueError('A saved upload needs receipt review. Check it in Publishing Studio before retrying; no duplicate was sent.')
        if pending:
            self.publisher.authorize({**declarations, 'ids': pending, 'authorize': True})
            self.start_delivery()
        elif any(j['status'] == 'uploaded_private' and j.get('release_action') for j in jobs):
            self.start_delivery()
        return {'jobs': [self.publisher.store.get(j['id']) for j in jobs],
                'message': 'Using the saved upload job. No duplicate upload was created. Release status appears after platform verification.',
                'worker_enabled': self.delivery_running or bool(self.publisher.thread and self.publisher.thread.is_alive())}

    @property
    def delivery_running(self):
        return bool(self.delivery and self.delivery.running)

    def start_delivery(self):
        if self.delivery is None:
            from .prepare_post_delivery import Delivery
            self.delivery = Delivery(self.publisher)
        self.delivery.start()
