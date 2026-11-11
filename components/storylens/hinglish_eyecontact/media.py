"""The video side of Eye Contact.

NVIDIA's app reads a file with OpenCV (it ignores phone rotation, drops audio and writes plain CFR video),
so we feed it clean chunks and rebuild the result ourselves:
source --decode, upright, 8-bit--> chunk.mp4 (near-lossless) --NVIDIA--> chunk.avi (MJPG)
       --encode with the SOURCE's own frame timestamps--> video.mp4 --+ original audio + timecode--> final.
Frame i of every step is frame i of the source, so the timing, sync and length never change."""
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
import heapq
import shutil

import av
import numpy as np

COPYABLE_AUDIO_MP4 = {'aac', 'mp3', 'ac3', 'eac3', 'alac', 'opus', 'flac'}
MJPEG_BYTES_PER_PIXEL = .14       # NVIDIA writes MJPG at OpenCV's quality 95 (~280 KB per 1080p frame)
CHUNK_BYTES = 3.0e9               # keep every intermediate AVI under OpenCV's 4 GB limit
MIN_CHUNK_SECONDS = 60.0
CUT_MARGIN = .5                   # seconds kept clear of the edit's used ranges at a chunk boundary
_ENCODERS = {}


@dataclass
class VideoInfo:
    path: str
    width: int                    # upright size (after any phone rotation)
    height: int
    rate: Fraction
    time_base: Fraction
    duration: float
    rotation: int                 # degrees clockwise needed to show it upright (0 / 90 / 180 / 270)
    pix_fmt: str
    codec: str
    audio: list = field(default_factory=list)
    timecode: str = ''
    hdr: bool = False

    @property
    def frames(self):
        return max(1, round(self.duration * float(self.rate)))

    @property
    def container_suffix(self):
        return '.mp4' if all(a in COPYABLE_AUDIO_MP4 for a in self.audio) else '.mov'


def upright_turn(frame):
    """ffmpeg's autorotate rule: theta = -display_rotation; 90 = turn clockwise."""
    try:
        return int(round(-(frame.rotation or 0))) % 360
    except Exception:
        return 0


def probe(path):
    path = Path(path)
    with av.open(str(path)) as c:
        if not c.streams.video:
            raise ValueError(f'{path.name} has no video')
        v = c.streams.video[0]
        rate = Fraction(v.average_rate or v.guessed_rate or 30)
        duration = float(v.duration * v.time_base) if v.duration else (c.duration / 1e6 if c.duration else 0.0)
        first = next(c.decode(v), None)
        turn = upright_turn(first) if first is not None else 0
        width, height = v.codec_context.width, v.codec_context.height
        if turn in (90, 270):
            width, height = height, width
        trc = str(getattr(first, 'color_trc', '') or '') if first is not None else ''
        timecode = v.metadata.get('timecode') or c.metadata.get('timecode') or ''
        return VideoInfo(str(path), width, height, rate, Fraction(v.time_base), duration, turn,
                         v.codec_context.format.name if v.codec_context.format else '', v.codec_context.name,
                         [a.codec_context.name for a in c.streams.audio], timecode,
                         hdr=trc in ('16', '18') or 'SMPTE2084' in trc.upper() or 'HLG' in trc.upper())


def chunk_frames(info):
    per = int(CHUNK_BYTES / max(1.0, info.width * info.height * MJPEG_BYTES_PER_PIXEL))
    return max(int(MIN_CHUNK_SECONDS * float(info.rate)), per)


def _upright(frame, turn):
    """yuv420p frame -> the same picture turned upright, still yuv420p (no colour conversion)."""
    if not turn:
        return frame
    k = {90: -1, 180: 2, 270: 1}[turn]
    h, w = frame.height, frame.width
    data = frame.to_ndarray()                      # yuv420p layout: Y rows, then U, then V packed
    y = data[:h]
    u = data[h:h + h // 4].reshape(h // 2, w // 2)
    v = data[h + h // 4:h + h // 2].reshape(h // 2, w // 2)
    y, u, v = (np.rot90(p, k) for p in (y, u, v))
    packed = np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(y.shape[0] * 3 // 2, y.shape[1])
    return av.VideoFrame.from_ndarray(np.ascontiguousarray(packed), format='yuv420p')


def _full_range(frame):
    try:
        return int(frame.color_range) == 2           # AVCOL_RANGE_JPEG
    except (TypeError, ValueError):
        return 'JPEG' in str(frame.color_range).upper()


def _to_tv_range(frame):
    h = frame.height
    data = frame.to_ndarray().astype(np.float32)
    data[:h] = 16 + data[:h] * (219 / 255)
    data[h:] = 128 + (data[h:] - 128) * (224 / 255)
    return av.VideoFrame.from_ndarray(np.clip(np.rint(data), 0, 255).astype(np.uint8), format='yuv420p')


def tv_yuv420p(frame):
    """Any decoded frame -> 8-bit TV-range yuv420p. PyAV's reformat changes bit depth and chroma layout but
    NOT the range when leaving full-range YUV (yuvj / JPEG-range frames keep their values), so we do it."""
    full = frame.format.name.startswith('yuvj') or _full_range(frame)
    pic = frame.reformat(format='yuv420p')
    return _to_tv_range(pic) if full else pic


def source_frames(info):
    """Every frame of the source in presentation order: (upright 8-bit yuv420p frame, pts, seconds)."""
    with av.open(info.path) as c:
        v = c.streams.video[0]
        v.thread_type = 'AUTO'
        for frame in c.decode(v):
            if frame.pts is None:
                continue
            pic = _upright(tv_yuv420p(frame), info.rotation)
            copy_colour(frame, pic)
            yield pic, frame.pts, float(frame.pts * frame.time_base)


TV_RANGE = 1   # AVCOL_RANGE_MPEG: every frame we write is standard limited-range yuv420p


def copy_colour(src, dst):
    """Keep the source's colour tags (primaries / transfer / matrix); the range is always TV range."""
    for name in ('color_primaries', 'color_trc', 'colorspace'):
        try:
            setattr(dst, name, getattr(src, name))
        except Exception:
            pass
    try:
        dst.color_range = TV_RANGE
    except Exception:
        pass


def tag_encoder(stream, frame):
    copy_colour(frame, stream.codec_context)


def encoder_name(preferred=None):
    """The first H.264 encoder that actually opens on this PC (NVENC on NVIDIA GPUs)."""
    if preferred is None:
        from hinglish_cut.model_preferences import preferences
        only_gpu=preferences(Path(__file__).resolve().parents[1]).get('heavy_workloads_gpu_only',False)
        preferred=('h264_nvenc',) if only_gpu else ('h264_nvenc','libx264')
    key = tuple(preferred)
    if key not in _ENCODERS:
        for name in preferred:
            try:
                cc = av.codec.CodecContext.create(name, 'w')
                cc.width, cc.height, cc.pix_fmt, cc.time_base = 256, 256, 'yuv420p', Fraction(1, 30)
                cc.open()
                _ENCODERS[key] = name
                break
            except Exception:
                continue
    if key not in _ENCODERS:
        raise RuntimeError('The selected video encoder could not start. Wait for the GPU queue and retry; no CPU fallback was started.')
    return _ENCODERS[key]


def _video_stream(container, info, rate, time_base, quality, near_lossless=False):
    name = encoder_name()
    stream = container.add_stream(name, rate=rate)
    stream.width, stream.height, stream.pix_fmt = info.width, info.height, 'yuv420p'
    stream.codec_context.time_base = time_base
    stream.time_base = time_base
    if name == 'h264_nvenc':
        stream.options = ({'preset': 'p4', 'rc': 'constqp', 'qp': '12'} if near_lossless else
                          {'preset': 'p6', 'tune': 'hq', 'rc': 'vbr', 'cq': str(quality), 'b': '0',
                           'spatial-aq': '1', 'profile': 'high', 'bf': '3'})
    else:
        stream.options = ({'crf': '10', 'preset': 'veryfast'} if near_lossless else
                          {'crf': str(quality), 'preset': 'medium', 'profile': 'high'})
    return stream


class ChunkInput:
    """A clean CFR H.264 file of consecutive source frames for NVIDIA's app to read."""

    def __init__(self, path, info):
        self.path = Path(path)
        self.info = info
        self.pts, self.seconds = [], []
        self.container = av.open(str(self.path), 'w')
        self.stream = _video_stream(self.container, info, info.rate, 1 / info.rate, 12, near_lossless=True)
        self.colour_done = False

    def add(self, frame, pts, seconds):
        if not self.colour_done:
            tag_encoder(self.stream, frame)
            self.colour_done = True
        frame.pts, frame.time_base = len(self.pts), 1 / self.info.rate
        self.container.mux(self.stream.encode(frame))
        self.pts.append(pts)
        self.seconds.append(seconds)

    def close(self):
        self.container.mux(self.stream.encode(None))
        self.container.close()


def plan_boundary(chunk, per_chunk, seconds, used):
    """Close the chunk here? At its size limit, or earlier at a moment the edit does not use."""
    n = len(chunk.pts)
    if n >= per_chunk:
        return True
    if n < .6 * per_chunk or not used:
        return False
    return not any(a - CUT_MARGIN <= seconds <= b + CUT_MARGIN for a, b in used)


class FinalVideo:
    """Encodes NVIDIA's frames with the source's own timestamps (video only; audio is added later)."""

    def __init__(self, path, info, quality):
        self.path = Path(path)
        self.info = info
        self.container = av.open(str(self.path), 'w')
        self.stream = _video_stream(self.container, info, info.rate, info.time_base, quality)
        self.frames = self.fixed = 0
        self.colour_done = False

    def append(self, corrected_avi, chunk):
        """Frame i of NVIDIA's output = frame i of the chunk; any frames it missed keep the original."""
        with av.open(str(corrected_avi)) as fixed, av.open(str(chunk.path)) as plain:
            fixed_frames = fixed.decode(fixed.streams.video[0])
            plain_frames = plain.decode(plain.streams.video[0])
            for i, pts in enumerate(chunk.pts):
                original = next(plain_frames, None)
                frame = next(fixed_frames, None) if fixed_frames is not None else None
                if frame is not None and (frame.width, frame.height) != (self.info.width, self.info.height):
                    raise RuntimeError(f'NVIDIA returned {frame.width}x{frame.height} frames, expected '
                                       f'{self.info.width}x{self.info.height} (split-screen view must be off)')
                if frame is None:
                    fixed_frames = None
                    frame = original
                else:
                    self.fixed += 1
                if frame is None:
                    break
                pic = tv_yuv420p(frame)                  # NVIDIA's MJPG frames are full-range YUV
                if original is not None:
                    copy_colour(original, pic)
                    if not self.colour_done:
                        tag_encoder(self.stream, original)
                        self.colour_done = True
                pic.pts, pic.time_base = pts, self.info.time_base
                self.container.mux(self.stream.encode(pic))
                self.frames += 1

    def close(self):
        self.container.mux(self.stream.encode(None))
        self.container.close()


def _packets(container, stream, out_stream):
    for packet in container.demux(stream):
        if packet.dts is None and packet.pts is None:
            continue
        t = packet.dts if packet.dts is not None else packet.pts
        packet.stream = out_stream
        yield float(t * stream.time_base), id(out_stream), packet


def add_original_audio(video_only, source, target, timecode=''):
    """Final file = our corrected video + the source's audio streams copied untouched (same clock)."""
    target = Path(target)
    with av.open(str(video_only)) as v, av.open(str(source)) as s, av.open(str(target), 'w') as out:
        vs = v.streams.video[0]
        ov = out.add_stream_from_template(vs)
        if timecode:
            ov.metadata['timecode'] = timecode
            out.metadata['timecode'] = timecode
        feeds = [_packets(v, vs, ov)]
        for a in s.streams.audio:
            feeds.append(_packets(s, a, out.add_stream_from_template(a)))
        for _, _, packet in heapq.merge(*feeds, key=lambda item: (item[0], item[1])):
            out.mux(packet)
    return target


def simulate_engine(source, target, frames, progress=print, label=''):
    """Developer stand-in for NVIDIA's app (no RTX here): the same MJPG AVI output, eyes unchanged."""
    with av.open(str(source)) as c, av.open(str(target), 'w', format='avi') as out:
        v = c.streams.video[0]
        rate = Fraction(v.average_rate or 30)
        stream = out.add_stream('mjpeg', rate=rate)
        stream.width, stream.height, stream.pix_fmt = v.codec_context.width, v.codec_context.height, 'yuvj420p'
        stream.bit_rate = int(stream.width * stream.height * float(rate) * 2)
        for n, frame in enumerate(c.decode(v)):
            pic = frame.reformat(format='yuvj420p')
            pic.pts, pic.time_base = n, 1 / rate
            out.mux(stream.encode(pic))
        out.mux(stream.encode(None))
    progress(f'  (simulated) eye contact {label}{frames} frames')
    return Path(target)


def _frames_from(path, start, rotation=0):
    with av.open(str(path)) as c:
        v = c.streams.video[0]
        v.thread_type = 'AUTO'
        c.seek(int(start / v.time_base), stream=v, backward=True, any_frame=False)
        for frame in c.decode(v):
            if frame.pts is None or float(frame.pts * frame.time_base) < start - 1e-3:
                continue
            yield _upright(tv_yuv420p(frame), rotation)


def side_by_side(info, fixed_path, start, seconds, target, height=960):
    """Before | after clip of the same moment (video only), for the results page."""
    h = min(height, info.height) // 2 * 2
    w = int(info.width * h / info.height) // 2 * 2
    frames = int(seconds * float(info.rate))
    with av.open(str(target), 'w') as out:
        stream = out.add_stream(encoder_name(), rate=info.rate)
        stream.width, stream.height, stream.pix_fmt = 2 * w, h, 'yuv420p'
        stream.options = {'cq': '21', 'rc': 'vbr', 'b': '0'} if stream.codec_context.name == 'h264_nvenc' else {'crf': '21'}
        pairs = zip(_frames_from(info.path, start, info.rotation), _frames_from(fixed_path, start))
        for n, (a, b) in enumerate(pairs):
            if n >= frames:
                break
            row = np.hstack([x.reformat(width=w, height=h, format='rgb24').to_ndarray() for x in (a, b)])
            pic = av.VideoFrame.from_ndarray(row, format='rgb24').reformat(format='yuv420p')
            pic.pts, pic.time_base = n, 1 / info.rate
            out.mux(stream.encode(pic))
        out.mux(stream.encode(None))
    return Path(target)


def free_bytes(folder):
    return shutil.disk_usage(Path(folder)).free
