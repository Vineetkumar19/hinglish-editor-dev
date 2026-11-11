"""Make one vertical short (1080x1920): the finished MP4 plus the layer files its editable sequence uses.

Template look (your shorts): dark blurred copy of the video behind, the full 16:9 video framed with a glow in
the middle, the title with a red bar above it, "WATCH FULL VIDEO ON  @handle" under it.
Face look (FireCut style): a 9:16 crop of the video that keeps the speaker's face in the middle."""
from fractions import Fraction
from pathlib import Path
import math

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from hinglish_broll.conform import encoder_for
from hinglish_cut.gpu_frames import with_cuda_frames

W, H = 1080, 1920
FG_W, FG_X, FG_CY = 864, 108, 988            # the framed video: width, left edge, vertical centre
GLOW = (104, 112, 255)
BORDER = (228, 232, 255)
RED = (225, 22, 36)
RATE = 48000
FADE = int(.008 * RATE)                       # 8 ms fades where two pieces meet: no clicks
CAPTION_POSITION = {'template': .86, 'face': .72}


def _font(names, size):
    from hinglish_captions.renderer import _font_path
    for name in names:
        try:
            return ImageFont.truetype(str(_font_path(name)), size)
        except (ValueError, OSError):
            continue
    return ImageFont.load_default()


SERIF_BOLD = ('georgiab.ttf', 'timesbd.ttf', 'arialbd.ttf')
SERIF = ('georgia.ttf', 'times.ttf', 'arial.ttf')


def fg_box(width, height):
    """Where the framed 16:9 video sits on the 1080x1920 canvas: (x, y, w, h)."""
    h = round(FG_W * height / width / 2) * 2
    h = min(h, 1200)
    w = FG_W if h < 1200 else round(1200 * width / height / 2) * 2
    return (W - w) // 2, FG_CY - h // 2, w, h


def _wrap(draw, text, font, max_width, max_lines=2):
    words, lines = text.split(), []
    while words and len(lines) < max_lines:
        line = words.pop(0)
        while words and draw.textlength(line + ' ' + words[0], font=font) <= max_width:
            line += ' ' + words.pop(0)
        lines.append(line)
    return lines, not words


def _title_font(draw, text, max_width):
    for size in range(60, 35, -2):                  # prefer a complete, readable single line
        font = _font(SERIF_BOLD, size)
        if draw.textlength(text, font=font) <= max_width:
            return font, [text]
    for size in range(58, 38, -2):
        font = _font(SERIF_BOLD, size)
        lines, fits = _wrap(draw, text, font, max_width)
        if fits and all(draw.textlength(l, font=font) <= max_width for l in lines):
            return font, lines
    # Never silently drop words at the end of a heading.
    for size in range(38,15,-2):
        font=_font(SERIF_BOLD,size);lines,fits=_wrap(draw,text,font,max_width)
        if fits:return font,lines
    raise ValueError('The Short heading does not fit. Ask the local title planner for a heading of seven words or fewer.')


def _glowing_text(layer, xy, text, font, fill=(255, 255, 255), glow=110, blur=6, anchor='la'):
    shadow = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text(xy, text, font=font, fill=(255, 255, 255, glow), anchor=anchor)
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(layer).text(xy, text, font=font, fill=fill + (255,), anchor=anchor)


def _youtube_logo(layer, x, y, h):
    w = round(h * 1.42)
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=round(h * .26), fill=(255, 0, 0, 255))
    cx, cy, s = x + w / 2 + h * .04, y + h / 2, h * .2
    draw.polygon([(cx - s, cy - s * 1.15), (cx - s, cy + s * 1.15), (cx + s * 1.25, cy)], fill=(255, 255, 255, 255))
    return w


def template_overlay(title, handle, cta, source_w, source_h):
    """Everything drawn over the video in the template look (RGBA 1080x1920, transparent elsewhere)."""
    x, y, w, h = fg_box(source_w, source_h)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rectangle((x - 4, y - 4, x + w + 4, y + h + 4), outline=GLOW + (255,), width=30)
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    alpha = np.asarray(glow)[:, :, 3].astype(np.float32) * 1.7
    alpha[y:y + h, x:x + w] = 0                     # the glow never tints the video itself
    glow.putalpha(Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8)))
    layer.alpha_composite(glow)
    ImageDraw.Draw(layer).rectangle((x - 1, y - 1, x + w, y + h), outline=BORDER + (255,), width=3)
    draw = ImageDraw.Draw(layer)
    text = ' '.join(str(title or '').upper().split())
    if text:
        font, lines = _title_font(draw, text, w - 40)
        line_h = round(font.size * 1.16)
        top = y - 34 - line_h * len(lines)
        draw.rectangle((x + 2, top + round(font.size * .1), x + 13, top + line_h * len(lines) - round(font.size * .08)),
                       fill=RED + (255,))
        for n, line in enumerate(lines):
            _glowing_text(layer, (x + 34, top + n * line_h), line, font)
    handle = str(handle or '').strip()
    if handle:
        small = _font(SERIF, 44)
        big = _font(SERIF, 52)
        cy = y + h + 90
        _glowing_text(layer, (W // 2, cy), str(cta or '').upper(), small, glow=80, anchor='mm')
        text_w = draw.textlength(handle, font=big)
        logo_h = 56
        total = logo_h * 1.42 + 18 + text_w
        left = round(W / 2 - total / 2)
        logo_w = _youtube_logo(layer, left, cy + 62 - logo_h // 2, logo_h)
        _glowing_text(layer, (left + logo_w + 18, cy + 62), handle, big, glow=80, anchor='lm')
    return layer


class _Blender:
    """Fast alpha blend of a fixed RGBA overlay onto frames: premultiplied, only in the rectangles it covers
    (the empty inside of the video frame is skipped), with OpenCV's SIMD maths."""

    def __init__(self, overlay, hole=None):
        rgba = np.asarray(overlay.convert('RGBA'))
        self.parts = []
        if hole is None:
            areas = [(0, H, 0, W)]
        else:          # around the framed video: above, below, left and right of it
            x, y, w, h = hole
            areas = [(0, y + 3, 0, W), (y + h - 3, H, 0, W), (y + 3, y + h - 3, 0, x + 3), (y + 3, y + h - 3, x + w - 3, W)]
        for top, bottom, left, right in areas:
            alpha = rgba[top:bottom, left:right, 3]
            rows, cols = np.nonzero(alpha.max(axis=1))[0], np.nonzero(alpha.max(axis=0))[0]
            if not len(rows):
                continue
            r0, r1, c0, c1 = top + rows[0], top + rows[-1] + 1, left + cols[0], left + cols[-1] + 1
            part = rgba[r0:r1, c0:c1].astype(np.float32)
            a = part[:, :, 3:4] / 255.0
            premultiplied = np.clip(part[:, :, :3] * a + .5, 0, 255).astype(np.uint8)
            keep = np.clip(np.repeat(1 - a, 3, axis=2), 0, 1).astype(np.float32)
            self.parts.append((r0, r1, c0, c1, premultiplied, keep))

    def apply(self, frame):
        for r0, r1, c0, c1, premultiplied, keep in self.parts:
            roi = frame[r0:r1, c0:c1]
            frame[r0:r1, c0:c1] = cv2.add(cv2.multiply(roi, keep, dtype=cv2.CV_8U), premultiplied)
        return frame


def _blend_rgba(frame, rgba, top, bottom):
    part = rgba[top:bottom]
    a = part[:, :, 3:4].astype(np.uint16)
    if not a.any():
        return frame
    roi = frame[top:bottom].astype(np.uint16)
    frame[top:bottom] = ((roi * (255 - a) + part[:, :, :3].astype(np.uint16) * a + 127) // 255).astype(np.uint8)
    return frame


class Composer:
    """Source frame -> finished 1080x1920 frame (+ the small background frame for the editable sequence)."""

    def __init__(self, look, source_w, source_h, overlay=None, gpu=None):
        self.look, self.sw, self.sh = look, source_w, source_h
        self.box = fg_box(source_w, source_h)
        self.gpu = gpu
        if gpu is not None:
            self.gpu_overlay = None
            if overlay is not None:
                rgba = np.array(overlay.convert('RGBA'), copy=True)
                if look == 'template':
                    x, y, w, h = self.box
                    rgba[y+3:y+h-3, x+3:x+w-3, 3] = 0
                self.gpu_overlay = gpu.upload(rgba)
            self.face_x = .5
            return
        self.blender = _Blender(overlay, self.box if look == 'template' else None) if overlay is not None else None
        self.scan = np.full((H, W, 3), 1.0, np.float32)
        self.scan[1::3] = .72                                  # the fine horizontal lines of your background
        self.face_x = .5

    def background(self, fg):
        """The framed picture -> tiny cover crop -> blur -> dark blue tint -> full size with scanlines."""
        fh, fw = fg.shape[:2]
        scale = max(135 / fw, 240 / fh)
        small = cv2.resize(fg, (max(135, round(fw * scale)), max(240, round(fh * scale))), interpolation=cv2.INTER_AREA)
        x0, y0 = (small.shape[1] - 135) // 2, (small.shape[0] - 240) // 2
        small = small[y0:y0 + 240, x0:x0 + 135].astype(np.float32)
        small = cv2.GaussianBlur(small, (0, 0), 4.5)
        small = small * np.array([.30, .32, .52], np.float32) + np.array([6, 8, 30], np.float32)
        bg = cv2.resize(np.clip(small, 0, 255).astype(np.uint8), (W, H), interpolation=cv2.INTER_LINEAR)
        return cv2.multiply(bg, self.scan, dtype=cv2.CV_8U)

    def compose(self, frame):
        """-> (full 1080x1920 RGB, 540x960 background RGB or None)."""
        if self.gpu is not None: return self._compose_cuda(frame)
        if self.look == 'face':
            scale = H / self.sh
            sw = max(W, round(self.sw * scale / 2) * 2)
            big = frame.reformat(width=sw, height=H, format='rgb24').to_ndarray()
            x0 = int(min(max(0, self.face_x * sw - W / 2), sw - W))
            out = np.ascontiguousarray(big[:, x0:x0 + W])
            return (self.blender.apply(out) if self.blender else out), None
        x, y, w, h = self.box
        fg = frame.reformat(width=w, height=h, format='rgb24').to_ndarray()
        out = self.background(fg)
        small_bg = cv2.resize(out, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
        out[y:y + h, x:x + w] = fg
        return (self.blender.apply(out) if self.blender else out), small_bg

    def _compose_cuda(self, frame):
        gpu = self.gpu
        source = gpu.upload(frame.to_ndarray(format='rgb24'))
        small_bg = None
        if self.look == 'face':
            scale = H/self.sh
            sw = max(W, round(self.sw*scale/2)*2)
            big = gpu.resize(source, sw, H, 'bicubic')
            x = int(min(max(0, self.face_x*sw-W/2), sw-W))
            out = big[..., :, x:x+W]
        else:
            x, y, w, h = self.box
            fg = gpu.resize(source, w, h, 'bicubic')
            small = gpu.fit(fg, 135, 240, fill=True)
            small = gpu.blur(small, 4.5)
            tint = gpu.torch.tensor([.30, .32, .52], device='cuda').view(1, 3, 1, 1)
            offset = gpu.torch.tensor([6, 8, 30], device='cuda').view(1, 3, 1, 1)
            out = gpu.resize((small*tint+offset).clamp(0, 255), W, H)
            out[..., 1::3, :] *= .72
            small_bg = gpu.resize(out, W//2, H//2, 'area')
            out[..., y:y+h, x:x+w] = fg
        if self.gpu_overlay is not None: out = gpu.over(out, self.gpu_overlay)
        return out, small_bg


def frame_plan(pieces, fps):
    """Pieces in seconds -> [(first source frame at `fps`, frame count)], cut on whole frames."""
    plan = []
    for s, e in pieces:
        first = round(s * fps)
        count = max(1, round((e - s) * fps))
        plan.append((first, count))
    return plan


def piece_audio(path, plan, fps):
    """Stereo 48 kHz float audio for each planned piece, joined with tiny fades."""
    chunks = []
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        for first, count in plan:
            start = first / fps
            need = round(count * RATE / fps)
            buf = np.zeros((2, need), np.float32)
            resampler = av.AudioResampler(format='fltp', layout='stereo', rate=RATE)
            container.seek(max(0, int((float(start) - 1.0) / stream.time_base)), stream=stream, backward=True)
            done = False
            for packet_frame in container.decode(stream):
                if packet_frame.pts is None:
                    continue
                t0 = float(packet_frame.pts * packet_frame.time_base)
                for r in resampler.resample(packet_frame):
                    data = r.to_ndarray().astype(np.float32)
                    if data.shape[0] == 1:
                        data = np.repeat(data, 2, axis=0)
                    offset = round((t0 - float(start)) * RATE)
                    a, b = max(0, offset), min(need, offset + data.shape[1])
                    if b > a:
                        buf[:, a:b] = data[:, a - offset:b - offset]
                    t0 += data.shape[1] / RATE
                    if offset + data.shape[1] >= need:
                        done = True
                if done:
                    break
            ramp = np.linspace(0, 1, FADE, dtype=np.float32)
            buf[:, :FADE] *= ramp
            buf[:, -FADE:] *= ramp[::-1]
            chunks.append(buf)
    return np.concatenate(chunks, axis=1) if chunks else np.zeros((2, 0), np.float32)


def source_frames(container, stream, plan, src_fps, out_fps):
    """Yield the source frame for every output frame of every piece (60 fps -> 30 fps takes every second one)."""
    for first, count in plan:
        start = first / out_fps
        container.seek(max(0, int((float(start) - .5) / stream.time_base)), stream=stream, backward=True)
        k, last = 0, None
        target = float(start)
        half = .5 / float(src_fps)
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            if frame.time < target - half:
                last = frame
                continue
            while k < count and frame.time >= target - half:
                yield frame if frame.time <= target + half or last is None else last
                k += 1
                target = float(start) + k / float(out_fps)
            last = frame
            if k >= count:
                break
        while k < count and last is not None:          # the file ended: hold the last picture
            yield last
            k += 1


class _Video:
    def __init__(self, target, width, height, fps, codec, audio=False):
        self.target = Path(target)
        self.fps = Fraction(fps)
        self.partial = self.target.with_name(self.target.stem + '.partial' + self.target.suffix)
        self.container = av.open(str(self.partial), 'w')
        self.stream = self.container.add_stream(codec, rate=Fraction(fps))
        self.stream.width, self.stream.height = width, height
        self.stream.pix_fmt = 'argb' if codec == 'qtrle' else 'yuv420p'
        if codec == 'h264_nvenc':
            self.stream.options = {'preset': 'p5', 'cq': '20'}
        elif codec == 'libx264':
            self.stream.options = {'preset': 'veryfast', 'crf': '19'}
        self.audio = None
        if audio:
            self.audio = self.container.add_stream('aac', rate=RATE)
            self.audio.layout = 'stereo'
            self.audio.bit_rate = 192000
        self.count = self.samples = 0

    def write(self, pixels, fmt='rgb24'):
        frame = av.VideoFrame.from_ndarray(pixels, format=fmt).reformat(format=self.stream.pix_fmt)
        self.write_frame(frame)

    def write_gpu(self, pixels, gpu):
        self.write_frame(gpu.video_frame(pixels))

    def write_frame(self, frame):
        frame.pts = self.count
        frame.time_base = 1/self.fps
        for packet in self.stream.encode(frame):
            self.container.mux(packet)
        self.count += 1

    def write_audio(self, samples):
        for n in range(0, samples.shape[1], 1024):
            part = np.ascontiguousarray(samples[:, n:n + 1024])
            frame = av.AudioFrame.from_ndarray(part, format='fltp', layout='stereo')
            frame.sample_rate = RATE
            frame.pts = self.samples
            self.samples += part.shape[1]
            for packet in self.audio.encode(frame):
                self.container.mux(packet)

    def finish(self):
        for packet in self.stream.encode():
            self.container.mux(packet)
        if self.audio is not None:
            for packet in self.audio.encode():
                self.container.mux(packet)
        self.container.close()
        self.partial.replace(self.target)
        return self.target

    def abort(self):
        try:
            self.container.close()
        except Exception:
            pass
        self.partial.unlink(missing_ok=True)


def still_layer(image, seconds_frames, fps, target):
    """A transparent layer (title, frame, captions...) as a QuickTime Animation file with alpha."""
    writer = _Video(target, W, H, fps, 'qtrle')
    try:
        frame = av.VideoFrame.from_ndarray(np.asarray(image.convert('RGBA')), format='rgba').reformat(format='argb')
        for n in range(seconds_frames):
            frame.pts = n
            for packet in writer.stream.encode(frame):
                writer.container.mux(packet)
        writer.count = seconds_frames
        return writer.finish()
    except BaseException:
        writer.abort()
        raise


def caption_cues(words, pieces):
    """Captions for the short: the words inside its pieces, on the short's own clock."""
    from hinglish_captions.core import build_cues, timed_words
    from hinglish_captions.numbers import digits
    from hinglish_cut.model import Word
    placed, offset = [], 0.0
    for s, e in pieces:
        piece_words=[]
        for w in words:
            middle = (w.start + w.end) / 2
            if s <= middle < e:
                piece_words.append(Word(w.text, max(0.0, w.start - s) + offset, min(e, w.end) - s + offset))
        # A cut may join unrelated numerical phrases. Normalize inside each
        # source piece so their quantities cannot accidentally be combined.
        placed.extend(digits(timed_words(piece_words,offset+e-s)))
        offset += e - s
    return build_cues(placed)


@with_cuda_frames
def render_short(video, pieces, look, target, assets, index, overlay=None, face_x=.5, cues=None,
                 caption_style='typography_1', device='cpu', progress=print,*,reuse_captions=False, _gpu=None):
    """Write the finished MP4 and the layer files for the editable sequence. Returns facts for the plan."""
    fps = video.short_fps
    plan = frame_plan(pieces, fps)
    total = sum(c for _, c in plan)
    assets = Path(assets)
    assets.mkdir(parents=True, exist_ok=True)
    ratio = int(video.fps / fps)                # layer files run at the source rate (the editable sequence's)
    layers = {}
    if overlay is not None:
        if device == 'cuda':
            # One static image is an I/O asset, not a CPU-encoded full-length movie.
            still=assets/f'overlay-{index:02d}.png'
            overlay.save(still)
            layers['overlay']=str(still)
        else:
            layers['overlay'] = str(still_layer(overlay, total * ratio, video.fps, assets / f'overlay-{index:02d}.mov'))
    captions = None
    if cues:
        from hinglish_captions.renderer import render_overlay
        path = assets / f'captions-{index:02d}.mov'
        if not (reuse_captions and path.is_file()):
            render_overlay(path, cues, W, H, total / float(fps), fps=video.fps, style_name=caption_style,
                           progress=lambda m: progress(f'Short {index}: {m.strip()}'), position=CAPTION_POSITION[look], device=device)
        layers['captions'] = str(path)
        captions = av.open(str(path))
    composer = Composer(look, video.width, video.height, overlay, gpu=_gpu)
    composer.face_x = face_x
    audio = piece_audio(video.path, plan, fps)
    codec = encoder_for(device)
    writer = _Video(target, W, H, fps, codec, audio=True)
    background = _Video(assets / f'background-{index:02d}.mp4', W // 2, H // 2, video.fps, codec) \
        if look == 'template' else None
    thumb = None
    band = None
    try:
        caption_frames = captions.decode(video=0) if captions else None
        with av.open(str(video.path)) as container:
            stream = container.streams.video[0]
            stream.thread_type = 'AUTO'
            per_frame = RATE / float(fps)
            for n, frame in enumerate(source_frames(container, stream, plan, video.fps, fps)):
                out, small_bg = composer.compose(frame)
                if caption_frames is not None:
                    cap = next(caption_frames, None)
                    for _ in range(ratio - 1):          # the caption layer runs at the source rate
                        next(caption_frames, None)
                    if cap is not None:
                        rgba = cap.to_ndarray(format='rgba')
                        if band is None:
                            centre = round(H * CAPTION_POSITION[look])
                            band = (max(0, centre - 260), min(H, centre + 200))
                        out = (_gpu.over(out, _gpu.upload(rgba)) if _gpu is not None
                               else _blend_rgba(out, rgba, *band))
                writer.write_gpu(out,_gpu) if _gpu is not None else writer.write(out)
                if background is not None:
                    for _ in range(ratio):
                        background.write_gpu(small_bg,_gpu) if _gpu is not None else background.write(small_bg)
                a, b = round(n * per_frame), round((n + 1) * per_frame)
                writer.write_audio(audio[:, a:b])
                if n == min(total - 1, round(float(fps) * 1.2)):
                    thumb = Image.fromarray(_gpu.download(out) if _gpu is not None else out).resize((270, 480))
                if n % max(1, round(float(fps) * 10)) == 0:
                    progress(f'  Short {index}: {round(n / total * 100)}%')
        writer.finish()
        if background is not None:
            layers['background'] = str(background.finish())
    except BaseException:
        writer.abort()
        if background is not None:
            background.abort()
        raise
    finally:
        if captions is not None:
            captions.close()
    if thumb is not None:
        thumb.save(assets / f'thumb-{index:02d}.jpg', quality=85)
    return {'frames': plan, 'fps': str(fps), 'layer_fps': str(video.fps), 'layers': layers,
            'thumb': f'assets/thumb-{index:02d}.jpg'}


def face_position(locator, path, pieces, samples=6):
    """Where the speaker's face is across the short (0-1 of the width), for the face look."""
    from hinglish_broll.library import read_frames
    times = [s + (e - s) * (k + .5) / samples for s, e in pieces for k in range(samples)]
    xs = []
    try:
        for _, image in read_frames(path, times, size=640):
            hit = locator._detect(image)
            if hit:
                xs.append(hit[0])
    except Exception:
        xs = []
    return float(np.median(xs)) if xs else .5, len(xs) / max(1, len(times))
