"""Durable B-roll work, without changing any model's relevance decisions."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def write_json(file, data):
    """Atomic save tolerant of brief Windows reader/antivirus rename locks."""
    file=Path(file);file.parent.mkdir(parents=True,exist_ok=True)
    temporary=file.with_name(file.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
        for attempt in range(6):
            try:
                temporary.replace(file)
                return
            except PermissionError:
                if attempt==5:raise
                time.sleep(.05*2**attempt)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(file, default=None):
    try:
        return json.loads(Path(file).read_text('utf-8'))
    except (OSError, ValueError):
        return default


def request_key(source, settings, **options):
    source = Path(source).resolve()
    files = [source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file())
    stamps = [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in files]
    # Rotating a provider key must not discard already checked clips. Auth
    # circuit breakers have their own credential digest in the stock client.
    configuration=asdict(settings)
    configuration.pop('pexels_key',None);configuration.pop('pixabay_key',None)
    spec = [6, str(source), stamps, configuration, options]
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


class RunStore:
    def __init__(self, root, key):
        self.root = Path(root).resolve()
        marker = os.environ.get('STORYLENS_BROLL_CHECKPOINT')
        self.marker = Path(marker) if marker else None
        record = read_json(self.marker) if self.marker else None
        self.file = None
        if record and record.get('key') == key:
            candidate = Path(record.get('journal', '')).resolve()
            if candidate.is_relative_to(self.root/'output/broll') and candidate.name == 'recovery.json':
                self.file = candidate
        if self.file is None:
            # Pressing Run again also resumes compatible unfinished work. A
            # finished run is never silently reused for a new request.
            for candidate in sorted((self.root/'output/broll').glob('*/recovery.json'),
                                    key=lambda p: p.stat().st_mtime, reverse=True):
                saved = read_json(candidate, {})
                if saved.get('key') == key and saved.get('state') != 'complete':
                    self.file = candidate
                    break
        self.data = read_json(self.file, {}) if self.file else {}
        if self.data.get('key') != key:
            self.file, self.data = None, {}
        self.key = key

    def start(self, output):
        self.file = Path(output)/'recovery.json'
        self.data = {'version': 1, 'key': self.key, 'state': 'running', 'plans': [], 'notes': []}
        self.save()

    @property
    def output(self):
        return self.file.parent if self.file else None

    def save(self):
        self.data['updated_at'] = time.time()
        write_json(self.file, self.data)
        if self.marker:
            write_json(self.marker, {'key': self.key, 'journal': str(self.file.resolve())})


def valid_clip(folder, relative):
    if not relative:
        return False
    file = (Path(folder)/relative).resolve()
    if not file.is_relative_to(Path(folder).resolve()) or not file.is_file() or file.stat().st_size == 0:
        return False
    try:
        import av
        with av.open(str(file)) as media:
            return next(media.decode(video=0), None) is not None
    except Exception:
        return False


def finalization_only(root, payload, source):
    """A completed bank can rebuild its small preview without occupying the GPU."""
    if not source or not Path(source).is_file():return False
    from .settings import load_settings
    settings=load_settings(root,density=payload.get('density','medium'),device=payload.get('device','cpu'))
    key=request_key(source,settings,output_format=None if payload.get('format','source')=='source' else payload['format'],
        black_background=bool(payload.get('broll_black_background')),target_count=payload.get('broll_count',0),
        brief=str(payload.get('broll_brief') or '').strip(),review_options=bool(payload.get('broll_review_options')),
        options_per_moment=payload.get('broll_options_per_moment',5),reference_script=str(payload.get('script') or '').strip())
    store=RunStore(root,key)
    if not store.output or not store.data.get('plans'):return False
    for plan in store.data['plans']:
        folder=store.output/plan['folder']
        project=read_json(folder/'broll-project.json',{})
        slots=project.get('slots',[])
        if len(slots)!=len(plan['slots']) or not read_json(folder/'ranked-candidates.json'):return False
        for slot in slots:
            if not slot.get('collection_complete'):return False
            clips=[c.get('clip') for c in slot.get('options',[])]+([slot['clip']] if slot.get('clip') else [])
            if not all(valid_clip(folder,clip) for clip in clips):return False
    return True


def restore_choices(folder, project):
    """Drop interrupted/broken media, never a valid saved choice or timing edit."""
    for slot in project.get('slots', []):
        removed = {c['id'] for c in slot.get('options', []) if not valid_clip(folder, c.get('clip'))}
        slot['options'] = [c for c in slot.get('options', []) if c['id'] not in removed]
        chosen = (slot.get('chosen') or {}).get('id')
        if slot.get('clip') and not valid_clip(folder, slot['clip']):
            removed.add(chosen)
            slot.update(chosen=None, clip=None)
        if removed:
            slot['attempted'] = [a for a in slot.get('attempted', []) if a['id'] not in removed]
            slot['collection_complete'] = False


def transient(error):
    import requests
    if isinstance(error, (TimeoutError, ConnectionError, requests.Timeout, requests.ConnectionError)):
        return True
    response = getattr(error, 'response', None)
    return response is not None and response.status_code in (408, 429, 500, 502, 503, 504)


def retry(operation, progress, label, attempts=3):
    """Only temporary transport errors; never retry an auth or relevance veto."""
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as error:
            if not transient(error) or attempt == attempts-1:
                raise
            progress(f'{label} was interrupted. Retrying ({attempt+1}/{attempts-1}); saved work is kept.')
            time.sleep(min(4, 2**attempt))
