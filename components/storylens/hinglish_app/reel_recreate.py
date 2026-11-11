"""Prepare one local reference reel for an editable After Effects assembly."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import threading
import uuid


def intervals(plan, duration):
    """Use actual detected attacks as boundaries; never manufacture beats."""
    boundaries = [0.0] + sorted({round(float(b['timeline_seconds']), 6)
                                  for b in plan['beats'] if 0 < float(b['timeline_seconds']) < duration}) + [duration]
    return [{'start': a, 'end': b, 'name': 'Beat section %02d' % (i + 1)}
            for i, (a, b) in enumerate(zip(boundaries, boundaries[1:])) if b - a > .001]


class ReelRecreateService:
    def __init__(self, root, work_lock):
        self.root = Path(root)
        self.folder = self.root / 'output' / 'reel-recreate'
        self.work_lock = work_lock
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='reel-recreate')
        self.jobs = {}

    def upload(self, name, stream, length):
        if Path(str(name).replace('\\', '/')).suffix.lower() != '.mp4' or not 0 < length <= 2 * 1024**3:
            raise ValueError('Choose an MP4 reel smaller than 2 GB.')
        folder = self.folder / 'uploads'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (uuid.uuid4().hex + '.mp4')
        partial = target.with_suffix('.partial')
        try:
            with partial.open('wb') as output:
                remaining = length
                while remaining:
                    block = stream.read(min(1024**2, remaining))
                    if not block: raise ValueError('The reel upload stopped early. Choose it again.')
                    output.write(block)
                    remaining -= len(block)
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return {'path': str(target.resolve()), 'name': Path(name).name}

    def start(self, payload):
        source = Path(str(payload.get('path', ''))).resolve()
        if not source.is_file() or not source.is_relative_to((self.folder / 'uploads').resolve()):
            raise ValueError('Upload an MP4 reel in Reel Recreate first.')
        density = payload.get('pace', 'medium')
        if density not in ('slow', 'medium', 'fast'): raise ValueError('Choose Slow, Medium or Fast.')
        style = str(payload.get('style', 'caption_2'))
        from hinglish_captions.styles import SELECTABLE_TEMPLATES
        if style not in SELECTABLE_TEMPLATES:raise ValueError('Choose a current Auto Captions style.')
        mode = payload.get('caption_source', 'auto')
        if mode not in ('auto', 'speech', 'lyrics'): raise ValueError('Choose Auto, Spoken voice or Song lyrics.')
        pasted = str(payload.get('reference_script') or '').strip()
        if len(pasted) > 12000: raise ValueError('Paste fewer than 12,000 caption characters.')
        key = uuid.uuid4().hex
        with self.lock:
            if any(j['status'] in ('queued', 'running') for j in self.jobs.values()):
                raise ValueError('A reel is already being prepared. Wait for it to finish.')
            self.jobs[key] = {'id': key, 'status': 'queued', 'stage': 'Waiting for the local editing queue.'}
        self.pool.submit(self._run, key, source, density, style, mode, pasted)
        return self.snapshot(key)

    def snapshot(self, key):
        with self.lock:
            if key in self.jobs: return json.loads(json.dumps(self.jobs[key]))
        if len(key) == 32 and all(c in '0123456789abcdef' for c in key):
            saved = self.folder / key / 'reel-plan.json'
            if saved.is_file():
                return {'id':key,'status':'complete','stage':'Saved reel preparation is ready.',
                        'result':json.loads(saved.read_text('utf-8'))}
        raise ValueError('This reel result is unavailable. Prepare it again.')

    def revise(self, payload):
        key = str(payload.get('id', ''))
        job = self.snapshot(key)
        if job['status'] != 'complete': raise ValueError('Finish preparing the reel before changing captions.')
        style = str(payload.get('style', job['result']['caption']['style']))
        from hinglish_captions.styles import SELECTABLE_TEMPLATES
        if style not in SELECTABLE_TEMPLATES: raise ValueError('Choose a current Auto Captions style.')
        from hinglish_captions.project import rebuild_project
        project_path = Path(job['result']['caption_project']).resolve()
        if not project_path.is_relative_to(self.folder.parent / 'captions'):
            raise ValueError('The saved caption project is outside Storylens.')
        changes = {'style':style,'save_project_only':True}
        if 'texts' in payload: changes['texts'] = payload['texts']
        with self.work_lock:
            revised = rebuild_project(project_path, changes)
            from .editor_panel import caption_manifest
            caption = caption_manifest(revised['project'])
            previous = job['result']
            revision_number = int(previous.get('revision_number', 0)) + 1
            revision_id = uuid.uuid4().hex
            job['result']['caption'] = caption
            job['result']['cues'] = revised['project']['cues']
            job['result']['caption_style'] = style
            job['result']['revision_number'] = revision_number
            job['result']['revision_id'] = revision_id
            folder = self.folder / key
            plan = json.dumps(job['result'],ensure_ascii=False,indent=2)
            (folder / ('reel-plan-revision-%04d.json' % revision_number)).write_text(plan,'utf-8')
            (folder / 'reel-plan.json').write_text(plan,'utf-8')
            with self.lock: self.jobs[key] = job
        return job

    def _stage(self, key, message):
        with self.lock: self.jobs[key]['stage'] = message

    def _run(self, key, source, pace, style, mode, pasted):
        try:
            from hinglish_cut.gpu_lock import gpu_lock
            with self.work_lock, gpu_lock(self.root):
                self._stage(key, 'Reading the reel and preparing its soundtrack.')
                with self.lock: self.jobs[key]['status'] = 'running'
                from hinglish_cut.media import prepare_media, extract_audio
                media, conform_note = prepare_media(source, self.root / 'cache' / 'conformed',
                                                    lambda msg: self._stage(key, msg), encoder='cuda',
                                                    require_30fps=True)
                if media.duration > 3600:raise ValueError('Choose a reel shorter than one hour.')
                folder = self.folder / key
                folder.mkdir(parents=True, exist_ok=True)
                audio = folder / 'analysis-audio.wav'
                extract_audio(media, audio)
                self._stage(key, 'Recognizing and timing captions locally.')
                from hinglish_captions.pipeline import run
                # The existing speech pipeline falls back to full-song lyric recognition
                # when conversational recognition rejects the soundtrack.
                caption_mode = 'lyrics' if mode == 'lyrics' else 'speech'
                caption_output = run(self.root, media.path, style=style, device='cuda',
                                     reference_script=pasted, caption_content=caption_mode,
                                     preview=False, editable_only=True, analysis_audio=audio,
                                     progress=lambda msg: self._stage(key, msg))
                projects = list(caption_output.rglob('caption-project.json'))
                if len(projects) != 1: raise ValueError('The reel did not produce one editable caption project.')
                project = json.loads(projects[0].read_text('utf-8'))
                from .editor_panel import caption_manifest
                caption = caption_manifest(project)
                self._stage(key, 'Finding music beats on NVIDIA RTX and making media slots.')
                from hinglish_beats.detect import analyze
                beat_plan = analyze({'path': str(audio), 'density': {'slow':'light','medium':'medium','fast':'strong'}[pace],
                                     'fps': caption['fps'], 'source_in': 0, 'source_out': min(media.duration, 3600),
                                     'device': 'cuda'})
                result = {'type': 'reel_recreate', 'version': 1, 'id': key, 'name': 'Reel Recreate', 'source': str(source),
                          'audio': str(source), 'analysis_audio': str(audio.resolve()), 'duration': caption['duration'],
                          'width': caption['width'], 'height': caption['height'], 'fps': caption['fps'],
                          'pace': pace, 'beats': beat_plan['beats'], 'sections': intervals(beat_plan, caption['duration']),
                          'beat_analysis_device': 'cuda', 'speech_device': 'cuda',
                          'video_conform_encoder': 'h264_nvenc' if conform_note else 'source_unchanged',
                          'caption_video_rendered': False,
                          'caption': caption, 'caption_project': str(projects[0].resolve()),
                          'cues': project['cues'],
                          'revision_number': 0,
                          'caption_source': project.get('caption_content', caption_mode),
                          'review_note': 'Review wording and beat positions. Mixed speech over singing may need Spoken voice selection or pasted captions.'}
                (folder / 'reel-plan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
                with self.lock: self.jobs[key] = {'id': key, 'status': 'complete', 'stage': 'Reel preparation is ready.', 'result': result}
        except Exception as error:
            from .user_messages import failure
            with self.lock: self.jobs[key] = {'id': key, 'status': 'failed', 'stage': 'Reel preparation stopped.', **failure(error, feature='Reel Recreate')}


_services = {}
def service(root, work_lock):
    key = str(Path(root).resolve())
    if key not in _services: _services[key] = ReelRecreateService(root, work_lock)
    return _services[key]
