"""The long video: fast facts (no 30 fps copy of a 4K file) and its words with timing."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import hashlib
import json

import av

from hinglish_cut.model import Media

RATES = [Fraction(x) for x in (24, 25, 30, 48, 50, 60)] + [Fraction(x * 1000, 1001) for x in (24, 30, 60)]


@dataclass
class LongVideo:
    path: str
    duration: float
    fps: Fraction
    width: int
    height: int
    channels: int
    sample_rate: int
    video_start: float

    @property
    def short_fps(self):
        """Shorts run at 30 fps or less: a 60 fps source gives a 30 fps short (every second frame)."""
        return self.fps / 2 if self.fps > 31 else self.fps

    def media(self):
        key = hashlib.sha256(str(Path(self.path).resolve()).encode()).hexdigest()[:16]
        return Media(key, self.path, self.duration, str(self.fps), self.width, self.height, self.channels,
                     self.sample_rate, self.video_start)


def open_video(path):
    path = Path(path).resolve()
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError(f'{path.name}: no video stream')
        if not container.streams.audio:
            raise ValueError(f'{path.name}: no sound in this video (shorts are chosen from what you say)')
        v, a = container.streams.video[0], container.streams.audio[0]
        rate = v.average_rate or v.guessed_rate
        if not rate:
            raise ValueError(f'{path.name}: unknown frame rate')
        fps = min(RATES, key=lambda r: abs(float(r - rate)))
        if abs(float(fps - rate)) > .05:
            raise ValueError(f'{path.name}: unsupported frame rate {float(rate):.3f}')
        duration = float(container.duration or 0) / av.time_base
        if v.duration and v.time_base:
            duration = min(duration, float(v.duration * v.time_base)) if duration else float(v.duration * v.time_base)
        start = float(v.start_time * v.time_base) if v.start_time is not None else 0.0
        width, height = v.codec_context.width, v.codec_context.height
        rotation = int(v.metadata.get('rotate', '0') or 0) % 360
        if rotation in (90, 270):
            width, height = height, width
        return LongVideo(str(path), duration, fps, width, height, min(2, a.codec_context.channels or 2),
                         a.codec_context.sample_rate or 48000, start)


def quick_fingerprint(path):
    """Size + date + the first and last 8 MB: enough to know the file changed, fast on a 13 GB export."""
    path = Path(path)
    stat = path.stat()
    h = hashlib.sha256(json.dumps([stat.st_size, int(stat.st_mtime)]).encode())
    with path.open('rb') as f:
        h.update(f.read(8 << 20))
        if stat.st_size > 16 << 20:
            f.seek(-(8 << 20), 2)
            h.update(f.read())
    return h.hexdigest()


def transcribe(root, video, device='cpu', progress=print, *, skip_invalid_recognition=False, retry_unreadable=False, cache_namespace=None):
    """Words of the long video in source seconds (cached; the speech model runs once per file)."""
    from hinglish_semantic.analysis import transcribe_media
    from hinglish_semantic.core import SemanticSettings
    root = Path(root)
    data = json.loads((root / 'config.phase2.json').read_text(encoding='utf-8-sig'))
    data.update(device=device, speech_backend='swift', matching_backend='word_coverage')
    settings = SemanticSettings(**data)
    engines = {}
    try:
        media=video.media();digest='shorts-' + quick_fingerprint(video.path)
        if cache_namespace:
            digest += '-run-' + hashlib.sha256(str(cache_namespace).encode()).hexdigest()[:24]
        from hinglish_cut.recognition_quality import InvalidRecognitionError
        try:
            transcript, _ = transcribe_media(media, digest, root, settings,
                                             progress, engines,skip_invalid_recognition=skip_invalid_recognition)
        except InvalidRecognitionError:
            if not retry_unreadable or skip_invalid_recognition:raise
            from dataclasses import replace
            if engines.get('engine') is not None:
                engines['engine'].close();engines['engine']=None
            progress('Retrying unreadable speech with the installed independent local recognizer')
            transcript, _ = transcribe_media(media,digest,root,replace(settings,speech_backend='turbo'),progress,engines)
    finally:
        if engines.get('engine') is not None:
            engines['engine'].close()
    return transcript.words
