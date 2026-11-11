"""Looks for Motion Graphics: built-in themes, and your own style cards learned from reference images / videos.

A style card is measured, not guessed: the colours come from the pixels (k-means over sampled frames), the energy
from how much the video moves, and a local vision model (Ollama qwen2.5vl) describes type, texture and mood.
New cards are 'candidate' until you approve them; only approved cards can be used."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import colorsys
import hashlib
import json
import re

import numpy as np
from PIL import Image

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'}
FONT_STACKS = {
    'condensed': '"League Gothic", "Bebas Neue", Impact, "Arial Narrow", sans-serif',
    'serif': '"Playfair Display", Georgia, "Times New Roman", serif',
    'geometric': '"Montserrat", "Segoe UI Black", "Arial Black", sans-serif',
    'handwritten': '"Segoe Print", "Comic Sans MS", cursive',
    'mono': '"IBM Plex Mono", Consolas, "Courier New", monospace',
}

THEMES = {
    # from your reference videos (style_memory of your motion graphics project)
    'archive': ('Archive paper (Edison look)', {'--bg': '#cdc9c1', '--paper': '#1c1b19', '--accent': '#8e1f1f', '--alert': '#8e1f1f',
                                              '--ink': '#f2efe8', '--panel': '#e3e0d9', '--ash': '#3a3834', '--muted': '#55524c',
                                              '--grain': '.22', '--texture': 'paper', '--photo': 'grayscale(1) contrast(1.12)',
                                              '--display': FONT_STACKS['geometric']}, .9),
    'teal': ('Teal pop (cut-outs on white)', {'--bg': '#f6f6f3', '--paper': '#111111', '--accent': '#16b3a3', '--alert': '#f2c230',
                                            '--ink': '#ffffff', '--panel': '#e9f6f4', '--ash': '#333333', '--muted': '#555555',
                                            '--grain': '.03', '--texture': 'plain', '--display': FONT_STACKS['geometric']}, 1.1),
    'desk': ('Desk grid (window light)', {'--bg': '#eceeee', '--paper': '#1a1a1a', '--accent': '#1fb8a8', '--alert': '#e0493a',
                                         '--ink': '#ffffff', '--panel': '#f7f7f7', '--ash': '#3a3a3a', '--muted': '#5d5d5d',
                                         '--grain': '.05', '--texture': 'grid', '--display': FONT_STACKS['serif']}, .95),
    'noir': ('Cinematic dark', {'--bg': '#0c0c0e', '--paper': '#ece7de', '--accent': '#d0a25a', '--alert': '#c8372d',
                               '--ink': '#0c0c0e', '--panel': '#18181b', '--grain': '.12', '--texture': 'dark',
                               '--display': FONT_STACKS['serif']}, .85),
    'street': ('Street tech (Madurai)', {'--bg': '#171310', '--paper': '#f3eadf', '--accent': '#ff6b2c', '--alert': '#e8373d',
                                        '--ink': '#171310', '--panel': '#211b17', '--grain': '.13', '--texture': 'road'}, 1.0),
    'documentary': ('Documentary gold', {'--bg': '#101114', '--paper': '#e9e2d0', '--accent': '#c9a227', '--alert': '#b3261e',
                                        '--ink': '#15130f', '--panel': '#1b1c20', '--grain': '.2', '--texture': 'dark',
                                        '--photo': 'sepia(.25) contrast(1.05)', '--display': FONT_STACKS['serif']}, .85),
    'newsroom': ('Newsroom', {'--bg': '#0b1a2e', '--paper': '#ffffff', '--accent': '#ffcc00', '--alert': '#e10600',
                              '--ink': '#0b1a2e', '--panel': '#12263f', '--grain': '.04', '--texture': 'dark'}, 1.1),
    'midnight': ('Midnight neon', {'--bg': '#0a0a14', '--paper': '#eeeefa', '--accent': '#7c5cff', '--alert': '#ff3d71',
                                   '--ink': '#0a0a14', '--panel': '#15152a', '--grain': '.06', '--texture': 'dark',
                                   '--display': FONT_STACKS['geometric']}, 1.15),
}

# Separate, explicit choices: saved themes and approved caption renderers keep their identity.
from .creative import STYLES as CREATIVE_STYLES
for _key, (_label, _recipes) in CREATIVE_STYLES.items():
    THEMES[_key.split(':')[1]] = (_label, {
        '--bg': '#111113', '--paper': '#f7f7f5', '--accent': '#dbfb56',
        '--panel': '#202024', '--grain': '0', '--texture': 'plain'}, 1.0)


def library(root):
    folder = Path(root) / 'library' / 'motion-styles'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


@dataclass
class StyleCard:
    id: str
    name: str
    status: str = 'candidate'           # candidate -> approved (only approved cards are used)
    sources: list = field(default_factory=list)
    tokens: dict = field(default_factory=dict)
    speed: float = 1.0
    notes: dict = field(default_factory=dict)
    created: str = ''

    def save(self, root):
        (library(root) / f'{self.id}.json').write_text(json.dumps(asdict(self), indent=1, ensure_ascii=False), encoding='utf-8')
        return self


def load_cards(root):
    cards = []
    for file in sorted(library(root).glob('card_*.json')):
        try:
            cards.append(StyleCard(**json.loads(file.read_text(encoding='utf-8'))))
        except (ValueError, TypeError):
            continue
    return cards


def card(root, card_id):
    file = library(root) / f'{card_id}.json'
    if not re.fullmatch(r'card_[a-z0-9_]+', card_id or '') or not file.is_file():
        raise ValueError(f'Unknown style card: {card_id}')
    return StyleCard(**json.loads(file.read_text(encoding='utf-8')))


def look(root, style):
    """'theme:<name>' or 'card:<id>' -> (css tokens, animation speed, name)."""
    style = style or 'theme:street'
    if style.startswith('card:'):
        c = card(root, style[5:])
        if c.status != 'approved':
            raise ValueError(f'Style card "{c.name}" is not approved yet: approve it first')
        base = dict(THEMES['street'][1])
        base.update(c.tokens)
        return base, c.speed, c.name
    name = style.split(':', 1)[-1]
    if name not in THEMES:
        raise ValueError(f'Unknown theme: {name}')
    title, tokens, speed = THEMES[name]
    return dict(tokens), speed, title


# ---- measuring references ----------------------------------------------------------------------------------------
def reference_frames(path, count=8, size=320):
    """RGB frames (small) from an image or evenly through a video; plus (frame pairs 0.2 s apart) for motion."""
    path = Path(path)
    if path.suffix.lower() in IMAGE_EXT:
        with Image.open(path) as im:
            im = im.convert('RGB')
            im.thumbnail((size, size))
            return [np.asarray(im)], []
    from hinglish_broll.library import probe_video, read_frames
    info = probe_video(path)
    if not info:
        return [], []
    seconds = max(.5, info[0])
    times = [seconds * (k + .5) / count for k in range(count)]
    frames = [np.asarray(im.convert('RGB')) for _, im in read_frames(path, times, size=size)]
    pairs = []
    for t in times[:6]:
        got = [np.asarray(im.convert('L'), np.float32) for _, im in read_frames(path, [t, min(seconds, t + .2)], size=160)]
        if len(got) == 2 and got[0].shape == got[1].shape:
            pairs.append(got)
    return frames, pairs


def _hex(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, v))) for v in rgb)


def palette(frames, k=6, seed=3):
    """Main colours by share: [(rgb, share, luminance, saturation)] from a small k-means."""
    pixels = np.concatenate([f.reshape(-1, 3) for f in frames]).astype(np.float32)
    rng = np.random.default_rng(seed)
    if len(pixels) > 40000:
        pixels = pixels[rng.choice(len(pixels), 40000, replace=False)]
    centres = pixels[rng.choice(len(pixels), k, replace=False)]
    for _ in range(12):
        labels = np.argmin(((pixels[:, None, :] - centres[None]) ** 2).sum(-1), axis=1)
        centres = np.stack([pixels[labels == i].mean(0) if (labels == i).any() else centres[i] for i in range(k)])
    shares = np.bincount(labels, minlength=k) / len(labels)
    out = []
    for c, s in zip(centres, shares):
        h, l, sat = colorsys.rgb_to_hls(*(c / 255))
        out.append((c, float(s), float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255, float(sat), h))
    return sorted(out, key=lambda x: -x[1])


def border_pixels(frames, margin=.08):
    """The outer edge of every frame: that is where the background shows (photos and titles sit inside)."""
    parts = []
    for f in frames:
        h, w = f.shape[:2]
        m = max(2, int(min(h, w) * margin))
        parts += [f[:m].reshape(-1, 3), f[-m:].reshape(-1, 3), f[:, :m].reshape(-1, 3), f[:, -m:].reshape(-1, 3)]
    return [np.concatenate(parts)[None]]


def tokens_from_palette(colours, edge=None):
    """Background, text/surface, accent and alert colours that keep text readable.

    The templates draw text in --paper on --bg (and --ink on --paper). A dark reference keeps that order; a light
    reference (paper, newspaper, white studio) swaps it: light background, dark text. A black-and-white reference
    gets a grey accent instead of an invented colour."""
    background = (edge or colours)[0]                 # the most common colour at the frame edges
    dark_scene = background[2] < .45
    lights = sorted(colours, key=lambda c: -c[2])
    darks = sorted(colours, key=lambda c: c[2])
    text = lights[0] if dark_scene else darks[0]
    if abs(text[2] - background[2]) < .45:          # not enough contrast in the reference: pure-ish text
        text = (np.array([243, 234, 223]) if dark_scene else np.array([22, 20, 18]), 0, .9 if dark_scene else .08, 0, 0)
    vivid = sorted([c for c in colours if c[3] > .35 and .2 < c[2] < .85 and c[1] > .01], key=lambda c: -(c[3] * (c[1] ** .3)))
    if vivid:
        accent = vivid[0][0]
    else:                                            # monochrome reference: a grey between text and background
        accent = background[0] * .45 + text[0] * .55
    alert = next((c for c in vivid[1:] if min(abs(c[4] - vivid[0][4]), 1 - abs(c[4] - vivid[0][4])) > .12), None)
    tokens = {'--bg': _hex(background[0]), '--paper': _hex(text[0]), '--accent': _hex(accent),
              '--ink': _hex(background[0]), '--panel': _hex(np.clip(background[0] * .85 + text[0] * .15, 0, 255))}
    if alert is not None:
        tokens['--alert'] = _hex(alert[0])
    elif not vivid:     # stamps / stickers in the background colour (it contrasts the text colour they sit on),
        tokens['--alert'] = _hex(background[0])      # not a red the reference never uses
    return tokens, dark_scene


def motion_energy(pairs):
    """0 (still) .. 1 (very busy), from how much the picture changes in 0.2 s."""
    if not pairs:
        return None
    diffs = [float(np.mean(np.abs(a - b))) / 255 for a, b in pairs]
    return float(min(1.0, np.median(diffs) * 12))


DESCRIBE_SYSTEM = '''You look at frames from a video editor's reference (motion graphics / documentary / reels).
Describe its graphic style so it can be recreated: the headline typeface kind, the texture, the energy and mood.'''
DESCRIBE_SCHEMA = {'type': 'object', 'properties': {
    'typeface': {'type': 'string', 'enum': ['condensed', 'serif', 'geometric', 'handwritten', 'mono']},
    'texture': {'type': 'string', 'enum': ['grain', 'paper', 'clean', 'glow']},
    'energy': {'type': 'string', 'enum': ['calm', 'medium', 'punchy']},
    'layout': {'type': 'string'}, 'mood': {'type': 'array', 'items': {'type': 'string'}}, 'summary': {'type': 'string'}},
    'required': ['typeface', 'texture', 'energy', 'mood', 'summary']}


def describe(root, frames, progress=print, *, receipt_path=None):
    """The vision model's reading of the style (None when Ollama / qwen2.5vl is not available)."""
    receipt={'frame_count':min(4,len(frames))}
    try:
        from hinglish_aigen.judge import Judge
        judge = Judge(root)
        receipt['model']=judge.model
    except Exception as error:
        progress(f'  Style: vision model not available ({error}); colours and motion are still measured')
        if receipt_path:
            receipt['error']=str(error);Path(receipt_path).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
        return None
    try:
        pictures = [Image.fromarray(f) for f in frames[:4]]
        from hinglish_visuals.evaluator import _for_model, _png64
        body = {'model': judge.model, 'stream': False, 'format': DESCRIBE_SCHEMA,
                'options': {'temperature': 0, 'seed': 3, 'num_ctx': 8192, 'num_predict': 400},
                'messages': [{'role': 'system', 'content': DESCRIBE_SYSTEM},
                             {'role': 'user', 'content': 'Describe the style of these frames.',
                              'images': [_png64(_for_model(p)) for p in pictures]}]}
        from hinglish_cut.model_preferences import configure_request
        configure_request(root,body)
        receipt['request']={'think':body.get('think'),'options':body.get('options'),'model':body['model']}
        response = judge.session.post(judge.url + '/api/chat', json=body, timeout=1800)
        response.raise_for_status()
        result=response.json();message=result.get('message') or {}
        receipt.update(content=message.get('content',''),done_reason=result.get('done_reason'),
                       eval_count=result.get('eval_count'),thinking_present=bool(message.get('thinking')))
        reading=json.loads(message.get('content') or '{}')
        if not isinstance(reading,dict) or any(not reading.get(key) for key in DESCRIBE_SCHEMA['required']):
            raise ValueError('The local Vision model returned an incomplete style description.')
        return reading
    except Exception as error:
        progress(f'  Style: vision model could not read the frames ({error})')
        receipt['error']=str(error)
        return None
    finally:
        if receipt_path:
            Path(receipt_path).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
        judge.close()


def analyse(root, files, name='', progress=print):
    """Reference images / videos -> a new candidate style card."""
    files = [Path(f) for f in files if Path(f).suffix.lower() in IMAGE_EXT | VIDEO_EXT and Path(f).is_file()]
    if not files:
        raise ValueError('Choose reference images or videos (jpg, png, mp4, mov...)')
    frames, pairs = [], []
    for f in files[:12]:
        progress(f'  Looking at {f.name}')
        got, moving = reference_frames(f)
        frames += got
        pairs += moving
    if not frames:
        raise ValueError('None of the references could be opened')
    tokens, dark = tokens_from_palette(palette(frames), palette(border_pixels(frames), k=4))
    energy = motion_energy(pairs)
    notes = {'dark': dark, 'measured_energy': None if energy is None else round(energy, 2)}
    reading = describe(root, frames, progress)
    if reading:
        notes.update({k: reading.get(k) for k in ('typeface', 'texture', 'energy', 'layout', 'mood', 'summary')})
        tokens['--display'] = FONT_STACKS.get(reading.get('typeface'), FONT_STACKS['condensed'])
        tokens['--grain'] = {'grain': '.18', 'paper': '.14', 'clean': '.03', 'glow': '.05'}.get(reading.get('texture'), '.1')
        tokens['--texture'] = {'paper': 'paper', 'clean': 'plain', 'glow': 'dark'}.get(reading.get('texture'),
                                                                                  'dark' if dark else 'paper')
    else:
        tokens['--texture'] = 'dark' if dark else 'paper'
    px = np.concatenate([np.asarray(f, np.float32).reshape(-1, 3)[::37] for f in frames])
    sat = float(np.mean((px.max(1) - px.min(1)) / np.maximum(px.max(1), 1)))    # how colourful the pixels are
    if sat < .08:                                      # a black-and-white reference: photos in black and white too
        tokens['--photo'] = 'grayscale(1) contrast(1.1)'
    speed = 1.0
    if energy is not None:
        speed = round(.85 + .45 * energy, 2)          # calm references animate slower, busy ones faster
    elif reading:
        speed = {'calm': .85, 'medium': 1.0, 'punchy': 1.2}.get(reading.get('energy'), 1.0)
    digest = hashlib.sha1(json.dumps(sorted(str(f.resolve()) for f in files)).encode()).hexdigest()[:10]
    title = name.strip() or f'My style {digest[:4]}'
    card_id = 'card_' + re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')[:30] + '_' + digest
    result = StyleCard(card_id, title, 'candidate', [str(f) for f in files], tokens, min(1.3, max(.8, speed)), notes,
                       datetime.now().isoformat(timespec='seconds'))
    return result.save(root)


def approve(root, card_id, name=None, approved=True):
    c = card(root, card_id)
    c.status = 'approved' if approved else 'candidate'
    if name and name.strip():
        c.name = name.strip()[:40]
    return c.save(root)


def delete(root, card_id):
    c = card(root, card_id)
    (library(root) / f'{c.id}.json').unlink()
    return c.id


def references_in(folder, limit=40):
    """Reference files inside a folder (e.g. the old motion-graphics project's style_memory/references)."""
    folder = Path(folder)
    found = [p for p in folder.rglob('*') if p.suffix.lower() in IMAGE_EXT | VIDEO_EXT and p.is_file()
             and 'derivatives' not in p.parts]
    return sorted(found)[:limit]


def choices(root):
    """[(value, name)] for the style menus: the built-in themes, then your approved style cards."""
    found = [(f'theme:{k}', v[0]) for k, v in THEMES.items()]
    return found + [(f'card:{c.id}', f'{c.name} (your style)') for c in load_cards(root) if c.status == 'approved']
