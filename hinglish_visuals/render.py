"""Turn downloaded photos, logos and videos into clips that sit pixel-exact on the sequence:

- full-screen photo:  slow push-in (Ken Burns), H.264. Photos with a different shape sit over a
                      blurred, darkened copy of themselves instead of being cropped to a sliver.
- full-screen video:  best part of the video, same size/fps, muted; archival 4:3 footage keeps its
                      whole picture over a blurred fill.
- pop-up card:        transparent QuickTime (Animation codec with alpha, like the caption layer):
                      logo card or face card with a name label, pops in, holds, pops out.
Everything is rendered, not keyframed, so Premiere and Resolve show exactly the same thing."""
from fractions import Fraction
import math
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from hinglish_broll.conform import encoder_for
from hinglish_broll.library import read_frames
from hinglish_cut.media import video_rotation

from .layout import place_card

PUSH = 1.07             # full-screen photo push-in over the clip
POP_IN, POP_OUT = .30, .22
FONTS = ('segoeuib.ttf', 'arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf')


def font(size):
    for name in FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def ease_sine(x):
    return .5 - .5 * math.cos(math.pi * min(1.0, max(0.0, x)))


def ease_out_back(x, s=1.5):
    x = min(1.0, max(0.0, x)) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def load_picture(path):
    """Any downloaded image as upright RGBA (first frame of GIF/WebP)."""
    with Image.open(path) as image:
        image.seek(0)
        image = ImageOps.exif_transpose(image)
        return image.convert('RGBA')


def _cover(image, width, height, anchor_y=.5):
    scale = max(width / image.width, height / image.height)
    w, h = max(width, round(image.width * scale)), max(height, round(image.height * scale))
    resized = image.resize((w, h), Image.LANCZOS)
    x = (w - width) // 2
    y = min(h - height, max(0, round((h - height) * anchor_y)))
    return resized.crop((x, y, x + width, y + height))


def _fit(image, width, height):
    scale = min(width / image.width, height / image.height)
    return image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)


def _blur_fill(image, width, height):
    small = _cover(image.convert('RGB'), max(8, width // 12), max(8, height // 12))
    small = small.filter(ImageFilter.GaussianBlur(3))
    return ImageEnhance.Brightness(small.resize((width, height), Image.BICUBIC)).enhance(.5)


def similar_shape(w, h, width, height, tolerance=.22):
    return abs(math.log((w / h) / (width / height))) <= tolerance


def compose_full(image, width, height, anchor_y=.4):
    """RGB canvas: cover when the shapes are close, else the whole picture over a blurred fill."""
    rgb = image.convert('RGBA')
    if similar_shape(rgb.width, rgb.height, width, height):
        flat = Image.new('RGB', rgb.size, (0, 0, 0))
        flat.paste(rgb, mask=rgb.getchannel('A'))
        return _cover(flat, width, height, anchor_y)
    canvas = _blur_fill(rgb, width, height).convert('RGBA')
    margin = round(min(width, height) * .04)
    front = _fit(rgb, width - 2 * margin, height - 2 * margin)
    x, y = (width - front.width) // 2, (height - front.height) // 2
    shadow = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((x, y + margin // 3, x + front.width, y + front.height + margin // 3),
                                     fill=(0, 0, 0, 150))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(margin / 2)))
    canvas.alpha_composite(front, (x, y))
    return canvas.convert('RGB')


class _Writer:
    """Constant-frame-rate writer: H.264 (opaque) or QuickTime Animation with alpha."""

    def __init__(self, target, width, height, fps, alpha=False, device='cpu'):
        self.target = Path(target)
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.partial = self.target.with_name(self.target.stem + '.partial' + self.target.suffix)
        self.container = av.open(str(self.partial), 'w')
        self.alpha = alpha
        if alpha:
            self.stream = self.container.add_stream('qtrle', rate=Fraction(fps))
            self.stream.width, self.stream.height, self.stream.pix_fmt = width, height, 'argb'
        else:
            codec = encoder_for(device)
            self.stream = self.container.add_stream(codec, rate=Fraction(fps))
            self.stream.width, self.stream.height, self.stream.pix_fmt = width, height, 'yuv420p'
            self.stream.options = {'preset': 'p5', 'cq': '19'} if codec == 'h264_nvenc' else \
                {'preset': 'veryfast', 'crf': '18'}
        self.count = 0

    def write(self, pixels):
        if self.alpha:
            frame = av.VideoFrame.from_ndarray(pixels, format='rgba').reformat(format='argb')
        else:
            frame = av.VideoFrame.from_ndarray(pixels, format='rgb24').reformat(format='yuv420p')
        frame.pts = self.count
        for packet in self.stream.encode(frame):
            self.container.mux(packet)
        self.count += 1

    def finish(self):
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()
        self.partial.replace(self.target)
        return self.target

    def abort(self):
        try: self.container.close()
        except Exception: pass
        self.partial.unlink(missing_ok=True)


def _frames(seconds, fps):
    count = round(seconds * Fraction(fps))
    if count <= 0:
        raise ValueError('Clip is too short')
    return count


def still_clip(image_path, seconds, width, height, fps, target, device='cpu'):
    """Full-screen photo with a gentle eased push-in."""
    count = _frames(seconds, fps)
    base = compose_full(load_picture(image_path), round(width * PUSH), round(height * PUSH))
    writer = _Writer(target, width, height, fps, device=device)
    try:
        for i in range(count):
            s = 1 + (PUSH - 1) * ease_sine(i / max(1, count - 1))
            w, h = base.width / s, base.height / s
            x, y = (base.width - w) / 2, (base.height - h) / 2
            frame = base.resize((width, height), Image.BILINEAR, box=(x, y, x + w, y + h))
            writer.write(np.asarray(frame))
        return writer.finish()
    except BaseException:
        writer.abort()
        raise


def _rounded(image, radius):
    mask = Image.new('L', image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius, fill=255)
    out = image.copy()
    out.putalpha(Image.fromarray(np.minimum(np.asarray(out.getchannel('A')), np.asarray(mask))))
    return out


def _is_light(image):
    pixels = np.asarray(image.convert('RGBA'), np.float32)
    visible = pixels[..., 3] > 128
    if visible.sum() < 20:
        return False
    luminance = (pixels[..., :3] @ np.array([.299, .587, .114], np.float32))[visible]
    return float(np.median(luminance)) > 205


def _has_transparency(image):
    return float((np.asarray(image.getchannel('A')) < 200).mean()) > .03


def card_box(width, height):
    """(max card width, max card height) for this canvas."""
    if height > width * 1.2:
        return round(width * .44), round(height * .22)
    if width > height * 1.2:
        return round(width * .24), round(height * .34)
    return round(width * .36), round(height * .26)


def popup_card(image_path, width, height, style='logo', label='', avoid=None):
    """-> (card RGBA with its shadow, (x, y) of its top-left corner on the canvas).

    avoid: canvas box (x0, y0, x1, y1) around the speaker's face; the card never covers it."""
    picture = load_picture(image_path)
    if max(picture.size) < 96:
        raise ValueError('the image is too small to look sharp')
    max_w, max_h = card_box(width, height)
    unit = min(width, height)
    radius = round(unit * .03)
    if style == 'logo':
        if _has_transparency(picture):
            pad = round(unit * .035)
            art = _fit(picture, max_w - 2 * pad, max_h - 2 * pad)
            body = Image.new('RGBA', (art.width + 2 * pad, art.height + 2 * pad),
                             (22, 22, 26, 238) if _is_light(picture) else (255, 255, 255, 246))
            body.alpha_composite(art, (pad, pad))
        else:   # an opaque logo (JPEG / square app icon) is its own card
            body = _fit(picture, max_w, max_h)
        body = _rounded(body, radius)
    else:       # face card: 4:5 photo cropped from the top (faces), white frame, name label
        text_h = round(unit * .06) if label else 0
        photo_h = max_h - text_h
        photo = _cover(picture, round(photo_h * .8), photo_h, anchor_y=.25)
        border = max(3, round(unit * .008))
        body = Image.new('RGBA', (photo.width + 2 * border, photo.height + 2 * border + text_h), (0, 0, 0, 0))
        frame = Image.new('RGBA', (photo.width + 2 * border, photo.height + 2 * border), (255, 255, 255, 255))
        body.alpha_composite(_rounded(frame, radius), (0, 0))
        body.alpha_composite(_rounded(photo, max(1, radius - border)), (border, border))
        if label:
            size = round(text_h * .52)
            typeface = font(size)
            while size > 10 and ImageDraw.Draw(body).textlength(label, font=typeface) > body.width * 1.6:
                size -= 2; typeface = font(size)
            text_w = round(ImageDraw.Draw(body).textlength(label, font=typeface))
            pill_w = min(max(body.width, text_w + 2 * round(size * .8)), round(width * .9))
            wide = Image.new('RGBA', (max(body.width, pill_w), body.height + round(text_h * .35)), (0, 0, 0, 0))
            wide.alpha_composite(body, ((wide.width - body.width) // 2, 0))
            draw = ImageDraw.Draw(wide)
            top = photo.height + 2 * border - round(text_h * .35)
            left = (wide.width - pill_w) // 2
            draw.rounded_rectangle((left, top, left + pill_w, top + text_h), text_h // 2, fill=(17, 17, 20, 235))
            draw.text((wide.width / 2, top + text_h / 2), label, font=typeface, fill=(255, 255, 255, 255), anchor='mm')
            body = wide
    blur = max(2, round(unit * .018))
    card = Image.new('RGBA', (body.width + 4 * blur, body.height + 4 * blur), (0, 0, 0, 0))
    shadow = Image.new('RGBA', card.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 120), (2 * blur, 2 * blur + blur // 2, 2 * blur + body.width, 2 * blur + body.height + blur // 2),
                 mask=body.getchannel('A'))
    card = Image.alpha_composite(card, shadow.filter(ImageFilter.GaussianBlur(blur)))
    card.alpha_composite(body, (2 * blur, 2 * blur))
    scale, spot = place_card(card.width, card.height, width, height, avoid)
    if scale != 1.0:
        card = card.resize((round(card.width * scale), round(card.height * scale)), Image.LANCZOS)
    return card, spot


def popup_clip(card, position, seconds, width, height, fps, target):
    """Transparent full-canvas clip: the card pops in with a small overshoot, holds, pops out."""
    count = _frames(seconds, fps)
    fps_f = float(Fraction(fps))
    centre = (position[0] + card.width / 2, position[1] + card.height / 2)
    card_px = np.asarray(card)
    held = None
    writer = _Writer(target, width, height, fps, alpha=True)
    try:
        for i in range(count):
            t, left = i / fps_f, (count - i) / fps_f
            if t < POP_IN:
                scale, opacity = .55 + .45 * ease_out_back(t / POP_IN), min(1.0, t / (POP_IN * .6))
            elif left < POP_OUT:
                k = ease_sine(1 - left / POP_OUT)
                scale, opacity = 1 - .18 * k, 1 - k
            else:
                scale, opacity = 1.0, 1.0
            if scale == 1.0 and opacity == 1.0 and held is not None:
                writer.write(held); continue
            canvas = np.zeros((height, width, 4), np.uint8)
            if scale == 1.0:
                pixels = card_px
            else:
                pixels = np.asarray(card.resize((max(1, round(card.width * scale)),
                                                 max(1, round(card.height * scale))), Image.BICUBIC))
            if opacity < 1.0:
                pixels = pixels.copy()
                pixels[..., 3] = (pixels[..., 3].astype(np.float32) * opacity).astype(np.uint8)
            h, w = pixels.shape[:2]
            x, y = round(centre[0] - w / 2), round(centre[1] - h / 2)
            x0, y0, x1, y1 = max(0, x), max(0, y), min(width, x + w), min(height, y + h)
            if x1 > x0 and y1 > y0:
                canvas[y0:y1, x0:x1] = pixels[y0 - y:y1 - y, x0 - x:x1 - x]
            if scale == 1.0 and opacity == 1.0:
                held = canvas
            writer.write(canvas)
        return writer.finish()
    except BaseException:
        writer.abort()
        raise


def probe_duration(path):
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        if stream.duration and stream.time_base:
            return float(stream.duration * stream.time_base)
        return float(container.duration or 0) / 1_000_000


def choose_offset(path, need, duration, scorer=None, samples=10):
    """Start of the best `need`-second part: skips titles/credits, black and flat frames (intertitles);
    `scorer(images) -> [similarity]` (CLIP) prefers frames that match the moment."""
    latest = duration - need - .2
    if latest <= .5:
        return 0.0
    first = min(latest, max(.5, duration * .04))
    last = max(first, min(latest, duration * .92 - need))
    times = [first + (last - first) * k / max(1, samples - 1) + need / 2 for k in range(samples)]
    frames = read_frames(path, times, size=224)
    if not frames:
        return first
    stats = []
    for _, image in frames:
        grey = np.asarray(image.convert('L'), np.float32)
        stats.append((grey.mean(), grey.std()))
    similarity = scorer([im for _, im in frames]) if scorer else [0.0] * len(frames)
    best_t, best = first, -1e9
    for (t, _), (mean, std), sim in zip(frames, stats, similarity):
        value = sim * 20 + min(std, 60) / 60 - (2 if mean < 28 or std < 14 else 0)
        if value > best:
            best, best_t = value, t
    return float(min(latest, max(0.0, best_t - need / 2)))


def video_clip(source, offset, seconds, width, height, fps, target, device='cpu'):
    """Part of a downloaded video as a full-screen clip (constant frame rate, muted)."""
    fps = Fraction(fps)
    count = _frames(seconds, fps)
    rotation = video_rotation(source)
    writer = _Writer(target, width, height, fps, device=device)
    written, last, fit = 0, None, None
    try:
        with av.open(str(source)) as inp:
            stream = inp.streams.video[0]
            stream.thread_type = 'AUTO'
            if offset > 0:
                inp.seek(int(offset / stream.time_base), stream=stream, backward=True)
            for frame in inp.decode(stream):
                t = frame.time if frame.time is not None else offset
                if t < offset - 1e-3:
                    continue
                image = frame.to_image()
                if rotation:
                    image = Image.fromarray(np.ascontiguousarray(np.rot90(np.asarray(image), rotation // 90)))
                if fit is None:
                    fit = not similar_shape(image.width, image.height, width, height)
                current = np.asarray(compose_full(image, width, height, .5) if fit else
                                     _cover(image, width, height, .5))
                while written < count and offset + written / fps < t - 1e-6:
                    writer.write(last if last is not None else current); written += 1
                last = current
                if written >= count:
                    break
            while last is not None and written < count:     # hold the last frame if the video ends early
                writer.write(last); written += 1
        if written < count:
            raise ValueError(f'Could not read enough video from {Path(source).name}')
        return writer.finish()
    except BaseException:
        writer.abort()
        raise
