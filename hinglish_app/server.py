from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
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
TIMELINE_MODES = ('broll', 'visuals', 'zoom', 'sound', 'eyecontact')   # work on a whole edited sequence (or XML)
SOUND_CHOICES = {'sound_style': ('auto', 'cinematic', 'funny', 'chill', 'emotional'),
                 'sound_density': ('low', 'medium', 'high')}
EYE_CHOICES = {'eye_reach': ('near', 'far'), 'eye_size': ('3', '2', '4', '5', '6')}
VISUALS_CHOICES = {'visuals_density': ('medium', 'low', 'high'), 'visuals_brain': ('auto', 'ollama', 'local')}
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
    def __init__(self, root, port=DEFAULT_PORT):
        self.root = Path(root).resolve()
        self.static = Path(__file__).parent / 'static'
        self.port = port
        self.token = app_token(self.root / 'cache' / 'app' / 'bridge.json')
        self.jobs = {}
        self.lock = threading.Lock()

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
            files = {'script': ('Choose your script', 'Text files (*.txt)|*.txt|All files (*.*)|*.*'),
                     'xml': ('Choose a timeline XML', 'Timeline XML (*.xml)|*.xml|All files (*.*)|*.*')}
            chooser = (
                "$dialog=New-Object System.Windows.Forms.OpenFileDialog;"
                f"$dialog.Title='{files[kind][0]}';"
                f"$dialog.Filter='{files[kind][1]}';"
                "$dialog.Multiselect=$false;"
                "$selected={ if($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK)"
                "{ $dialog.FileName } else { '' } };"
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
        mode = payload.get('mode')
        if mode not in ('clean', 'script', 'captions') + TIMELINE_MODES:
            raise ValueError('Choose Smart Clean, Script Edit, Auto Captions, B-roll, Smart Visuals, Smart Zoom, '
                             'Sound Design or Eye Contact')
        source_paths = [Path(p).resolve() for p in payload.get('source_paths', []) if p]
        input_path = Path(payload['input_path']).resolve() if payload.get('input_path') else None
        timeline_mode = mode in TIMELINE_MODES
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
        elif source_paths:
            if any(not p.is_file() or p.suffix.lower() not in VIDEO_EXTENSIONS for p in source_paths):
                raise ValueError('One or more selected timeline files are unavailable')
        elif not input_path or not input_path.exists():
            raise ValueError('Choose a video folder first')
        script = str(payload.get('script', '')).strip()
        if mode == 'script' and not script:
            raise ValueError('Paste your script or reference outline')
        job_id = uuid.uuid4().hex[:12]
        job = {'id': job_id, 'mode': mode, 'status': 'queued', 'progress': 0,
               'stage': 'Waiting', 'logs': [], 'created': time.time(), 'result': None}
        with self.lock:
            self.jobs[job_id] = job
        thread = threading.Thread(target=self._run_job,
            args=(job_id, payload, source_paths, input_path, script), daemon=True)
        thread.start()
        return job.copy()

    def save_upload(self, batch, name, stream, length):
        batch = str(batch or '')
        if not re.fullmatch(r'[A-Za-z0-9-]{6,80}', batch):
            raise ValueError('Invalid upload session')
        name = Path(str(name or '').replace('\\', '/')).name
        if not name or Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError('Choose a supported video file')
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
        for index, source in enumerate(sorted(set(paths), key=lambda p: str(p).casefold())):
            target = folder / f'{index:04d}-{source.name}'
            try:
                os.link(source, target)
            except OSError:
                shutil.copyfile(source, target)
        return folder

    def _update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values)

    def _log(self, job_id, message):
        clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', message).strip()
        if not clean:
            return
        with self.lock:
            logs = self.jobs[job_id]['logs']
            logs.append(clean)
            del logs[:-120]
            self.jobs[job_id]['stage'] = clean[:140]

    def _run_job(self, job_id, payload, paths, input_path, script):
        try:
            staged = self._stage_sources(job_id, paths)
            if staged:
                self._consume_uploads(paths)
            supplied = staged or input_path
            work = self.root / 'cache' / 'app' / 'jobs' / job_id
            work.mkdir(parents=True, exist_ok=True)
            fmt = payload.get('format', 'source')
            command = [str(self.root / '.venv' / 'Scripts' / 'python.exe'), '-u']
            if supplied == 'resolve':
                from .resolve_adapter import export_current_timeline
                supplied = export_current_timeline(work / 'resolve-timeline.xml')
                self._log(job_id, 'Exported the current Resolve timeline')
            if payload['mode'] in TIMELINE_MODES and Path(supplied).suffix.lower() == '.xml':
                fmt = 'source'   # an existing sequence keeps its own canvas
            if payload['mode'] == 'broll':
                command += ['-m', 'hinglish_broll', '--root', str(self.root), '--input', str(supplied),
                            '--density', payload.get('density', 'medium'), '--device', payload.get('device', 'cpu')]
            elif payload['mode'] == 'visuals':
                command += ['-m', 'hinglish_visuals', '--root', str(self.root), '--input', str(supplied),
                            '--device', payload.get('device', 'cpu')]
                for key, allowed in VISUALS_CHOICES.items():
                    value = payload.get(key, allowed[0])
                    if value not in allowed:
                        raise ValueError(f'Unknown {key.replace("_", " ")}: {value}')
                    command += ['--' + key.split('_', 1)[1], value]
                if payload.get('visuals_popups') is False:
                    command.append('--no-popups')
                if payload.get('visuals_web') is False:
                    command.append('--no-web')
                if payload.get('visuals_check') is False:
                    command += ['--evaluator', 'off']
            elif payload['mode'] == 'sound':
                command += ['-m', 'hinglish_sound', '--root', str(self.root), '--input', str(supplied),
                            '--device', payload.get('device', 'cpu')]
                for key, allowed in SOUND_CHOICES.items():
                    value = payload.get(key, allowed[0] if key == 'sound_style' else 'medium')
                    if value not in allowed:
                        raise ValueError(f'Unknown {key.replace("_", " ")}: {value}')
                    command += ['--' + key.split('_', 1)[1], value]
                for key, flag in (('sound_music', '--no-music'), ('sound_effects', '--no-effects'),
                                  ('sound_transitions', '--no-transitions')):
                    if payload.get(key) is False:
                        command.append(flag)
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
                            '--style', payload.get('caption_style', 'flash_cut'),
                            '--device', payload.get('device', 'cpu')]
                if script:
                    script_file = work / 'caption-reference.txt'
                    script_file.write_text(script, encoding='utf-8')
                    command += ['--script', str(script_file)]
            if fmt in ('instagram_vertical', 'square', 'youtube_horizontal'):
                command += ['--format', fmt]
            if payload.get('quality_check', True):
                # every feature runs under the quality evaluator: rules checked, failures redone with corrections
                command = command[:2] + ['-m', 'hinglish_eval', 'run', '--root', str(self.root),
                                         '--attempts', str(QUALITY_ATTEMPTS), '--'] + command[2:]
            self._update(job_id, status='running', progress=3, stage='Starting local AI')
            process = subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},   # engines print Hinglish/Devanagari
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            result_page = None
            line_count = 0
            for line in process.stdout:
                line_count += 1
                self._log(job_id, line)
                match = re.search(r'Results:\s*(.+?)(?:\s*$)', line)
                if match:
                    result_page = Path(match.group(1).strip())
                self._update(job_id, progress=min(94, 5 + line_count // 2))
            code = process.wait()
            if code not in (0, 2) or not result_page or not result_page.exists():
                raise RuntimeError(f'Editing engine stopped with code {code}. Check the activity log.')
            output = result_page.parent
            # source-timeline.xml is B-roll's internal copy of a single video, not a result.
            xml = [str(p.resolve()) for p in output.rglob('*.xml') if p.name != 'source-timeline.xml']
            previews = [str(p.resolve()) for p in output.rglob('preview.mp4')]
            previews += [str(p.resolve()) for p in output.rglob('cleaned.mp4')]
            quality = output / 'quality-check.html'
            result = {'page': str(result_page.resolve()), 'folder': str(output.resolve()),
                      'xml_files': xml, 'previews': previews,
                      'quality': str(quality.resolve()) if quality.is_file() else None,
                      'quality_summary': quality_summary(output)}
            self._update(job_id, status='complete', progress=100, stage='Ready to review', result=result)
        except BaseException as error:
            self._log(job_id, str(error))
            self._update(job_id, status='failed', stage=str(error), progress=100)

    def snapshot(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError(job_id)
            return json.loads(json.dumps(self.jobs[job_id]))

    def open_path(self, path):
        target = Path(path).resolve()
        allowed = (self.root / 'output').resolve()
        if not target.is_relative_to(allowed) or not target.exists():
            raise ValueError('Only generated output can be opened')
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
        return rebuild_project(project, payload, lambda _: None)

    def rebuild_broll(self, payload):
        from hinglish_broll.pipeline import rebuild_project
        project = Path(payload.get('project_path', '')).resolve()
        allowed = (self.root / 'output' / 'broll').resolve()
        if not project.is_relative_to(allowed) or project.name != 'broll-project.json' or not project.is_file():
            raise ValueError('This B-roll project is unavailable')
        choices = payload.get('choices') or {}
        if not isinstance(choices, dict) or not all(isinstance(v, str) for v in choices.values()):
            raise ValueError('Invalid B-roll choices')
        return rebuild_project(project, choices)

    def rebuild_visuals(self, payload):
        from hinglish_visuals.pipeline import rebuild_project
        project = Path(payload.get('project_path', '')).resolve()
        allowed = (self.root / 'output' / 'visuals').resolve()
        if not project.is_relative_to(allowed) or project.name != 'visuals-project.json' or not project.is_file():
            raise ValueError('This Smart Visuals project is unavailable')
        choices = payload.get('choices') or {}
        if not isinstance(choices, dict) or not all(isinstance(v, str) for v in choices.values()):
            raise ValueError('Invalid visual choices')
        return rebuild_project(project, choices)

    def rebuild_sound(self, payload):
        from hinglish_sound.pipeline import remix
        plan = Path(payload.get('plan_path', '')).resolve()
        allowed = (self.root / 'output' / 'sound').resolve()
        if not plan.is_relative_to(allowed) or plan.name != 'sound-plan.json' or not plan.is_file():
            raise ValueError('This sound design is unavailable')
        keep = payload.get('keep') or []
        if not isinstance(keep, list) or not all(isinstance(i, int) for i in keep):
            raise ValueError('Invalid sound choices')
        return remix(plan, keep, payload.get('music', True) is not False)

    def sound_settings(self, values=None):
        from dataclasses import asdict
        from hinglish_sound.settings import load_settings, save_user_settings
        return asdict(load_settings(self.root)) if values is None else save_user_settings(self.root, values)

    def eyecontact_status(self):
        from hinglish_eyecontact.maxine import doctor
        report = doctor(self.root)
        return {'ready': report.ready, 'gpu': report.gpu.name if report.gpu else '',
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
            if origin in local or (origin and origin.startswith('uxp://')):
                self.send_header('Access-Control-Allow-Origin', origin or 'null')
                self.send_header('Vary', 'Origin')

        def _json(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status); self._cors()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def _authorized(self):
            return secrets.compare_digest(self.headers.get('X-Hinglish-Token', ''), state.token)

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
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Hinglish-Token')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'); self.end_headers()

        def do_GET(self):
            if not self._host_ok(): return
            parsed = urlparse(self.path)
            if parsed.path == '/api/health':
                return self._json(200, {'ok': True, 'version': 7})
            if parsed.path == '/api/bridge':
                # Only our own page, the Premiere UXP panel and local programs (no Origin) get the token. A "null"
                # origin can be any website's sandboxed frame; local review pages and CEP read it from disk instead.
                origin = self.headers.get('Origin')
                own = (f'http://127.0.0.1:{state.port}', f'http://localhost:{state.port}')
                if origin is not None and origin not in own and not origin.startswith('uxp://'):
                    return self._json(403, {'error': 'Not allowed'})
                return self._json(200, {'url': f'http://127.0.0.1:{state.port}', 'token': state.token})
            if parsed.path == '/api/pick':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                try:
                    chosen = state.pick(parse_qs(parsed.query).get('kind', ['folder'])[0])
                    return self._json(200, {'path': chosen})
                except Exception as error:
                    return self._json(400, {'error': str(error)})
            if parsed.path == '/api/broll/settings':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                return self._json(200, state.broll_settings())
            if parsed.path == '/api/sound/settings':
                if not self._authorized(): return self._json(403, {'error': 'Not connected'})
                return self._json(200, state.sound_settings())
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
            if path == 'index.html':
                data = data.replace(b'__APP_TOKEN__', state.token.encode())
            self.send_response(200); self.send_header('Content-Type', mimetypes.guess_type(file)[0] or 'application/octet-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

        def do_POST(self):
            if not self._host_ok(): return
            if not self._authorized(): return self._json(403, {'error': 'Not connected'})
            try:
                parsed = urlparse(self.path)
                if parsed.path == '/api/upload':
                    query = parse_qs(parsed.query)
                    length = int(self.headers.get('Content-Length', '0'))
                    target = state.save_upload(query.get('batch', [''])[0], query.get('name', [''])[0],
                                               self.rfile, length)
                    return self._json(201, {'path': str(target.resolve()), 'name': target.name.split('-', 1)[-1]})
                length = int(self.headers.get('Content-Length', '0'))
                payload = json.loads(self.rfile.read(length) or b'{}')
                if parsed.path == '/api/jobs':
                    return self._json(202, state.create_job(payload))
                if parsed.path == '/api/read-script':
                    script = Path(payload['path']).resolve()
                    if not script.is_file() or script.suffix.lower() != '.txt' or script.stat().st_size > 2_000_000:
                        raise ValueError('Choose a normal .txt script file')
                    return self._json(200, {'text': script.read_text(encoding='utf-8-sig')})
                if parsed.path == '/api/open':
                    state.open_path(payload['path']); return self._json(200, {'ok': True})
                if parsed.path == '/api/import-resolve':
                    names = state.import_into_resolve(payload.get('xml_files', []))
                    return self._json(200, {'ok': True, 'timelines': names})
                if parsed.path == '/api/captions/rebuild':
                    return self._json(200, state.rebuild_captions(payload))
                if parsed.path == '/api/broll/rebuild':
                    return self._json(200, state.rebuild_broll(payload))
                if parsed.path == '/api/sound/rebuild':
                    return self._json(200, state.rebuild_sound(payload))
                if parsed.path == '/api/visuals/rebuild':
                    return self._json(200, state.rebuild_visuals(payload))
                if parsed.path == '/api/broll/settings':
                    return self._json(200, state.broll_settings(payload))
                if parsed.path == '/api/sound/settings':
                    return self._json(200, state.sound_settings(payload))
                return self._json(404, {'error': 'Unknown action'})
            except Exception as error:
                return self._json(400, {'error': str(error)})
    return Handler


def serve(root, port=DEFAULT_PORT):
    state = AppState(root, port)
    server = LocalHTTPServer(('127.0.0.1', port), make_handler(state))
    state.port = server.server_address[1]      # the real port (port 0 = any free port)
    state.publish_bridge()
    return server, state
