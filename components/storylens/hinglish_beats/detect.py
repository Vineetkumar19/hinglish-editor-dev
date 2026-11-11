"""Streaming onset analysis: no cloud, model weights or GPU required.

Markers describe audible transient candidates, not a claim of perfect musical
downbeat recognition. Never invent an evenly spaced grid over silence.
"""
from pathlib import Path
import math
import numpy as np
import wave

RATE = 16000
HOP = 160
WINDOW = 512
EXTENSIONS = {'.wav', '.mp3', '.flac', '.m4a', '.aac', '.ogg', '.aif', '.aiff', '.mp4', '.mov'}


def number(value, name, low, high):
    if isinstance(value, bool):
        raise ValueError('Invalid ' + name)
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError('Invalid ' + name) from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}')
    return value


def features(path, source_in=0., source_out=None):
    """Decode incrementally. Memory is proportional to onset count, not PCM length."""
    import av
    path = Path(path).resolve()
    if not path.exists():raise FileNotFoundError('The selected music file is missing: '+str(path))
    if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
        raise ValueError('Choose a supported local music file, such as WAV, MP3 or M4A.')
    pending = np.empty(0, dtype=np.float32)
    previous = np.zeros(WINDOW // 2 + 1)
    flux, energy, attacks = [], [], []
    start = round(source_in * RATE)
    stop = round(source_out * RATE) if source_out is not None else start + RATE * 3600
    position = 0
    window = np.hanning(WINDOW)
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise ValueError('This file has no audio stream')
        if len(container.streams.audio) != 1:
            raise ValueError('Choose a music file with one audio stream')
        resampler = av.AudioResampler(format='fltp', layout='mono', rate=RATE)

        def consume(frame):
            nonlocal position, pending, previous
            data = frame.to_ndarray().reshape(-1)
            left, right = max(0, start - position), min(len(data), stop - position)
            position += len(data)
            if right <= left:
                return
            pending = np.concatenate((pending, data[left:right]))
            count = max(0, (len(pending) - WINDOW) // HOP + 1)
            for index in range(count):
                block = pending[index * HOP:index * HOP + WINDOW]
                spectrum = np.abs(np.fft.rfft(block * window))
                # Compressed magnitudes keep a cymbal from drowning out a kick.
                compressed = np.log1p(10 * spectrum)
                flux.append(float(np.maximum(compressed - previous, 0).mean()))
                energy.append(float(np.sqrt(np.mean(block * block))))
                attacks.append(float(np.sqrt(np.mean(block[:HOP] * block[:HOP]))))
                previous = compressed
            pending = pending[count * HOP:]

        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                consume(converted)
            if position >= stop:
                break
        else:
            for converted in resampler.resample(None):
                consume(converted)
    duration = max(0., (min(position, stop) - start) / RATE)
    if duration >= 3599.9 and source_out is None:
        raise ValueError('Select a music segment shorter than one hour')
    if source_out is not None and duration + .05 < source_out - source_in:
        raise ValueError('The selected music range extends beyond the source file')
    return np.asarray(flux), np.asarray(energy), np.asarray(attacks), duration


def features_cuda_wav(path, source_in=0., source_out=None):
    """Compute onset spectra in bounded CUDA batches for 16 kHz PCM analysis audio.

    WAV reads and the final small candidate list stay on CPU; the FFT, magnitude,
    spectral flux and RMS calculations run on the GPU. Reel Recreate already
    writes this exact analysis format, so no second compressed-audio decode is
    needed here.
    """
    import torch
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError('The selected music file is missing: ' + str(path))
    if not torch.cuda.is_available():
        raise RuntimeError('NVIDIA CUDA is unavailable for Reel Recreate beat analysis.')
    try:
        (torch.ones((2, 2), device='cuda') @ torch.ones((2, 2), device='cuda')).sum().item()
    except RuntimeError as error:
        raise RuntimeError('The NVIDIA CUDA kernel could not run Reel Recreate beat analysis.') from error
    start = round(source_in * RATE)
    requested_stop = round(source_out * RATE) if source_out is not None else start + RATE * 3600
    flux, energy, attacks = [], [], []
    pending = np.empty(0, dtype=np.float32)
    previous = torch.zeros(WINDOW // 2 + 1, device='cuda')
    window = torch.from_numpy(np.hanning(WINDOW).astype(np.float32)).to('cuda')
    with wave.open(str(path), 'rb') as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth(), audio.getcomptype()) != (RATE, 1, 2, 'NONE'):
            raise ValueError('GPU beat analysis needs the saved 16 kHz mono PCM soundtrack.')
        available = audio.getnframes()
        audio.setpos(min(start, available))
        remaining = max(0, min(requested_stop, available) - start)
        read = 0
        while read < remaining:
            raw = audio.readframes(min(HOP * 4096, remaining - read))
            if not raw:
                break
            data = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
            read += len(data)
            pending = np.concatenate((pending, data))
            count = max(0, (len(pending) - WINDOW) // HOP + 1)
            if not count:
                continue
            samples = torch.from_numpy(pending).to('cuda')
            blocks = samples.unfold(0, WINDOW, HOP)[:count]
            compressed = torch.log1p(10 * torch.abs(torch.fft.rfft(blocks * window, dim=1)))
            prior = torch.cat((previous[None, :], compressed[:-1]), dim=0)
            flux.extend(torch.clamp_min(compressed - prior, 0).mean(dim=1).cpu().numpy())
            energy.extend(torch.sqrt(torch.mean(blocks * blocks, dim=1)).cpu().numpy())
            attack_blocks = blocks[:, :HOP]
            attacks.extend(torch.sqrt(torch.mean(attack_blocks * attack_blocks, dim=1)).cpu().numpy())
            previous = compressed[-1].detach()
            pending = pending[count * HOP:]
    duration = read / RATE
    if duration >= 3599.9 and source_out is None:
        raise ValueError('Select a music segment shorter than one hour')
    if source_out is not None and duration + .05 < source_out - source_in:
        raise ValueError('The selected music range extends beyond the source file')
    return np.asarray(flux), np.asarray(energy), np.asarray(attacks), duration


def candidates(flux, energy, attacks, device='cpu'):
    if len(flux) < 3 or np.max(energy, initial=0) < .0001:
        return []
    if device == 'cuda':
        import torch
        import torch.nn.functional as functional
        gpu_flux = torch.as_tensor(flux, device='cuda')
        gpu_energy = torch.as_tensor(energy, device='cuda')
        padded = functional.pad(gpu_flux[None, None, :], (50, 50), mode='replicate')
        local = functional.avg_pool1d(padded, 101, stride=1).reshape(-1)
        threshold = local * 1.35 + max(float(np.max(flux)) * .025, .00001)
        indices = torch.nonzero((gpu_flux > threshold) & (gpu_energy > .0001)).reshape(-1).cpu().numpy()
    else:
        local = np.convolve(np.pad(flux, (50, 50), mode='edge'), np.ones(101) / 101, mode='valid')
        threshold = local * 1.35 + max(float(np.max(flux)) * .025, .00001)
        indices = np.flatnonzero((flux > threshold) & (energy > .0001))
    # Strongest-first nonmaximum suppression merges a drum's attack into one marker.
    kept = []
    occupied = np.zeros(len(flux), dtype=bool)
    for index in sorted(indices, key=lambda i: (-flux[i], i)):
        if not occupied[index]:
            kept.append(int(index))
            occupied[max(0, index - 18):index + 19] = True
    maximum = float(np.max(flux))
    # FFT windows anticipate an attack. Refine with non-overlapping 10 ms RMS
    # hops so the marker lands at the sound, not at the FFT window's beginning.
    rise = np.diff(attacks, prepend=0)
    result = []
    for index in sorted(kept):
        begin, end = max(0, index - 2), min(len(rise), index + WINDOW // HOP + 2)
        attack = begin + int(np.argmax(rise[begin:end]))
        result.append({'seconds': round(max(0., attack * HOP / RATE), 6),
                       'strength': round(float(flux[index]) / maximum, 6)})
    return result


def thin(beats, count):
    """Keep real attacks, spread through the song; no synthetic extra markers."""
    if count >= len(beats):
        return list(beats)
    if count <= 0:
        return []
    # Equal groups preserve coverage; strongest attack in each group wins.
    return [max(group, key=lambda b: b['strength']) for group in
            (beats[i * len(beats) // count:(i + 1) * len(beats) // count] for i in range(count))]


def features_cuda_media(path, source_in=0., source_out=None):
    """Decode compressed music on CPU; keep FFT/onset work on CUDA in bounded blocks."""
    import subprocess
    from tempfile import TemporaryDirectory
    from imageio_ffmpeg import get_ffmpeg_exe
    try:
        with wave.open(str(path),'rb') as audio:
            compatible=(audio.getframerate(),audio.getnchannels(),audio.getsampwidth(),audio.getcomptype())==(RATE,1,2,'NONE')
    except (wave.Error,EOFError):compatible=False
    if compatible:return features_cuda_wav(path,source_in,source_out)
    with TemporaryDirectory(prefix='storylens-beat-') as folder:
        target=Path(folder)/'analysis.wav'
        duration=source_out-source_in if source_out is not None else 3600
        result=subprocess.run([get_ffmpeg_exe(),'-nostdin','-hide_banner','-loglevel','error','-y',
            '-ss',str(source_in),'-i',str(path),'-t',str(duration),'-vn','-ac','1','-ar',str(RATE),'-c:a','pcm_s16le',str(target)],
            capture_output=True,timeout=600,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:raise ValueError('The music could not be prepared for GPU beat analysis: '+result.stderr.decode('utf-8',errors='replace')[-1000:])
        return features_cuda_wav(target,0,duration if source_out is not None else None)


def analyze(payload):
    source_in = number(payload.get('source_in', 0), 'Music in point', 0, 86400)
    source_out = payload.get('source_out')
    if source_out is not None:
        source_out = number(source_out, 'Music out point', source_in + .1, source_in + 3600)
    start = number(payload.get('timeline_start', 0), 'Timeline placement', 0, 86400)
    speed = number(payload.get('speed', 1), 'Music speed', .1, 10)
    fps = number(payload.get('fps', 30), 'Timeline frame rate', 1, 240)
    density = payload.get('density', 'medium')
    if density not in ('light', 'medium', 'strong'):
        raise ValueError('Choose Light, Medium or Strong beat density')
    target = payload.get('target_count')
    if target not in (None, ''):
        parsed = number(target, 'Maximum markers', 1, 10000)
        if parsed != int(parsed):
            raise ValueError('Maximum markers must be a whole number')
        target = int(parsed)
    path = Path(payload['path']).resolve()
    device = payload.get('device', 'cpu')
    if device not in ('cpu', 'cuda'):
        raise ValueError('Choose CPU or NVIDIA CUDA beat analysis')
    flux, energy, attacks, duration = (features_cuda_media if device == 'cuda' else features)(path, source_in, source_out)
    strong = candidates(flux, energy, attacks, device)
    medium = thin(strong, max(1, round(len(strong) * .5))) if strong else []
    light = thin(medium, max(1, round(len(strong) * .2))) if strong else []
    choices = {'light': light, 'medium': medium, 'strong': strong}
    beats = thin(choices[density], target) if target else choices[density]
    mapped = {}
    for beat in beats:
        frame = int(math.floor((start + beat['seconds'] / speed) * fps + .5))
        if frame / fps >= start + duration / speed:
            continue
        candidate = {**beat, 'source_seconds': source_in + beat['seconds'], 'frame': frame,
                     'timeline_seconds': frame / fps}
        if frame not in mapped or candidate['strength'] > mapped[frame]['strength']:
            mapped[frame] = candidate
    return {'version': 1, 'path': str(path), 'source_in': source_in,
            'source_out': source_in + duration, 'timeline_start': start, 'speed': speed,
            'fps': fps, 'duration': duration / speed, 'density': density,
            'sequence_id': str(payload.get('sequence_id', ''))[:200],
            'counts': {k: len(v) for k, v in choices.items()},
            'beats': sorted(mapped.values(), key=lambda b: b['frame']),
            'notice': 'Audible attack detection. Review syncopation and quiet passages by ear. No clips are cut.'}


def effect_plan(plan, payload):
    style = payload.get('style', 'punch')
    if style not in ('punch', 'smooth'):
        raise ValueError('Choose Punch zoom or Smooth zoom')
    amount = number(payload.get('amount', 8), 'Zoom amount (%)', 1, 20)
    duration = number(payload.get('duration', .24), 'Pulse duration', .08, 1)
    track = number(payload.get('video_track', 1), 'Video track for effects', 1, 99)
    if track != int(track): raise ValueError('Video track must be a whole number')
    return {'version': 1, 'sequence_id': plan['sequence_id'], 'fps': plan['fps'],
            'analysis_id': plan['id'], 'style': style, 'amount': amount,
            'duration': duration, 'video_track': int(track), 'beats': plan['beats']}
