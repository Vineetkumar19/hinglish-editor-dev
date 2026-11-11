"""Find hard cuts so a continuous zoom can use verified framing in each shot."""
import hashlib
import json
from pathlib import Path

import av
import numpy as np

CUT_MIN_DIFF = 18.0     # mean absolute grey-level change (0-255) that counts as a hard cut
CUT_RATIO = 4.0         # ...and it must stand out this much from the usual frame-to-frame change


def detect_cuts(path, cache_dir=None):
    """Times (seconds) where the picture changes to a new shot. Cached per file."""
    path = Path(path)
    stat = path.stat()
    key = hashlib.sha1(json.dumps([str(path.resolve()), stat.st_size, int(stat.st_mtime), 1]).encode()).hexdigest()
    cache = Path(cache_dir) / f'{key}.json' if cache_dir else None
    if cache and cache.exists():
        return json.loads(cache.read_text(encoding='utf-8'))
    diffs, times, previous = [], [], None
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = 'AUTO'
        for frame in container.decode(stream):
            small = frame.reformat(width=48, height=48, format='gray').to_ndarray().astype(np.float32)
            if previous is not None:
                diffs.append(float(np.abs(small - previous).mean()))
                times.append(frame.time or 0.0)
            previous = small
    cuts = []
    if diffs:
        values = np.array(diffs)
        for i, value in enumerate(values):
            window = values[max(0, i - 15):i + 16]
            typical = float(np.median(window)) + 1.0
            if value >= CUT_MIN_DIFF and value >= CUT_RATIO * typical:
                if not cuts or times[i] - cuts[-1] > .3:
                    cuts.append(round(times[i], 3))
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(cuts), encoding='utf-8')
    return cuts


def sequence_shots(seq, cache_dir=None):
    """[(start_s, end_s)] shots on the talking-head track: clip edges plus cuts inside each source."""
    fps = float(seq.fps)
    bounds = set()
    for clip in seq.clips:
        start, end = clip.start / fps, clip.end / fps
        bounds.update((round(start, 3), round(end, 3)))
        if not clip.path or not Path(clip.path).is_file():
            continue
        src_in, src_out = clip.source_seconds(seq.fps)
        for cut in detect_cuts(clip.path, cache_dir):
            if src_in < cut < src_out:
                bounds.add(round(start + cut - src_in, 3))
    edges = sorted(bounds)
    return [(a, b) for a, b in zip(edges, edges[1:]) if b - a > 1e-3]
