"""Real Hindi speech with known inserted silences across analysis boundaries.

Run from the project root with the local Python. This is an integration check,
not a synthetic tone demonstration or a claim of semantic speech accuracy.
"""
from pathlib import Path
from fractions import Fraction
import json
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import av
import numpy as np
from hinglish_clean.detection import CleanSettings
from hinglish_clean.pipeline import clean_one
from hinglish_cut.media import extract_audio, probe, read_audio


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'validation' / 'phase1-speech-check'
    folder.mkdir(exist_ok=True)
    sample = root / 'validation' / 'provider-hindi-sample.wav'
    with av.open(str(sample)) as source:
        resampler = av.AudioResampler(format='fltp', layout='mono', rate=48000)
        chunks = [converted.to_ndarray().reshape(-1) for frame in source.decode(audio=0)
                  for converted in resampler.resample(frame)]
        chunks.extend(c.to_ndarray().reshape(-1) for c in resampler.resample(None))
    speech = np.concatenate(chunks)
    duration, sr, fps = 75, 48000, 25
    samples = np.zeros(duration * sr, dtype=np.float32)
    # One utterance crosses the 60-second analysis boundary.
    placements = [2, 12, 32, 58.5, 68]
    for start in placements:
        a = round(start * sr)
        samples[a:a + len(speech)] = speech
    video_path = folder / 'hindi-with-known-pauses.mp4'
    with av.open(str(video_path), 'w') as out:
        video = out.add_stream('libx264', rate=fps)
        video.width, video.height, video.pix_fmt = 160, 90, 'yuv420p'
        video.options = {'preset': 'ultrafast', 'crf': '18'}
        audio = out.add_stream('aac', rate=sr)
        audio.layout = 'mono'
        audio.bit_rate = 128000
        for i in range(duration * fps):
            # Brightness encodes source time to check actual frame selection.
            pixels = np.full((90, 160, 3), 20 + i % 200, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(pixels, format='rgb24')
            frame.pts, frame.time_base = i, Fraction(1, fps)
            for packet in video.encode(frame):
                out.mux(packet)
            start = i * (sr // fps)
            af = av.AudioFrame.from_ndarray(samples[None, start:start + sr // fps].copy(), format='fltp', layout='mono')
            af.sample_rate, af.pts, af.time_base = sr, start, Fraction(1, sr)
            for packet in audio.encode(af):
                out.mux(packet)
        for stream in (video, audio):
            for packet in stream.encode():
                out.mux(packet)
    from datetime import datetime
    output = folder / ('run-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    result = clean_one(video_path, root, output, CleanSettings())
    assert result['mp4_created'], result
    decisions = json.loads((output / 'edit-decisions.json').read_text())
    cuts = decisions['cuts']
    assert result['removed_seconds'] > 45, result
    # Every sentence occurrence must survive, including the boundary occurrence.
    for start in placements:
        assert any(c['start_frame'] / fps <= start + 1 and c['end_frame'] / fps >= start + 3 for c in cuts), (start, cuts)
    original = probe(video_path)
    cleaned = probe(output / 'cleaned.mp4')
    extract_audio(original, folder / 'original.wav')
    extract_audio(cleaned, folder / 'cleaned.wav')
    expected = np.concatenate([read_audio(folder / 'original.wav', c['start_frame'] / fps, c['end_frame'] / fps) for c in cuts])
    actual = read_audio(folder / 'cleaned.wav')
    assert len(expected) == len(actual), (len(expected), len(actual))
    correlation = float(np.corrcoef(expected, actual)[0, 1])
    assert correlation > .98, correlation
    source_numbers = [n for c in cuts for n in range(c['start_frame'], c['end_frame'])]
    with av.open(str(output / 'cleaned.mp4')) as encoded:
        means = [float(f.to_ndarray(format='rgb24').mean()) for f in encoded.decode(video=0)]
    # Two encodes can change flat-field RGB slightly.
    max_pixel_error = max(abs(mean - (20 + n % 200)) for mean, n in zip(means, source_numbers))
    assert len(means) == len(source_numbers)
    assert max_pixel_error < 10, max_pixel_error
    summary = {'source_seconds': duration, 'edited_seconds': cleaned.duration,
               'removed_seconds': result['removed_seconds'], 'utterances_preserved': len(placements),
               'audio_correlation': correlation, 'max_frame_brightness_error': max_pixel_error,
               'output': str(output)}
    (folder / 'validation.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
