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
    cadence_min: float = 0.0   # short-form target interval; zero means key-points only
    cadence_max: float = 0.0
    hook_deadline: float = 0.0
    wide_max: float = 0.0      # maximum stable wide hold; zero leaves long-form gaps unconstrained
    pacing: str = 'keypoints'
    cut_ramp: float = .8       # restore the slower, gentle zoom-in; hold after the entrance
    cut_ramp_out: float = .7   # zoom-out uses the earlier slower pace too


PROFILES = {
    # New short-video runs alternate in/out at real cuts, holding until the next
    # cut regardless of shot length. Legacy timing fields remain readable for
    # older saved plans; they are not quotas or hold limits in cut pacing.
    # Long videos retain major-script-point pacing without a periodic quota.
    'short': ZoomProfile('short', 0.0, 3.0, .75, .65, 3.0, 5.0, 1.1, 4.0, .28, 0.0, 10.0, 3.0, 5.0, 'cuts'),
    'long': ZoomProfile('long', 25.0, 3.0, 1.0, .9, 3.0, 5.0, 1.5, 6.0, .35),
}
FREQUENCY = {'low': 1.6, 'medium': 1.0, 'high': .65}
STRENGTH = {'subtle': 1.06, 'medium': 1.12, 'strong': 1.18}   # minimal, face-centred zooms
STYLES = ('mixed', 'smooth', 'punch')


def profile_for(duration, frequency='medium'):
    if frequency not in FREQUENCY:
        raise ValueError('Frequency must be low, medium or high')
    base = PROFILES['short' if duration <= SHORT_FORM_LIMIT else 'long']
    factor = FREQUENCY[frequency]
    return replace(base, spacing=base.spacing * factor,
                   cadence_min=base.cadence_min * factor,
                   # Frequency must not compress the owner's settled holds.
                   cadence_max=base.cadence_max)


@dataclass
class ZoomSettings:
    style: str = 'smooth'
    strength: str = 'medium'
    frequency: str = 'medium'
    face: bool = True          # zoom into the detected face instead of the frame centre
    jump_cuts: bool = False    # optional: alternate framing on every cut to hide jump cuts
    device: str = 'cpu'
    cpu_threads: int = 4
    sounds: bool = False       # opt-in; plain SmartZoom keeps its approved original soundtrack
    overlays: bool = False     # opt-in subtle cut transitions, separate from camera movement

    def __post_init__(self):
        if self.style not in STYLES: raise ValueError('Style must be mixed, smooth or punch')
        if self.strength not in STRENGTH: raise ValueError('Strength must be subtle, medium or strong')
        if self.frequency not in FREQUENCY: raise ValueError('Frequency must be low, medium or high')
        if self.device not in ('cpu', 'cuda'): raise ValueError('Device must be cpu or cuda')

    @property
    def level(self):
        return STRENGTH[self.strength]
