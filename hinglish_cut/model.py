from dataclasses import dataclass, field
from fractions import Fraction
import math


@dataclass
class Settings:
    asr_model: str = 'Oriserve/Whisper-Hindi2Hinglish-Swift'
    align_model: str = 'MahmoudAshraf/mms-300m-1130-forced-aligner'
    judge_model: str | None = None
    device: str = 'cpu'
    cpu_threads: int = 4
    offline: bool = False
    chunk_seconds: float = 25.0
    vad_threshold: float = 0.5
    min_silence: float = 0.45
    pre_padding: float = 0.12
    post_padding: float = 0.16
    match_threshold: float = 0.72
    ambiguity_margin: float = 0.04
    coverage_threshold: float = 0.85
    alignment_threshold: float = 0.10
    beam_width: int = 12
    candidates_per_line: int = 8
    aliases: dict[str, str] = field(default_factory=lambda: {'nahin':'nahi','nahī':'nahi'})
    important_terms: list[str] = field(default_factory=list)

    def __post_init__(self):
        for name in ('vad_threshold','match_threshold','ambiguity_margin','coverage_threshold','alignment_threshold'):
            value = getattr(self,name)
            if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f'{name} must be between 0 and 1')
        for name in ('min_silence','pre_padding','post_padding'):
            value=getattr(self,name)
            if not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f'{name} must be nonnegative')
        if not 2 <= self.chunk_seconds <= 28:
            raise ValueError('chunk_seconds must be between 2 and 28')
        if self.device not in ('cpu','cuda'):
            raise ValueError('device must be cpu or cuda')
        if type(self.cpu_threads) is not int or not 1<=self.cpu_threads<=64:
            raise ValueError('cpu_threads must be between 1 and 64')
        if not 1 <= self.beam_width <= 100 or not 1 <= self.candidates_per_line <= 30:
            raise ValueError('Invalid search limits')
        if not isinstance(self.aliases,dict) or not all(isinstance(k,str) and isinstance(v,str) and k.strip() and v.strip() for k,v in self.aliases.items()):
            raise ValueError('aliases must map non-empty words or phrases to non-empty words or phrases')


@dataclass
class Word:
    text: str
    start: float
    end: float
    score: float = 0.0
    aligned: bool = True


@dataclass
class Media:
    id: str
    path: str
    duration: float
    fps: str
    width: int
    height: int
    channels: int
    sample_rate: int
    video_start: float = 0.0

    @property
    def rate(self):
        return Fraction(self.fps)


@dataclass
class Transcript:
    media: Media
    words: list[Word]
    speech: list[tuple[float,float]]
    issues: list[str]


@dataclass
class Selection:
    line_index: int
    script: str
    media_id: str | None
    first_word: int = 0
    last_word: int = 0
    score: float = 0.0
    ambiguous: bool = False
    alternatives: list[dict] = field(default_factory=list)


@dataclass
class Cut:
    media_id: str
    start_frame: int
    end_frame: int
    line_index: int

    @property
    def duration(self):
        return self.end_frame-self.start_frame
