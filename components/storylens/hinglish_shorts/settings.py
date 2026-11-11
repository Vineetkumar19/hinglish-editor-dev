"""Choices for Long to Shorts (the same controls as FireCut Highlights, plus your own template)."""
from dataclasses import dataclass

# Shorts per minute of long video. A 15-min video: low 4, medium 8, high 12 (fewer when it has less to say).
COUNT_PER_MINUTE = {'low': 1 / 4, 'medium': 1 / 2, 'high': 1 / 1.25}
LOOKS = ('template', 'face')
MIN_LENGTH, MAX_LENGTH = 5, 120            # seconds, FireCut's slider range
WINDOW_SECONDS = 300.0                      # the AI reads the long video in 5-minute parts
WINDOW_OVERLAP = 40.0                       # a story that crosses a border is still seen whole once


def parse_time(value):
    """'12:30', '1:02:03' or seconds -> seconds (None when empty)."""
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    parts = [float(p) for p in str(value).strip().split(':')]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


@dataclass
class ShortsSettings:
    count: str = 'medium'          # low / medium / high, or an exact number like "10"
    min_length: float = 30.0
    max_length: float = 60.0
    pieces: int = 3                # a short may join up to this many parts of the long video (1 = one piece)
    look: str = 'template'         # template = your framed 16:9 video; face = 9:16 crop that follows the face
    title: str = ''                # the same title on every short (empty = the AI writes one per short)
    handle: str = ''               # "@Vineetkumar_19" under the video; empty = no "watch full video" line
    cta: str = 'WATCH FULL VIDEO ON'
    captions: bool = False
    fresh: bool = False
    caption_style: str = 'typography_1'
    start: float | None = None     # only look between these times of the long video (FireCut: In/Out points)
    end: float | None = None
    device: str = 'cpu'
    brain: str = 'auto'            # auto (Ollama qwen3:8b if running) / ollama / local
    cpu_threads: int = 4

    def __post_init__(self):
        if self.look not in LOOKS:
            raise ValueError('Look must be template or face')
        if not (MIN_LENGTH <= self.min_length <= self.max_length <= MAX_LENGTH):
            raise ValueError(f'Length must be between {MIN_LENGTH} and {MAX_LENGTH} seconds (shortest first)')
        if self.max_length - self.min_length < 5:
            raise ValueError('Give the AI at least 5 seconds of room between shortest and longest')
        if not 1 <= int(self.pieces) <= 3:
            raise ValueError('Pieces must be 1, 2 or 3')
        if self.device not in ('cpu', 'cuda'):
            raise ValueError('Device must be cpu or cuda')
        if self.brain not in ('auto', 'ollama', 'local'):
            raise ValueError('Brain must be auto, ollama or local')
        if str(self.count) not in COUNT_PER_MINUTE and not (str(self.count).isdigit() and 1 <= int(self.count) <= 40):
            raise ValueError('How many: low, medium, high or a number from 1 to 40')
        if self.start is not None and self.end is not None and self.end - self.start < self.min_length:
            raise ValueError('The From-To part is shorter than the shortest short')

    def target(self, seconds, scale=1.0):
        """How many shorts to aim for in `seconds` of long video."""
        if str(self.count).isdigit():
            wanted = int(self.count)
        else:
            wanted = round(seconds / 60 * COUNT_PER_MINUTE[self.count] * scale)
        room = int(seconds // max(self.min_length, 1))       # never more than the video can hold
        return max(1, min(wanted, room, 40))
