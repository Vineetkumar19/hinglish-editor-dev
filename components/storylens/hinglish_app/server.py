from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote, quote
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid

from . import DEFAULT_PORT, app_token

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mxf', '.mkv', '.avi', '.mts', '.m2ts', '.webm'}
TIMELINE_MODES = ('broll', 'visuals', 'zoom', 'sound', 'eyecontact', 'aiimage', 'aivideo', 'motion')   # can work on a whole edited sequence (or XML)
SOUND_CHOICES = {'sound_style': ('auto', 'cinematic', 'funny', 'chill', 'emotional'),
                 'sound_density': ('low', 'medium', 'high')}
EYE_CHOICES = {'eye_reach': ('near', 'far'), 'eye_size': ('3', '2', '4', '5', '6')}
VISUALS_CHOICES = {'visuals_density': ('medium', 'low', 'high'), 'visuals_brain': ('auto', 'ollama', 'local'),
                   'visuals_presentation': ('auto', 'fullscreen', 'popup', 'cutout', 'behind')}
AI_TOOLS = {'aiimage': 'hinglish_aiimage', 'aivideo': 'hinglish_aivideo'}      # two separate tools, one shared engine
AI_CHOICES = {'count': ('medium', 'low', 'high'), 'aspect': ('auto', '16:9', '9:16', '1:1'), 'brain': ('auto', 'ollama', 'local')}
MOTION_CHOICES = {'motion_count': ('medium', 'low', 'high'), 'motion_mode': ('auto', 'full', 'overlay'),
                  'motion_engine': ('remotion', 'motion-canvas', 'hyperframes'),
                  'motion_coverage': ('auto', 'full', 'key'), 'motion_assets': ('all', 'web', 'ai'),
                  'motion_aspect': ('auto', '16:9', '9:16', '1:1'),
                  'motion_brain': ('auto', 'ollama', 'local'), 'motion_quality': ('full', 'preview')}
SHORTS_CHOICES = {'shorts_count': ('medium', 'low', 'high'), 'shorts_look': ('template', 'face'),
                  'shorts_pieces': ('3', '2', '1'), 'shorts_brain': ('auto', 'ollama', 'local')}
ZOOM_CHOICES = {'zoom_style': ('smooth', 'mixed', 'punch'), 'zoom_strength': ('subtle', 'medium', 'strong'),
                'zoom_frequency': ('low', 'medium', 'high')}


QUALITY_ATTEMPTS = 3   # first run + up to 2 corrected redos when a feature's output breaks its rules


def quality_summary(folder):
    try:
        data = json.loads((Path(folder) / 'quality-check.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    chosen = next((a for a in data['attempts'] if a['attempt'] == data['chosen_attempt']), None)
    if not chosen or not chosen.get('evaluations'):
        return None
    evals = chosen['evaluations']
    failed = [c['title'] for e in evals for c in e['checks'] if c['hard'] and not c['passed']]
    return {'score': min(e['score'] for e in evals), 'passed': not failed, 'failed': failed[:5],
            'attempts': len(data['attempts']), 'used': data['chosen_attempt']}


class LocalHTTPServer(ThreadingHTTPServer):
    """A single local bridge; Windows must not share this port between apps."""
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class AppState:
    def __init__(self, root, port=DEFAULT_PORT, *, python_executable=None, engine_root=None, license_client=None, restore_pending_jobs=True):
        self.root = Path(root).resolve()
        # The hosted worker supplies a private job root while reusing the
        # installed engine. The desktop app retains its original defaults.
        self.python_executable = Path(python_executable) if python_executable else self.root / '.venv' / 'Scripts' / 'python.exe'
        self.engine_root = Path(engine_root).resolve() if engine_root else self.root
        self.license_client = license_client
        self.license_clients = {license_client.edition:license_client} if license_client else {}
        self.static = Path(__file__).parent / 'static'
        self.port = port
        self.token = app_token(self.root / 'cache' / 'app' / 'bridge.json')
        self.jobs = {}
        self.lock = threading.Lock()
        self._publisher = None
        self._assistant = None
        self._local_browser = None
        self._scheduled_posts = None
        self._scheduled_lock=threading.Lock()
        self.work_lock = threading.RLock()
        self._beats = None
        self._cinematic = None
        self._restore_visuals_jobs(restore_pending_jobs)
        self._restore_broll_jobs(restore_pending_jobs)
        from .completed_visual_jobs import load as completed_visuals
        for key,job in completed_visuals(self.root,self.port).items():
            if key not in self.jobs:self.jobs[key]=job
        from .completed_sound_jobs import load as completed_sounds
        for key,job in completed_sounds(self.root,self.port).items():
            if key not in self.jobs:self.jobs[key]=job

    def _persist_broll_job(self, job):
        if job.get('mode') == 'broll' and job.get('recovery_request'):
            from hinglish_broll.recovery import write_json
            write_json(self.root/'cache/app/broll-jobs'/str(self.port)/(job['id']+'.json'),job)

    def _restore_broll_jobs(self, resume=True):
        for file in (self.root/'cache/app/broll-jobs'/str(self.port)).glob('*.json'):
            try:
                job=json.loads(file.read_text('utf-8'))
                if not re.fullmatch(r'[a-f0-9]{12}',job['id']) or job.get('mode')!='broll':continue
                if not resume and job['status'] in ('queued', 'running'):continue
                self.jobs[job['id']]=job
                if job['status'] not in ('queued','running'):continue
                request=job['recovery_request']
                if job.get('recovery_attempts',0)>=2:
                    job.update(status='failed',stage='Saved B-roll work is kept. Press Run again to continue the unfinished steps.',
                        error_code='broll_recovery_stopped',error_details='The worker stopped after its bounded automatic recovery.')
                    self._persist_broll_job(job)
                    continue
                threading.Thread(target=self._run_job,args=(job['id'],request['payload'],
                    [Path(p) for p in request['paths']],Path(request['input']) if request['input'] else None,request['script']),daemon=True).start()
            except (OSError,ValueError,KeyError,TypeError):continue

    def _persist_visuals_job(self, job):
        if job.get('visuals_project'):
            from hinglish_clean.detection import write_json
            write_json(self.root/'cache/app/visuals-jobs'/str(self.port)/(job['id']+'.json'),job)
        elif job.get('mode')=='visuals' and job.get('status')=='complete':
            from .completed_visual_jobs import save as save_completed_visuals
            save_completed_visuals(self.root,self.port,job)

    def _restore_visuals_jobs(self, resume=True):
        # Only this service's saved research jobs; never resurrect publishing or
        # another workspace's GPU work. One interrupted job gets one recovery.
        for file in (self.root/'cache/app/visuals-jobs'/str(self.port)).glob('*.json'):
            try:
                job=json.loads(file.read_text('utf-8'))
                project=Path(job['visuals_project']).resolve()
                if not project.is_relative_to((self.root/'output/visuals').resolve()) or not project.is_file():continue
                if not resume and job['status'] in ('queued', 'running'):continue
                self.jobs[job['id']]=job
                if job['status'] in ('queued','running'):
                    if job.get('attempts',0)>=2:
                        job.update(status='failed',stage='Research stopped twice. Saved choices are kept; open the review to resume.',
                            error='Research stopped twice. Saved choices are kept; open the review to resume.')
                        from hinglish_visuals.recovery import pause_project
                        pause_project(project)
                        self._persist_visuals_job(job)
                    else:
                        self._start_visuals_research(job['id'],project)
            except (OSError,ValueError,KeyError):continue

    def _start_visuals_research(self, job_id, project):
        def run():
            from hinglish_cut.gpu_lock import gpu_lock
            from hinglish_visuals.references import recheck_project
            try:
                with self.work_lock,gpu_lock(self.root):
                    with self.lock:
                        job=self.jobs[job_id]
                        job['attempts']=job.get('attempts',0)+1
                        job.update(status='running',stage='Continuing from saved searches and image checks')
                        self._persist_visuals_job(job)
                    result=recheck_project(project,lambda message:self._log(job_id,message),find_more=job.get('find_more',False),only_entity=job.get('entity'))
                self._update(job_id,status='complete',progress=100,stage='Research finished. Review available choices and any unmatched subjects.',result=result)
            except (Exception,SystemExit) as error:
                from hinglish_visuals.recovery import pause_project
                try:pause_project(project)
                except Exception:pass
                from .user_messages import problem
                issue=problem(error,feature='Smart Visuals')
                self._update(job_id,status='failed',stage=issue['message'],error=issue['message'],error_details=issue['details'])
        threading.Thread(target=run,daemon=True).start()

    @property
    def cinematic(self):
        # Resolve the beat service before taking this non-reentrant state lock.
        beats = self.beats
        with self.lock:
            if self._cinematic is None:
                from hinglish_cinematic.service import CinematicService
                self._cinematic = CinematicService(self.root, beats, self.work_lock)
            return self._cinematic

    @property
    def beats(self):
        with self.lock:
            if self._beats is None:
                from hinglish_beats.service import BeatService
                self._beats = BeatService(self.root, self.work_lock)
            return self._beats

    @property
    def publisher(self):
        browser=self.local_browser
        with self.lock:
            if self._publisher is None:
                from hinglish_publish.service import Publisher
                self._publisher = Publisher(self.root,browser=browser)
            return self._publisher

    def license_for(self,edition):
        if self.license_client is None:return None
        if edition not in ('desktop','plugins'):raise ValueError('Choose Desktop or Editor Plugins.')
        with self.lock:
            if edition not in self.license_clients:
                from hinglish_license.client import LicenseClient
                original=self.license_client
                self.license_clients[edition]=LicenseClient(original.folder,original.origin,original.public_key,edition)
            return self.license_clients[edition]

    @property
    def assistant(self):
        with self.lock:
            if self._assistant is None:
                from .assistant import Assistant
                self._assistant = Assistant(self)
            return self._assistant

    @property
    def local_browser(self):
        with self.lock:
            if self._local_browser is None:
                from hinglish_publish.local_browser import LocalBrowser
                self._local_browser = LocalBrowser(self.root)
            return self._local_browser

    @property
    def scheduled_posts(self):
        with self._scheduled_lock:
            if self._scheduled_posts is None:
                from .scheduled_posts import ScheduledPosts
                self._scheduled_posts=ScheduledPosts(self)
            return self._scheduled_posts

    def publish_bridge(self):
        bridge = self.root / 'cache' / 'app' / 'bridge.json'
        bridge.parent.mkdir(parents=True, exist_ok=True)
        bridge.write_text(json.dumps({'url': f'http://127.0.0.1:{self.port}', 'token': self.token,
                                      'root': str(self.root)}, indent=2), encoding='utf-8')

    def pick(self, kind):
        # The bundled Python runtime does not ship Tcl/Tk. On Windows use the
        # native WinForms picker in its own STA process; no browser upload or
        # copy is involved, and the server receives the selected local path.
        if os.name == 'nt':
            powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / \
                'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
            if not powershell.is_file():
                powershell = Path(shutil.which('powershell.exe') or shutil.which('pwsh.exe') or '')
            if not powershell.is_file():
                raise RuntimeError('Windows PowerShell is unavailable')
            files = {'videos': ('Choose videos', 'Videos|*.mp4;*.mov;*.mxf;*.mkv;*.avi;*.mts;*.m2ts;*.webm'),
                     'script': ('Choose your script', 'Text files (*.txt)|*.txt|All files (*.*)|*.*'),
                     'xml': ('Choose a timeline XML', 'Timeline XML (*.xml)|*.xml|All files (*.*)|*.*'),
                     'handoff-video': ('Choose video', 'Video|*.mp4;*.mov;*.mxf;*.avi;*.m4v;*.mkv;*.webm'),
                     'handoff-aep': ('Choose After Effects project', 'After Effects project (*.aep)|*.aep'),
                     'references': ('Choose pictures / videos of the look you want',
                                    'Pictures and videos (*.jpg;*.jpeg;*.png;*.webp;*.mp4;*.mov;*.webm)|'
                                    '*.jpg;*.jpeg;*.png;*.webp;*.mp4;*.mov;*.webm|All files (*.*)|*.*')}
            many = kind in ('references', 'videos')  # several files: one path per line
            chooser = (
                "$dialog=New-Object System.Windows.Forms.OpenFileDialog;"
                f"$dialog.Title='{files[kind][0]}';"
                f"$dialog.Filter='{files[kind][1]}';"
                f"$dialog.Multiselect=${'true' if many else 'false'};"
                "$selected={ if($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK)"
                + ("{ $dialog.FileNames -join [Environment]::NewLine } else { '' } };" if many else
                   "{ $dialog.FileName } else { '' } };")
            ) if kind in files else (
                "$dialog=New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$dialog.Description='Choose folder containing your videos';"
                "$dialog.ShowNewFolderButton=$false;"
                "$selected={ if($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK)"
                "{ $dialog.SelectedPath } else { '' } };"
            )
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false);"
                "$owner=New-Object System.Windows.Forms.Form;"
                "$owner.TopMost=$true;$owner.ShowInTaskbar=$false;"
                "$owner.Width=1;$owner.Height=1;$owner.Opacity=0;$owner.Show();$owner.Activate();"
                + chooser +
                "try { $path=& $selected; if($path){[Console]::Write($path)} }"
                "finally { $dialog.Dispose();$owner.Close();$owner.Dispose() }"
            )
            command = [str(powershell), '-NoProfile', '-STA', '-WindowStyle', 'Hidden', '-Command', script]
        else:
            command = [sys.executable, '-m', 'hinglish_app.picker', kind]
        result = subprocess.run(
            command,
            cwd=self.root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode:
            detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'Windows picker stopped'
            raise RuntimeError(f'Could not open the file picker: {detail}')
        return result.stdout.strip()

    def create_job(self, payload):
        if self.license_client is not None:
            host=payload.get('host')
            edition='plugins' if host in ('premiere','aftereffects','resolve') else 'desktop'
            self.license_for(edition).ensure(host if edition=='plugins' else 'standalone')
        from hinglish_niche.profiles import Profiles, valid_profile
        payload = dict(payload)
        from hinglish_cut.model_preferences import preferences,preferred_device
        if preferences(self.root).get('require_cuda_inference'):
            payload['device']='cuda'
        else:
            payload.setdefault('device',preferred_device(self.root))
        profile = valid_profile(payload.get('profile', 'general'))
        payload['profile'] = profile
        payload['_creator_context'] = Profiles(self.root).context(profile)
        mode = payload.get('mode')
        if mode == 'aivideo':
            from hinglish_aigen.settings import GenSettings
            GenSettings(kind='video', video_method=str(payload.get('aivideo_video_method','generative')),
                        reference=str(payload.get('aivideo_reference','')).strip(),
                        motion_style=str(payload.get('aivideo_motion_style','orbit')),
                        quality=str(payload.get('aivideo_quality','full')))
        if mode == 'thumbnail':
            from hinglish_niche.image_design import settings
            payload={**payload,'thumbnail_design':settings(payload.get('thumbnail_design'))}
            if not str(payload.get('script','')).strip():raise ValueError('Describe the image you want to create first.')
        if mode in ('captions', 'shorts'):
            from hinglish_captions.styles import SELECTABLE_TEMPLATES
            if payload.get('caption_style') not in SELECTABLE_TEMPLATES:
                payload['caption_style'] = 'caption_1'
        if mode not in ('clean', 'script', 'captions', 'shorts', 'gaming', 'thumbnail') + TIMELINE_MODES:
            raise ValueError('Choose Smart Clean, Script Edit, Auto Captions, B-roll, Smart Visuals, Smart Zoom, '
                             'Sound Design, Eye Contact, Long to Shorts, Thumbnail, AI Video or Motion Graphics')
        source_paths = [Path(p).resolve() for p in payload.get('source_paths', []) if p]
        input_path = Path(payload['input_path']).resolve() if payload.get('input_path') else None
        if input_path and not input_path.exists():
            raise FileNotFoundError('The selected video or folder is missing: '+str(input_path))
        timeline_mode = mode in TIMELINE_MODES or mode in ('clean','script')
        if timeline_mode and payload.get('timeline_xml'):
            timeline = Path(payload['timeline_xml']).resolve()
            if not timeline.is_file() or timeline.suffix.lower() != '.xml':
                raise ValueError('The exported timeline XML is unavailable')
            payload = {**payload, 'input_path': str(timeline)}
            input_path, source_paths = timeline, []
        elif timeline_mode and payload.get('use_resolve_timeline'):
            input_path, source_paths = 'resolve', []
        elif timeline_mode and input_path and input_path.is_file() and input_path.suffix.lower() == '.xml':
            pass
        elif mode in (*AI_TOOLS, 'motion', 'thumbnail') and not source_paths and not (input_path and input_path.exists()):
            if not str(payload.get('script', '')).strip():
                raise ValueError('Paste your script (or choose a video / timeline)')
            input_path = None                    # a script alone is enough
        elif source_paths:
            missing=next((p for p in source_paths if not p.is_file()),None)
            if missing:raise FileNotFoundError('The selected video is missing: '+str(missing))
            if any(p.suffix.lower() not in VIDEO_EXTENSIONS for p in source_paths):
                raise ValueError('One of the selected files is not a supported video. Select an MP4, MOV, MKV or another supported video file.')
        elif not input_path:
            raise ValueError('Choose a video or folder before starting this edit.')
        script = str(payload.get('script', '')).strip()
        if mode == 'script' and not script:
            raise ValueError('Paste your script or reference outline')
        job_id = uuid.uuid4().hex[:12]
        job = {'id': job_id, 'mode': mode, 'device':payload.get('device','cpu'),'status': 'queued', 'progress': 0,
               'stage': 'Waiting', 'logs': [], 'created': time.time(), 'result': None}
        if mode=='broll':
            job['recovery_request']={'payload':payload,'paths':[str(p) for p in source_paths],
                'input':str(input_path) if input_path else None,'script':script}
        with self.lock:
            self.jobs[job_id] = job
            self._persist_broll_job(job)
        if mode in ('broll','visuals','sound'):
            from .progress_events import record
            record(self.root,'job',job_id,status='queued',stage='Waiting',progress=0)
        thread = threading.Thread(target=self._run_job,
            args=(job_id, payload, source_paths, input_path, script), daemon=True)
        thread.start()
        return {k:v for k,v in job.items() if k!='recovery_request'}

    def save_upload(self, batch, name, stream, length):
        batch = str(batch or '')
        if not re.fullmatch(r'[A-Za-z0-9-]{6,80}', batch):
            raise ValueError('Invalid upload session')
        name = Path(str(name or '').replace('\\', '/')).name
        if not name or Path(name).suffix.lower() not in VIDEO_EXTENSIONS | {'.png','.jpg','.jpeg','.webp'}:
            raise ValueError('Choose a supported video or image file')
        if length <= 0 or length > 500 * 1024 ** 3:
            raise ValueError('The video file size is invalid')
        folder = self.root / 'cache' / 'app' / 'uploads' / batch
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f'{uuid.uuid4().hex[:8]}-{name}'
        partial = target.with_suffix(target.suffix + '.partial')
        remaining = length
        try:
            with partial.open('wb') as output:
                while remaining:
                    chunk = stream.read(min(4 * 1024 * 1024, remaining))
                    if not chunk:
                        raise ConnectionError('The video upload stopped early')
                    output.write(chunk)
                    remaining -= len(chunk)
            partial.replace(target)
            return target
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

    def _consume_uploads(self, paths):
        upload_root = (self.root / 'cache' / 'app' / 'uploads').resolve()
        batches = set()
        for source in paths:
            source = Path(source).resolve()
            if source.is_relative_to(upload_root) and source.parent.parent == upload_root:
                batches.add(source.parent)
                source.unlink(missing_ok=True)
        for batch in batches:
            shutil.rmtree(batch, ignore_errors=True)

    def _stage_sources(self, job_id, paths):
        if not paths:
            return None
        folder = self.root / 'cache' / 'app' / 'jobs' / job_id / 'media'
        folder.mkdir(parents=True, exist_ok=True)
        for index, source in enumerate(dict.fromkeys(paths)):
            target = folder / f'{index:04d}-{source.name}'
            try:
                os.link(source, target)
            except OSError:
                shutil.copyfile(source, target)
        return folder

    def _update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values)
            self._persist_visuals_job(self.jobs[job_id])
            self._persist_broll_job(self.jobs[job_id])
            if self.jobs[job_id].get('mode')=='sound' and self.jobs[job_id].get('status')=='complete':
                from .completed_sound_jobs import save as save_sound
                save_sound(self.root,getattr(self,'port',DEFAULT_PORT),self.jobs[job_id])
            if self.jobs[job_id].get('mode') in ('broll','visuals','sound'):
                from .progress_events import record
                record(self.root,'job',job_id,**{k:values[k] for k in ('status','stage','progress') if k in values})

    def _log(self, job_id, message):
        clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', message).strip()
        if not clean:
            return
        with self.lock:
            logs = self.jobs[job_id]['logs']
            logs.append(clean)
            del logs[:-120]
            from .user_messages import editing_activity
            self.jobs[job_id]['stage'] = editing_activity(clean,self.jobs[job_id].get('stage','Preparing the video'))
            if self.jobs[job_id].get('mode')=='broll' and re.search(r'Error:|\[WinError|Traceback|Could not|engine stopped',clean,re.I):
                from .user_messages import problem
                self.jobs[job_id]['stage']=problem(clean)['message']
            if self.jobs[job_id].get('visuals_project') and re.search(r'unavailable:|skipped:|Could not|Vision check failed',clean,re.I):
                self.jobs[job_id]['stage']='Some sources are unavailable; checking the remaining options.'
            if self.jobs[job_id].get('mode') in ('broll','visuals','sound'):
                from .progress_events import record
                record(self.root,'job',job_id,stage=self.jobs[job_id]['stage'])
            self._persist_visuals_job(self.jobs[job_id])
            self._persist_broll_job(self.jobs[job_id])

    def _run_job(self, job_id, payload, paths, input_path, script):
        self._update(job_id, stage="Waiting for the current editing task")
        from hinglish_niche.photo_thumbnail import cpu_only
        if cpu_only(self.root,payload,script):
            self._execute_job(job_id,payload,paths,input_path,script)
            return
        from hinglish_cut.gpu_lock import gpu_lock
        from contextlib import nullcontext
        cpu_recovery=False
        if payload['mode']=='broll' and not paths:
            from hinglish_broll.recovery import finalization_only
            cpu_recovery=finalization_only(self.root,payload,input_path)
        with self.work_lock, (nullcontext() if cpu_recovery else gpu_lock(self.root)):
            if payload['mode']!='broll':
                self._execute_job(job_id, payload, paths, input_path, script)
                return
            while self.jobs[job_id].get('recovery_attempts',0)<2:
                self._update(job_id,recovery_attempts=self.jobs[job_id].get('recovery_attempts',0)+1)
                self._execute_job(job_id, payload, paths, input_path, script)
                job=self.jobs[job_id]
                marker=self.root/'cache/app/jobs'/job_id/'broll-checkpoint.json'
                # Wrong inputs, disk exhaustion and subscription failures need
                # attention, not another heavy run. A worker crash with saved
                # progress gets one automatic continuation.
                if job['status']!='failed' or not marker.is_file() or job.get('error_code') in (
                        'disk_full','subscription_required','media_missing','file_missing'):
                    break
                if job.get('recovery_attempts',0)>=2:break
                self._log(job_id,'The B-roll worker stopped. Continuing once from saved progress.')
                request=job['recovery_request']
                payload,paths,input_path,script=request['payload'],[Path(p) for p in request['paths']],Path(request['input']) if request['input'] else None,request['script']
                self._update(job_id,status='running',stage='Recovering saved B-roll work',progress=3)
            if self.jobs[job_id]['status']=='failed' and (self.root/'cache/app/jobs'/job_id/'broll-checkpoint.json').is_file():
                from .user_messages import problem
                issue=problem('B-roll recovery paused')
                self._update(job_id,stage=issue['message'],error_code=issue['code'])

    def _execute_job(self, job_id, payload, paths, input_path, script):
        usage_started=time.monotonic()
        try:
            staged = self._stage_sources(job_id, paths)
            if payload['mode']=='broll' and staged:
                self._update(job_id,recovery_request={'payload':payload,'paths':[], 'input':str(staged),'script':script})
            if staged:
                self._consume_uploads(paths)
            supplied = staged or input_path
            work = self.root / 'cache' / 'app' / 'jobs' / job_id
            work.mkdir(parents=True, exist_ok=True)
            context_file = work / 'creator-context.json'
            from hinglish_niche.profiles import Profiles
            context_file.write_text(json.dumps(payload.get('_creator_context', Profiles(self.root).context(payload.get('profile'))), ensure_ascii=False), encoding='utf-8')
            manual_sound=payload['mode']=='sound' and payload.get('panel_sound_action')=='recommend'
            if payload['mode']=='sound' and payload.get('panel_sound_action') not in (None,'recommend','auto'):
                raise ValueError('Choose sound suggestions or automatic sound design.')
            fmt = payload.get('format', 'source')
            command = [str(self.python_executable), '-u']
            if supplied == 'resolve':
                from .resolve_adapter import export_current_timeline
                supplied = export_current_timeline(work / 'resolve-timeline.xml')
                self._log(job_id, 'Exported the current Resolve timeline')
            cut_timeline=None
            if payload['mode'] in ('clean','script') and supplied and Path(supplied).suffix.lower()=='.xml':
                from .timeline_cut import prepare
                cut_timeline=Path(supplied)
                supplied=prepare(cut_timeline,work,lambda text:self._log(job_id,text))
                fmt='source'
            if payload['mode'] in TIMELINE_MODES and supplied and Path(supplied).suffix.lower() == '.xml':
                fmt = 'source'   # an existing sequence keeps its own canvas
            if payload['mode'] == 'gaming':
                minutes = int(payload.get('target_minutes', 15))
                if not 1 <= minutes <= 30:
                    raise ValueError('Highlights target must be 1-30 minutes')
                command += ['-m', 'hinglish_niche', 'gaming', '--root', str(self.root),
                            '--input', str(supplied), '--minutes', str(minutes), '--device', payload.get('device', 'cpu')]
                if payload.get('memes') is False:
                    command.append('--no-memes')
            elif payload['mode'] == 'thumbnail':
                story = work / 'thumbnail-story.txt'
                story.write_text(script, encoding='utf-8')
                command += ['-m', 'hinglish_niche', 'thumbnail', '--root', str(self.root), '--script', str(story)]
                design=work/'image-design.json'
                design.write_text(json.dumps(payload['thumbnail_design'],ensure_ascii=False),encoding='utf-8')
                command += ['--design',str(design)]
                for key in ('portrait', 'background', 'reference'):
                    if payload.get(key):
                        picture = Path(payload[key]).resolve()
                        if not picture.is_file() or picture.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                            raise ValueError('Attach a supported thumbnail picture')
                        command += ['--' + key, str(picture)]
                command.append('--generate' if payload.get('generate_background', True) else '--no-generate')
            elif payload['mode'] == 'broll':
                command += ['-m', 'hinglish_broll', '--root', str(self.root), '--input', str(supplied),
                            '--density', payload.get('density', 'medium'), '--device', payload.get('device', 'cpu')]
                if payload.get('broll_black_background'):command.append('--black-background')
                if payload.get('broll_review_options'):
                    command.append('--review-options')
                    method=payload.get('broll_search_method','website')
                    if method!='website':raise ValueError('B-roll now uses website search and human review. Reopen Add B-roll to continue.')
                    from hinglish_broll.choice_policy import choice_limit
                    options=choice_limit(payload.get('broll_options_per_moment'),payload.get('broll_orientation'),output_format=fmt)
                    command+=['--options-per-moment',str(options)]
                    orientation=payload.get('broll_orientation')
                    if orientation is not None:
                        if orientation not in ('vertical','horizontal'):raise ValueError('Choose Vertical or Horizontal.')
                        command+=['--orientation',orientation]
                count=payload.get('broll_count',0)
                if type(count) is not int or not 0<=count<=30:
                    raise ValueError('Choose a B-roll count between 1 and 30, or leave it blank for automatic coverage.')
                if count:command+=['--count',str(count)]
                brief=str(payload.get('broll_brief') or '').strip()
                if len(brief)>1200:raise ValueError('Shorten the B-roll direction to 1200 characters and try again.')
                if brief:command+=['--brief',brief]
                if script:
                    if len(script)>20000:raise ValueError('Shorten the reference script to 20,000 characters and try again.')
                    script_file=work/'broll-reference-script.txt'
                    script_file.write_text(script,encoding='utf-8')
                    command+=['--reference-script',str(script_file)]
            elif payload['mode'] == 'visuals':
                command += ['-m', 'hinglish_visuals', '--root', str(self.root), '--input', str(supplied),
                            '--device', payload.get('device', 'cpu')]
                for key, allowed in VISUALS_CHOICES.items():
                    value = payload.get(key, allowed[0])
                    if value not in allowed:
                        raise ValueError(f'Unknown {key.replace("_", " ")}: {value}')
                    command += ['--' + key.split('_', 1)[1], value]
                if payload.get('visuals_options_per_moment') is not None:
                    count=payload['visuals_options_per_moment']
                    if type(count) is not int or count not in (2,5):raise ValueError('Choose two long-form or five short-form image options.')
                    command += ['--options-per-moment',str(count)]
                if payload.get('visuals_popups') is False:
                    command.append('--no-popups')
                if payload.get('visuals_black_background'):
                    command.append('--black-background')
                from .visuals_search_dispatch import arguments as visuals_search_arguments
                command += visuals_search_arguments(payload)
                if script:
                    script_file = work / 'visuals-script.txt'
                    script_file.write_text(script, encoding='utf-8')
                    command += ['--script', str(script_file)]
            elif payload['mode'] == 'sound':
                script_file = work / 'sound-script.txt'
                if manual_sound:
                    from .panel_sound_worker import command as recommendation_command
                    script_file.write_text(script, encoding='utf-8')
                    command+=recommendation_command(self.root,supplied,script_file,context_file,job_id,payload.get('density','medium'))
                else:
                    command += ['-m', 'hinglish_sound', '--root', str(self.root), '--input', str(supplied),
                                '--device', payload.get('device', 'cpu')]
                    command.append('--keep-source-audio')
                    content_form=payload.get('sound_content_form','auto')
                    if content_form not in ('auto','short','long'):raise ValueError('Choose Auto, Short-form or Long-form sound design.')
                    command+=['--content-form',content_form]
                    for key, allowed in SOUND_CHOICES.items():
                        value = payload.get(key, allowed[0] if key == 'sound_style' else 'medium')
                        if value not in allowed:raise ValueError(f'Unknown {key.replace("_", " ")}: {value}')
                        command += ['--' + key.split('_', 1)[1], value]
                    for key, flag in (('sound_music', '--no-music'), ('sound_effects', '--no-effects'),
                                      ('sound_transitions', '--no-transitions'), ('sound_layered', '--restrained')):
                        if payload.get(key) is False:command.append(flag)
                    if script:
                        script_file.write_text(script, encoding='utf-8');command += ['--script', str(script_file)]
            elif payload['mode'] == 'eyecontact':
                command += ['-m', 'hinglish_eyecontact', '--root', str(self.root), '--input', str(supplied)]
                for key, flag in (('eye_reach', '--reach'), ('eye_size', '--eye-size')):
                    value = str(payload.get(key, EYE_CHOICES[key][0]))
                    if value not in EYE_CHOICES[key]:
                        raise ValueError(f'Unknown {key.replace("_", " ")}: {value}')
                    command += [flag, value]
                if payload.get('eye_look_away') is False:
                    command.append('--no-look-away')
            elif payload['mode'] == 'zoom':
                command += ['-m', 'hinglish_zoom', '--root', str(self.root), '--input', str(supplied),
                            '--device', payload.get('device', 'cpu')]
                for key, allowed in ZOOM_CHOICES.items():
                    value = payload.get(key, allowed[0] if key == 'zoom_style' else 'medium')
                    if value not in allowed:
                        raise ValueError(f'Unknown {key.replace("_", " ")}: {value}')
                    command += ['--' + key.split('_', 1)[1], value]
                if payload.get('zoom_face') is False:
                    command.append('--no-face')
                if payload.get('zoom_jump_cuts') is True:
                    command.append('--jump-cuts')
                for key,flag in (('zoom_sounds','--sounds'),('zoom_overlays','--cut-overlays')):
                    if key in payload and type(payload[key]) is not bool:
                        raise ValueError('Choose on or off for SmartZoom sounds and cut overlays.')
                    if payload.get(key) is True:command.append(flag)
            elif payload['mode'] in AI_TOOLS:
                # AI Images and AI Video are separate tools: each reads its own settings (aiimage_* / aivideo_*)
                mode = payload['mode']
                command += ['-m', AI_TOOLS[mode], '--root', str(self.root)]
                if mode=='aiimage':
                    for field,choices in (('request_mode',('script','idea')),('channel',('auto','general','gaming','cricket')),('purpose',('scene','thumbnail','background'))):
                        value=str(payload.get('aiimage_'+field,choices[0]))
                        if value not in choices:raise ValueError('Choose valid AI image settings and try again.')
                        command += ['--'+field.replace('_','-'),value]
                if mode=='aivideo':
                    for field,choices in (('video_method',('generative','reference','motion')),('motion_style',('orbit','gsap','product','explainer','studio')),('quality',('full','preview'))):
                        value=str(payload.get('aivideo_'+field,choices[0]))
                        if value not in choices:raise ValueError('AI Video settings invalid: select an available method, motion style and quality.')
                        command += ['--'+field.replace('_','-'),value]
                    reference=str(payload.get('aivideo_reference') or '').strip()
                    if len(reference)>2048:raise ValueError('AI Video reference unsupported: choose one reference video.')
                    if payload.get('aivideo_video_method')=='reference' and not reference:
                        raise ValueError('AI Video reference missing: choose a local video or public YouTube link.')
                    if reference:command += ['--reference',reference]
                if supplied:
                    command += ['--input', str(supplied)]
                for key, allowed in AI_CHOICES.items():
                    value = str(payload.get(f'{mode}_{key}', allowed[0]))
                    if key == 'count' and value.isdigit() and 1 <= int(value) <= 60:
                        pass
                    elif value not in allowed:
                        raise ValueError(f'Unknown {key}: {value}')
                    command += ['--' + key, value]
                style = str(payload.get(f'{mode}_style') or 'cinematic')
                if len(style) > 60 or '\n' in style:
                    raise ValueError('Unknown style')
                command += ['--style', style]
                custom = str(payload.get(f'{mode}_custom_style') or '').strip()
                if custom:
                    command += ['--custom-style', custom[:400].replace('\n', ' ')]
                options = str(payload.get(f'{mode}_options', '2' if mode == 'aiimage' else '1'))
                if options not in ('1', '2', '3', '4'):
                    raise ValueError('Options per moment: 1-4')
                command += ['--options', options]
                if payload.get(f'{mode}_check') is False:
                    command.append('--no-check')
                if mode == 'aivideo' and payload.get('aivideo_from_text') is True:
                    command.append('--from-text')
                if script:
                    script_file = work / f'{mode}-script.txt'
                    script_file.write_text(script, encoding='utf-8')
                    command += ['--script', str(script_file)]
            elif payload['mode'] == 'motion':
                command += ['-m', 'hinglish_motion', '--root', str(self.root)]
                if payload.get('motion_object_continue'):
                    saved=Path(str(payload['motion_object_continue'])).resolve()
                    if not saved.is_relative_to(self.root/'output/motion') or not (saved/'shared-graphs.json').is_file():raise ValueError('Object motion invalid: select the saved object film.')
                    command += ['--object-motion-continue',str(saved)]
                if payload.get('motion_object_script'):
                    source=Path(str(payload['motion_object_script'])).resolve()
                    if not source.is_relative_to(self.root/'output/motion') or source.name!='script.json' or not source.is_file():raise ValueError('Object motion invalid: use the saved script from this comparison.')
                    command += ['--object-motion-script',str(source)]
                if payload.get('motion_compare_script_image'):
                    image=Path(str(payload['motion_compare_script_image'])).resolve()
                    if not image.is_file() or image.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise ValueError('Motion comparison invalid: select an existing script image.')
                    seconds=float(payload.get('motion_compare_seconds',50))
                    if not 5<=seconds<=180:raise ValueError('Motion comparison invalid: choose 5 to 180 seconds.')
                    command += ['--compare-script-image',str(image),'--compare-seconds',str(seconds)]
                    if payload.get('motion_compare_correction'):
                        previous=Path(str(payload['motion_compare_correction'])).resolve()
                        if not previous.is_relative_to(self.root/'output/motion') or not (previous/'local-qwen-plan.json').is_file():raise ValueError('Motion comparison invalid: select the saved original comparison.')
                        command += ['--compare-correction',str(previous)]
                if payload.get('motion_reference'):
                    reference=Path(str(payload['motion_reference'])).resolve()
                    if not reference.is_file() or reference.suffix.lower() not in ('.mp4','.mov','.mkv','.webm'):
                        raise ValueError('Motion reference unavailable: select one local reference video.')
                    command += ['--reference',str(reference)]
                    if payload.get('motion_sounds_folder'):
                        sounds=Path(str(payload['motion_sounds_folder'])).resolve()
                        if not sounds.is_dir():raise ValueError('Motion reference sound unavailable: select an existing sound folder.')
                        command += ['--sounds-folder',str(sounds)]
                if supplied:
                    command += ['--input', str(supplied)]
                for key, allowed in MOTION_CHOICES.items():
                    value = str(payload.get(key, allowed[0]))
                    if key == 'motion_count' and value.isdigit() and 1 <= int(value) <= 60:
                        pass
                    elif value not in allowed:
                        raise ValueError(f'Unknown {key.replace("_", " ")}: {value}')
                    command += ['--' + key.split('_', 1)[1], value]
                style = str(payload.get('motion_style', 'theme:studio'))
                if not re.fullmatch(r'(theme:[a-z]+|card:card_[a-z0-9_]+)', style):
                    raise ValueError('Unknown motion style')
                command += ['--style', style]
                if script:
                    script_file = work / 'motion-script.txt'
                    script_file.write_text(script, encoding='utf-8')
                    command += ['--script', str(script_file)]
            elif payload['mode'] == 'shorts':
                command += ['-m', 'hinglish_shorts', '--root', str(self.root), '--input', str(supplied),
                            '--device', payload.get('device', 'cpu')]
                if payload.get('shorts_fresh') is True:command += ['--fresh']
                for key, allowed in SHORTS_CHOICES.items():
                    value = str(payload.get(key, allowed[0]))
                    if key == 'shorts_count' and value.isdigit() and 1 <= int(value) <= 40:
                        pass
                    elif value not in allowed:
                        raise ValueError(f'Unknown {key.replace("_", " ")}: {value}')
                    command += ['--' + key.split('_', 1)[1], value]
                for key, flag, limit in (('shorts_min', '--min', 120), ('shorts_max', '--max', 120)):
                    if payload.get(key) not in (None, ''):
                        value = float(payload[key])
                        if not 5 <= value <= limit:
                            raise ValueError('Short length must be 5-120 seconds')
                        command += [flag, f'{value:g}']
                for key, flag in (('shorts_title', '--title'), ('shorts_handle', '--handle'), ('shorts_cta', '--cta'),
                                  ('shorts_from', '--start'), ('shorts_to', '--end')):
                    value = str(payload.get(key) or '').strip()
                    if value:
                        if len(value) > 120 or '\n' in value:
                            raise ValueError(f'{key.replace("_", " ")} is too long')
                        command += [flag, value]
                if payload.get('shorts_captions') is True:
                    command += ['--captions', '--caption-style', str(payload.get('caption_style', 'caption_1'))]
                if script:
                    script_file = work / 'shorts-script.txt'
                    script_file.write_text(script, encoding='utf-8')
                    command += ['--script', str(script_file)]
            elif payload['mode'] == 'clean':
                command += ['-m', 'hinglish_clean', '--root', str(self.root), '--input', str(supplied)]
                if not payload.get('preview', True):
                    command.append('--xml-only')
            elif payload['mode'] == 'script':
                script_file = work / 'script.txt'
                script_file.write_text(script, encoding='utf-8')
                command += ['-m', 'hinglish_semantic', 'assemble', '--root', str(self.root),
                            '--input', str(supplied), '--script', str(script_file),
                            '--pacing', payload.get('pacing', 'natural')]
                if payload.get('device') == 'cuda':
                    command += ['--device', 'cuda']
            else:
                command += ['-m', 'hinglish_captions', '--root', str(self.root), '--input', str(supplied),
                            '--style', payload.get('caption_style', 'caption_1'),
                            '--device', payload.get('device', 'cpu'),
                            '--content',payload.get('caption_content','speech')]
                if payload.get('preview',True):command.append('--preview')
                if script:
                    script_file = work / 'caption-reference.txt'
                    script_file.write_text(script, encoding='utf-8')
                    command += ['--script', str(script_file)]
            if fmt in ('instagram_vertical', 'square', 'youtube_horizontal') and not manual_sound:
                command += ['--format', fmt]
            from .visuals_search_dispatch import method as visuals_search_method
            manual_visuals=payload['mode']=='visuals' and visuals_search_method(payload)=='website'
            if payload.get('quality_check', True) and payload['mode'] not in ('gaming', 'thumbnail') and not manual_sound and not manual_visuals:
                # every feature runs under the quality evaluator: rules checked, failures redone with corrections
                command = command[:2] + ['-m', 'hinglish_eval', 'run', '--root', str(self.root),
                                         '--attempts', str(QUALITY_ATTEMPTS), '--'] + command[2:]
            self._update(job_id, status='running', progress=3, stage='Starting local AI')
            worker_env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'HINGLISH_CREATOR_CONTEXT_FILE': str(context_file),
                     'STORYLENS_REFERENCE_FEATURE': payload['mode'],
                     **({'STORYLENS_GPU_LOCK_HELD':str(self.root.resolve())} if payload['mode']=='aivideo' else {}),
                     **({'STORYLENS_VISUALS_CHECKPOINT':str(work/'visuals-checkpoint.json')} if payload['mode']=='visuals' else {}),
                     **({'STORYLENS_BROLL_CHECKPOINT':str(work/'broll-checkpoint.json')} if payload['mode']=='broll' else {}),
                     **({'HINGLISH_EDITION':'plugins' if payload.get('host') in ('premiere','aftereffects','resolve') else 'desktop'} if self.license_client else {})}
            from hinglish_cut.gpu_lock import held_by_current_thread,child_environment
            if held_by_current_thread(self.root):
                worker_env=child_environment(self.root,worker_env)
            process = subprocess.Popen(command, cwd=self.engine_root, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                env=worker_env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            license_stop=threading.Event();license_failure=[]
            if self.license_client:
                edition='plugins' if payload.get('host') in ('premiere','aftereffects','resolve') else 'desktop'
                def verify_running_license():
                    while not license_stop.wait(30):
                        if process.poll() is not None:return
                        try:self.license_for(edition).ensure(payload.get('host') if edition=='plugins' else 'standalone')
                        except Exception:
                            license_failure.append('Editing stopped because this computer could not verify its subscription. Reconnect or contact Support.')
                            if process.poll() is None:
                                if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                                else:process.terminate()
                            return
                threading.Thread(target=verify_running_license,name='license-watchdog',daemon=True).start()
            result_page = None
            line_count = 0
            engine_tail=[]
            for line in process.stdout:
                engine_tail.append(line.rstrip())
                del engine_tail[:-50]
                line_count += 1
                self._log(job_id, line)
                match = re.search(r'Results:\s*(.+?)(?:\s*$)', line)
                if match:
                    result_page = Path(match.group(1).strip())
                self._update(job_id, progress=min(94, 5 + line_count // 2))
            code = process.wait()
            license_stop.set()
            if license_failure:raise RuntimeError(license_failure[0])
            if payload['mode']=='visuals' and code not in (0,2):
                from .visual_clarification import read as visual_question, message as visual_question_message
                clarification=visual_question(self.root,job_id)
                if clarification:
                    from .user_messages import diagnostics
                    self._update(job_id,status='failed',progress=100,needs_input=True,
                        stage=visual_question_message(clarification),error_code='visuals_clarification_required',
                        error_details=diagnostics('\n'.join(engine_tail)),clarification=clarification)
                    return
            if payload['mode']=='visuals' and (code not in (0,2) or not result_page or not result_page.exists()):
                from hinglish_visuals.recovery import resumable_projects
                from hinglish_visuals.references import recheck_project
                saved=resumable_projects(work/'visuals-checkpoint.json',self.root)
                for project in saved:
                    self._log(job_id,'The research worker stopped. Continuing once from saved searches and checks; not restarting the video.')
                    try:
                        recheck_project(project,lambda message:self._log(job_id,message))
                    except Exception as error:
                        self._log(job_id,'Some research is unfinished. Your saved review remains available.')
                        self._log(job_id,str(error))
                    if (project.parent/'report.html').is_file():
                        result_page=project.parent/'report.html'
                        code=2
            if code not in (0, 2) or not result_page or not result_page.exists():
                error=RuntimeError(f'Editing engine stopped with code {code}. Check the activity log.')
                error.stderr='\n'.join(engine_tail)
                raise error
            output = result_page.parent
            # source-timeline.xml is B-roll's internal copy of a single video, not a result.
            xml = [str(p.resolve()) for p in output.rglob('*.xml') if p.name != 'source-timeline.xml']
            if payload['mode']=='visuals':xml=[p for p in xml if Path(p).name=='VISUALS_SEQUENCE.xml']
            if cut_timeline:
                from .timeline_cut import remap
                restored=[]
                for file in [p for p in xml if Path(p).name in ('timeline.xml','EDITED_SEQUENCE.xml')]:
                    target=Path(file).with_name(Path(file).stem+'-SOURCE-TIMELINE.xml')
                    restored.append(remap(cut_timeline,supplied,file,target))
                xml=restored
            previews = [str(p.resolve()) for p in output.rglob('preview.mp4')]
            previews += [str(p.resolve()) for p in output.rglob('cleaned.mp4')]
            previews += [str(p.resolve()) for p in output.rglob('MOTION_GRAPHICS.mp4')]
            previews += [str(p.resolve()) for p in output.rglob('GAMING_HIGHLIGHTS.mp4')]
            previews += [str(p.resolve()) for p in output.rglob('captioned-preview.mp4')]
            quality = output / 'quality-check.html'
            result = {'page': str(result_page.resolve()), 'folder': str(output.resolve()),
                      'xml_files': xml, 'previews': previews,
                      'quality': str(quality.resolve()) if quality.is_file() else None,
                      'quality_summary': quality_summary(output)}
            if payload['mode']=='broll':
                from .broll_preview_result import collect as broll_previews
                result.update(broll_previews(self.root,output))
            if cut_timeline and not xml:result['review_required']=True
            if manual_sound:
                analysis=json.loads((output/'result.json').read_text('utf-8'))
                manifest=Path(analysis['manifest']).resolve()
                if (analysis.get('status') not in ('ready','no_match') or analysis.get('rendered') is not False
                        or manifest.parent!=output.resolve() or manifest.name!='manifest.json' or not manifest.is_file()):
                    raise ValueError('The sound recommendation receipt does not match this saved review. Analysis is kept.')
                import hashlib
                result.update(review_required=True,sound_recommendations={'status':analysis['status'],
                    'manifest_path':str(manifest),'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()})
            if payload['mode']=='broll':
                projects=[json.loads(p.read_text(encoding='utf-8')) for p in output.rglob('broll-project.json')]
                slots=[s for p in projects for s in p.get('slots',[])]
                filled=sum(bool(s.get('chosen') and s.get('clip')) for s in slots)
                expected=sum(max(len(p.get('slots',[])),p.get('requested_count',0)) for p in projects)
                result['broll_summary']={'filled':filled,'moments':expected,
                    'review_options':any(p.get('review_options') for p in projects),
                    'options':sum(len(s.get('options',[])) for s in slots)}
                result['review_required']=not filled or filled<expected
            if payload['mode']=='visuals':
                projects=[json.loads(p.read_text('utf-8')) for p in output.rglob('visuals-project.json')]
                from .visuals_search_dispatch import summary as visuals_summary
                result['visuals_summary']=visuals_summary(projects)
                result['review_required']=result['visuals_summary']['review_options']
            if payload['mode'] == 'gaming':
                projects = [json.loads(p.read_text(encoding='utf-8')) for p in output.rglob('gaming-project.json')]
                passed = bool(projects) and all(p['quality']['passed'] for p in projects)
                result['quality_summary'] = {'score': 100 if passed else 0, 'passed': passed,
                    'failed': [] if passed else ['Gaming output validation'], 'attempts': 1, 'used': 1}
            if payload['mode'] == 'thumbnail':
                result['images'] = [str(p.resolve()) for p in output.glob('thumbnail-*.png')]
                result['image_urls']=['/thumbnail-output/'+p.resolve().relative_to((self.root/'output/thumbnails').resolve()).as_posix() for p in sorted(output.glob('thumbnail-*.png'))]
                result['thumbnail_design']=payload['thumbnail_design']
            result['media'] = [str(p.resolve()) for p in output.rglob('*') if p.is_file()
                               and p.suffix.lower() in ('.mp4','.wav','.png','.jpg','.jpeg')]
            self._update(job_id, status='complete', progress=100, stage='Ready to review', result=result)
        except BaseException as error:
            self._log(job_id, str(error))
            from .user_messages import problem
            feature={'clean':'Smart Clean','script':'Script editing','captions':'Captions','shorts':'Long to Shorts',
                'gaming':'Gaming highlights','broll':'B-roll','visuals':'Smart Visuals','zoom':'Smart Zoom',
                'sound':'Sound design','eyecontact':'Eye contact','aiimage':'AI images','aivideo':'AI video',
                'motion':'Motion graphics','thumbnail':'Thumbnail creation'}.get(payload.get('mode'),'Editing')
            issue=problem(error,feature=feature)
            self._update(job_id,status='failed',stage=issue['message'],error_code=issue['code'],error_details=issue['details'],progress=100)
        finally:
            if self.license_client and payload.get('mode') in ('clean','script','captions','broll','visuals','zoom','sound','eyecontact','shorts','aiimage','aivideo','motion'):
                client=self.license_for('plugins' if payload.get('host') in ('premiere','aftereffects','resolve') else 'desktop')
                with self.lock:outcome='complete' if self.jobs[job_id]['status']=='complete' else 'failed'
                threading.Thread(target=client.report_usage,args=(payload['mode'],outcome,time.monotonic()-usage_started),daemon=True).start()

    def snapshot(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError(job_id)
            return json.loads(json.dumps({k:v for k,v in self.jobs[job_id].items() if k!='recovery_request'}))

    def open_path(self, path):
        target = Path(path).resolve()
        allowed = (self.root / 'output').resolve()
        if not target.is_relative_to(allowed) or not target.exists():
            raise ValueError('Only generated output can be opened')
        for feature,prefix in (('captions','caption-output'),('broll','broll-output'),('visuals','visuals-output'),('thumbnails','thumbnail-output'),('sound','sound-output')):
            generated=(self.root/'output'/feature).resolve()
            if target.name=='report.html' and target.is_relative_to(generated):
                import webbrowser
                webbrowser.open(f'http://127.0.0.1:{self.port}/{prefix}/'+quote(target.relative_to(generated).as_posix(),safe='/'))
                return
        os.startfile(target)

    def import_into_resolve(self, paths):
        from .resolve_adapter import import_timelines
        allowed = (self.root / 'output').resolve()
        timelines = []
        for value in paths:
            path = Path(value).resolve()
            if not path.is_relative_to(allowed) or not path.is_file() or path.suffix.lower() != '.xml':
                raise ValueError('Only generated XML timelines can be imported')
            timelines.append(str(path))
        if not timelines:
            raise ValueError('No XML timeline was generated')
        return import_timelines(timelines)

    def rebuild_captions(self, payload):
        from hinglish_captions.project import rebuild_project
        project = Path(payload.get('project_path', '')).resolve()
        allowed = (self.root / 'output' / 'captions').resolve()
        if not project.is_relative_to(allowed) or project.name != 'caption-project.json' or not project.is_file():
            raise ValueError('This caption project is unavailable')
        if payload.get('save_project_only') is True:
            return rebuild_project(project,payload,lambda _:None)
        # CPU caption composition/H.264 encoding does not use the shared GPU.
        # Keep it independent of long-running visual-model jobs.
        caption_data = json.loads(project.read_text(encoding='utf-8'))
        if caption_data.get('transcription', {}).get('device', 'cpu') != 'cuda':
            return rebuild_project(project,payload,lambda _:None)
        from hinglish_cut.gpu_lock import gpu_lock
        with gpu_lock(self.root):return rebuild_project(project,payload,lambda _:None)

    def rebuild_broll(self, payload):
        from hinglish_broll.pipeline import rebuild_project
        project = Path(payload.get('project_path', '')).resolve()
        allowed = (self.root / 'output' / 'broll').resolve()
        if not project.is_relative_to(allowed) or project.name != 'broll-project.json' or not project.is_file():
            raise ValueError('This B-roll project is unavailable')
        choices = payload.get('choices') or {}
        if not isinstance(choices, dict) or not all(isinstance(v, str) for v in choices.values()):
            raise ValueError('Invalid B-roll choices')
        black=payload.get('black_background')
        if black is not None and type(black) is not bool:raise ValueError('Choose on or off for the audio-only preview.')
        with self.work_lock:
            return rebuild_project(project, choices, edits=payload.get('edits'),black_background=black)

    def rebuild_visuals(self, payload):
        from hinglish_visuals.pipeline import rebuild_project
        project = Path(payload.get('project_path', '')).resolve()
        allowed = (self.root / 'output' / 'visuals').resolve()
        if not project.is_relative_to(allowed) or project.name != 'visuals-project.json' or not project.is_file():
            raise ValueError('This Smart Visuals project is unavailable')
        choices = payload.get('choices') or {}
        if not isinstance(choices, dict) or not all(isinstance(v, str) for v in choices.values()):
            raise ValueError('Invalid visual choices')
        if not self.work_lock.acquire(blocking=False):
            raise ValueError('Visual research is still running. Your selections are kept. Wait for research to finish, then press Save & rebuild.')
        try:
            return rebuild_project(project, choices)
        finally:self.work_lock.release()

    def recheck_visuals(self, payload):
        project=Path(payload.get('project_path','')).resolve()
        allowed=(self.root/'output/visuals').resolve()
        if not project.is_relative_to(allowed) or project.name!='visuals-project.json' or not project.is_file():
            raise ValueError('This Smart Visuals project is unavailable')
        entity=payload.get('entity') or None
        if entity is not None and (not isinstance(entity,str) or entity not in json.loads(project.read_text('utf-8')).get('entities',{})):
            raise ValueError('Choose a keyword from this Smart Visuals project')
        job_id=uuid.uuid4().hex[:12]
        with self.lock:
            existing=next((j for j in self.jobs.values() if j.get('visuals_project')==str(project)
                and j.get('status') in ('queued','running')),None)
            if existing:return {'job_id':existing['id']}
            self.jobs[job_id]={'id':job_id,'status':'queued','stage':'Waiting for the current local editing task to finish',
                'progress':0,'logs':[],'result':None,'visuals_project':str(project),'find_more':True,'entity':entity}
            self._persist_visuals_job(self.jobs[job_id])
        self._start_visuals_research(job_id,project)
        return {'job_id':job_id}

    def aigen_status(self):
        from hinglish_aigen.engine import doctor
        from hinglish_aigen.settings import all_styles
        from hinglish_aivideo.studio import capabilities
        return {**doctor(self.root), 'styles': all_styles(self.root),'video_studio':capabilities(self.root)}

    def aigen_styles(self, payload):
        from hinglish_aigen.settings import save_styles
        styles = payload.get('styles')
        if not isinstance(styles, list) or len(styles) > 30 or not all(isinstance(s, dict) for s in styles):
            raise ValueError('Invalid styles')
        return {'styles': save_styles(self.root, styles)}

    def rebuild_aigen(self, payload):
        from hinglish_aigen.pipeline import rebuild_project
        project = Path(payload.get('project_path', '')).resolve()
        ok = any(project.is_relative_to((self.root / 'output' / tool).resolve()) and project.name == f'{tool}-project.json'
                 for tool in AI_TOOLS)
        if not ok or not project.is_file():
            raise ValueError('This AI Images / AI Video project is unavailable')
        choices, regenerate = payload.get('choices') or {}, payload.get('regenerate') or {}
        if not isinstance(choices, dict) or not isinstance(regenerate, dict) or \
                not all(isinstance(v, str) and len(v) <= 800 for v in list(choices.values()) + list(regenerate.values())):
            raise ValueError('Invalid choices')
        return rebuild_project(project, {'choices': choices, 'regenerate': regenerate})

    def motion_styles(self, payload=None):
        """GET: the themes + your style cards. POST {action: learn|approve|unapprove|rename|delete, ...}."""
        from hinglish_motion import style
        payload = payload or {}
        action = payload.get('action')
        if action == 'learn':
            files = []
            for item in payload.get('paths') or []:
                path = Path(str(item)).resolve()
                if path.is_dir():
                    files += style.references_in(path)
                elif path.is_file():
                    files.append(path)
            name = str(payload.get('name') or '').strip()[:40]
            card = style.analyse(self.root, files[:40], name, lambda m: None)
            payload = {'made': card.id}
        elif action in ('approve', 'unapprove', 'rename'):
            name = str(payload.get('name') or '').strip()[:40] or None
            current = style.card(self.root, str(payload.get('id', '')))
            style.approve(self.root, current.id, name, approved=(action == 'approve') or
                          (action == 'rename' and current.status == 'approved'))
        elif action == 'delete':
            style.delete(self.root, str(payload.get('id', '')))
        elif action:
            raise ValueError('Unknown style action')
        cards = [{'id': c.id, 'name': c.name, 'status': c.status, 'sources': len(c.sources),
                  'summary': (c.notes or {}).get('summary') or '',
                  'group': (c.notes or {}).get('settings_group', ''),
                  'animation': (c.notes or {}).get('archive_defaults', {}).get('archive_composition'),
                  'animations': (c.notes or {}).get('animation_settings', []), 'colors': {k: c.tokens.get(k) for k in
                  ('--bg', '--paper', '--accent', '--alert')}} for c in style.load_cards(self.root)]
        groups = {'card:' + c['id']: c['group'] for c in cards}
        from hinglish_motion.capabilities import connections
        from hinglish_motion.engines import ENGINES
        return {'choices': [{'value': v, 'name': n, 'group': groups.get(v, '')} for v, n in style.choices(self.root)], 'cards': cards,
                'render_engines': [{'value':k,'name':v} for k,v in ENGINES.items()],
                'default_engine':'remotion',
                'connected_tools': connections(self.root),
                **({'made': payload['made']} if 'made' in payload else {})}

    def rebuild_motion(self, payload):
        from hinglish_motion.pipeline import rebuild_project
        project = Path(payload.get('project_path', '')).resolve()
        allowed = (self.root / 'output' / 'motion').resolve()
        if not project.is_relative_to(allowed) or project.name != 'motion-project.json' or not project.is_file():
            raise ValueError('This Motion Graphics project is unavailable')
        scenes = payload.get('scenes') or {}
        if not isinstance(scenes, dict) or len(scenes) > 200 or not all(isinstance(v, dict) for v in scenes.values()):
            raise ValueError('Invalid motion graphics changes')
        changes = {'scenes': scenes}
        style = payload.get('style')
        if isinstance(style, str) and re.fullmatch(r'(theme:[a-z]+|card:card_[a-z0-9_]+)', style):
            changes['style'] = style
        for s in scenes.values():
            find = s.get('find')
            if find is not None and (not isinstance(find, list) or len(find) > 4 or
                                     not all(isinstance(f, str) and len(f) <= 120 for f in find)):
                raise ValueError('Invalid picture search')
        return rebuild_project(project, changes)

    def rebuild_shorts(self, payload):
        from hinglish_shorts.pipeline import rebuild_project
        project = Path(payload.get('project_path', '')).resolve()
        allowed = (self.root / 'output' / 'shorts').resolve()
        if not project.is_relative_to(allowed) or project.name != 'shorts-project.json' or not project.is_file():
            raise ValueError('This shorts project is unavailable')
        shorts = payload.get('shorts')
        if not isinstance(shorts, list) or len(shorts) > 60:
            raise ValueError('Invalid shorts')
        for s in shorts:
            pieces = s.get('pieces') if isinstance(s, dict) else None
            if not isinstance(pieces, list) or len(pieces) > 3 or not all(
                    isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) for v in p) for p in pieces):
                raise ValueError('Invalid short times')
        changes = {'shorts': shorts}
        if payload.get('look') in ('template', 'face'):
            changes['look'] = payload['look']
        if isinstance(payload.get('captions'), bool):
            changes['captions'] = payload['captions']
        for key in ('title', 'handle'):
            if isinstance(payload.get(key), str) and len(payload[key]) <= 120:
                changes[key] = payload[key].strip()
        return rebuild_project(project, changes)

    def rebuild_sound(self, payload):
        from hinglish_sound.pipeline import remix
        plan = Path(payload.get('plan_path', '')).resolve()
        allowed = (self.root / 'output' / 'sound').resolve()
        if not plan.is_relative_to(allowed) or plan.name != 'sound-plan.json' or not plan.is_file():
            raise ValueError('This sound design is unavailable')
        if 'selections' in payload:
            from hinglish_sound.human_review import apply
            import uuid
            data = apply(json.loads(plan.read_text('utf-8')), payload['selections'])
            # A review creates a revision; previous preview, stems and choices stay intact on failure.
            folder = plan.parent.with_name(plan.parent.name + '-review-' + uuid.uuid4().hex[:6])
            folder.mkdir()
            reviewed = folder / 'sound-plan.json'
            reviewed.write_text(json.dumps(data, indent=2), encoding='utf-8')
            result = remix(reviewed, data['kept'], payload.get('music', True) is not False, remember_choices=False)
            from urllib.parse import quote
            result['report_url'] = '/sound-output/' + quote((folder / 'report.html').relative_to(allowed).as_posix())
            return result
        keep = payload.get('keep') or []
        if not isinstance(keep, list) or not all(isinstance(i, int) for i in keep):
            raise ValueError('Invalid sound choices')
        return remix(plan, keep, payload.get('music', True) is not False)

    def audition_sound(self, payload):
        from hinglish_sound.human_review import audition
        plan = Path(payload.get('plan_path', '')).resolve()
        if not plan.is_relative_to((self.root / 'output/sound').resolve()) or plan.name != 'sound-plan.json' or not plan.is_file():
            raise ValueError('This sound design is unavailable. Reopen its saved result.')
        return audition(plan, payload.get('event'), payload.get('candidate'))

    def sound_settings(self, values=None):
        from dataclasses import asdict
        from hinglish_sound.settings import load_settings, save_user_settings
        from hinglish_sound.providers import status
        result = asdict(load_settings(self.root)) if values is None else save_user_settings(self.root, values)
        result['providers'] = status(self.root)
        return result

    def eyecontact_status(self):
        from hinglish_eyecontact.engine import doctor
        report = doctor(self.root)
        return {'ready': report.ready, 'gpu': report.gpu.name if report.gpu else 'CPU',
                'engine': getattr(report, 'label', 'NVIDIA Maxine'),
                'checks': [{'ok': ok, 'text': text} for ok, text in report.checks]}

    def broll_settings(self, values=None):
        from hinglish_broll.settings import public_settings, save_user_settings
        return public_settings(self.root) if values is None else save_user_settings(self.root, values)


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'HinglishEditor/0.1'

        def log_message(self, *_):
            pass

        def _cors(self):
            origin = self.headers.get('Origin')
            local = (None, 'null', f'http://127.0.0.1:{state.port}', f'http://localhost:{state.port}')
            extension = self.path.startswith(('/api/local-browser/worker/','/api/stock-browser/worker/')) and bool(re.fullmatch(r'chrome-extension://[a-p]{32}', origin or ''))
            if origin in local or origin=='uxp://com.hinglish.editor.uxp' or extension:
                self.send_header('Access-Control-Allow-Origin', origin or 'null')
                self.send_header('Vary', 'Origin')

        def _json(self, status, value):
            if status>=400 and isinstance(value,dict) and value.get('error'):
                from .user_messages import problem,diagnostics
                issue=problem(value['error'],status)
                value={**value,'error':issue['message'],'error_code':value.get('error_code',issue['code']),
                    'error_details':diagnostics(value.get('error_details') or issue['details'])}
            body = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status); self._cors()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def send_error(self, code, message=None, explain=None):
            from .user_messages import problem
            if urlparse(self.path).path.startswith('/api/'):
                return self._json(code,{'error':message or 'Requested operation unavailable'})
            from html import escape
            issue=problem(message or 'Requested page unavailable',code)
            body=('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                '<title>Storylens · Needs attention</title><body style="background:#14181d;color:#eee;font:18px/1.6 system-ui;max-width:700px;margin:10vh auto;padding:24px">'
                '<h1>This page could not be opened</h1><p>'+escape(issue['message'])+'</p><a style="color:#ff974d" href="/">Back to Storylens</a>'
                '<details style="margin-top:24px"><summary>Technical details</summary><pre>'+escape('HTTP '+str(code)+' · '+issue['details'])+'</pre></details></body></html>').encode('utf-8')
            self.send_response(code);self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(body)));self.end_headers()
            if self.command!='HEAD':self.wfile.write(body)

        def _authorized(self):
            return secrets.compare_digest(self.headers.get('X-Hinglish-Token', '').encode(), state.token.encode())

        def _host_ok(self):
            # DNS-rebinding guard: a web page that points its own domain at 127.0.0.1 would otherwise count as
            # "same site", read the token from / or /api/bridge and control the app. Only our own address is served.
            host = (self.headers.get('Host') or '').strip().lower()
            if host in (f'127.0.0.1:{state.port}', f'localhost:{state.port}', f'[::1]:{state.port}'):
                return True
            self.send_error(403, 'Unknown host')
            return False

        def do_OPTIONS(self):
            if not self._host_ok(): return
            self.send_response(204); self._cors()
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Hinglish-Token, X-Storylens-Browser, X-Storylens-Stock')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'); self.end_headers()

        def do_GET(self):
            try:self._get()
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
            except Exception as error:
                from .user_messages import exception_status
                self._json(exception_status(error),{'error':error})

        def _get(self):
            if not self._host_ok(): return
            parsed = urlparse(self.path)
            if parsed.path.startswith('/api/analytics/'):
                from .analytics_http import get
                return get(self,state,parsed)
            if parsed.path.startswith('/api/agents/'):
                from .agents_http import get
                return get(self,state,parsed)
            if parsed.path.startswith('/api/support-call/'):
                from .support_call import handle
                return handle(self, state, parsed.path)
            if parsed.path.startswith('/api/call-qa/'):
                from .call_qa_http import get
                return get(self, state, parsed)
            if parsed.path.startswith('/api/native-tools/'):
                from .native_browser_bridge import get
                return get(self,state,parsed)
            if parsed.path.startswith('/api/workbench/'):
                from .workbench_http import get
                return get(self,state,parsed)
            if parsed.path.startswith('/api/voiceover/'):
                from .voiceover_http import get
                return get(self,state,parsed)
            if parsed.path.startswith('/api/panel/'):
                from .editor_panel_http import get
                return get(self,state,parsed)
            if parsed.path.startswith('/api/photos/'):
                from .photo_collector_http import get
                return get(self,state,parsed)
            if parsed.path.startswith('/api/downloader/'):
                from .downloader_http import get
                return get(self,state,parsed)
            if parsed.path == '/api/captions/important/status':
                if not self._authorized():return self._json(403,{'error':'Not connected'})
                from hinglish_captions.important_words import snapshot
                return self._json(200,snapshot(state.root,parse_qs(parsed.query).get('id',[''])[0]))
            if parsed.path in ('/api/captions/auto2/catalog','/api/captions/auto2/job'):
                if not self._authorized():return self._json(403,{'error':'Not connected'})
                from hinglish_captions import auto_caption
                if parsed.path.endswith('/catalog'):return self._json(200,{'styles':auto_caption.references(state.root)})
                return self._json(200,auto_caption.snapshot(state.root,parse_qs(parsed.query).get('id',[''])[0]))
            if parsed.path in ('/api/editors/task','/api/editors/download','/api/editors/capcut-projects'):
                query=parse_qs(parsed.query)
                if not self._authorized() and not secrets.compare_digest(query.get('token',[''])[0],state.token):
                    return self._json(403,{'error':'Not connected'})
                from . import editor_handoff,capcut_adapter
                if parsed.path.endswith('capcut-projects'):return self._json(200,capcut_adapter.projects(state.root))
                if parsed.path.endswith('task'):return self._json(200,editor_handoff.snapshot(query.get('id',[''])[0]))
                path=editor_handoff.download(state.root,query.get('id',[''])[0],int(query.get('index',['-1'])[0]))
                self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
                self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(path.name))
                self.send_header('Content-Length',str(path.stat().st_size));self.send_header('Cache-Control','no-store')
                self.send_header('Referrer-Policy','no-referrer');self.end_headers()
                with path.open('rb') as stream:shutil.copyfileobj(stream,self.wfile)
                return
            if parsed.path=='/api/scheduled':
                if not self._authorized():return self._json(403,{'error':'Not connected'})
                return self._json(200,state.scheduled_posts.snapshot())
            if parsed.path=='/api/scheduled/thumbnail':
                query=parse_qs(parsed.query)
                if not secrets.compare_digest(query.get('token',[''])[0],state.token):return self._json(403,{'error':'Not connected'})
                try:
                    content=state.scheduled_posts.thumbnail(query.get('id',[''])[0])
                    self.send_response(200);self.send_header('Content-Type','image/jpeg')
                    self.send_header('Cache-Control','private, max-age=300');self.send_header('Referrer-Policy','no-referrer')
                    self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
                    return
                except (ValueError,OSError):return self._json(404,{'error':'Preview unavailable'})
            if parsed.path == '/api/distribution':
                if not self._authorized():return self._json(403,{'error':'Not connected'})
                from .assistant_distribution import context
                from .campaign_memory import catalog
                chrome=state.local_browser.snapshot()
                return self._json(200,{'workflow':context(state.root),'batches':catalog(state.assistant),
                    'chrome_connected':chrome['connected'],'instagram_accounts':chrome['accounts'],'instagram_readiness':chrome['readiness'],
                    'youtube_accounts':{p:state.publisher.accounts(p)['youtube'] for p in ('cricket','gaming')}})
            if parsed.path == '/api/local-browser':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                return self._json(200, state.local_browser.snapshot())
            if parsed.path=='/api/stock-browser' or parsed.path.startswith('/api/stock-browser/'):
                from .stock_browser import get
                return get(self,state,parsed)
            if parsed.path.startswith(('/caption-output/','/broll-output/','/visuals-output/','/thumbnail-output/','/sound-output/')):
                return self._caption_output(parsed)
            if parsed.path == '/api/health':
                return self._json(200, {'ok': True, 'version': 9, 'capabilities': ['beat_markers_v1', 'beat_zoom_v1', 'cinematic_reels_v1', 'private_youtube_chat_v1', 'instagram_library_v1', 'local_shorts_campaign_v1', 'broll_reference_script_v1', 'visuals_website_options_v1', 'thumbnail_studio_v1', 'publishing_discovery_v1', 'weekly_seo_browser_v1', 'weekly_seo_resume_v2', 'downloader_queue_v1', 'downloader_transfer_v2', 'cinematic_footage_v1', 'resolve_node_grade_v1', 'browser_native_tools_v1']})
            if parsed.path == '/api/license':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                try:
                    client=state.license_for(parse_qs(parsed.query).get('edition',[state.license_client.edition if state.license_client else 'desktop'])[0])
                    return self._json(200,(client.status()|{'usage_reporting':client.usage_preference()}) if client else {'active':True,'edition':'owner'})
                except ValueError as error:return self._json(400, {'error':error})
            if parsed.path.startswith('/api/jobs/') and parsed.path.endswith('/aftereffects'):
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                try:
                    from .aftereffects_adapter import result_manifest
                    job=state.snapshot(parsed.path.split('/')[3])
                    return self._json(200,result_manifest(job))
                except (KeyError,ValueError,OSError) as error:return self._json(400, {'error':error})
            if parsed.path == '/api/captions/capabilities':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                from hinglish_captions.project import caption_export_capabilities
                return self._json(200, caption_export_capabilities())
            if parsed.path.startswith('/api/reference-reel/'):
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                from .reference_reel import get
                return get(self, state, parsed)
            if parsed.path == '/api/reel-recreate/styles':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                from hinglish_captions.styles import SELECTABLE_TEMPLATES
                return self._json(200, {'styles':[{'id':key,'name':row['name']} for key,row in SELECTABLE_TEMPLATES.items()]})
            if parsed.path == '/api/bridge':
                # Only our own page, the Premiere UXP panel and local programs (no Origin) get the token. A "null"
                # origin can be any website's sandboxed frame; local review pages and CEP read it from disk instead.
                origin = self.headers.get('Origin')
                own = (f'http://127.0.0.1:{state.port}', f'http://localhost:{state.port}')
                if origin is not None and origin not in own and origin!='uxp://com.hinglish.editor.uxp':
                    return self._json(403, {'error': 'Not allowed'})
                return self._json(200, {'url': f'http://127.0.0.1:{state.port}', 'token': state.token})
            if parsed.path.startswith('/api/beats/jobs/'):
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                try: return self._json(200, state.beats.snapshot(parsed.path.rsplit('/', 1)[-1]))
                except ValueError as error: return self._json(404, {'error':error})
            if parsed.path.startswith('/api/reel-recreate/jobs/'):
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                from .reel_recreate import service
                try:return self._json(200, service(state.root,state.work_lock).snapshot(parsed.path.rsplit('/',1)[-1]))
                except ValueError as error:return self._json(404, {'error':str(error)})
            if parsed.path.startswith('/api/cinematic/jobs/'):
                if not self._authorized(): return self._json(403, {'error':'Not connected'})
                try:return self._json(200,state.cinematic.snapshot(parsed.path.rsplit('/',1)[-1]))
                except ValueError as error:return self._json(404,{'error':error})
            if parsed.path.startswith('/api/cinematic/video/'):
                query=parse_qs(parsed.query)
                if not secrets.compare_digest(query.get('token',[''])[0],state.token):return self._json(403,{'error':'Not connected'})
                try:
                    path=state.cinematic.video(parsed.path.rsplit('/',1)[-1]);size=path.stat().st_size
                    start,end=0,size-1;requested=self.headers.get('Range')
                    if requested:
                        match=re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
                        if not match:raise ValueError('Invalid range')
                        start=int(match[1]);end=min(end,int(match[2])) if match[2] else end
                        if start>end:raise ValueError('Invalid range')
                    self.send_response(206 if requested else 200)
                    self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes')
                    self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
                    if requested:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                    self.send_header('Content-Length',str(end-start+1));self.end_headers()
                    with path.open('rb') as file:
                        file.seek(start);remaining=end-start+1
                        while remaining:
                            block=file.read(min(1024**2,remaining))
                            if not block:break
                            self.wfile.write(block);remaining-=len(block)
                    return
                except (ValueError,OSError) as error:return self._json(404,{'error':error})
            if parsed.path == '/api/niche':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                from hinglish_niche.profiles import Profiles
                return self._json(200, Profiles(state.root).read())
            if parsed.path == '/api/niche/style-search':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                from hinglish_niche.style_memory import search
                query = parse_qs(parsed.query)
                try:
                    return self._json(200, {'matches': search(state.root, query.get('style', [''])[0],
                                                            query.get('query', [''])[0])})
                except (ValueError, OSError) as error:
                    return self._json(400, {'error':error})
            if parsed.path == '/api/assistant/session':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                try: return self._json(200, state.assistant.snapshot(parse_qs(parsed.query).get('id', [''])[0]))
                except ValueError as error: return self._json(404, {'error':error})
            if parsed.path == '/api/assistant/history':
                if not self._authorized():return self._json(403,{'error':'Not connected'})
                return self._json(200,{'chats':state.assistant.memory.history(parse_qs(parsed.query).get('q',[''])[0][:300])})
            if parsed.path == '/api/assistant/messages':
                if not self._authorized():return self._json(403,{'error':'Not connected'})
                query=parse_qs(parsed.query)
                try:
                    session_id=query.get('id',[''])[0];state.assistant.snapshot(session_id)
                    return self._json(200,state.assistant.memory.messages(session_id,query.get('before',[None])[0]))
                except ValueError as error:return self._json(404,{'error':error})
            if parsed.path == '/api/assistant/media':
                return self._assistant_media(parsed)
            if parsed.path == '/api/publisher':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                try: return self._json(200, state.publisher.snapshot(parse_qs(parsed.query).get('profile', ['general'])[0]))
                except Exception as error:return self._json(500,{'error':error})
            if parsed.path == '/api/pick':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                try:
                    chosen = state.pick(parse_qs(parsed.query).get('kind', ['folder'])[0])
                    return self._json(200, {'path': chosen})
                except Exception as error:
                    return self._json(400, {'error':error})
            if parsed.path == '/api/broll/settings':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                return self._json(200, state.broll_settings())
            if parsed.path == '/api/sound/settings':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                return self._json(200, state.sound_settings())
            if parsed.path == '/api/aigen/status':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                return self._json(200, state.aigen_status())
            if parsed.path == '/api/motion/styles':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                return self._json(200, state.motion_styles())
            if parsed.path == '/api/eyecontact/status':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                return self._json(200, state.eyecontact_status())
            if parsed.path.startswith('/api/jobs/'):
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                try: return self._json(200, state.snapshot(parsed.path.rsplit('/', 1)[-1]))
                except KeyError: return self._json(404, {'error': 'Job not found'})
            path = 'index.html' if parsed.path in ('', '/') else parsed.path.lstrip('/')
            file = (state.static / path).resolve()
            if not file.is_relative_to(state.static.resolve()) or not file.is_file():
                return self.send_error(404)
            data = file.read_bytes()
            if path=='feedback.js':
                from .user_messages import catalog
                data=('window.storylensErrorCatalog='+json.dumps(catalog(),ensure_ascii=False)+';\n').encode('utf-8')+data
            if path in ('creator-analytics.html', 'ai-agents.html', 'selective-slow-motion.html', 'index.html', 'publisher.html', 'chrome.html', 'stock-browser.html', 'workflow.html', 'activation.html', 'beats.html', 'cinematic.html', 'cinematic-footage.html', 'match-cut.html', 'hook-drafts.html', 'intro-create.html', 'native-curation.html', 'documentary-intro.html', 'sound-library.html', 'color-grade.html', 'editor-link.html', 'auto-caption-2.html', 'important-captions.html', 'downloader.html', 'photos.html', 'editor-panel.html', 'reel-recreate.html', 'voiceover.html', 'call-qa.html'):
                data = data.replace(b'__APP_TOKEN__', state.token.encode())
            if path == 'index.html':
                from hinglish_cut.model_preferences import preferred_device, preferences
                data = data.replace(b'__DEFAULT_DEVICE__', preferred_device(state.root).encode())
                data = data.replace(b'__RTX_ONLY__', b'true' if preferences(state.root).get('require_cuda_inference') else b'false')
            self.send_response(200); self.send_header('Content-Type', mimetypes.guess_type(file)[0] or 'application/octet-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

        def _caption_output(self,parsed):
            # Serve only generated captions; keep bridge authentication and
            # reject traversal, junction escapes and arbitrary local files.
            is_broll=parsed.path.startswith('/broll-output/')
            is_visuals=parsed.path.startswith('/visuals-output/')
            is_thumbnail=parsed.path.startswith('/thumbnail-output/')
            is_sound=parsed.path.startswith('/sound-output/')
            prefix='/sound-output/' if is_sound else '/thumbnail-output/' if is_thumbnail else '/visuals-output/' if is_visuals else '/broll-output/' if is_broll else '/caption-output/'
            base=(state.root/('output/sound' if is_sound else 'output/thumbnails' if is_thumbnail else 'output/visuals' if is_visuals else 'output/broll' if is_broll else 'output/captions')).resolve()
            path=(base/unquote(parsed.path[len(prefix):])).resolve()
            allowed={'.html','.mp4','.mov','.srt','.ass','.txt','.xml','.json','.png','.jpg','.jpeg','.webp','.webm','.ogv','.zip'}
            if is_sound:allowed.update({'.wav','.mp3','.m4a'})
            if not path.is_relative_to(base) or not path.is_file() or path.suffix.lower() not in allowed:
                return self._json(404,{'error':'Caption output unavailable'})
            if path.suffix.lower()=='.html':
                from .presentation import caption_html
                data=path.read_bytes() if is_broll or is_visuals or is_thumbnail or is_sound else caption_html(path.read_bytes(),path.parent,state.token)
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data);return
            total=path.stat().st_size;start,end=0,total-1
            value=self.headers.get('Range')
            if value:
                match=re.fullmatch(r'bytes=(\d+)-(\d*)',value)
                if not match:return self._json(416,{'error':'Invalid range'})
                start=int(match[1]);end=min(end,int(match[2])) if match[2] else end
                if start>end:return self._json(416,{'error':'Invalid range'})
            self.send_response(206 if value else 200)
            self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
            self.send_header('Cache-Control','no-store');self.send_header('Accept-Ranges','bytes')
            self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff')
            if value:self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
            self.send_header('Content-Length',str(end-start+1));self.end_headers()
            try:
                with path.open('rb') as stream:
                    stream.seek(start);remaining=end-start+1
                    while remaining>0:
                        chunk=stream.read(min(1024*1024,remaining))
                        if not chunk:break
                        self.wfile.write(chunk);remaining-=len(chunk)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass

        def _assistant_media(self, parsed):
            # HTML media cannot set custom headers. Use a session-scoped file and bridge token;
            # never expose arbitrary local paths, HTML or authenticated platform credentials.
            query = parse_qs(parsed.query)
            if not secrets.compare_digest(query.get('token', [''])[0], state.token):
                return self._json(403, {'error': 'Not connected'})
            try:
                session = state.assistant.snapshot(query.get('session', [''])[0])
                index = int(query.get('index', ['-1'])[0])
                videos = [p for m in session['messages'] for p in m.get('videos', [])]
                if not 0 <= index < len(videos): raise ValueError('Video unavailable')
                path = Path(videos[index]).resolve()
                if not path.is_relative_to((state.root / 'output').resolve()) or not path.is_file() or path.suffix.lower() != '.mp4':
                    raise ValueError('Video unavailable')
                size = path.stat().st_size
                start, end = 0, size - 1
                range_value = self.headers.get('Range')
                if range_value:
                    match = re.fullmatch(r'bytes=(\d+)-(\d*)', range_value)
                    if not match: raise ValueError('Invalid video range')
                    start = int(match[1])
                    end = min(size - 1, int(match[2])) if match[2] else size - 1
                    if start > end: raise ValueError('Invalid video range')
                self.send_response(206 if range_value else 200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                if range_value: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.send_header('Content-Length', str(end - start + 1))
                self.end_headers()
                with path.open('rb') as file:
                    file.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = file.read(min(1024 * 1024, remaining))
                        if not chunk: break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (ValueError, OSError):
                return self._json(404, {'error': 'Video unavailable'})

        def do_POST(self):
            try:self._post()
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
            except Exception as error:
                from .user_messages import exception_status
                self._json(exception_status(error),{'error':error})

        def _post(self):
            if not self._host_ok(): return
            parsed_call_qa = urlparse(self.path)
            if parsed_call_qa.path.startswith('/api/support-call/'):
                from .support_call import handle
                return handle(self, state, parsed_call_qa.path)
            if parsed_call_qa.path.startswith('/api/call-qa/'):
                from .call_qa_http import post
                return post(self, state, parsed_call_qa)
            if urlparse(self.path).path.startswith('/api/stock-browser/worker/'):
                from .stock_browser import worker
                return worker(self,state)
            if urlparse(self.path).path.startswith('/api/local-browser/worker/'):
                if not state.local_browser.authorized(self.headers.get('X-Storylens-Browser', '')):
                    return self._json(403, {'error': 'Connect the Storylens Chrome extension first.'})
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    action = urlparse(self.path).path.rsplit('/', 1)[-1]
                    if not 0 <= length <= (512 * 1024 if action == 'finish' else 4096):
                        self.close_connection = True
                        raise ValueError('Invalid Chrome request size.')
                    payload = json.loads(self.rfile.read(length) or b'{}')
                    if not isinstance(payload, dict): raise ValueError('Send a JSON object.')
                    bridge = state.local_browser
                    if length > 4096:
                        job = bridge.get(payload.get('id',''))
                        if job.get('action') not in ('instagram_comments_read', 'instagram_comment_posts', 'instagram_analytics_read') or job.get('status') != 'running' or not secrets.compare_digest(str(job.get('lease','')),str(payload.get('lease',''))):
                            raise ValueError('Invalid Chrome comment receipt.')
                    if action == 'claim': return self._json(200, bridge.claim(payload.get('version', ''),payload.get('supports',[])))
                    if action == 'phase': return self._json(200, bridge.phase(payload['id'], payload['lease'], payload['status'], payload.get('message', '')))
                    if action == 'media': return self._json(200, bridge.media(payload['id'], payload['lease'], payload['offset']))
                    if action == 'finish':
                        result = bridge.finish(payload['id'], payload['lease'], payload['result'])
                        return self._json(200, {'status': result['status']})
                    return self._json(404, {'error': 'Unknown Chrome operation.'})
                except (ValueError, KeyError, OSError) as error:
                    return self._json(400, {'error':error})
            if not self._authorized(): return self._json(403, {'error': 'Not connected'})
            try:
                parsed = urlparse(self.path)
                if parsed.path=='/api/license/usage-preference':
                    if not state.license_client:return self._json(400,{'error':'Commercial installation required.'})
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<=length<=1024:raise ValueError('Invalid privacy request.')
                    value=json.loads(self.rfile.read(length) or b'{}')
                    if not isinstance(value,dict) or set(value)-{'enabled'} or not isinstance(value.get('enabled'),bool):raise ValueError('Set a boolean privacy preference.')
                    return self._json(200,{'enabled':state.license_client.usage_preference(value['enabled'])})
                if parsed.path == '/api/license/start':
                    if not state.license_client: return self._json(400, {'error':'This is the owner development installation.'})
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<=length<=1024:raise ValueError('Invalid activation request.')
                    value=json.loads(self.rfile.read(length) or b'{}')
                    if not isinstance(value,dict):raise ValueError('Send a JSON object.')
                    return self._json(200,state.license_for(value.get('edition',state.license_client.edition)).begin())
                if state.license_client and not parsed.path.startswith(('/api/panel/','/api/native-tools/','/api/workbench/')) and parsed.path not in ('/api/assistant/stop','/api/jobs','/api/beats/analyze','/api/beats/effects','/api/beats/upload','/api/reel-recreate/upload','/api/reel-recreate/start','/api/reel-recreate/revise','/api/cinematic/upload','/api/cinematic/assemble','/api/cinematic/effects','/api/cinematic/import-manifest','/api/cinematic/import-resolve','/api/cinematic/open','/api/cinematic/cancel'):
                    state.license_for('desktop').ensure('standalone')
                if parsed.path in ('/api/beats/upload','/api/cinematic/upload','/api/reel-recreate/upload'):
                    host=parse_qs(parsed.query).get('host',['standalone'])[0]
                    if host not in ('premiere','aftereffects','resolve','standalone'):raise ValueError('Choose Premiere, Resolve or Desktop')
                    client=state.license_for('plugins' if host!='standalone' else 'desktop')
                    if client:client.ensure(host)
                if parsed.path == '/api/panel/image-upload':
                    from .editor_panel_http import image_upload
                    return image_upload(self,state)
                if parsed.path == '/api/photos/upload':
                    from .photo_collector_http import upload
                    return upload(self,state)
                if parsed.path == '/api/voiceover/upload':
                    from .voiceover_http import upload
                    return upload(self,state,parsed)
                if parsed.path == '/api/beats/upload':
                    return self._json(201, state.beats.save_upload(parse_qs(parsed.query).get('name', [''])[0],
                        self.rfile, int(self.headers.get('Content-Length', '0'))))
                if parsed.path.startswith('/api/reference-reel/'):
                    from .reference_reel import post
                    return post(self, state, parsed)
                if parsed.path == '/api/reel-recreate/upload':
                    from .reel_recreate import service
                    return self._json(201, service(state.root,state.work_lock).upload(parse_qs(parsed.query).get('name',[''])[0],self.rfile,int(self.headers.get('Content-Length','0'))))
                if parsed.path == '/api/cinematic/upload':
                    return self._json(201,state.cinematic.upload(parse_qs(parsed.query).get('name',[''])[0],
                        self.rfile,int(self.headers.get('Content-Length','0'))))
                if parsed.path == '/api/assistant/upload':
                    query = parse_qs(parsed.query)
                    item = state.assistant.save_upload(query.get('session', [''])[0], query.get('name', [''])[0],
                        self.rfile, int(self.headers.get('Content-Length', '0')), query.get('kind', ['file'])[0])
                    return self._json(201, item)
                if parsed.path == '/api/upload':
                    query = parse_qs(parsed.query)
                    length = int(self.headers.get('Content-Length', '0'))
                    target = state.save_upload(query.get('batch', [''])[0], query.get('name', [''])[0],
                                               self.rfile, length)
                    return self._json(201, {'path': str(target.resolve()), 'name': target.name.split('-', 1)[-1]})
                length = int(self.headers.get('Content-Length', '0'))
                limit=8*1024**2 if parsed.path=='/api/panel/template-text-start' else 1024**2
                if not 0<=length<=limit:
                    self.close_connection=True
                    return self._json(413, {'error':'This text scan is too large. Work on a shorter composition.' if parsed.path=='/api/panel/template-text-start' else 'This request is too large.'})
                payload = json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(payload,dict):return self._json(400, {'error':'Send a JSON object.'})
                if parsed.path.startswith('/api/analytics/'):
                    from .analytics_http import post
                    return post(self,state,parsed.path,payload)
                if parsed.path.startswith('/api/agents/'):
                    from .agents_http import post
                    return post(self,state,parsed.path,payload)
                if parsed.path.startswith('/api/native-tools/'):
                    from .native_browser_bridge import post
                    return post(self,state,parsed.path,payload)
                if parsed.path == '/api/editor-link/prepare':
                    from .editor_link import prepare
                    return self._json(201, prepare(state.root, payload))
                if parsed.path == '/api/editor-link/apply':
                    from .editor_link import apply
                    return self._json(200, apply(state.root, payload.get('id')))
                if parsed.path == '/api/editor-link/capcut-drafts':
                    from .editor_link import capcut_drafts
                    return self._json(200, capcut_drafts(state.root))
                if parsed.path.startswith('/api/workbench/'):
                    from .workbench_http import post
                    return post(self,state,parsed.path,payload)
                if parsed.path.startswith('/api/voiceover/'):
                    from .voiceover_http import post
                    return post(self,state,parsed.path,payload)
                if parsed.path.startswith('/api/stock-browser/'):
                    from .stock_browser import post
                    return post(self,state,parsed.path,payload)
                if parsed.path.startswith('/api/panel/'):
                    from .editor_panel_http import post
                    return post(self,state,parsed.path,payload)
                if parsed.path.startswith('/api/photos/'):
                    from .photo_collector_http import post
                    return post(self,state,parsed.path,payload)
                if parsed.path in ('/api/downloader/start','/api/downloader/cancel','/api/downloader/retry','/api/downloader/settings','/api/downloader/enqueue'):
                    from .downloader import service
                    downloads=service(state.root)
                    if parsed.path.endswith('/enqueue'):return self._json(202,downloads.enqueue(payload))
                    if parsed.path.endswith('/start'):return self._json(202,downloads.start(payload))
                    if parsed.path.endswith('/settings'):return self._json(200,downloads.settings(payload))
                    if parsed.path.endswith('/retry'):return self._json(202,downloads.retry(payload.get('id','')))
                    return self._json(200,downloads.cancel(payload.get('id','')))
                if parsed.path=='/api/scheduled/action':return self._json(202,state.scheduled_posts.act(payload))
                if parsed.path.startswith('/api/local-browser/'):
                    bridge = state.local_browser
                    action = parsed.path.rsplit('/', 1)[-1]
                    if action == 'pair': return self._json(200, bridge.pairing())
                    if action == 'revoke': return self._json(200, bridge.revoke())
                    if action == 'bind': return self._json(200, bridge.bind(payload['profile'], payload['account']))
                    if action == 'inspect': return self._json(202, {'id': bridge.inspect_account(payload.get('profile'))['id']})
                    if action == 'youtube-preview':
                        saved=bridge.get(payload['id'])
                        if saved['action']!='youtube_schedule':raise ValueError('Select an existing reviewed Studio scheduling task.')
                        task=bridge.enqueue_youtube(saved['channel_id'],saved['video_id'],saved['publish_at'],saved['session'],authorized=True,preview=True)
                        return self._json(202, {'id':task['id']})
                    if action == 'cancel': return self._json(200, {'id': bridge.cancel(payload['id'])['id']})
                    if action == 'retry': return self._json(202, {'id': state.assistant.retry_browser(payload['id'])['id']})
                    return self._json(404, {'error': 'Unknown Chrome operation.'})
                if parsed.path in ('/api/cinematic/assemble','/api/cinematic/effects','/api/cinematic/import-manifest','/api/cinematic/import-resolve','/api/cinematic/open'):
                    host=payload.get('host','standalone')
                    if host not in ('premiere','aftereffects','resolve','standalone'):raise ValueError('Choose Premiere, Resolve or Desktop')
                    client=state.license_for('plugins' if host!='standalone' else 'desktop')
                    if client:client.ensure(host)
                    if parsed.path.endswith('/import-manifest'):return self._json(200,state.cinematic.latest())
                    if parsed.path.endswith('/open'):
                        job=state.cinematic.snapshot(payload.get('id',''))
                        if job['status']!='complete':raise ValueError('Finish the cinematic reel first')
                        target=payload.get('target','folder')
                        if target not in ('folder','xml'):raise ValueError('Choose the output folder or XML')
                        state.open_path(job['result']['folder'] if target=='folder' else job['result']['xml_files'][0])
                        return self._json(200,{'ok':True})
                    if parsed.path.endswith('/import-resolve'):
                        job=state.cinematic.snapshot(payload.get('id',''))
                        if job['status']!='complete':raise ValueError('Finish the cinematic reel first')
                        from .resolve_adapter import import_timelines
                        names=import_timelines(job['result']['xml_files'],checkpoint_dir=state.root/'output/cinematic-reels/project-backups')
                        return self._json(200,{'timelines':names})
                    return self._json(202,state.cinematic.start(payload,effects=parsed.path.endswith('/effects'),
                        verify_license=(lambda:client.ensure(host)) if client else None))
                if parsed.path == '/api/cinematic/cancel':
                    return self._json(200,state.cinematic.cancel(payload.get('id','')))
                if parsed.path in ('/api/beats/analyze', '/api/beats/effects'):
                    host = payload.get('host', 'standalone')
                    if host not in ('premiere', 'aftereffects', 'resolve', 'standalone'):
                        raise ValueError('Choose Premiere, Resolve or Desktop')
                    client = state.license_for('plugins' if host != 'standalone' else 'desktop')
                    if client: client.ensure(host)
                    if parsed.path.endswith('/analyze'):
                        return self._json(202, state.beats.start(payload))
                    return self._json(200, state.beats.effects(payload))
                if parsed.path == '/api/reel-recreate/start':
                    from .reel_recreate import service
                    host=payload.get('host','standalone')
                    if host not in ('aftereffects','standalone'):raise ValueError('Open Reel Recreate in After Effects or Storylens.')
                    client=state.license_for('plugins' if host=='aftereffects' else 'desktop')
                    if client:client.ensure(host)
                    return self._json(202,service(state.root,state.work_lock).start(payload))
                if parsed.path == '/api/reel-recreate/revise':
                    from .reel_recreate import service
                    host=payload.get('host','standalone')
                    if host not in ('aftereffects','standalone'):raise ValueError('Open Reel Recreate in After Effects or Storylens.')
                    client=state.license_for('plugins' if host=='aftereffects' else 'desktop')
                    if client:client.ensure(host)
                    return self._json(200,service(state.root,state.work_lock).revise(payload))
                if parsed.path == '/api/niche':
                    from hinglish_niche.profiles import Profiles
                    return self._json(200, Profiles(state.root).save(payload['profile'], payload.get('changes')))
                if parsed.path == '/api/niche/research':
                    from hinglish_niche.research import fetch
                    return self._json(200, fetch(state.root, payload['profile'], progress=lambda _: None))
                if parsed.path == '/api/assistant/session':
                    return self._json(201, state.assistant.create())
                if parsed.path == '/api/assistant/check-context':
                    from .assistant_planner_check import check
                    return self._json(200,check(state.assistant,payload['session']))
                if parsed.path == '/api/assistant/message':
                    args = (payload['session'], payload.get('message', ''), payload.get('attachments', []), payload.get('voice'))
                    options={key:payload[key] for key in ('profile','motion_engine') if key in payload}
                    return self._json(202, state.assistant.send(*args, **options))
                if parsed.path == '/api/assistant/attach':
                    return self._json(201, state.assistant.attach(payload['session'], payload['path']))
                if parsed.path == '/api/assistant/stop':
                    return self._json(200, state.assistant.stop(payload['session']))
                if parsed.path == '/api/assistant/retry-upload-plan':
                    from .assistant_upload_workflow import retry_unplanned
                    return self._json(202,retry_unplanned(state.assistant,payload['session']))
                if parsed.path == '/api/assistant/resume-upload-workflow':
                    from .assistant_upload_workflow import resume_saved
                    return self._json(202,resume_saved(state.assistant,payload['session']))
                if parsed.path == '/api/assistant/publish':
                    from .assistant_publish import start
                    return self._json(202, start(state.assistant, payload))
                if parsed.path == '/api/publisher/prepare-post':
                    from .prepare_post_http import dispatch
                    return self._json(200, dispatch(state, payload))
                if parsed.path.startswith('/api/publisher/'):
                    publisher = state.publisher
                    action = parsed.path.rsplit('/', 1)[-1]
                    if action == 'settings':
                        return self._json(200, publisher.settings({k: v for k, v in payload.items() if k != 'profile'}, payload.get('profile', 'general')))
                    if action == 'folders':
                        return self._json(200, publisher.init_folders(payload.get('profile', 'general')))
                    if action == 'stop-task':return self._json(200,publisher.stop_task(payload['id']))
                    if action in ('prepare','resume-task'):
                        if action=='resume-task':payload=publisher.resume_request(payload['id'])
                        if payload.get('operation')!='diagnostics' and not payload.get('expected_accounts'):
                            scope=payload.get('platforms',['youtube'])
                            if not isinstance(scope,list) or not scope or any(p not in ('youtube','instagram') for p in scope) or len(set(scope))!=len(scope):raise ValueError('Choose YouTube, Instagram, or both destinations.')
                            current=publisher.accounts(payload.get('profile','general'))
                            payload={**payload,'expected_accounts':{p:current.get(p,{}).get('id','') for p in scope}}
                        def prepare(progress=print):
                            if payload.get('operation')=='diagnostics':
                                from hinglish_publish.readiness import check
                                return check(state.root,payload.get('profile','general'),state.local_browser,progress)
                            if payload.get('source_mode')=='stream':
                                from hinglish_publish.stream_intake import prepare_stream
                                return prepare_stream(publisher,payload,progress,state.work_lock)
                            from hinglish_cut.gpu_lock import gpu_lock
                            with state.work_lock,gpu_lock(state.root):return publisher.prepare(payload,progress)
                        return self._json(202, publisher.task(prepare,request=None if payload.get('operation')=='diagnostics' else payload))
                    if action == 'edit':
                        return self._json(200, publisher.edit(payload))
                    if action == 'feedback':
                        from hinglish_publish.memory import CreatorMemory
                        record_id = CreatorMemory(state.root, payload.get('profile', 'general')).add(payload)
                        return self._json(200, {'ok': True, 'id': record_id})
                    if action == 'memory-toggle':
                        from hinglish_publish.memory import CreatorMemory
                        CreatorMemory(state.root, payload.get('profile', 'general')).set_active(payload['id'], payload['active'])
                        return self._json(200, {'ok': True})
                    if action == 'authorize':
                        return self._json(200, publisher.authorize(payload))
                    if action == 'cancel':
                        return self._json(200, publisher.cancel(payload['id']))
                    if action == 'review':
                        job = publisher.store.get(payload['id'])
                        if not job.get('review_file'):
                            raise ValueError('This post has no generated Shorts review page')
                        state.open_path(job['review_file'])
                        return self._json(200, {'ok': True})
                    if action == 'connect-youtube':
                        from hinglish_publish.signin import start
                        return self._json(202, start(publisher, payload.get('client_file', ''), payload.get('profile', 'general')))
                    if action == 'connect-instagram':
                        from hinglish_publish.providers import connect_instagram
                        return self._json(200, connect_instagram(state.root, payload['token'],
                                                                payload['account_id'], profile=payload.get('profile', 'general')))
                    return self._json(404, {'error': 'Unknown publisher action'})
                if parsed.path == '/api/jobs':
                    return self._json(202, state.create_job(payload))
                if parsed.path == '/api/read-script':
                    script = Path(payload['path']).resolve()
                    if not script.is_file() or script.suffix.lower() != '.txt' or script.stat().st_size > 2_000_000:
                        raise ValueError('Choose a normal .txt script file')
                    return self._json(200, {'text': script.read_text(encoding='utf-8-sig')})
                if parsed.path == '/api/open':
                    state.open_path(payload['path']); return self._json(200, {'ok': True})
                if parsed.path == '/api/editors/prepare':
                    from .editor_handoff import start
                    return self._json(202,start(state.root,payload))
                if parsed.path == '/api/editors/action':
                    from .editor_handoff import act
                    return self._json(200,act(state.root,payload))
                if parsed.path == '/api/editors/capcut-source':
                    from .capcut_adapter import source
                    return self._json(200,{'path':source(state.root,payload.get('project_id'),payload.get('media_id'))})
                if parsed.path == '/api/editors/capcut-timeline':
                    from .capcut_adapter import export_timeline
                    return self._json(200,{'path':export_timeline(state.root,payload.get('project_id'))})
                if parsed.path == '/api/import-resolve':
                    names = state.import_into_resolve(payload.get('xml_files', []))
                    return self._json(200, {'ok': True, 'timelines': names})
                if parsed.path == '/api/captions/script-preview':
                    from hinglish_captions.script_preview import create_script_preview
                    return self._json(201, create_script_preview(state.root,payload))
                if parsed.path == '/api/captions/important/start':
                    from hinglish_captions.important_words import start
                    return self._json(202,start(state.root,payload))
                if parsed.path == '/api/captions/auto2/start':
                    from hinglish_captions.auto_caption import start
                    return self._json(202,start(state.root,payload))
                if parsed.path == '/api/captions/rebuild':
                    return self._json(200, state.rebuild_captions(payload))
                if parsed.path == '/api/broll/rebuild':
                    return self._json(200, state.rebuild_broll(payload))
                if parsed.path == '/api/aigen/rebuild':
                    return self._json(200, state.rebuild_aigen(payload))
                if parsed.path == '/api/aigen/styles':
                    return self._json(200, state.aigen_styles(payload))
                if parsed.path == '/api/shorts/rebuild':
                    return self._json(200, state.rebuild_shorts(payload))
                if parsed.path == '/api/motion/rebuild':
                    return self._json(200, state.rebuild_motion(payload))
                if parsed.path == '/api/motion/styles':
                    return self._json(200, state.motion_styles(payload))
                if parsed.path == '/api/sound/rebuild':
                    return self._json(200, state.rebuild_sound(payload))
                if parsed.path == '/api/sound/audition':
                    return self._json(200, state.audition_sound(payload))
                if parsed.path == '/api/visuals/rebuild':
                    return self._json(200, state.rebuild_visuals(payload))
                if parsed.path == '/api/visuals/recheck':
                    return self._json(200,state.recheck_visuals(payload))
                if parsed.path == '/api/broll/settings':
                    return self._json(200, state.broll_settings(payload))
                if parsed.path == '/api/sound/settings':
                    return self._json(200, state.sound_settings(payload))
                return self._json(404, {'error': 'Unknown action'})
            except Exception as error:
                from .user_messages import exception_status
                return self._json(exception_status(error), {'error':error})
    return Handler


def serve(root, port=DEFAULT_PORT, publish_bridge=True, **kwargs):
    state = AppState(root, port, **kwargs)
    server = LocalHTTPServer(('127.0.0.1', port), make_handler(state))
    state.port = server.server_address[1]      # the real port (port 0 = any free port)
    if publish_bridge:state.publish_bridge()
    return server, state
