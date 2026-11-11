"""Real-subject presentation choices and smooth, frame-rate-independent motion."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

MODES = ('auto', 'fullscreen', 'popup', 'cutout', 'behind')
LABELS = {'auto': 'Choose for the story', 'fullscreen': 'Full screen', 'popup': 'Moving pop-up',
          'cutout': 'Cutout rising from below', 'behind': 'Behind the speaker'}
REVISION = 5


def smoother(value):
    x = min(1.0, max(0.0, value))
    return x * x * x * (x * (x * 6 - 15) + 10)


def entrance_seconds(duration, rise=False):
    return min(.48 if rise else .36, duration * .35)


def motion(seconds, duration, rise=False):
    """Continuous position/scale, soft start and stop, no bounce or random per-frame targets."""
    entrance = entrance_seconds(duration, rise)
    exit_time = min(.32, duration * .25)
    from hinglish_motion.curves import ease
    enter = ease('sine.inOut', seconds / max(.001, entrance))
    leave = ease('sine.inOut', (seconds - (duration - exit_time)) / max(.001, exit_time))
    drift = ease('sine.inOut', seconds / max(.001, duration))
    scale = (.88 + .12 * enter) * (1 + .035 * drift) * (1 - .08 * leave)
    return scale, enter * (1 - leave), enter, leave, drift


def overlay_frame(art, position, size, seconds, duration, rise=False):
    """Subpixel transform avoids integer resize/position steps, including on transparent edges."""
    width, height = size
    scale, opacity, enter, leave, drift = motion(seconds, duration, rise)
    cx = position[0] + art.width / 2
    cy = position[1] + art.height / 2
    travel = (height - position[1] + art.height * .05) if rise else height * .035
    cy += travel * (1 - enter) + height * .055 * leave - height * .012 * drift
    a = 1 / scale
    # Pillow's RGBa mode resamples premultiplied alpha to avoid dark fringes.
    frame = art.convert('RGBa').transform((width, height), Image.Transform.AFFINE,
        (a, 0, art.width / 2 - cx * a, 0, a, art.height / 2 - cy * a),
        resample=Image.Resampling.BICUBIC).convert('RGBA')
    if opacity < 1:
        frame.putalpha(frame.getchannel('A').point(lambda v: round(v * opacity)))
    return frame


def choose(moment, selected='auto'):
    if selected not in MODES:
        raise ValueError('Choose a supported Smart Visuals presentation')
    if selected != 'auto':
        return selected
    # Historical/event footage stays full screen. Named people can rise as real cutouts.
    if moment.display == 'popup' and moment.show == 'photo':
        return 'cutout'
    return moment.display


def prepare_cutout(root, path, target, kind='person'):
    """Keep an existing PNG alpha or remove the photo background locally; never synthesize identity."""
    from hinglish_motion.assets import Remover, has_alpha, cutout_ok, trim
    from .render import load_picture
    target = Path(target)
    if target.is_file():
        return load_picture(target)
    picture = load_picture(path)
    if not has_alpha(picture):
        try:
            picture = Remover(root)(picture, kind).convert('RGBA')
        except Exception as error:
            raise RuntimeError(f'Smart Visuals cutout unavailable: {error}') from error
        if not cutout_ok(picture):
            raise ValueError('Smart Visuals cutout has no usable isolated subject')
    picture = trim(picture)
    target.parent.mkdir(parents=True, exist_ok=True)
    picture.save(target)
    return picture


def render_overlay(art, position, seconds, width, height, fps, target, rise=False):
    from .render import _Writer, _frames
    count = _frames(seconds, fps)
    writer = _Writer(target, width, height, fps, alpha=True)
    try:
        for i in range(count):
            # Include the transparent last frame even at low preview frame rates.
            t = seconds * i / max(1, count - 1)
            writer.write(np.asarray(overlay_frame(art, position, (width, height), t, seconds, rise)))
        return writer.finish()
    except BaseException:
        writer.abort()
        raise


def render_signature(slot, timeline, media):
    value = [REVISION, slot['start'], slot['end'], slot['display'], slot.get('avoid'),
             slot.get('label'), timeline.width, timeline.height, str(timeline.fps), media.id, media.url]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]
