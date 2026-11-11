"""Choose a measured musical passage instead of always playing a track's intro."""
import numpy as np
from .library import decode


def passage(path, duration, energy=2, climax=None):
    rate = 8000
    audio = decode(path, rate, mono=True)[0]
    if not len(audio) or not np.isfinite(audio).all() or np.max(np.abs(audio)) < 1e-7:
        raise ValueError('Sound music file is silent')
    n = max(1, round(duration * rate))
    if len(audio) <= n:
        return {'source_offset': 0., 'selection': 'whole track; crossfade loop if needed'}
    block = rate // 4
    envelope = np.array([np.sqrt(np.mean(audio[i:i + block] ** 2) + 1e-12)
                         for i in range(0, len(audio), block)])
    active = envelope[envelope > max(1e-7, envelope.max() * .01)]
    if not len(active):
        raise ValueError('Sound music file is silent')
    target = np.percentile(active, {1: 25, 2: 50, 3: 80}.get(energy, 50))
    width = max(1, round(duration * 4))
    candidates = range(0, max(1, len(envelope) - width), 4)
    def score(i):
        e = envelope[i:i + width]
        silence = float(np.mean(e < active.max() * .015))
        match = abs(float(e.mean()) - target) / (active.mean() + 1e-8)
        if climax is not None and len(e):
            peak = np.argmax(e) / 4
            match += abs(peak - min(duration, max(0, climax))) / max(1, duration)
        return match + silence * 4
    best = min(candidates, key=score)
    return {'source_offset': best / 4, 'selection': 'measured energy passage',
            'requested_energy': energy, 'climax_seconds': climax}
