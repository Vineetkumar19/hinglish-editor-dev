"""Folder discovery, local drafting, Shorts integration and an opt-in publishing worker."""
import json
import hashlib
import re
import threading
import time
import uuid
import os
from pathlib import Path

from . import metadata, secrets
from .providers import Instagram, PreflightError, YouTube
from .store import Store, fingerprint

DEFAULTS = {'media_root': '', 'source_root': '', 'daily_time': '19:00', 'enabled': False,
            'visibility': 'public', 'youtube_public_api_ready': False,
            'vision': False, 'shorts_count': '8', 'shorts_look': 'template',
            's3_bucket': '', 's3_region': '', 's3_prefix': 'hinglish-publisher'}


class PreparationStopped(RuntimeError):
    pass


class Publisher:
    def __init__(self, root, providers=None, browser=None):
        self.root = Path(root).resolve()
        self.settings_path = self.root / 'config.publish.local.json'
        self.store = Store(self.root)
        self.providers = providers or {'youtube': YouTube, 'instagram': Instagram}
        self.browser = browser
        self.tasks = {}
        self.lock = threading.RLock()
        self.preparing = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self._last_verification = 0
        self.cancellations={};self.task_folder=self.root/'cache/publisher/tasks';self.task_folder.mkdir(parents=True,exist_ok=True)
        import psutil
        self.owner_started=psutil.Process().create_time()
        for saved in sorted(self.task_folder.glob('*.json'),key=lambda p:p.stat().st_mtime)[-100:]:
            try:
                task=json.loads(saved.read_text('utf-8'))
                if task.get('status') in ('working','stopping'):
                    try:alive=abs(psutil.Process(task['owner_pid']).create_time()-task['owner_started'])<.01
                    except (psutil.Error,KeyError):alive=False
                    if not alive:task.update(status='interrupted',message='Preparation stopped when Storylens closed. Saved files are kept; resume to continue.')
                self.tasks[task['id']]=task
            except (ValueError,OSError,KeyError):continue

    def settings(self, changes=None, profile='general'):
        from hinglish_niche.profiles import valid_profile
        valid_profile(profile)
        settings_path = self.settings_path if profile == 'general' else self.root / 'cache' / 'publisher' / ('settings-' + profile + '.json')
        with self.lock:
            try:
                saved = json.loads(settings_path.read_text(encoding='utf-8-sig'))
            except FileNotFoundError:
                saved = {}
            value = {**DEFAULTS, 'media_root': str(self.root / 'publishing' / profile) if profile != 'general' else str(self.root / 'publishing'), **saved}
            if profile != 'general' and not value['source_root']:
                value['source_root'] = self.settings()['source_root']
            if changes is not None:
                if set(changes) - set(DEFAULTS):
                    raise ValueError('Unknown publisher setting')
                value.update(changes)
                if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(value['daily_time'])):
                    raise ValueError('Daily time must be HH:MM in India time')
                if value['visibility'] not in ('public', 'private'):
                    raise ValueError('Choose public or private visibility')
                if any(type(value[k]) is not bool for k in ('enabled', 'youtube_public_api_ready', 'vision')):
                    raise ValueError('Publisher switches must be true or false')
                if not str(value['shorts_count']).isdigit() or not 1 <= int(value['shorts_count']) <= 40:
                    raise ValueError('Choose 1-40 Shorts')
                if value['shorts_look'] not in ('template', 'face'):
                    raise ValueError('Choose template or face crop')
                if not str(value['media_root']).strip():
                    raise ValueError('Choose a media folder')
                value['media_root'] = str(Path(value['media_root']).resolve())
                if not isinstance(value['source_root'], str):
                    raise ValueError('Choose a source video folder')
                if value['source_root']:
                    source = Path(value['source_root']).resolve()
                    if not source.is_dir():
                        raise ValueError('The source video folder is unavailable')
                    value['source_root'] = str(source)
                settings_path.parent.mkdir(parents=True, exist_ok=True)
                temp = settings_path.with_suffix('.tmp')
                temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
                temp.replace(settings_path)
            return value

    def folders(self, profile='general'):
        base = Path(self.settings(profile=profile)['media_root'])
        return {k: base / k for k in ('long-youtube', 'shorts-both', 'thumbnails-youtube')}

    def init_folders(self, profile='general'):
        for path in self.folders(profile).values():
            path.mkdir(parents=True, exist_ok=True)
        return {k: str(v) for k, v in self.folders(profile).items()}

    def scan(self, profile='general'):
        folders = self.folders(profile)
        files = []
        for name, kind in (('long-youtube', 'long'), ('shorts-both', 'short')):
            if not folders[name].exists():
                continue
            for video in sorted(folders[name].glob('*.mp4')):
                if not video.is_file() or video.stat().st_size == 0 or time.time() - video.stat().st_mtime < 10:
                    continue
                thumb = next((p for p in folders['thumbnails-youtube'].glob('*')
                              if p.stem.casefold() == video.stem.casefold() and
                              p.suffix.lower() in ('.png', '.jpg', '.jpeg') and p.is_file()), None)
                files.append({'video': str(video.resolve()), 'kind': kind, 'name': video.stem,
                              'thumbnail': str(thumb.resolve()) if thumb else ''})
        return files

    def selected(self, name, profile='general'):
        name = re.sub(r'^(?:upload|prepare)\s+', '', str(name).strip(), flags=re.I)
        name = re.sub(r'\s+(?:on|to)\s+youtube\s*$', '', name, flags=re.I)
        name = re.sub(r'\.mp4$', '', name, flags=re.I)
        found = [f for f in self.scan(profile) if f['name'].casefold() == name.casefold() or
                 f['video'].casefold() == name.casefold()]
        if len(found) != 1:
            raise ValueError('Use an exact video name from the folder list; missing or duplicate names are not guessed')
        return found[0]

    def accounts(self, profile='general'):
        from hinglish_niche.profiles import account_key
        result = {}
        for platform in self.providers:
            try:
                data = secrets.load(self.root, account_key(platform, profile))
                result[platform] = {'connected': True, 'name': data.get('name', ''),
                                    'id': data.get('channel_id') or data.get('account_id')}
            except Exception:
                result[platform] = {'connected': False, 'name': '', 'id': ''}
        if self.browser is not None:
            account=self.browser.snapshot().get('accounts',{}).get(profile)
            if account:result['instagram']={'connected':True,'name':'@'+account,'id':account,'transport':'browser'}
        return result

    def provider(self,job,config):
        if job.get('transport')=='browser' and job['platform']=='instagram':
            if self.browser is None:raise PreflightError('The Instagram browser connection is unavailable. Open Storylens and reconnect Chrome.')
            from .browser_provider import BrowserInstagram
            return BrowserInstagram(self.browser)
        return self.providers[job['platform']](self.root,config)

    def snapshot(self, profile='general'):
        with self.lock:
            tasks = [{**{k:v for k,v in t.items() if k not in ('request','owner_pid','owner_started')},
                      'can_stop':bool(t.get('request') and t['id'] in self.cancellations and t['status']=='working'),
                      'can_resume':bool(t.get('request') and t['status'] in ('failed','interrupted','stopped'))} for t in self.tasks.values()]
        # Presigned media URLs and account tokens never reach the dashboard.
        jobs = [{k: v for k, v in j.items() if k not in ('video_url',)} for j in self.store.list()]
        from .memory import CreatorMemory
        from hinglish_app.assistant_preferences import declarations
        return {'settings': self.settings(profile=profile), 'accounts': self.accounts(profile), 'files': self.scan(profile),
                'publishing_defaults':declarations(self.root),
                'profile_accounts': {p: self.accounts(p) for p in ('general', 'cricket', 'gaming')},
                'jobs': jobs, 'events': self.store.events(), 'tasks': tasks,
                'worker_enabled':bool(self.thread and self.thread.is_alive()),
                'memory': CreatorMemory(self.root, 'general').list(),
                'profile_memory': {p: CreatorMemory(self.root, p).list() for p in ('cricket', 'gaming')}}

    def _save_task(self,key):
        if self.tasks[key].get('request') is not None:
            from hinglish_app.durable_json import write
            write(self.task_folder/(key+'.json'),self.tasks[key])

    def stop_task(self,key):
        with self.lock:
            if key not in self.cancellations or not self.tasks[key].get('request') or self.tasks[key]['status'] not in ('working','stopping'):
                raise ValueError('This preparation is not running in this Storylens instance.')
            self.cancellations[key].set();self.tasks[key].update(status='stopping',message='Stopping after the current step. Saved files are kept.');self._save_task(key)
            return {'id':key}

    def resume_request(self,key):
        with self.lock:
            task=self.tasks.get(key,{})
            if not task.get('request') or task.get('status') not in ('failed','stopped','interrupted'):
                raise ValueError('Choose a stopped preparation to resume. Existing work and receipts are kept.')
            return dict(task['request'])

    def task(self, function, *args, request=None):
        task_id = uuid.uuid4().hex[:12]
        with self.lock:
            self.tasks[task_id] = {'id': task_id, 'status': 'working', 'message': 'Preparing…','request':request,
                'owner_pid':os.getpid(),'owner_started':self.owner_started}
            self.cancellations[task_id]=threading.Event();self._save_task(task_id)

        def progress(message):
            with self.lock:
                if self.cancellations[task_id].is_set():raise PreparationStopped()
                self.tasks[task_id]['message'] = str(message)
                self._save_task(task_id)

        def run():
            try:
                # One speech/LLM/render preparation at once in this publisher.
                with self.preparing:
                    progress('Preparing…')
                    result = function(*args, progress=progress)
                with self.lock:
                    self.tasks[task_id].update(status='done', result=result, message=(result.get('message') if isinstance(result,dict) else None) or 'Ready to review');self._save_task(task_id)
            except PreparationStopped:
                with self.lock:
                    self.tasks[task_id].update(status='stopped',message='Preparation stopped. Saved files are kept; resume when ready.');self._save_task(task_id)
            except Exception as error:
                from hinglish_app.user_messages import failure
                issue=failure(error,feature='Publishing preparation')
                with self.lock:
                    self.tasks[task_id].update(status='failed',message=issue['error'],**issue);self._save_task(task_id)
        threading.Thread(target=run, daemon=True).start()
        return {'id': task_id}

    def prepared_thumbnail(self, source):
        if not source:
            return ''
        from PIL import Image
        target = self.root / 'cache' / 'publisher' / 'thumbnails' / (fingerprint(source) + '.jpg')
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image = image.convert('RGB')
            image.thumbnail((1280, 720))
            image.save(target, 'JPEG', quality=90)
        if target.stat().st_size > 2_000_000:
            raise ValueError('Thumbnail exceeds YouTube upload size')
        return str(target)

    def item(self, video, kind, thumbnail, config, transcript=None, notes='', progress=print):
        from hinglish_shorts.source import open_video
        facts = open_video(video)
        if kind == 'short' and (facts.height <= facts.width or facts.duration > 180):
            raise ValueError('Shorts must be portrait videos up to 180 seconds')
        before = Path(video).stat()
        digest = fingerprint(video)
        after = Path(video).stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Video is still being copied or rendered; wait until it has finished')
        progress('Writing title, description and Instagram caption from the spoken content')
        from hinglish_niche.profiles import Profiles, use
        profile = config.get('profile', 'general')
        with use(Profiles(self.root).context(profile)):
            meta, brain = metadata.generate(self.root, video, thumbnail, transcript, notes,
                                            config['vision'], progress)
        sidecar = Path(video).with_suffix('.publish.json')
        side = json.loads(sidecar.read_text(encoding='utf-8-sig')) if sidecar.is_file() else {}
        thumb = self.prepared_thumbnail(thumbnail)
        base = {'video': str(Path(video).resolve()), 'kind': kind, 'fingerprint': digest, 'profile': profile,
                'metadata': meta, 'brain': brain, 'thumbnail': thumb,
                'thumbnail_fingerprint': fingerprint(thumb) if thumb else '',
                'visibility': config['visibility'], 'video_url': side.get('video_url', ''),
                'duration': facts.duration, 'width': facts.width, 'height': facts.height}
        from .description_policy import apply as description_policy
        return [{**base, 'platform': platform, 'thumbnail': thumb if platform == 'youtube' else '',
                 'metadata': description_policy(self.root, profile, meta, platform)}
                for platform in (('youtube',) if kind == 'long' else ('youtube', 'instagram'))]

    def prepare(self, payload, progress=print):
        if payload.get('operation')=='diagnostics':
            from .readiness import report
            return report(self.root,payload.get('profile','general'),online=payload.get('online') is True)
        if str(payload.get('video_path','')).strip():
            from hinglish_shorts.source import open_video
            path=Path(str(payload['video_path']).strip().strip(chr(34))).resolve()
            if not path.is_file() or path.suffix.lower()!='.mp4':
                raise ValueError('The selected video was not found or is not a finished MP4. Check that exact path; no other source was selected.')
            kind=payload.get('kind','auto')
            if kind=='auto':
                facts=open_video(path);kind='short' if facts.height>facts.width and facts.duration<=180 else 'long'
            if kind not in ('short','long'):raise ValueError('Choose a Short or a full video.')
            return self.prepare_file({'video':str(path),'name':path.stem,'kind':kind,'thumbnail':''},payload,progress)
        return self.prepare_file(self.selected(payload['name'], payload.get('profile', 'general')), payload, progress)

    def prepare_file(self, file, payload, progress=print):
        # The conversational editor supplies explicitly attached files through the same draft pipeline.
        from hinglish_niche.profiles import valid_profile, Profiles, use
        profile = valid_profile(payload.get('profile', 'general'))
        scope=payload.get('platforms')
        if scope is not None:
            if not isinstance(scope,list) or not scope or any(p not in ('youtube','instagram') for p in scope) or len(set(scope))!=len(scope):
                raise ValueError('Choose YouTube, Instagram, or both destinations.')
        accounts=self.accounts(profile) if scope is not None else {}
        for platform in scope or []:
            if not accounts.get(platform,{}).get('connected') or not accounts[platform].get('id'):
                raise ValueError('Connect this profile\'s '+platform+' account before preparing its publishing drafts.')
            expected=payload.get('expected_accounts',{}).get(platform)
            if expected is not None and expected!=accounts[platform]['id']:
                raise ValueError('The saved destination account changed since this request. Review this profile before preparing a new draft.')
        config = self.settings(profile=profile)
        config = {**config, 'profile': profile}
        before_copy={j['id']:j['metadata'] for j in self.store.list()} if payload.get('refresh_copy') is True else {}
        if 'shorts_count' in payload:
            wanted=payload['shorts_count']
            if type(wanted) is not int or not 1<=wanted<=40:raise ValueError('Choose between 1 and 40 Shorts.')
            config['shorts_count']=str(wanted)
        items = self.item(file['video'], file['kind'], file['thumbnail'], config,
                          transcript=str(payload.get('script','')).strip() or None,
                          notes=str(payload.get('notes', '')), progress=progress)
        if file['kind'] == 'long' and payload.get('make_shorts') is True:
            from hinglish_shorts.pipeline import run
            from hinglish_shorts.settings import ShortsSettings
            from .memory import CreatorMemory
            shorts_source = payload.get('shorts_source') or file['video']
            source_fingerprint = fingerprint(shorts_source)
            clip_context = {'count': config['shorts_count'], 'look': 'template' if profile == 'gaming' else config['shorts_look'],
                            'profile': profile,
                            'spellings': CreatorMemory(self.root, profile).spellings(),
                            'creator_context': Profiles(self.root).context(profile) if profile != 'general' else {}}
            revision = hashlib.sha256(json.dumps(clip_context, sort_keys=True).encode()).hexdigest()[:16]
            marker = self.root / 'cache' / 'publisher' / (
                'shorts-' + source_fingerprint + '-' + revision + '.json')
            projects = []
            if marker.exists():
                projects = [Path(p) for p in json.loads(marker.read_text())]
                if not all(p.is_file() for p in projects):
                    projects = []
            if not projects:
                progress('Finding complete hook moments and rendering vertical Shorts')
                with use(Profiles(self.root).context(profile)):
                    from hinglish_cut.model_preferences import preferred_device
                    report = run(self.root, Path(shorts_source), ShortsSettings(
                        count=config['shorts_count'], look=clip_context['look'], captions=True,
                        device=preferred_device(self.root)),
                        progress=progress)
                projects = list(report.parent.rglob('shorts-project.json'))
                marker.write_text(json.dumps([str(p) for p in projects]), encoding='utf-8')
            for project_file in projects:
                project = json.loads(project_file.read_text(encoding='utf-8'))
                for short in project['shorts']:
                    video = project_file.parent / short['mp4']
                    words = project['words']
                    transcript = ' '.join(str(w[0]) for w in words if any(
                        a <= (w[1] + w[2]) / 2 < b for a, b in short['pieces']))
                    items.extend(self.item(video, 'short', '', config, transcript=transcript,
                                           notes=str(payload.get('notes', '')), progress=progress))
                    for prepared in items[-2:]:
                        prepared['review_file'] = str(project_file.parent / 'report.html')
        if scope is not None:
            items=[item for item in items if item['platform'] in scope]
            if not items:raise ValueError('Long videos go to YouTube. Choose YouTube or prepare portrait Shorts for Instagram.')
            from hinglish_niche.profiles import account_key
            current=self.accounts(profile)
            for platform in scope:
                if current.get(platform,{}).get('id')!=accounts[platform]['id']:
                    raise ValueError('The destination account changed while preparing. Review the selected profile and try again; nothing was queued.')
            for item in items:
                account=accounts[item['platform']];ref=account_key(item['platform'],profile)
                item.update(account_id=account['id'],connection_ref=ref,
                            destination=dict(profile_id=profile,platform=item['platform'],account_id=account['id'],connection_ref=ref,verified=True))
                if account.get('transport')=='browser':item['transport']='browser'
        ids = self.store.add_batch(items, config['daily_time'],daily_window=payload.get('daily_window') is True)
        if before_copy:self.store.refresh_draft_copy(ids,items,before_copy)
        count=len({i['fingerprint'] for i in items if i['kind']=='short'})
        return {'job_ids': ids,'shorts_count':count, 'message': f'{len(ids)} platform posts prepared as drafts'+(f' · {count} Shorts' if count else '')}

    def edit(self, payload):
        job = self.store.get(payload['id'])
        if job['status'] not in ('draft', 'ready', 'blocked') or job.get('remote'):
            raise ValueError('This item has already started uploading; edit it on the platform')
        meta = metadata.validate(payload['metadata'])
        from .description_policy import apply as description_policy
        meta = description_policy(self.root, job.get('profile', 'general'), meta, job['platform'])
        due = float(payload.get('due', job['due']))
        if not 0 < due < 4_102_444_800:
            raise ValueError('Invalid publishing date')
        self.store.change(job['id'], expected_status=('draft', 'ready', 'blocked'),
                          metadata=meta, due=due, status='draft', error='')
        if payload.get('remember') is True:
            from .memory import CreatorMemory
            CreatorMemory(self.root, job.get('profile', 'general')).remember_edit(job['metadata'], meta)
        return {'ok': True}

    def channel_queue_proposal(self, **request):
        from .channel_queue_service import propose
        with self.lock:return propose(self,**request)

    def channel_queue_commit(self, proposal, **request):
        from .channel_queue_service import commit
        with self.lock:return commit(self,proposal,**request)

    def authorize(self, payload):
        from hinglish_app.assistant_preferences import declarations
        payload={**declarations(self.root),**payload}
        if payload.get('authorize') is not True or type(payload.get('made_for_kids')) is not bool or \
                type(payload.get('synthetic_media')) is not bool:
            raise ValueError('Confirm publication and explicitly choose audience and realistic synthetic-media disclosure')
        jobs = [self.store.get(j) for j in payload['ids']]
        for job in jobs:
            accounts = self.accounts(job.get('profile', 'general'))
            from .channel_queue_service import check_authorization_binding
            check_authorization_binding(job,accounts)
            if job['status'] not in ('draft', 'blocked') or job.get('remote'):
                raise ValueError('Only unstarted drafts or blocked items can be authorized')
            if not accounts[job['platform']]['connected']:
                raise ValueError(f'Connect {job["platform"]} before authorizing its posts')
            from .description_policy import apply as description_policy
            job['metadata'] = description_policy(self.root, job.get('profile', 'general'), job['metadata'], job['platform'])
            metadata.validate(job['metadata'])
        for job in jobs:
            accounts = self.accounts(job.get('profile', 'general'))
            check_authorization_binding(job,accounts)
            self.store.change(job['id'], expected_status=('draft', 'blocked'),
                              status='ready', error='', authorized_at=time.time(), metadata=job['metadata'],
                              account_id=accounts[job['platform']]['id'],
                              made_for_kids=payload['made_for_kids'], synthetic_media=payload['synthetic_media'],
                              **({'execution_authorized':True} if job.get('queue_proposal_id') else {}))
            self.store.event(job['id'], 'Authorized for ' + job['platform'])
        return {'ok': True}

    def cancel(self, job_id):
        job = self.store.get(job_id)
        if job['status'] not in ('draft', 'ready', 'blocked') or job.get('remote'):
            raise ValueError('This item has started uploading; manage it on the platform')
        self.store.change(job_id, expected_status=('draft', 'ready', 'blocked'), status='cancelled')
        return {'ok': True}

    def host_instagram(self, job, checkpoint, config):
        if job.get('video_url'):
            return job
        if not config['s3_bucket']:
            raise PreflightError('Set an S3 media bucket or supply video_url in a .publish.json sidecar for Instagram')
        try:
            import boto3
        except ImportError as error:
            raise PreflightError('Install requirements-publish.txt for automatic Instagram media hosting') from error
        client = boto3.client('s3', region_name=config['s3_region'] or None)
        remote = dict(job.get('remote') or {})
        key = remote.get('hosting_key') or config['s3_prefix'].strip('/') + '/' + job['fingerprint'] + '.mp4'
        if not remote.get('hosting_key'):
            client.upload_file(job['video'], config['s3_bucket'], key, ExtraArgs={'ContentType': 'video/mp4'})
            remote.update(hosting_key=key, hosting_bucket=config['s3_bucket'])
            checkpoint(remote)
        url = client.generate_presigned_url('get_object', Params={'Bucket': config['s3_bucket'], 'Key': key},
                                           ExpiresIn=86400)
        return {**job, 'remote': remote, 'video_url': url}

    def tick(self):
        configs = {p: self.settings(profile=p) for p in ('general', 'cricket', 'gaming')}
        enabled = [p for p, config in configs.items() if config['enabled']]
        if not enabled:
            return None
        now = time.time()
        # Query scheduled/processing receipts at most once per minute.
        if now - self._last_verification >= 60:
            self._last_verification = now
            for waiting in self.store.list():
                if waiting.get('profile', 'general') not in enabled or waiting['status'] not in ('scheduled', 'processing') or waiting['due'] > now:
                    continue
                try:
                    status = self.provider(waiting,configs[waiting.get('profile', 'general')]).verify(waiting)
                    if status != waiting['status']:
                        self.store.change(waiting['id'], status=status,remote=waiting['remote'])
                        self.store.event(waiting['id'], 'Publication verified: ' + waiting['remote'].get('url', ''))
                except Exception:
                    self.store.change(waiting['id'], status='needs_review', error='Could not verify remote publication')
                    self.store.event(waiting['id'], 'Scheduled upload needs review; no second upload was attempted')
        job = self.store.claim(now, enabled)
        if not job:
            return None
        config = configs[job.get('profile', 'general')]
        try:
            if fingerprint(job['video']) != job['fingerprint']:
                raise PreflightError('The video changed after preparation; prepare the updated file again')
            if job.get('thumbnail') and fingerprint(job['thumbnail']) != job['thumbnail_fingerprint']:
                raise PreflightError('The prepared thumbnail changed; prepare this post again')
            def checkpoint(remote):
                self.store.change(job['id'], remote=remote)
            if job['platform'] == 'instagram' and job.get('transport')!='browser':
                job = self.host_instagram(job, checkpoint, config)
            remote, status = self.provider(job,config).publish(job, checkpoint)
            self.store.change(job['id'], status=status, remote=remote, error='')
            label = {'published': 'Published and verified', 'scheduled': 'Uploaded and scheduled',
                     'processing': 'Uploaded; still processing', 'uploaded_private': 'Uploaded privately'}[status]
            if job.get('transport')=='browser' and status=='processing':label='Waiting for Instagram browser publication'
            self.store.event(job['id'], label + ' on ' + job['platform'] + ': ' + remote.get('url', ''))
        except PreflightError as error:
            self.store.change(job['id'], status='blocked', error=str(error))
            self.store.event(job['id'], str(error))
        except Exception:
            # HTTP timeout could mean the server accepted the video/post. Never auto-repeat it.
            self.store.change(job['id'], status='needs_review', error='Upload outcome needs review. '
                              'Check the connected platform; the saved remote ID is preserved.')
            self.store.event(job['id'], 'Upload needs review; automatic retry was stopped to avoid duplicates')
        return self.store.get(job['id'])

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        from .worker_lock import acquire
        self._worker_lock = acquire(self.root)
        self.store.recover()
        def work():
            try:
                while not self.stop.is_set():
                    try:
                        self.tick()
                    except Exception:
                        self.store.event(None, 'Publisher worker needs attention; check settings')
                    self.stop.wait(30)
            finally:
                self._worker_lock.close()
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()
