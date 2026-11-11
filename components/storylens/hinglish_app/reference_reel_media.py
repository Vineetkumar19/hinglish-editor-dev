"""Bounded media operations for Reference Reel."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys

import cv2
import numpy as np


def periodic_cues(onsets, fps):
    """Find a repeated pulse only where measured transients support the grid."""
    strong = [item for item in onsets if item['strength'] >= .18]
    if len(strong) < 7 or strong[-1]['seconds'] - strong[0]['seconds'] < 3:
        return None
    seconds = np.asarray([item['seconds'] for item in strong])
    trials = []
    for period in np.arange(.33, 1.001, .01):
        for origin in seconds[:3]:
            ticks = np.rint((seconds - origin) / period).astype(int)
            delta = np.abs(seconds - origin - ticks * period)
            hits = delta <= .035
            if hits.sum() < max(7, .8 * len(seconds)):
                continue
            selected = ticks[hits]
            occupancy = len(set(selected)) / (selected[-1] - selected[0] + 1)
            if occupancy < .75:
                continue
            trials.append((occupancy, hits.sum(), -float(np.median(delta[hits])), period, hits))
    if not trials:
        return None
    _, _, _, period, hits = max(trials, key=lambda trial: trial[:3])
    frames = sorted({item['frame'] for item, present in zip(strong, hits) if present})
    return {'status': 'periodic transient candidate', 'estimated_bpm': round(60 / period, 1),
            'frames': frames, 'seconds': [round(frame / fps, 6) for frame in frames],
            'scope': 'Measured transients on a regular pulse. Downbeats and musical meter need review.'}


def rgb(frame, width=None, height=None):
    """Decode the tagged YUV matrix and range to full-range RGB."""
    return frame.reformat(width=width, height=height, format='rgb24',
                          dst_color_range='JPEG', threads=2).to_ndarray()


def flow_pair(first, last):
    """Estimate bidirectional motion on a reduced grid. Reject cuts and bad matches."""
    height, width = first.shape[:2]
    scale = min(1., 448 / max(height, width))
    size = (max(8, round(width * scale)), max(8, round(height * scale)))
    a, b = (cv2.cvtColor(cv2.resize(image, size), cv2.COLOR_RGB2GRAY) for image in (first, last))
    histograms = [cv2.calcHist([im], [0], None, [32], [0, 256]) for im in (a, b)]
    if cv2.absdiff(a, b).mean() > 32 and cv2.compareHist(*histograms, cv2.HISTCMP_BHATTACHARYYA) > .44:
        return None
    forward, backward = (cv2.calcOpticalFlowFarneback(x, y, None, .5, 3, 17, 3, 5, 1.2, 0)
                         for x, y in ((a, b), (b, a)))
    gx, gy = np.meshgrid(np.arange(size[0], dtype=np.float32), np.arange(size[1], dtype=np.float32))
    reverse = cv2.remap(backward, gx + forward[:, :, 0], gy + forward[:, :, 1],
                        cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if np.mean(np.linalg.norm(forward + reverse, axis=2) <= 2.5) < .68:
        return None
    return tuple(cv2.resize(flow, (width, height)) * np.array([width / size[0], height / size[1]], np.float32)
                 for flow in (forward, backward))


def interpolate(first, last, pair, amount, grid):
    gx, gy = grid
    a = cv2.remap(first, gx - pair[0][:, :, 0] * amount, gy - pair[0][:, :, 1] * amount,
                  cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    b = cv2.remap(last, gx - pair[1][:, :, 0] * (1 - amount), gy - pair[1][:, :, 1] * (1 - amount),
                  cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return cv2.addWeighted(a, 1 - amount, b, amount, 0)


def separate_reference(engine_root, source, folder):
    """Reuse the installed Demucs executor. Preserve timing and stereo."""
    import soundfile as sf
    from hinglish_cut.compute_policy import heavy_device
    from hinglish_cut.gpu_lock import child_environment, gpu_lock

    engine_root = Path(engine_root)
    runtime = engine_root / 'tools/sound-separation-runtime/separate.py'
    checkpoint_name = '955717e8-8726e21a.th'
    stores = [Path(os.environ['TORCH_HOME'])] if os.environ.get('TORCH_HOME') else []
    stores += [Path('D:/Ai Models/cache/torch'), engine_root / 'cache/sound-separation-models']
    weights = next((store for store in stores if (store / 'hub/checkpoints' / checkpoint_name).is_file()), None)
    if not runtime.is_file() or weights is None:
        raise ValueError('Reference audio separation needs the installed Demucs executor and cached htdemucs checkpoint.')
    with (weights / 'hub/checkpoints' / checkpoint_name).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != '8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4':
        raise ValueError('The cached Demucs checkpoint failed its hash check.')
    vocal_path = folder / 'vocal-estimate.wav'
    backing_path = folder / 'backing-residual.wav'
    device = heavy_device(engine_root, 'cpu')
    env = os.environ | {'TORCH_HOME': str(weights)}
    from contextlib import nullcontext
    lease = gpu_lock(engine_root) if device == 'cuda' else nullcontext()
    with lease, (folder / 'separation.log').open('wb') as log:
        completed = subprocess.run([sys.executable, str(runtime), '--input', str(source),
                                    '--output', str(vocal_path), '--device', device],
                                   cwd=engine_root, stdout=log, stderr=subprocess.STDOUT,
                                   env=child_environment(engine_root, env),
                                   timeout=900, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if completed.returncode or not vocal_path.is_file():
        raise RuntimeError('The installed Demucs executor did not produce a vocal estimate.')
    original, rate = sf.read(source, dtype='float32', always_2d=True)
    vocals, vocal_rate = sf.read(vocal_path, dtype='float32', always_2d=True)
    if vocals.shape != original.shape or rate != vocal_rate or not np.isfinite(vocals).all():
        raise RuntimeError('Reference separation produced an invalid sample grid.')
    backing = original - vocals
    sf.write(backing_path, backing, rate, subtype='FLOAT')
    return [{'name': 'Vocal estimate', 'path': str(vocal_path)}, {'name': 'Backing residual', 'path': str(backing_path)}], {
        'engine': 'Demucs 4.0.1 htdemucs + phase-aligned residual', 'checkpoint_sha256': digest,
        'device': device, 'samples': len(vocals), 'sample_rate': rate, 'channels': vocals.shape[1],
        'vocal_peak': float(np.abs(vocals).max()), 'backing_peak': float(np.abs(backing).max()),
        'limits': 'Voice, music and effects may leak across tracks. The residual contains all remaining material.',
    }


LUMA = np.array([.2126, .7152, .0722], np.float32)
PRIMARIES = {
    1: ((.640, .330), (.300, .600), (.150, .060)),
    5: ((.640, .330), (.290, .600), (.150, .060)),
    6: ((.630, .340), (.310, .595), (.155, .070)),
}


def rgb_to_xyz(primaries):
    xy = np.asarray(primaries)
    basis = np.stack((xy[:, 0] / xy[:, 1], np.ones(3), (1 - xy.sum(axis=1)) / xy[:, 1]))
    white = np.array([.3127 / .3290, 1., (1 - .3127 - .3290) / .3290])
    return basis * np.linalg.solve(basis, white)


TO_709 = {tag: (np.linalg.solve(rgb_to_xyz(PRIMARIES[1]), rgb_to_xyz(points))).astype(np.float32)
          for tag, points in PRIMARIES.items() if tag != 1}


def display_rgb(pixels, metadata):
    """Normalize supported SDR transfer tags before estimating or applying the look."""
    primaries = metadata['color_primaries']
    transfer = metadata['color_trc']
    if primaries not in (1, 2, 5, 6) or transfer not in (1, 2, 4, 5, 6, 13):
        raise ValueError('Managed look matching supports Rec.709, sRGB and common SD SDR tags. '
                         'Normalize HDR, log or wide-gamut inputs first.')
    values = pixels.astype(np.float32) / 255
    if transfer in (1, 2, 6) and primaries in (1, 2):
        return values
    if transfer == 13:
        linear = np.where(values <= .04045, values / 12.92, ((values + .055) / 1.055)**2.4)
    elif transfer in (4, 5):
        linear = values**(2.2 if transfer == 4 else 2.8)
    else:
        linear = np.where(values < .081, values / 4.5, ((values + .099) / 1.099)**(1 / .45))
    if primaries in TO_709:
        linear = np.clip(linear @ TO_709[primaries].T, 0, 1)
    return np.where(linear < .018, linear * 4.5, 1.099 * linear**.45 - .099)


def look_sample(asset, start, end, lut=None):
    import av
    samples = []
    with av.open(asset['path']) as media:
        stream = media.streams.video[0]
        for proportion in np.arange(.05, 1, .10):
            target = asset['origin'] + start + (end - start) * proportion
            media.seek(int(target / float(stream.time_base)), stream=stream)
            closest = None
            for frame in media.decode(stream):
                if frame.time is None:
                    continue
                closest = frame
                if frame.time >= target:
                    break
            if closest is None:
                raise ValueError(f'Cannot read a color sample from {asset["name"]}.')
            sample = display_rgb(rgb(closest, 96, 96), asset['color_metadata'])
            if lut is not None:
                sample = lut[np.rint(sample * 255).astype(np.uint8)].astype(np.float32) / 255
            samples.append(sample[10:-10, 10:-10].reshape(-1, 3))
    values = np.concatenate(samples)
    luma = values @ LUMA
    spread = np.max(values, axis=1) - np.min(values, axis=1)
    neutral = values[(spread < .12) & (luma > .15) & (luma < .85)]
    tint = np.median(neutral - (neutral @ LUMA)[:, None], axis=0) if len(neutral) > 128 else np.zeros(3)
    return {'tone': np.percentile(luma, (5, 50, 95)).tolist(), 'saturation': float(np.median(spread)),
            'neutral_tint': tint.tolist(), 'neutral_pixels': len(neutral)}


def reference_still(asset, seconds):
    import av
    with av.open(asset['path']) as media:
        stream = media.streams.video[0]
        target = asset['origin'] + seconds
        media.seek(int(target / float(stream.time_base)), stream=stream)
        chosen = None
        for frame in media.decode(stream):
            if frame.time is None:
                continue
            if frame.time > target and chosen is not None:
                break
            chosen = frame
            if frame.time >= target:
                break
        if chosen is not None:
            scale = min(1., 960 / max(chosen.width, chosen.height))
            pixels = rgb(chosen, round(chosen.width * scale), round(chosen.height * scale))
            rotation = getattr(chosen, 'rotation', 0)
            if rotation:
                pixels = np.rot90(pixels, round(rotation / 90))
            sdr = np.rint(display_rgb(pixels, asset['color_metadata']) * 255).astype(np.uint8)
            ok, encoded = cv2.imencode('.jpg', cv2.cvtColor(sdr, cv2.COLOR_RGB2BGR),
                                       [cv2.IMWRITE_JPEG_QUALITY, 91])
            if ok:
                return encoded.tobytes()
    raise ValueError('A representative reference still could not be encoded.')


def fit_look(reference, target, strength):
    original = np.asarray(target['tone'])
    desired = np.asarray(reference['tone'])
    # Bound the movement of individual quantiles and preserve monotonicity.
    mapped = np.maximum.accumulate(original + np.clip(desired - original, -.18, .18) * strength)
    tint = np.clip(np.asarray(reference['neutral_tint']) - target['neutral_tint'], -.025, .025)
    return {'source_tone': original.tolist(), 'output_tone': mapped.tolist(),
            'saturation': float(1 + (np.clip(reference['saturation'] / max(.02, target['saturation']), .75, 1.25) - 1) * strength),
            'tint': (tint * strength).tolist(), 'strength': strength,
            'reference_sample': reference, 'source_sample': target}


def apply_look(values, look):
    luma = values @ LUMA
    points = {x: y for x, y in zip(look['source_tone'], look['output_tone']) if 0 < x < 1}
    x = [0., *points, 1.]
    y = [0., *points.values(), 1.]
    shift = np.interp(luma, x, y).astype(np.float32) - luma
    tint = np.asarray(look['tint'], np.float32)
    return np.clip(luma[..., None] + shift[..., None] +
                   (values - luma[..., None]) * look['saturation'] + tint, 0, 1)


def color_lut(shot, path):
    size = 33
    axis = np.linspace(0, 1, size, dtype=np.float32)
    b, g, r = np.meshgrid(axis, axis, axis, indexing='ij')
    result = apply_look(np.stack((r, g, b), axis=-1), shot['managed_look'])
    with Path(path).open('w', encoding='ascii') as output:
        output.write(f'TITLE "Reference Reel Rec709 shot {shot["start"]}"\nLUT_3D_SIZE {size}\n')
        np.savetxt(output, result.reshape(-1, 3), fmt='%.7f')
