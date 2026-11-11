"""Stream a source into a cleaned MP4 using the same frame ranges as the XML."""
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path
import time
from hinglish_cut.gpu_frames import with_cuda_frames


@with_cuda_frames
def render_mp4(media, cuts, destination, canvas=None, progress=print, *, device='cpu', _gpu=None):
    import av
    import numpy as np

    destination = Path(destination)
    partial = destination.with_name(destination.stem + '.partial.mp4')
    fps = media.rate
    width, height = canvas or (media.width, media.height)
    if width % 2 or height % 2:
        raise ValueError('MP4 output requires even image dimensions')
    starts = [c.start_frame for c in cuts]
    offsets = []
    total = 0
    for c in cuts:
        offsets.append(total)
        total += c.duration
    sr = 48000
    audio_ranges = [(round(Fraction(c.start_frame * sr) / fps),
                     round(Fraction(c.end_frame * sr) / fps)) for c in cuts]
    # Cumulative rounding prevents drift over thousands of NTSC cuts.
    audio_offsets = [round(Fraction(n * sr) / fps) for n in offsets]
    audio_lengths = [round(Fraction((offsets[i] + c.duration) * sr) / fps) - audio_offsets[i]
                     for i, c in enumerate(cuts)]
    audio_ends = [b for a, b in audio_ranges]
    target_samples = round(Fraction(total * sr) / fps)
    video_count = 0
    audio_written = 0
    last_update = time.monotonic()
    with av.open(media.path) as source, av.open(str(partial), 'w', options={'movflags': '+faststart'}) as out:
        sv, sa = source.streams.video[0], source.streams.audio[0]
        sv.thread_type = 'AUTO'
        sv.codec_context.thread_count = 4
        from hinglish_cut.compute_policy import h264_profile
        codec, options = h264_profile(device, 18)
        video = out.add_stream(codec, rate=fps)
        video.width, video.height = width, height
        video.pix_fmt = 'yuv420p'
        video.options = options
        video.codec_context.thread_count = 4
        audio = out.add_stream('aac', rate=sr)
        audio.layout = 'mono' if media.channels == 1 else 'stereo'
        audio.bit_rate = 192000
        channels = len(audio.layout.channels)
        resampler = av.AudioResampler(format='fltp', layout=audio.layout.name, rate=sr)
        audio_source_position = 0

        def encode_audio(samples):
            nonlocal audio_written
            if samples.shape[1] == 0:
                return
            frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(samples), format='fltp', layout=audio.layout.name)
            frame.sample_rate = sr
            frame.time_base = Fraction(1, sr)
            frame.pts = audio_written
            audio_written += frame.samples
            for packet in audio.encode(frame):
                out.mux(packet)

        def pad_audio(target):
            while audio_written < target:
                encode_audio(np.zeros((channels, min(4096, target - audio_written)), dtype=np.float32))

        def process_audio(frame):
            nonlocal audio_source_position
            data = frame.to_ndarray()
            start = (round((float(frame.pts * frame.time_base) - media.video_start) * sr)
                     if frame.pts is not None else audio_source_position)
            end = start + frame.samples
            audio_source_position = end
            index = bisect_right(audio_ends, start)
            while index < len(cuts) and audio_ranges[index][0] < end:
                a, b = audio_ranges[index]
                lo, hi = max(a, start), min(b, end, a + audio_lengths[index])
                dest_start = audio_offsets[index] + lo - a
                lo += max(0, audio_written - dest_start)
                dest_start = max(dest_start, audio_written)
                if hi > lo:
                    pad_audio(dest_start)
                    samples = data[:, lo - start:hi - start].copy()
                    # Five millisecond ramps at edits reduce waveform clicks.
                    position = np.arange(lo - a, hi - a)
                    fade = 240
                    ramp = np.minimum(1.0, np.minimum(position / fade,
                                      (audio_lengths[index] - 1 - position) / fade)).clip(0, 1)
                    samples *= ramp.astype(np.float32)
                    encode_audio(samples)
                index += 1

        scale = min(width / media.width, height / media.height)
        fitted_w = max(2, min(width, int(media.width * scale) // 2 * 2))
        fitted_h = max(2, min(height, int(media.height * scale) // 2 * 2))
        for packet in source.demux(sv, sa):
            for frame in packet.decode():
                if isinstance(frame, av.VideoFrame):
                    if frame.pts is None:
                        raise ValueError('Video frame has no timestamp')
                    number = round((float(frame.pts * frame.time_base) - media.video_start) * float(fps))
                    index = bisect_right(starts, number) - 1
                    if index < 0 or number >= cuts[index].end_frame:
                        continue
                    output_number = offsets[index] + number - cuts[index].start_frame
                    if output_number != video_count:
                        raise ValueError('Source frame timing changed; refusing an out-of-sync render')
                    if _gpu is not None:
                        image = _gpu.resize(_gpu.upload(frame.to_ndarray(format='rgb24')), fitted_w, fitted_h, 'bicubic')
                        canvas_gpu = _gpu.blank(width, height)
                        x, y = (width-fitted_w)//2, (height-fitted_h)//2
                        canvas_gpu[..., y:y+fitted_h, x:x+fitted_w] = image
                        converted = _gpu.video_frame(canvas_gpu)
                    elif (fitted_w, fitted_h) == (width, height):
                        converted = frame.reformat(width=width, height=height, format='yuv420p')
                    else:
                        pixels = np.zeros((height, width, 3), dtype=np.uint8)
                        resized = frame.reformat(width=fitted_w, height=fitted_h, format='rgb24').to_ndarray()
                        x, y = (width - fitted_w) // 2, (height - fitted_h) // 2
                        pixels[y:y + fitted_h, x:x + fitted_w] = resized
                        converted = av.VideoFrame.from_ndarray(pixels, format='rgb24').reformat(format='yuv420p')
                    converted.pts = output_number
                    converted.time_base = 1 / fps
                    for encoded in video.encode(converted):
                        out.mux(encoded)
                    video_count += 1
                else:
                    for converted in resampler.resample(frame):
                        process_audio(converted)
            if time.monotonic() - last_update > 8:
                progress(f'  Saving MP4: {100 * video_count / total:.0f}%')
                last_update = time.monotonic()
        for converted in resampler.resample(None):
            process_audio(converted)
        pad_audio(target_samples)
        if video_count != total or audio_written != target_samples:
            raise ValueError('Rendered duration does not match the edit plan')
        for encoded in video.encode():
            out.mux(encoded)
        for encoded in audio.encode():
            out.mux(encoded)
    with av.open(str(partial)) as check:
        if check.streams.video[0].frames != total or not check.streams.audio:
            raise ValueError('Export verification failed')
    partial.replace(destination)
    return {'video_frames': video_count, 'audio_samples': audio_written, 'sample_rate': sr}
