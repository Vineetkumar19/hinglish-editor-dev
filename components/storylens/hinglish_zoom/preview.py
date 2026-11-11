"""Playable render of a zoomed sequence: talking head with zooms + B-roll track + caption layers + audio."""
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image

from hinglish_broll.timeline import parse_xmeml
from hinglish_cut.media import video_rotation
from .xml_apply import motion_values
from hinglish_cut.gpu_frames import with_cuda_frames

SAMPLE_RATE = 48000


class Reader:
    """Sequential frame access: frame_at(t) returns the latest frame whose time is <= t (upright)."""

    def __init__(self, path, start=0.0):
        self.container = av.open(str(path))
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = 'AUTO'
        self.rotation = video_rotation(path)
        self.alpha = 'a' in (self.stream.codec_context.pix_fmt or '')
        if start > 0:
            self.container.seek(int(start / self.stream.time_base), stream=self.stream, backward=True)
        self.frames = self.container.decode(self.stream)
        self.current = self.next = None
        self.last_time = None
        self.end_reached = False

    def _image(self, frame):
        image = frame.to_image() if not self.alpha else frame.to_ndarray(format='rgba')
        if self.alpha:
            image = Image.fromarray(image, 'RGBA')
        if self.rotation:
            image = Image.fromarray(np.ascontiguousarray(np.rot90(np.asarray(image), self.rotation // 90)))
        return image

    def frame_at(self, t):
        while True:
            if self.next is None:
                try:
                    frame = next(self.frames)
                except (StopIteration, av.error.EOFError):
                    self.end_reached = True
                    return self.current
                self.next = (frame.time if frame.time is not None else 0.0, frame)
            if self.next[0] <= t + 1e-4 or self.current is None:
                self.last_time = self.next[0]
                self.current = self._image(self.next[1]); self.next = None
                continue
            return self.current

    def close(self):
        self.container.close()


def _audio_track(xml_path, total_seconds):
    """Mono 48 kHz mix of the timeline's first audio track (the speech)."""
    timeline = parse_xmeml(xml_path)
    buffer = np.zeros(int(total_seconds * SAMPLE_RATE) + SAMPLE_RATE, np.float32)
    for clip in timeline.clips:
        try:
            with av.open(clip.path) as source:
                if not source.streams.audio:
                    continue
                stream = source.streams.audio[0]
                resampler = av.AudioResampler(format='flt', layout='mono', rate=SAMPLE_RATE)
                source.seek(max(0, int(clip.source_in / stream.time_base)), stream=stream, backward=True)
                need = int((clip.source_out - clip.source_in) * SAMPLE_RATE)
                got, have = [], 0
                for frame in source.decode(stream):
                    t = frame.time or 0.0
                    for out in resampler.resample(frame):
                        data = out.to_ndarray().reshape(-1)
                        skip = max(0, int((clip.source_in - t) * SAMPLE_RATE)) if t < clip.source_in else 0
                        got.append(data[skip:]); have += len(data) - skip
                    if have >= need:
                        break
                samples = np.concatenate(got)[:need] if got else np.zeros(0, np.float32)
                start = int(clip.start * SAMPLE_RATE)
                buffer[start:start + len(samples)] += samples
        except Exception:
            continue
    return np.clip(buffer, -1, 1)


def upper_layers(seq):
    """[(start_frame, end_frame, path, source_start_seconds)] for B-roll/graphics above the talking head, bottom to top."""
    from .xml_apply import _int
    layers = []
    for track in seq.upper:
        if (track.findtext('enabled') or 'TRUE').upper() == 'FALSE':
            continue
        for item in track.findall('clipitem'):
            file = item.find('file')
            path = seq.files.get(file.get('id')) if file is not None else None
            start, end = _int(item, 'start'), _int(item, 'end')
            if path and Path(path).is_file() and 0 <= start < end:
                layers.append((start, end, path, float(Fraction(max(0, _int(item, 'in', 0))) / seq.fps)))
    return layers


@with_cuda_frames
def render_preview(seq, curve, anchors, destination, max_side=960, progress=print, extra_layers=(), audio=None, device='cpu', _gpu=None):
    """extra_layers: more (start_frame, end_frame, path, source_start) drawn on top, e.g. a caption overlay.
    audio: mono [samples] or stereo [2,samples] 48 kHz soundtrack."""
    fps = seq.fps
    scale = min(1.0, max_side / max(seq.width, seq.height))
    width, height = (max(2, int(n * scale) // 2 * 2) for n in (seq.width, seq.height))
    p = width / seq.width
    frames = seq.frames
    supplied_mix = audio is not None
    audio = _audio_track(seq.path, frames / float(fps)) if audio is None else np.asarray(audio, np.float32)
    if audio.ndim not in (1,2) or (audio.ndim==2 and audio.shape[0] not in (1,2)):
        raise ValueError('Preview audio must contain one or two channels')
    audio = audio.reshape(1,-1) if audio.ndim==1 else audio
    audio_layout = 'stereo' if audio.shape[0]==2 else 'mono'
    layers = upper_layers(seq) + list(extra_layers)
    destination = Path(destination)
    partial = destination.with_name(destination.stem + '.partial.mp4')
    by_frame = {}
    for clip in seq.clips:
        for f in range(max(0, clip.start), min(frames, clip.end)):
            by_frame.setdefault(f, clip)
    readers = {}

    def reader(key, path, start):
        if key not in readers:
            readers[key] = Reader(path, start)
        return readers[key]

    def release(active_keys):
        for key in [k for k in readers if k not in active_keys]:
            readers.pop(key).close()

    with av.open(str(partial), 'w', options={'movflags': '+faststart'}) as out:
        from hinglish_cut.compute_policy import h264_profile
        codec, options = h264_profile(device, 21)
        video = out.add_stream(codec, rate=fps)
        video.width, video.height, video.pix_fmt = width, height, 'yuv420p'
        video.options = options
        sound = out.add_stream('aac', rate=SAMPLE_RATE)
        sound.layout = audio_layout
        if supplied_mix:
            # Short broadband whooshes lose detail at AAC's default mono rate.
            # Preserve the prepared effects mix in both preview and chat export.
            sound.bit_rate = 192000
        for f in range(frames):
            if f % 150 == 0:
                progress(f'  Rendering {round(100 * f / frames)}%')
            t = f / float(fps)
            active = set()
            clip = by_frame.get(f)
            canvas = _gpu.blank(width, height) if _gpu is not None else Image.new('RGB', (width, height))
            if clip is not None:
                src_in = float(Fraction(clip.source_in) / clip.rate)
                key = ('v1', clip.id); active.add(key)
                image = reader(key, clip.path, src_in).frame_at(src_in + (f - clip.start) / float(fps))
                if image is not None:
                    canvas = _frame(image.convert('RGB'), clip, curve[f], anchors[f] or (0.0, 0.0),
                                    seq, width, height, p, gpu=_gpu)
            for n, (start, end, path, source_start) in enumerate(layers):
                if not start <= f < end:
                    continue
                key = ('layer', n); active.add(key)
                image = reader(key, path, source_start).frame_at(source_start + (f - start) / float(fps))
                if image is None:
                    continue
                if _gpu is not None:
                    canvas = _gpu.over(canvas, _gpu.upload(np.asarray(image)))
                    continue
                image = image.resize((width, height), Image.BILINEAR)
                if image.mode == 'RGBA':
                    canvas = Image.alpha_composite(canvas.convert('RGBA'), image).convert('RGB')
                else:
                    canvas = image.convert('RGB')
            release(active)
            frame = (_gpu.video_frame(canvas) if _gpu is not None
                     else av.VideoFrame.from_image(canvas).reformat(format='yuv420p'))
            frame.pts = f
            for packet in video.encode(frame): out.mux(packet)
        release(set())
        for packet in video.encode(): out.mux(packet)
        pcm = (np.clip(audio[:, :int(frames / float(fps) * SAMPLE_RATE)],-1,1) * 32767).astype(np.int16)
        for i in range(0, pcm.shape[1], 1024):
            chunk = np.ascontiguousarray(pcm[:, i:i+1024].T).reshape(1,-1)
            af = av.AudioFrame.from_ndarray(chunk, format='s16', layout=audio_layout)
            af.sample_rate, af.time_base, af.pts = SAMPLE_RATE, Fraction(1, SAMPLE_RATE), i
            for packet in sound.encode(af): out.mux(packet)
        for packet in sound.encode(): out.mux(packet)
    partial.replace(destination)
    return destination


def _frame(image, clip, z, face, seq, width, height, p, gpu=None):
    z = float(z) if clip.zoomable else 1.0
    scale_pct, center = motion_values(clip, z, face, seq.width, seq.height)
    s = scale_pct / 100
    cx, cy = center[0] * seq.width, center[1] * seq.height
    sw, sh = image.size
    # The source region that fills the frame (sub-pixel accurate). Resizing that region with an
    # antialiasing filter avoids the shimmer that plain sampling shows on fine textures while zooming.
    x0, x1 = (-seq.width / 2 - cx) / s + sw / 2, (seq.width / 2 - cx) / s + sw / 2
    y0, y1 = (-seq.height / 2 - cy) / s + sh / 2, (seq.height / 2 - cy) / s + sh / 2
    if gpu is not None:
        return gpu.crop(gpu.upload(np.asarray(image)), (x0, y0, x1, y1), width, height, mode='bicubic')
    if x0 >= -1e-6 and y0 >= -1e-6 and x1 <= sw + 1e-6 and y1 <= sh + 1e-6:
        return image.resize((width, height), Image.BICUBIC,
                            box=(max(0.0, x0), max(0.0, y0), min(sw, x1), min(sh, y1)), reducing_gap=2.0)
    # letterboxed clips (fit smaller than the frame): output pixel -> sequence pixel -> source pixel
    a = 1 / (p * s)
    c = (0.5 / p - seq.width / 2 - cx) / s + sw / 2 - .5
    e = 1 / (p * s)
    f = (0.5 / p - seq.height / 2 - cy) / s + sh / 2 - .5
    return image.transform((width, height), Image.AFFINE, (a, 0, c, 0, e, f), resample=Image.BILINEAR)
