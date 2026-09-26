"""Bounded-memory speech detection, independent of script matching and ASR."""
from dataclasses import dataclass, asdict
import hashlib
import json
import math
from pathlib import Path

from hinglish_cut.cutting import merge_ranges
from hinglish_cut.media import SAMPLE_RATE, read_audio
from hinglish_cut.model import Cut


@dataclass
class CleanSettings:
    threshold: float = 0.35
    min_silence: float = 0.30
    pre_padding: float = 0.08
    post_padding: float = 0.12
    block_seconds: int = 60
    cpu_threads: int = 4

    def __post_init__(self):
        if not math.isfinite(self.threshold) or not 0.05 <= self.threshold <= 0.95:
            raise ValueError('Speech threshold must be between 0.05 and 0.95')
        for field in ('min_silence', 'pre_padding', 'post_padding'):
            value = getattr(self, field)
            if not math.isfinite(value) or not 0 <= value <= 5:
                raise ValueError(f'{field} must be between 0 and 5 seconds')
        if not 10 <= self.block_seconds <= 300:
            raise ValueError('Analysis blocks must be 10 to 300 seconds')
        if not 1 <= self.cpu_threads <= 32:
            raise ValueError('CPU threads must be 1 to 32')


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


class SpeechDetector:
    def __init__(self, settings):
        import torch
        from silero_vad import load_silero_vad
        torch.set_num_threads(settings.cpu_threads)
        self.model = load_silero_vad()
        self.settings = settings

    def __call__(self, samples):
        import torch
        from silero_vad import get_speech_timestamps
        found = get_speech_timestamps(
            torch.from_numpy(samples.copy()), self.model,
            sampling_rate=SAMPLE_RATE, threshold=self.settings.threshold,
            min_speech_duration_ms=50, min_silence_duration_ms=100,
            speech_pad_ms=0, return_seconds=False,
        )
        return [(r['start'] / SAMPLE_RATE, r['end'] / SAMPLE_RATE) for r in found]


def detect_blocks(wav, duration, cache, settings, detector=None, progress=print):
    """Overlap blocks so a word crossing a minute boundary is not cut in half.

    Cache belongs to a whole-file media digest supplied by the caller. Each
    completed minute can be reused after interruption, without loading ASR.
    """
    config = {'version': 1, 'silero': '6.2.1', **asdict(settings)}
    key = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
    cache = Path(cache) / key
    regions = []
    for index, start in enumerate(range(0, math.ceil(duration), settings.block_seconds)):
        end = min(duration, start + settings.block_seconds)
        cached = cache / f'{index:06d}.json'
        if cached.exists():
            data = json.loads(cached.read_text(encoding='utf-8'))
            block = data['speech']
            if data['start'] != start or data['end'] != end:
                raise ValueError(f'Analysis cache mismatch: {cached}')
            progress(f'  Reusing speech analysis {start:.0f}-{end:.0f}s')
        else:
            progress(f'  Detecting speech {start:.0f}-{end:.0f}s / {duration:.0f}s')
            if detector is None:
                detector = SpeechDetector(settings)
            left, right = max(0, start - 2), min(duration, end + 2)
            block = [(max(start, left + a), min(end, left + b))
                     for a, b in detector(read_audio(wav, left, right))
                     if left + a < end and left + b > start]
            write_json(cached, {'start': start, 'end': end, 'speech': block})
        for a, b in block:
            if not (math.isfinite(a) and math.isfinite(b) and start <= a < b <= end):
                raise ValueError(f'Invalid speech bounds in {cached}')
        regions.extend(block)
    return merge_ranges(regions)


def plan_cuts(media, speech, settings):
    """Keep speech chronologically, padding outward onto actual video frames."""
    fps = float(media.rate)
    limit = math.floor(media.duration * fps + 1e-6)
    groups = merge_ranges(speech, settings.min_silence)
    ranges = merge_ranges([
        (max(0, math.floor((a - settings.pre_padding) * fps + 1e-9)),
         min(limit, math.ceil((b + settings.post_padding) * fps - 1e-9)))
        for a, b in groups
    ])
    # Do not leave one- or two-frame jumps between padded regions.
    ranges = merge_ranges(ranges, 1)
    return [Cut(media.id, int(a), int(b), i) for i, (a, b) in enumerate(ranges)]


def removed_ranges(media, cuts):
    cursor = 0
    removed = []
    limit = math.floor(media.duration * float(media.rate) + 1e-6)
    for cut in cuts:
        if cut.start_frame > cursor:
            removed.append((cursor, cut.start_frame))
        cursor = cut.end_frame
    if cursor < limit:
        removed.append((cursor, limit))
    return removed


def verify_plan(media, cuts, speech):
    """Check time bounds, chronology and preservation of ALL detected speech."""
    fps = float(media.rate)
    limit = math.floor(media.duration * fps + 1e-6)
    previous = 0
    for cut in cuts:
        if cut.media_id != media.id or not previous <= cut.start_frame < cut.end_frame <= limit:
            raise ValueError('Invalid or overlapping edit ranges')
        previous = cut.end_frame
    for a, b in speech:
        if not any(c.start_frame / fps <= a + 1e-6 and c.end_frame / fps >= b - 1e-6 for c in cuts):
            raise ValueError('An edit would remove detected speech; export stopped')
