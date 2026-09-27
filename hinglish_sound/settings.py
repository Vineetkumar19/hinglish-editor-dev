"""Sound design choices, category behaviour and mix levels (ideas carried over from the user's earlier
`sound` project: per-category placement, voice-relative loudness, ducking, density budget)."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json

LOCAL_SETTINGS = 'config.sound.local.json'
_LIBRARY = Path(r'C:\Users\vinee\OneDrive\Desktop\AI Video Editing Automation\caption-studio')
DEFAULT_MUSIC = str(_LIBRARY / 'music')
DEFAULT_SFX = str(_LIBRARY / 'sfx')
OLD_SCAN_CACHE = Path(r'C:\Users\vinee\OneDrive\Desktop\AI Video Editing Automation\sound\.cache')

# How each effect type behaves. `offset` = how loud the effect SOUNDS on a phone (its loudest 150 ms,
# phone-weighted) relative to how loud your spoken words sound (dB). Peaks were the wrong measure: a compressed voice has dense body while a
# whoosh or pop is a thin transient, so peak-matched effects came out 15-22 dB quieter than the voice and
# could not be heard. Reel style: hits and pops are almost as loud as you, whooshes a few dB under.
# `align`: 'peak' = the loudest instant lands on the word/cut (sub-frame sync), 'start' = the sound
# starts on it. `hpf`: roll off lows on UI sounds so they don't clash with the voice.
SFX_BEHAVIOUR = {
    'impact':   {'label': 'Cinematic hit / boom', 'offset': -2.0, 'align': 'peak', 'max_len': 3.0, 'hpf': None},
    'whoosh':   {'label': 'Whoosh / swoosh / transition', 'offset': -4.0, 'align': 'peak', 'max_len': 1.6, 'hpf': 120},
    'riser':    {'label': 'Riser / swell into a moment', 'offset': -5.0, 'align': 'peak', 'max_len': 3.0, 'hpf': 120},
    'awkward':  {'label': 'Fail / error / record scratch', 'offset': -3.0, 'align': 'start', 'max_len': 2.5, 'hpf': 150},
    'cute':     {'label': 'Ding / chime / sparkle', 'offset': -4.0, 'align': 'peak', 'max_len': 2.0, 'hpf': 150},
    'retro':    {'label': 'Game / coin / win', 'offset': -4.0, 'align': 'peak', 'max_len': 2.0, 'hpf': 150},
    'suspense': {'label': 'Heartbeat / ticking / tension', 'offset': -8.0, 'align': 'start', 'max_len': 4.0, 'hpf': None},
    'vanish':   {'label': 'Vanish / poof', 'offset': -5.0, 'align': 'peak', 'max_len': 2.5, 'hpf': 150},
    'poke':     {'label': 'Pop / click / notification / typing', 'offset': -3.0, 'align': 'peak', 'max_len': 1.2, 'hpf': 150},
    'glitch':   {'label': 'Glitch / digital stutter', 'offset': -4.0, 'align': 'peak', 'max_len': 1.2, 'hpf': 150},
}
LAYER_WHOOSH_OFFSET = -7.0    # a whoosh leading into every hit (brain: layer 2-3 sounds for a pro composite)
MUSIC_IN_GAPS = -6.0          # music loudness vs voice loudness in pauses (the bed swells between lines)
MUSIC_DUCK = 6.0              # dB the music ducks while you speak -> 12 dB under the voice: clearly present
                              # but never competing (a Reel talks almost non-stop, so the duck level IS the bed)
MUSIC_EQ_DIP = (2000.0, -3.0, .7)   # centre Hz, gain dB, Q: a gentle hole at 1-3 kHz for the voice
PULL_BACK_DB = 10.0           # extra dip just before the biggest reveal ("pull back and punch")
DUCK_ATTACK, DUCK_RELEASE = .08, .9
SFX_UNDER_VOICE = 0.0         # effects are not ducked: they must be heard
VOICE_HPF = 80.0              # dialogue high-pass (rumble, AC hum, mic bumps)
TARGET_LOUDNESS = -14.0       # master loudness (streaming platforms)
PEAK_CEILING = -2.0           # master limiter ceiling (brain: -2 dB)
SFX_PEAK_ROOM = 3.0           # an effect's peak may exceed the voice peak by this much at most
SFX_CREST_TRIM = 4.0          # dB shaved off each effect's sharpest transient (per-sound limiter)
SFX_CREST_KEEP = 12.0         # ...more if its spike stands over 12 dB above its body (tiny pops)
SFX_CREST_MAX = 10.0          # ...but never more than this
SFX_CREST_RELEASE = .03       # fast release: only the spike is shaved, the sound keeps its shape
NO_CREST_TRIM = {'riser', 'whoosh', 'suspense', 'vanish', 'impact'}   # their peak IS the climax / the punch
SFX_MAX_OVER_WORDS = 2.0      # full-range (bass included) loudness of an effect never above your words + this
TRANSITION_OFFSET = -4.0      # whoosh on each B-roll cut-in (sounding loudness vs your speech)
ZOOM_OFFSET = -4.0            # low boom when a zoom lands on the key word

DENSITY = {  # about one designed sound every N seconds INCLUDING B-roll/zoom sounds, minimum spacing
    # v4: fewer, motivated sounds (v3's one-every-2.5-s plus edit sounds on top felt random)
    'short': {'low': (6.0, 2.0), 'medium': (4.0, 1.5), 'high': (3.0, 1.0)},
    'long': {'low': (20.0, 4.0), 'medium': (12.0, 3.0), 'high': (8.0, 2.0)},
}
EDIT_SHARE = .5               # B-roll whooshes + zoom booms may use at most half of the budget
STYLES = ('auto', 'cinematic', 'funny', 'chill', 'emotional')


@dataclass
class SoundSettings:
    music_folder: str = DEFAULT_MUSIC
    sfx_folder: str = DEFAULT_SFX
    style: str = 'auto'
    density: str = 'medium'
    music: bool = True
    effects: bool = True
    transitions: bool = True      # whoosh when B-roll cuts in
    music_level: float = 0.0      # user trim in dB
    device: str = 'cpu'
    cpu_threads: int = 4
    pro_folder: str = ''                           # downloaded pro pack; '' = <project>/library/sfx-pro
    think_model: str = 'qwen3:8b'                  # Ollama model that reasons about the video
    embed_model: str = 'qwen3-embedding:0.6b'      # Ollama model for the library vector index
    listen: bool = True                            # CLAP listens to every file (what it really sounds like)
    listen_model: str = 'laion/larger_clap_general'
    evaluate: bool = True                          # check every effect/music bed and the final mix

    def __post_init__(self):
        if self.style not in STYLES: raise ValueError('Style must be one of ' + ', '.join(STYLES))
        if self.density not in ('low', 'medium', 'high'): raise ValueError('Density must be low, medium or high')


USER_KEYS = ('music_folder', 'sfx_folder', 'pro_folder', 'style', 'density', 'music', 'effects', 'transitions',
             'music_level', 'think_model', 'embed_model', 'listen', 'listen_model', 'evaluate')


def load_settings(root, **overrides):
    file = Path(root) / LOCAL_SETTINGS
    data = json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {}
    data = {k: v for k, v in data.items() if k in USER_KEYS}
    data.update({k: v for k, v in overrides.items() if v is not None})
    settings = SoundSettings(**data)
    # On another PC the default / saved folders may not exist: use the project's own library folders
    for key, name in (('music_folder', 'music'), ('sfx_folder', 'sfx')):
        if not Path(getattr(settings, key)).is_dir():
            fallback = Path(root) / 'library' / name
            fallback.mkdir(parents=True, exist_ok=True)
            setattr(settings, key, str(fallback))
    return settings


def save_user_settings(root, values):
    file = Path(root) / LOCAL_SETTINGS
    data = json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {}
    for key in USER_KEYS:
        if key in values:
            data[key] = values[key]
    for key in ('music_folder', 'sfx_folder'):
        if data.get(key) and not Path(data[key]).is_dir():
            raise ValueError('Folder not found: ' + data[key])
    SoundSettings(**data)
    file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return asdict(load_settings(root))
