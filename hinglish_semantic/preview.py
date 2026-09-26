"""Small playable preview of the exact XML edit, with bounded frame decoding."""
from fractions import Fraction
from pathlib import Path
import wave


def render_preview(cuts, media, audio_path, destination, canvas, progress=print):
    import av
    import numpy as np
    destination = Path(destination)
    partial = destination.with_suffix('.partial.mp4')
    fps = media[cuts[0].media_id].rate
    scale = min(960 / max(canvas), 1)
    width, height = (max(2, int(n * scale) // 2 * 2) for n in canvas)
    written, audio_written = 0, 0
    total = sum(c.duration for c in cuts)
    with av.open(str(partial), 'w', options={'movflags': '+faststart'}) as output, wave.open(str(audio_path), 'rb') as wav:
        sr = wav.getframerate()
        video = output.add_stream('libx264', rate=fps)
        video.width, video.height, video.pix_fmt = width, height, 'yuv420p'
        video.options = {'crf': '23', 'preset': 'fast'}
        video.codec_context.thread_count = 4
        audio = output.add_stream('aac', rate=sr)
        audio.layout, audio.bit_rate = 'mono', 96000

        def audio_to(target):
            nonlocal audio_written
            while audio_written < target:
                count = min(2048, target - audio_written)
                data = wav.readframes(count)
                array = np.frombuffer(data, dtype='<i2').copy()
                if len(array) < count: array = np.pad(array, (0, count - len(array)))
                frame = av.AudioFrame.from_ndarray(array.reshape(1, -1), format='s16', layout='mono')
                frame.sample_rate, frame.time_base, frame.pts = sr, Fraction(1, sr), audio_written
                for packet in audio.encode(frame): output.mux(packet)
                audio_written += count

        for i, cut in enumerate(cuts):
            m = media[cut.media_id]
            progress(f'Saving preview: clip {i + 1}/{len(cuts)}')
            start_count = written
            with av.open(m.path) as source:
                stream = source.streams.video[0]
                stream.thread_type = 'AUTO'
                stream.codec_context.thread_count = 4
                start = cut.start_frame / float(fps) + m.video_start
                source.seek(max(0, int(start / float(stream.time_base))), stream=stream, backward=True)
                fitted = min(width / m.width, height / m.height)
                fw, fh = max(2, int(m.width * fitted) // 2 * 2), max(2, int(m.height * fitted) // 2 * 2)
                for frame in source.decode(stream):
                    number = round((float(frame.pts * frame.time_base) - m.video_start) * float(fps))
                    if number < cut.start_frame: continue
                    if number >= cut.end_frame: break
                    if number != cut.start_frame + written - start_count:
                        raise ValueError('Preview source frame discontinuity')
                    if (fw, fh) == (width, height):
                        converted = frame.reformat(width=width, height=height, format='yuv420p')
                    else:
                        pixels = np.zeros((height, width, 3), dtype=np.uint8)
                        x, y = (width - fw) // 2, (height - fh) // 2
                        pixels[y:y + fh, x:x + fw] = frame.reformat(width=fw, height=fh, format='rgb24').to_ndarray()
                        converted = av.VideoFrame.from_ndarray(pixels, format='rgb24').reformat(format='yuv420p')
                    converted.pts, converted.time_base = written, 1 / fps
                    for packet in video.encode(converted): output.mux(packet)
                    written += 1
                    audio_to(round(written * sr / float(fps)))
            if written - start_count != cut.duration: raise ValueError('Preview clip is incomplete')
        for packet in video.encode(): output.mux(packet)
        for packet in audio.encode(): output.mux(packet)
    if written != total: raise ValueError('Preview duration differs from XML')
    partial.replace(destination)
    return {'frames': written, 'audio_samples': audio_written, 'width': width, 'height': height}
