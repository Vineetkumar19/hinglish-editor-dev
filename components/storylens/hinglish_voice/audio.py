"""Decode uploads and encode downloadable MP3 without a system FFmpeg install."""
from pathlib import Path
import wave

MAX_UPLOAD = 50 * 1024 * 1024


def reference(source, destination):
    import av
    import numpy as np
    frames = []
    samples = 0
    try:
        with av.open(str(source)) as container:
            if not container.streams.audio:
                raise ValueError('Voice sample: choose a recording with audible speech.')
            resampler = av.AudioResampler(format='s16', layout='mono', rate=24000)
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    samples += converted.samples
                    if samples > 21 * 24000:
                        raise ValueError('Voice sample: choose a clean 3–20 second recording. Trim longer recordings first.')
                    frames.append(converted.to_ndarray().tobytes())
            for converted in resampler.resample(None):
                samples += converted.samples
                frames.append(converted.to_ndarray().tobytes())
        duration = samples / 24000
        if not 3 <= duration <= 20:
            raise ValueError('Voice sample: choose a clean 3–20 second recording.')
        audio = b''.join(frames)
        if not audio or np.max(np.abs(np.frombuffer(audio, dtype=np.int16).astype(np.int32))) < 64:
            raise ValueError('Voice sample: this recording is silent. Choose clear speech without music.')
        with wave.open(str(destination), 'wb') as output:
            output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            output.writeframes(audio)
        return duration
    except ValueError:
        raise
    except Exception as error:
        raise ValueError('Voice sample: this file could not be decoded. Choose a playable WAV, MP3, M4A or video recording.') from error


def mp3(source, destination):
    import av
    # libmp3lame requires planar floats; resample every frame and flush both stages.
    with av.open(str(source)) as incoming, av.open(str(destination), 'w', format='mp3') as outgoing:
        stream = outgoing.add_stream('libmp3lame', rate=24000)
        stream.bit_rate = 192000
        stream.layout = 'mono'
        converter = av.AudioResampler(format='fltp', layout='mono', rate=24000)
        for frame in incoming.decode(audio=0):
            for converted in converter.resample(frame):
                for packet in stream.encode(converted): outgoing.mux(packet)
        for converted in converter.resample(None):
            for packet in stream.encode(converted): outgoing.mux(packet)
        for packet in stream.encode(None): outgoing.mux(packet)


def inspect_audio(path):
    import av
    import numpy as np
    count = 0
    peak = 0.
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            values = frame.to_ndarray()
            if not np.isfinite(values).all(): raise ValueError('Voiceover output: the generated audio contains invalid samples. Retry this script.')
            peak = max(peak, float(np.abs(values.astype(float)).max()))
            count += frame.samples / frame.sample_rate
    if count <= .1 or peak < .0001:
        raise ValueError('Voiceover output: no audible narration was generated. Keep your script and retry.')
    return round(count, 3)
