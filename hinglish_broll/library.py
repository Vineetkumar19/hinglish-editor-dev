"""Index the user's own footage folders with CLIP so B-roll can come from their clips first."""
import hashlib
import json
import os
from pathlib import Path

import av
import numpy as np
from PIL import Image

from hinglish_cut.media import orient_frame, video_rotation
from .stock import Candidate
from .timeline import path_key

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.mts', '.m2ts', '.webm', '.mxf'}
INDEX_VERSION = 1


def sample_times(duration):
    if duration <= 0: return []
    step = 2.0 if duration <= 120 else max(4.0, duration / 240)
    times, t = [], min(.5, duration / 2)
    while t < duration - .1:
        times.append(round(t, 2)); t += step
    return times or [duration / 2]


def read_frames(path, times, size=256):
    """Decode the frames nearest to `times` (seconds), upright, as small PIL images."""
    frames = []
    rotation = video_rotation(path)
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = 'AUTO'
        base = stream.time_base
        for t in times:
            container.seek(int(t / base), stream=stream, backward=True, any_frame=False)
            chosen = None
            for frame in container.decode(stream):
                chosen = frame
                if frame.time is None or frame.time >= t - .02:
                    break
            if chosen is None:
                continue
            image = orient_frame(chosen, rotation).to_image() if rotation else chosen.to_image()
            image.thumbnail((size, size))
            frames.append((t, image))
    return frames


def probe_video(path):
    with av.open(str(path)) as container:
        if not container.streams.video:
            return None
        stream = container.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration else \
            (container.duration / 1_000_000 if container.duration else 0)
        width, height = stream.codec_context.width, stream.codec_context.height
    if video_rotation(path) in (90, 270):
        width, height = height, width
    return duration, width, height


class Library:
    def __init__(self, root, folders, vision, exclude=(), progress=print):
        self.root, self.vision, self.progress = Path(root), vision, progress
        self.cache = self.root / 'cache' / 'broll' / 'library'
        self.cache.mkdir(parents=True, exist_ok=True)
        blocked = {path_key(p) for p in exclude}
        skip_dirs = {path_key(self.root / 'output'), path_key(self.root / 'cache')}
        self.files = []
        for folder in folders:
            for base, dirs, names in os.walk(folder):
                dirs[:] = [d for d in dirs if path_key(Path(base) / d) not in skip_dirs]
                for name in names:
                    p = Path(base) / name
                    if p.suffix.lower() in VIDEO_EXTENSIONS and path_key(p) not in blocked:
                        self.files.append(p)
        self.entries = []   # (path, duration, width, height, times[n], embeddings[n,d])

    def build(self):
        for n, path in enumerate(self.files, 1):
            try:
                stat = path.stat()
                key = hashlib.sha1(json.dumps([INDEX_VERSION, path_key(path), stat.st_size, int(stat.st_mtime),
                                               self.vision_name()]).encode()).hexdigest()
                file = self.cache / f'{key}.npz'
                if file.exists():
                    data = np.load(file)
                    meta = json.loads(str(data['meta']))
                    self.entries.append((str(path), meta['duration'], meta['width'], meta['height'],
                                         data['times'], data['embeddings']))
                    continue
                self.progress(f'  Indexing your footage {n}/{len(self.files)}: {path.name}')
                info = probe_video(path)
                if not info or info[0] < 1.0:
                    continue
                frames = read_frames(path, sample_times(info[0]))
                if not frames:
                    continue
                times = np.array([t for t, _ in frames], np.float32)
                embeddings = self.vision.images([im for _, im in frames]).astype(np.float16)
                meta = json.dumps({'duration': info[0], 'width': info[1], 'height': info[2]})
                np.savez(file, times=times, embeddings=embeddings, meta=np.array(meta))
                self.entries.append((str(path), info[0], info[1], info[2], times, embeddings))
            except Exception as error:
                self.progress(f'  Skipped {path.name}: {error}')
        return self

    def vision_name(self):
        return getattr(self.vision.model.config, '_name_or_path', 'clip')

    def search(self, text_embedding, need, top=5):
        """Best (file, moment) matches for one visual description; one hit per file."""
        hits = []
        for path, duration, width, height, times, embeddings in self.entries:
            if duration < need:
                continue
            sims = embeddings.astype(np.float32) @ text_embedding
            best = int(np.argmax(sims))
            offset = float(min(max(0.0, times[best] - need / 2), duration - need))
            hits.append(Candidate('library', 'library:' + path_key(path) + f'@{offset:.1f}', Path(path).name,
                                  duration, width, height, path=path, offset=offset, score=float(sims[best])))
        return sorted(hits, key=lambda c: -c.score)[:top]
