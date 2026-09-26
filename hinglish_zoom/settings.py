"""Zoom timing profiles (Reel vs YouTube) and user choices."""
from dataclasses import dataclass, replace

SHORT_FORM_LIMIT = 180.0   # seconds; longer timelines use YouTube long-form pacing


@dataclass(frozen=True)
class ZoomProfile:
    name: str
    spacing: float      # minimum seconds between two emphasised words that get a zoom
    gap: float          # minimum un-zoomed seconds between two zoom events
    ramp_in: float      # smooth zoom-in duration (reaches full zoom on the stressed word)
    ramp_out: float     # smooth zoom-out duration
    hold_min: float     # shortest time a zoom stays in
    hold_max: float     # longest time a zoom stays in
    reveal: float       # zoom-out "reveal" duration
    push_max: float     # longest slow story push-in
    settle: float       # impact zoom: overshoot settles in this time


PROFILES = {
    # Editors use zooms sparingly ("a handful per video"), so a zoom stays meaningful:
    # Reels at most one every ~6.5 s (B-roll takes some moments too), YouTube about one every ~25 s.
    # Smooth zooms take ~0.8 s in / ~0.7 s out on Reels and ~1 s / ~0.9 s on YouTube.
    # A zoomed section lasts for the whole point: 2-8 s on Reels, 3-15 s on YouTube,
    # with at least 2 s (Reels) / 3 s (YouTube) of normal wide framing between sections.
    'short': ZoomProfile('short', 6.5, 2.0, .75, .65, 2.0, 8.0, 1.1, 4.0, .28),
    'long': ZoomProfile('long', 25.0, 3.0, 1.0, .9, 3.0, 15.0, 1.5, 6.0, .35),
}
FREQUENCY = {'low': 1.6, 'medium': 1.0, 'high': .65}
STRENGTH = {'subtle': 1.06, 'medium': 1.12, 'strong': 1.18}   # minimal, face-centred zooms
STYLES = ('mixed', 'smooth', 'punch')


def profile_for(duration, frequency='medium'):
    if frequency not in FREQUENCY:
        raise ValueError('Frequency must be low, medium or high')
    base = PROFILES['short' if duration <= SHORT_FORM_LIMIT else 'long']
    return replace(base, spacing=base.spacing * FREQUENCY[frequency])


@dataclass
class ZoomSettings:
    style: str = 'smooth'
    strength: str = 'medium'
    frequency: str = 'medium'
    face: bool = True          # zoom into the detected face instead of the frame centre
    jump_cuts: bool = False    # optional: alternate framing on every cut to hide jump cuts
    device: str = 'cpu'
    cpu_threads: int = 4

    def __post_init__(self):
        if self.style not in STYLES: raise ValueError('Style must be mixed, smooth or punch')
        if self.strength not in STRENGTH: raise ValueError('Strength must be subtle, medium or strong')
        if self.frequency not in FREQUENCY: raise ValueError('Frequency must be low, medium or high')
        if self.device not in ('cpu', 'cuda'): raise ValueError('Device must be cpu or cuda')

    @property
    def level(self):
        return STRENGTH[self.strength]
