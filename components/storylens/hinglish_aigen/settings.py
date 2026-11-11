"""Choices for AI Images & Video, the built-in styles and your own saved styles."""
from dataclasses import dataclass
from pathlib import Path
import json

CONFIG = 'config.aigen.local.json'

# One style for every visual in a video: the AI writes WHAT is shown, the style says HOW it looks.
STYLES = {
    'cinematic': ('Cinematic realistic',
                  'cinematic film still, photorealistic, natural light, shallow depth of field, 35mm lens, rich detail, '
                  'professional colour grading'),
    'documentary': ('Documentary archive',
                    'vintage archival documentary photograph, film grain, slightly faded desaturated colours, old paper '
                    'texture, historical atmosphere, authentic period detail'),
    '3d': ('3D animated',
           '3D animated film style, soft global illumination, expressive characters, vibrant colours, highly detailed '
           'render'),
    'illustration': ('2D illustration',
                     'flat 2D editorial illustration, clean vector shapes, bold limited colour palette, simple '
                     'background'),
    'anime': ('Anime', 'anime style, detailed painted background, cel shading, cinematic composition'),
}
NEGATIVE = ('blurry, low quality, distorted face, deformed hands, extra fingers, garbled text, watermark, logo, '
            'static, jittery, flickering')
# how many per minute of speech: pictures take seconds each, clips take minutes each
PER_MINUTE = {'image': {'low': 1.5, 'medium': 3.0, 'high': 5.0},
              'video': {'low': .25, 'medium': .5, 'high': 1.0}}
SIZES = {'16:9': (1344, 768), '9:16': (768, 1344), '1:1': (1024, 1024)}
VIDEO_SIZES = {'16:9': (1280, 704), '9:16': (704, 1280), '1:1': (960, 960)}
WORDS_PER_SECOND = 2.6                                      # Hinglish speech, to time a script with no video


def config_path(root):
    return Path(root) / CONFIG


def load_config(root):
    try:
        return json.loads(config_path(root).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}


def save_styles(root, styles):
    """Your own styles: [{'name': ..., 'prompt': ...}] kept on this computer (config.aigen.local.json)."""
    clean = []
    for s in styles or []:
        name, prompt = str(s.get('name', '')).strip()[:40], str(s.get('prompt', '')).strip()[:400]
        if name and prompt and name.lower() not in {n.lower() for n in (c['name'] for c in clean)}:
            clean.append({'name': name, 'prompt': prompt})
    data = load_config(root)
    data['styles'] = clean[:30]
    config_path(root).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    return all_styles(root)


def all_styles(root):
    """Built-in + your own, as [{id, name, prompt, own}]."""
    built = [{'id': k, 'name': v[0], 'prompt': v[1], 'own': False} for k, v in STYLES.items()]
    own = [{'id': 'my:' + s['name'], 'name': s['name'], 'prompt': s['prompt'], 'own': True}
           for s in load_config(root).get('styles', [])]
    return built + own


def style_prompt(root, style, custom=''):
    """The style words added to every prompt."""
    if custom.strip():
        return custom.strip()
    for s in all_styles(root):
        if s['id'] == style:
            return s['prompt']
    raise ValueError(f'Unknown style: {style}')


@dataclass
class GenSettings:
    """Settings of one tool run. kind = 'image' (AI Images) or 'video' (AI Video)."""
    kind: str = 'image'
    style: str = 'cinematic'
    custom_style: str = ''          # a one-off style prompt (overrides the style menu)
    count: str = 'medium'           # low / medium / high, or an exact number
    options: int = 2                # pictures made per moment (AI Video: first frames to choose from)
    aspect: str = 'auto'            # auto (from the video), 16:9, 9:16 or 1:1
    brain: str = 'auto'
    check: bool = True              # vision model looks at every result and rejects bad ones
    from_picture: bool = True       # AI Video: make a sharp first frame with the picture model, then animate it
    cpu_threads: int = 4
    request_mode: str = 'script'
    channel: str = 'auto'
    purpose: str = 'scene'
    video_method: str = 'generative'
    reference: str = ''
    motion_style: str = 'orbit'
    quality: str = 'full'

    def __post_init__(self):
        if self.video_method not in ('generative','reference','motion'):
            raise ValueError('AI Video method unavailable: choose Prompt to video, Reference guided, or Motion / 3D.')
        if self.motion_style not in ('gsap','orbit','product','explainer','studio') or self.quality not in ('full','preview'):
            raise ValueError('AI Video settings invalid: choose an available motion style and quality.')
        if self.kind=='video' and self.video_method=='reference' and not self.reference.strip():
            raise ValueError('AI Video reference missing: choose a local reference video or a public YouTube link.')
        if self.request_mode not in ('script','idea') or (self.kind!='image' and self.request_mode!='script'):
            raise ValueError('Choose an image idea or pictures from a script.')
        if self.channel not in ('auto','general','gaming','cricket'):
            raise ValueError('Choose Gaming, Cricket or Auto for the image channel.')
        if self.purpose not in ('scene','thumbnail','background'):
            raise ValueError('Choose Scene, Thumbnail image or Background.')
        if self.kind not in PER_MINUTE:
            raise ValueError('kind must be image or video')
        if str(self.count) not in PER_MINUTE[self.kind] and not (str(self.count).isdigit() and 1 <= int(self.count) <= 60):
            raise ValueError('How many: low, medium, high or a number 1-60')
        if not 1 <= int(self.options) <= 4:
            raise ValueError('Options per moment: 1-4')
        if self.aspect not in ('auto',) + tuple(SIZES):
            raise ValueError('Format: auto, 16:9, 9:16 or 1:1')
        if self.brain not in ('auto', 'ollama', 'local'):
            raise ValueError('Brain: auto, ollama or local')

    def target(self, seconds):
        """How many moments to aim for in `seconds` of speech."""
        if str(self.count).isdigit():
            return int(self.count)
        return max(1, round(seconds / 60 * PER_MINUTE[self.kind][self.count]))
