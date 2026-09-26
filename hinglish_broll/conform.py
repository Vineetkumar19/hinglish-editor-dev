"""Cut one B-roll clip: best part, crop-to-fill the sequence canvas, constant frame rate, muted."""
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from hinglish_cut.media import video_rotation

_ENCODER_CACHE = {}


def encoder_for(device):
    """NVENC on an NVIDIA card when requested and working, otherwise libx264."""
    if device != 'cuda':
        return 'libx264'
    if 'nvenc' not in _ENCODER_CACHE:
        try:
            codec = av.CodecContext.create('h264_nvenc', 'w')
            codec.width, codec.height, codec.pix_fmt = 256, 256, 'yuv420p'
            codec.time_base = Fraction(1, 30)
            codec.open()
            _ENCODER_CACHE['nvenc'] = True
        except Exception:
            _ENCODER_CACHE['nvenc'] = False
    return 'h264_nvenc' if _ENCODER_CACHE['nvenc'] else 'libx264'


def crop_box(src_w, src_h, dst_w, dst_h):
    """Centered crop of the source with the destination aspect ratio (fills, never letterboxes)."""
    scale = max(dst_w / src_w, dst_h / src_h)
    crop_w, crop_h = min(src_w, round(dst_w / scale)), min(src_h, round(dst_h / scale))
    x, y = (src_w - crop_w) // 2, (src_h - crop_h) // 2
    return x, y, crop_w, crop_h


def make_clip(source, offset, seconds, width, height, fps, target, device='cpu'):
    fps = Fraction(fps)
    frames_needed = round(seconds * fps)
    if frames_needed <= 0:
        raise ValueError('B-roll clip is too short')
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.stem + '.partial' + target.suffix)
    rotation = video_rotation(source)
    codec = encoder_for(device)
    written, last = 0, None
    try:
        with av.open(str(source)) as inp, av.open(str(partial), 'w') as out:
            stream = inp.streams.video[0]
            stream.thread_type = 'AUTO'
            video = out.add_stream(codec, rate=fps)
            video.width, video.height, video.pix_fmt = width, height, 'yuv420p'
            video.options = {'preset': 'p5', 'cq': '19'} if codec == 'h264_nvenc' else {'preset': 'veryfast', 'crf': '18'}

            def emit(pixels):
                nonlocal written
                frame = av.VideoFrame.from_ndarray(pixels, format='rgb24').reformat(
                    width=width, height=height, format='yuv420p')
                frame.pts = written
                for packet in video.encode(frame):
                    out.mux(packet)
                written += 1

            if offset > 0:
                inp.seek(int(offset / stream.time_base), stream=stream, backward=True)
            box = None
            for frame in inp.decode(stream):
                t = frame.time if frame.time is not None else offset
                if t < offset - 1e-3:
                    continue
                pixels = frame.to_ndarray(format='rgb24')
                if rotation:
                    pixels = np.rot90(pixels, rotation // 90)
                if box is None:
                    box = crop_box(pixels.shape[1], pixels.shape[0], width, height)
                x, y, w, h = box
                current = np.ascontiguousarray(pixels[y:y + h, x:x + w])
                # Constant frame rate: each output frame shows the latest source frame at its time.
                while written < frames_needed and offset + written / fps < t - 1e-6:
                    emit(last if last is not None else current)
                last = current
                if written >= frames_needed:
                    break
            while last is not None and written < frames_needed:   # hold last frame if source ends early
                emit(last)
            for packet in video.encode():
                out.mux(packet)
        if written < frames_needed:
            raise ValueError(f'Could not read enough video from {Path(source).name}')
        partial.replace(target)
        return target
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
