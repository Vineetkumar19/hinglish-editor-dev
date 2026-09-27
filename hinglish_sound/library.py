"""Index the music and sound-effect folders: category (folder), name + tags (sidecar .json),
duration, loudness and the moment of the peak. Read-only on the user's library; cached locally."""
from dataclasses import dataclass, asdict
import functools
import hashlib
import json
import os
from pathlib import Path
import re

import av
import numpy as np

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac'}
SAMPLE_RATE = 48000
INDEX_VERSION = 2


@dataclass
class Asset:
    path: str
    kind: str            # music | sfx
    category: str        # folder name, e.g. impact / riser / hopeful
    name: str
    text: str            # name + tags + description, used for matching
    duration: float
    loudness: float      # dB, gated RMS (comparable across files)
    peak_time: float     # seconds from the start to the loudest moment


def decode(path, rate=SAMPLE_RATE, mono=False, limit=None):
    """Decode any audio file to float32 [channels, samples] at `rate` (stereo unless mono)."""
    layout = 'mono' if mono else 'stereo'
    chunks, total = [], 0
    with av.open(str(path)) as container:
        if not container.streams.audio:
            return np.zeros((1 if mono else 2, 0), np.float32)
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format='fltp', layout=layout, rate=rate)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                data = out.to_ndarray()
                chunks.append(data); total += data.shape[1]
            if limit and total >= limit * rate:
                break
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray())
    audio = np.concatenate(chunks, axis=1) if chunks else np.zeros((1 if mono else 2, 0), np.float32)
    return audio[:, :int(limit * rate)] if limit else audio


def loudness_db(samples, rate, gate=-60.0):
    """Gated RMS loudness in dB of a mono signal (approximates LUFS well enough to balance sounds)."""
    samples = np.asarray(samples, np.float32).reshape(-1)
    block = max(1, int(.4 * rate))
    if len(samples) < block:
        rms = float(np.sqrt(np.mean(samples ** 2))) if len(samples) else 0.0
        return 20 * np.log10(max(rms, 1e-9))
    hop = block // 4
    frames = np.lib.stride_tricks.sliding_window_view(samples, block)[::hop]
    power = np.mean(frames ** 2, axis=1)
    db = 10 * np.log10(np.maximum(power, 1e-12))
    keep = db > gate
    if not keep.any():
        return float(db.max())
    relative = db > (10 * np.log10(np.mean(power[keep])) - 10)     # second, relative gate (like LUFS)
    return float(10 * np.log10(np.mean(power[keep & relative])))


@functools.lru_cache(maxsize=4096)
def audible_span(path):
    """Seconds between the first and last moment the sound is within 20 dB of its loudest point.
    A 15 ms click cannot be heard next to a voice however loud it is set, so tiny sounds are avoided."""
    try:
        audio = decode(path, 16000, mono=True, limit=6)[0]
    except Exception:
        return 0.0
    if not len(audio):
        return 0.0
    env = np.abs(audio)
    loud = np.where(env >= env.max() * .1)[0]
    return float((loud[-1] - loud[0]) / 16000) if len(loud) else 0.0


@functools.lru_cache(maxsize=4096)
def exact_peak_time(path, limit=12.0, window=.05, hpf=None):
    """Centre of the loudest 50 ms of the file, to the millisecond (for sub-frame sync). Measured after the
    same low cut the mix applies (`hpf`): a whoosh's bass swell and its heard peak are not at the same time."""
    try:
        audio = decode(path, 48000, mono=True, limit=limit)[0].astype(np.float64)
        if hpf:
            import torch
            import torchaudio.functional as AF
            audio = AF.highpass_biquad(torch.from_numpy(audio.astype(np.float32))[None], 48000, hpf)[0].numpy()
            audio = audio.astype(np.float64)
    except Exception:
        return None
    n = int(window * 48000)
    if len(audio) <= n:
        return float(np.abs(audio).argmax() / 48000) if len(audio) else None
    energy = np.concatenate([[0.0], np.cumsum(audio ** 2)])
    return float((np.argmax(energy[n:] - energy[:-n]) + n / 2) / 48000)


def peak_time(samples, rate, window=.05):
    samples = np.abs(np.asarray(samples, np.float32).reshape(-1))
    hop = max(1, int(window * rate))
    if len(samples) < hop:
        return 0.0
    energy = np.add.reduceat(samples ** 2, np.arange(0, len(samples), hop))
    return float(np.argmax(energy) * hop / rate)


def _describe(path):
    sidecar = Path(str(path) + '.json')
    name = re.sub(r'[_\-]+', ' ', re.sub(r'_\d+$', '', Path(path).stem)).strip()
    tags, title = [], ''
    if sidecar.is_file():
        try:
            data = json.loads(sidecar.read_text(encoding='utf-8'))
            title = str(data.get('name', ''))
            tags = [str(t) for t in data.get('tags', [])][:20]
        except Exception:
            pass
    return (title or name), ' '.join([name, title, ' '.join(tags)]).strip()


def _old_values(cache_dir):
    """Loudness/duration already measured by the user's earlier sound project (by file path)."""
    known = {}
    for kind in ('music', 'sfx'):
        file = Path(cache_dir) / f'scan_{kind}.json' if cache_dir else None
        if file and file.is_file():
            try:
                for item in json.loads(file.read_text(encoding='utf-8')):
                    key = os.path.normcase(os.path.normpath(item.get('path', '')))
                    known[key] = item
            except Exception:
                pass
    return known


def scan(folder, kind, cache_dir, old_cache=None, progress=print):
    folder = Path(folder)
    if not folder.is_dir():
        return []
    cache_dir = Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    tag = hashlib.sha1(str(folder.resolve()).lower().encode()).hexdigest()[:8]
    index_file = cache_dir / f'index-{kind}-{tag}.json'          # one cache per folder
    cached = json.loads(index_file.read_text(encoding='utf-8')) if index_file.exists() else {}
    old = _old_values(old_cache)
    assets, fresh = [], {}
    files = sorted(p for p in folder.rglob('*') if p.suffix.lower() in AUDIO_EXTENSIONS)
    for n, path in enumerate(files, 1):
        stat = path.stat()
        key = hashlib.sha1(json.dumps([INDEX_VERSION, str(path), stat.st_size, int(stat.st_mtime)]).encode()).hexdigest()
        if key in cached:
            fresh[key] = cached[key]
            if not cached[key].get('failed'):     # unreadable files are remembered and skipped quietly
                assets.append(Asset(**cached[key]))
            continue
        if n == 1 or n % 50 == 0:
            progress(f'  Reading your {kind} library {n}/{len(files)}')
        category = path.relative_to(folder).parts[0] if len(path.relative_to(folder).parts) > 1 else 'general'
        name, text = _describe(path)
        try:
            limit = 40 if kind == 'music' else 12      # loudness of music from its first 40 s is plenty
            audio = decode(path, 16000, mono=True, limit=limit)[0]
            with av.open(str(path)) as c:
                duration = float(c.duration / 1_000_000) if c.duration else len(audio) / 16000
            previous = old.get(os.path.normcase(os.path.normpath(str(path))), {})
            level = previous.get('lufs')
            level = float(level) if level is not None else loudness_db(audio, 16000)
            asset = Asset(str(path), kind, category, name, text, duration, level, peak_time(audio, 16000))
        except Exception:
            progress(f'  Skipped unreadable file {path.name}')
            fresh[key] = {'failed': True}
            continue
        fresh[key] = asdict(asset); assets.append(asset)
    index_file.write_text(json.dumps(fresh), encoding='utf-8')
    return assets
