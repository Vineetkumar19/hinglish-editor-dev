"""Zoom events and their per-frame zoom curve (eased, never jittery)."""
from dataclasses import dataclass
import math

import numpy as np

IMPACT_OVERSHOOT = 1.045   # impact zoom lands 4.5% past the target, then settles


def ease_in_out(t):
    """Sine ease-in-out: gentle start and landing; peak speed only 1.57x the average (cubic is 3x)."""
    t = min(1.0, max(0.0, t))
    return (1 - math.cos(math.pi * t)) / 2


def ease_out(t):
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


@dataclass
class ZoomEvent:
    kind: str          # smooth | punch | impact | reveal | push
    start: float       # seconds: first frame affected
    word: float        # seconds: the stressed word (full zoom is reached here)
    hold_end: float    # seconds: zoom starts leaving
    end: float         # seconds: back to normal
    level: float       # zoom factor at full zoom, e.g. 1.15
    text: str = ''
    word_text: str = ''
    strength: int = 2
    settle: float = .28   # impact only

    def value(self, t):
        """Zoom factor at time t (1.0 outside the event)."""
        if t < self.start or t >= self.end:
            return 1.0
        L = self.level
        if self.kind == 'punch':
            return L
        if self.kind == 'impact':
            peak = L * IMPACT_OVERSHOOT
            return peak - (peak - L) * ease_out((t - self.word) / self.settle) if t < self.word + self.settle else L
        if self.kind == 'reveal':
            return L - (L - 1) * ease_in_out((t - self.start) / max(1e-6, self.end - self.start))
        # smooth and push: ease in, hold, ease out
        if t < self.word:
            return 1 + (L - 1) * ease_in_out((t - self.start) / max(1e-6, self.word - self.start))
        if t < self.hold_end:
            return L
        return 1 + (L - 1) * (1 - ease_in_out((t - self.hold_end) / max(1e-6, self.end - self.hold_end)))


def build_curve(events, frames, fps, baseline=None):
    """Per-frame zoom factor for the whole sequence. `baseline` holds jump-cut framing."""
    curve = np.ones(frames) if baseline is None else np.array(baseline, dtype=float)
    fps = float(fps)
    for e in events:
        first, last = max(0, int(e.start * fps)), min(frames, int(np.ceil(e.end * fps)))
        for f in range(first, last):
            curve[f] = max(curve[f], e.value(f / fps))
    return curve


def quantize(curve, step=.0001):
    """Round to 0.01% steps. Coarser steps (0.1%) made the slow start/end of an ease hold still for a few
    frames and then jump, which reads as stutter; 0.01% is far below one pixel at 4K."""
    return np.round(np.asarray(curve) / step) * step
