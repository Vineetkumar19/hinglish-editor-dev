"""Audio-only visual-search review: replace the existing edit with black, keep its speech."""
from fractions import Fraction
from pathlib import Path

import av
import numpy as np


def black_timeline(timeline, folder, progress=print):
    from hinglish_zoom.preview import _audio_track, SAMPLE_RATE
    from hinglish_cut.model import Cut, Media
    from hinglish_cut.xml_export import export_xml
    from hinglish_broll.timeline import parse_xmeml
    folder = Path(folder)
    video_path = folder / 'audio-on-black.mp4'
    progress('Keeping the original audio and replacing the existing pictures with black')
    count = round(timeline.duration * timeline.fps)
    audio = _audio_track(timeline.xml_path, count / float(timeline.fps))
    # Low-resolution black needs no detailed pixels; the sequence keeps the same aspect ratio.
    factor = min(1, 720 / max(timeline.width, timeline.height))
    width, height = [max(2, round(v * factor / 2) * 2) for v in (timeline.width, timeline.height)]
    partial = video_path.with_suffix('.partial.mp4')
    with av.open(str(partial), 'w', options={'movflags': '+faststart'}) as out:
        video = out.add_stream('libx264', rate=timeline.fps)
        video.width, video.height, video.pix_fmt = width, height, 'yuv420p'
        video.options = {'crf': '20', 'preset': 'veryfast'}
        sound = out.add_stream('aac', rate=SAMPLE_RATE)
        sound.layout, sound.bit_rate = 'mono', 192000
        pixels = np.zeros((height, width, 3), np.uint8)
        for index in range(count):
            frame = av.VideoFrame.from_ndarray(pixels, format='rgb24')
            frame.pts = index
            for packet in video.encode(frame):
                out.mux(packet)
        for packet in video.encode():
            out.mux(packet)
        pcm = (audio[:round(count / float(timeline.fps) * SAMPLE_RATE)] * 32767).astype(np.int16)
        for index in range(0, len(pcm), 1024):
            frame = av.AudioFrame.from_ndarray(pcm[index:index + 1024].reshape(1, -1), format='s16', layout='mono')
            frame.sample_rate, frame.time_base, frame.pts = SAMPLE_RATE, Fraction(1, SAMPLE_RATE), index
            for packet in sound.encode(frame):
                out.mux(packet)
        for packet in sound.encode():
            out.mux(packet)
    partial.replace(video_path)
    source = Media('audio-black', str(video_path.resolve()), count / float(timeline.fps),
                   str(timeline.fps), width, height, 1, SAMPLE_RATE)
    xml = folder / 'AUDIO_BLACK.xml'
    export_xml(xml, [Cut(source.id, 0, count, 0)], {source.id: source}, None)
    result = parse_xmeml(xml)
    result.name = timeline.name + ' · audio on black'
    return result
