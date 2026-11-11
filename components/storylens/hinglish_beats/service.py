"""Bounded background analysis shared by Desktop, Premiere and Resolve panels."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import csv
import json
import threading
import uuid
from .detect import analyze, effect_plan


class BeatService:
    def __init__(self, root, work_lock=None):
        self.root = Path(root)
        self.folder = self.root / 'output' / 'beats'
        self.lock = threading.Lock()
        self.work_lock = work_lock or threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='beat-analysis')
        self.jobs = {}

    def save_upload(self, name, stream, length):
        from .detect import EXTENSIONS
        name = Path(str(name or '').replace('\\', '/')).name
        if Path(name).suffix.lower() not in EXTENSIONS or not 0 < length <= 2 * 1024**3:
            raise ValueError('Choose a supported music file smaller than 2 GB')
        folder = self.folder / 'music'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (uuid.uuid4().hex + Path(name).suffix.lower())
        partial = target.with_suffix(target.suffix + '.partial')
        try:
            remaining = length
            with partial.open('wb') as file:
                while remaining:
                    block = stream.read(min(1024**2, remaining))
                    if not block: raise ValueError('The music upload stopped early')
                    file.write(block)
                    remaining -= len(block)
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return {'path': str(target.resolve()), 'name': name}

    def start(self, payload):
        with self.lock:
            if any(j['status'] in ('queued', 'running') for j in self.jobs.values()):
                raise ValueError('A music analysis is already running. Wait for it to finish.')
            key = uuid.uuid4().hex
            # Bound memory; completed plans remain on disk.
            if len(self.jobs) > 50:
                self.jobs.pop(next(iter(self.jobs)))
            self.jobs[key] = {'id': key, 'status': 'queued'}
        self.pool.submit(self._run, key, dict(payload))
        return self.snapshot(key)

    def _run(self, key, payload):
        try:
            from hinglish_cut.gpu_lock import gpu_lock
            from hinglish_cut.compute_policy import heavy_device
            with self.work_lock,gpu_lock(self.root):
                payload['device']=heavy_device(self.root,payload.get('device'))
                with self.lock:
                    self.jobs[key]['status'] = 'running'
                plan = analyze(payload)
                plan['id'] = key
                folder = self.folder / key
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'beat-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
                with (folder / 'markers.csv').open('w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(['Name', 'Timeline seconds', 'Frame', 'Strength', 'Source seconds'])
                    for i, beat in enumerate(plan['beats'], 1):
                        writer.writerow([f'Storylens Beat {i}', beat['timeline_seconds'], beat['frame'], beat['strength'], beat['source_seconds']])
                with self.lock:
                    self.jobs[key] = {'id': key, 'status': 'complete', 'plan': plan, 'folder': str(folder.resolve())}
        except Exception as error:
            from hinglish_app.user_messages import failure
            with self.lock:
                self.jobs[key] = {'id': key, 'status': 'failed', **failure(error,feature='Beat analysis')}

    def snapshot(self, key):
        with self.lock:
            if key not in self.jobs:
                raise ValueError('Beat analysis unavailable; analyze the music again')
            return json.loads(json.dumps(self.jobs[key]))

    def effects(self, payload):
        job = self.snapshot(payload.get('id', ''))
        if job['status'] != 'complete':
            raise ValueError('Finish beat detection before applying effects')
        result = effect_plan(job['plan'], payload)
        (Path(job['folder']) / 'effect-plan.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
