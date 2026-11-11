"""Completed-job binding for Smart Visuals' manual SOURCE-bank transport.

No listener, tokens, model calls, renders or host actions. The suite supplies its
already-authorized application state and keeps route/license authorization.
Media access takes an offered asset ID plus active baseline, never a file path.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

from hinglish_visuals.source_result import ensure_source_result, apply_source_request

_locks = {}
_guard = threading.Lock()
_FORMATS = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}


class VisualSourceTransport:
    """Use the engine application's snapshot method, not client-supplied jobs.

    describe(job_id, project_path=None) -> typed bank and media identity choices
    select(job_id, payload) -> explicit raw decisions, never insertion
    resolve_media(job_id, project_path, manifest_sha256, asset_id) -> checked file

    All methods bind to a completed `mode=visuals` AppState job. Standalone
    recheck journals and arbitrary output folders are not application receipts.
    """
    def __init__(self, state, *, lock_timeout=5.):
        self.state = state
        self.root = Path(state.root).resolve()
        self.output = (self.root / 'output').resolve()
        self.visuals = (self.output / 'visuals').resolve()
        if self.output.parent != self.root or self.output.name != 'output' or self.visuals.parent != self.output or self.visuals.name != 'visuals':
            raise ValueError('The Smart Visuals output location is not bound to this application.')
        self.lock_timeout = max(0., min(float(lock_timeout), 30.))

    @staticmethod
    def _path(value, parent, *, directory=False):
        if not isinstance(value, (str, Path)) or not str(value):
            raise ValueError('Choose a saved Smart Visuals result.')
        raw = Path(value)
        if not raw.is_absolute():
            raise ValueError('Choose a saved Smart Visuals result from this application.')
        path = raw.resolve(strict=True)
        if raw.absolute() != path or path == parent or not path.is_relative_to(parent):
            raise ValueError('This file is not bound to the selected Smart Visuals result.')
        if not (path.is_dir() if directory else path.is_file()):
            raise ValueError('This saved Smart Visuals result is unavailable.')
        return path

    def _project(self, job_id, requested):
        try:
            if not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', job_id):
                raise ValueError()
            job = self.state.snapshot(job_id)
            if not isinstance(job, dict) or job.get('id') != job_id or job.get('mode') != 'visuals' or job.get('status') != 'complete':
                raise ValueError()
            result = job['result']
            folder = self._path(result['folder'], self.visuals, directory=True)
            page = self._path(result['page'], folder)
            if page.parent != folder or page.name not in ('report.html', 'index.html'):
                raise ValueError()
            if page.name == 'report.html':
                allowed = [self._path(folder / 'visuals-project.json', folder)]
            else:
                receipt = self._path(folder / 'result.json', folder)
                rows = json.loads(receipt.read_text('utf-8'))['results']
                if not isinstance(rows, list) or not rows:
                    raise ValueError()
                allowed = []
                for row in rows:
                    name = row['folder']
                    if not isinstance(name, str) or name in ('.', '..') or '/' in name or '\\' in name or ':' in name:
                        raise ValueError()
                    child = self._path(folder / name, folder, directory=True)
                    self._path(child / 'report.html', child)
                    allowed.append(self._path(child / 'visuals-project.json', child))
                if len(set(allowed)) != len(allowed):
                    raise ValueError()
            if requested is None:
                if len(allowed) != 1:
                    raise ValueError()
                project = allowed[0]
            else:
                project = self._path(requested, folder)
                if project not in allowed:
                    raise ValueError()
            saved = json.loads(project.read_text('utf-8'))
            if saved.get('review_options') is not True or saved.get('collecting'):
                raise ValueError()
            return project
        except (KeyError, TypeError, ValueError, OSError):
            raise ValueError('Choose a completed Smart Visuals job and its saved review. Running, foreign or unavailable results cannot be used.') from None

    @contextmanager
    def _transaction(self, project):
        # Same byte-lock pattern as existing project intake transactions. This
        # is a short CPU/file lock, never the shared GPU or publishing lock.
        key = hashlib.sha256(os.path.normcase(str(project)).encode('utf-8')).hexdigest()
        folder = self.root / 'cache/app/visual-source-locks'
        folder.mkdir(parents=True, exist_ok=True)
        if not folder.resolve().is_relative_to(self.root):
            raise ValueError('The source-bank lock location is outside this application.')
        path = folder / (key + '.lock')
        if path.resolve() != path:
            raise ValueError('The source-bank lock file is not bound to this application.')
        with _guard:
            lock = _locks.setdefault(str(path), threading.RLock())
        deadline = time.monotonic() + self.lock_timeout
        with lock, path.open('a+b') as stream:
            stream.seek(0, 2)
            if not stream.tell():
                stream.write(b'0'); stream.flush()
            acquired = False
            while not acquired:
                stream.seek(0)
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError as error:
                    if error.errno not in (11, 13, 35, 36):
                        raise
                    if time.monotonic() >= deadline:
                        raise ValueError('Another source-bank update is finishing. Your choices are kept; try again shortly.') from None
                    time.sleep(.05)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def _current(self, job_id, project):
        if self._project(job_id, str(project)) != project:
            raise ValueError('The completed result changed. Reopen its review.')
        descriptor = ensure_source_result(project)
        manifest_path = self._path(descriptor['manifest_path'], project.parent)
        raw = manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != descriptor['manifest_sha256']:
            raise ValueError('The raw source-bank baseline changed. Reopen its review.')
        manifest = json.loads(raw)
        if manifest['source_project']['path'] != str(project) or manifest['source_project']['sha256'] != hashlib.sha256(project.read_bytes()).hexdigest():
            raise ValueError('The source project changed. Reopen its review.')
        return descriptor, manifest

    def _allowed_media(self, project, choice):
        if choice.get('kind') != 'image':
            raise ValueError('Only raw image choices are available here. Keep B-roll videos separate.')
        file = choice['file']
        path = self._path(file['path'], project.parent)
        mime = _FORMATS.get(path.suffix.lower())
        if not mime or mime != file.get('mime'):
            raise ValueError('This image format is not supported by the panel source transport.')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != file.get('sha256') or len(raw) != file.get('bytes'):
            raise ValueError('This source image changed. Reopen the latest review before using it.')
        return {'asset_id':choice['asset_id'], 'media_id':choice['media_id'], 'path':str(path),
                'sha256':file['sha256'], 'bytes':len(raw), 'mime':mime}

    def _describe(self, job_id, project, descriptor, manifest):
        banks = []
        for bank in manifest['banks']:
            choices, unavailable = [], list(bank['unavailable_choices'])
            for choice in bank['choices']:
                try:
                    media = self._allowed_media(project, choice)
                    choices.append({**choice, 'media':media})
                except (ValueError, KeyError, TypeError, OSError) as error:
                    unavailable.append({'media_id':choice.get('media_id'), 'reason':str(error)})
            banks.append({**bank, 'choices':choices, 'unavailable_choices':unavailable,
                'shortfall':max(0, bank['target']-len(choices)),
                'availability':'no_match' if not choices else ('ready' if len(choices)>=bank['target'] else 'partial')})
        return {**descriptor, 'job_id':job_id, 'banks':banks}

    def describe(self, job_id, project_path=None):
        project = self._project(job_id, project_path)
        with self._transaction(project):
            descriptor, manifest = self._current(job_id, project)
            return self._describe(job_id, project, descriptor, manifest)

    def select(self, job_id, payload):
        if not isinstance(payload, dict):
            raise ValueError('Choose visuals from the completed review before saving source assets.')
        project = self._project(job_id, payload.get('project_path'))
        with self._transaction(project):
            descriptor, manifest = self._current(job_id, project)
            # Reject unsupported media before core apply can advance the pointer.
            choices = payload.get('choices')
            if not isinstance(choices, dict):
                raise ValueError('Choose visuals by their saved slot and media identity.')
            offered = {str(b['slot_index']):{o['media_id']:o for o in b['choices']} for b in manifest['banks']}
            for index, media_id in choices.items():
                if media_id is None or media_id == '':
                    continue
                if not isinstance(media_id, str) or str(index) not in offered or media_id not in offered[str(index)]:
                    raise ValueError('That image is not an offered choice for this subject.')
                self._allowed_media(project, offered[str(index)][media_id])
            # Core SOURCE banks support more formats than this panel transport.
            # An inherited choice must pass the same allowlist as a new pick;
            # explicit No visual can still clear an unsupported saved choice.
            for bank in manifest['banks']:
                if str(bank['slot_index']) in choices:
                    continue
                if bank['selection']['state'] == 'selected':
                    inherited = next(o for o in bank['choices'] if o['asset_id'] == bank['selection']['asset_id'])
                    self._allowed_media(project, inherited)
            result = apply_source_request({**payload, 'project_path':str(project)})
            current, updated = self._current(job_id, project)
            return {**self._describe(job_id, project, current, updated),
                    'selected_sources':result['selected_sources']}

    def resolve_media(self, job_id, project_path, manifest_sha256, asset_id):
        project = self._project(job_id, project_path)
        with self._transaction(project):
            descriptor, manifest = self._current(job_id, project)
            if manifest_sha256 != descriptor['manifest_sha256']:
                raise ValueError('This source-bank baseline is stale. Reopen the latest review.')
            if not isinstance(asset_id, str):
                raise ValueError('Choose an offered source-image identity.')
            choice = next((o for b in manifest['banks'] for o in b['choices'] if o['asset_id']==asset_id), None)
            if choice is None:
                raise ValueError('That image is not offered by this completed result.')
            return self._allowed_media(project, choice)
