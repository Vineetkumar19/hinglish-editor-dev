"""Settings of one Motion Graphics run."""
from dataclasses import dataclass

PER_MINUTE = {'low': 2.0, 'medium': 4.0, 'high': 6.0}      # key moments per minute of speech (coverage 'key')
SIZES = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080)}
FULL_AUTO_SECONDS = 180                                      # 'auto': a whole motion-graphics video up to 3 minutes


@dataclass
class MotionSettings:
    count: str = 'medium'            # key moments: low / medium / high, or an exact number
    style: str = 'theme:archive'     # legacy API default; new application requests choose Connected studio
    mode: str = 'auto'               # auto (per scene) / full (all full screen) / overlay (over your video where it fits)
    coverage: str = 'auto'           # full = the whole script as motion graphics (MOTION_GRAPHICS.mp4) / key = key moments
    aspect: str = 'auto'             # script only (no video): 16:9, 9:16 or 1:1
    fps: int = 30                    # script only; with a video the timeline's frame rate is used
    assets: str = 'all'              # all (web + stock + AI Images) / web (no AI-made objects) / ai (objects made on the GPU)
    check: bool = True               # the vision model checks every downloaded picture
    brain: str = 'auto'
    cpu_threads: int = 4
    brain_model: str = 'qwen3:8b'     # Language model can change without replacing style memory.
    quality: str = 'full'            # preview uses a 360px short side; existing full exports unchanged
    preserve_script_text: bool = False  # AI Video's scripted motion keeps complete short source lines.
    engine: str = 'hyperframes'      # saved/legacy projects retain their original renderer

    def __post_init__(self):
        if self.engine not in ('hyperframes', 'remotion', 'motion-canvas'):
            raise ValueError('Motion engine unavailable: choose Remotion, Motion Canvas or Hyperframes.')
        self.count = str(self.count).strip().lower()
        if self.count not in PER_MINUTE and not (self.count.isdigit() and 1 <= int(self.count) <= 60):
            raise ValueError('count must be low, medium, high or a number from 1 to 60')
        if self.mode not in ('auto', 'full', 'overlay'):
            raise ValueError('mode must be auto, full or overlay')
        if self.coverage not in ('auto', 'full', 'key'):
            raise ValueError('coverage must be auto, full or key')
        if self.aspect not in ('auto', *SIZES):
            raise ValueError('aspect must be auto, 16:9, 9:16 or 1:1')
        if self.assets not in ('all', 'web', 'ai'):
            raise ValueError('assets must be all, web or ai')
        self.fps = int(self.fps) if int(self.fps) in (24, 25, 30, 50, 60) else 30
        if self.quality not in ('full', 'preview'):
            raise ValueError('Choose Full quality or Quick preview')

    def target(self, seconds):
        """How many key moments to aim for in `seconds` of speech."""
        if self.count.isdigit():
            return int(self.count)
        return max(1, round(seconds / 60 * PER_MINUTE[self.count]))

    def full(self, seconds, has_video):
        """The whole script as motion graphics (a script alone always is)."""
        if self.coverage != 'auto':
            return self.coverage == 'full'
        return not has_video or seconds <= FULL_AUTO_SECONDS
