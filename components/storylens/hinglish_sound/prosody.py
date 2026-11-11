"""How each line is SAID (not just what): loudness, pitch, liveliness and pace relative to the speaker."""
import numpy as np

RATE = 16000
FRAME, HOP = 640, 320            # 40 ms windows, 20 ms hop
F0_MIN, F0_MAX = 70.0, 400.0


def _frames(x):
    if len(x) < FRAME:
        return np.zeros((0, FRAME), np.float32)
    return np.lib.stride_tricks.sliding_window_view(x, FRAME)[::HOP].astype(np.float32)


def pitch_track(x):
    """F0 per frame (Hz, NaN when unvoiced) by normalized autocorrelation."""
    frames = _frames(x)
    if not len(frames):
        return np.zeros(0)
    frames = frames - frames.mean(axis=1, keepdims=True)
    energy = (frames ** 2).sum(axis=1)
    spec = np.fft.rfft(frames * np.hanning(FRAME), n=2 * FRAME, axis=1)
    ac = np.fft.irfft(np.abs(spec) ** 2, axis=1)[:, :FRAME]
    ac /= np.maximum(ac[:, :1], 1e-9)
    lo, hi = int(RATE / F0_MAX), int(RATE / F0_MIN)
    lag = lo + np.argmax(ac[:, lo:hi], axis=1)
    strength = ac[np.arange(len(ac)), lag]
    voiced = (strength > .45) & (energy > np.percentile(energy, 40))
    f0 = np.where(voiced, RATE / lag, np.nan)
    return f0


def describe_lines(voice16k, lines):
    """[{'id', 'loud', 'pitch', 'lively', 'pace', 'note'}] relative to the speaker's own median."""
    rows = []
    for line in lines:
        a, b = int(line.start * RATE), int(line.end * RATE)
        x = voice16k[a:b]
        if len(x) < FRAME:
            rows.append(None); continue
        frames = _frames(x)
        power = (frames ** 2).mean(axis=1)
        active = power > np.percentile(power, 30)
        loud = 10 * np.log10(max(power[active].mean() if active.any() else power.mean(), 1e-12))
        f0 = pitch_track(x)
        voiced = f0[~np.isnan(f0)]
        semis = 12 * np.log2(voiced / 100.0) if len(voiced) >= 5 else np.array([])
        words = max(1, len(line.text.split()))
        rows.append({'id': line.id, 'loud': loud,
                     'pitch': float(np.median(semis)) if len(semis) else None,
                     'lively': float(np.subtract(*np.percentile(semis, [90, 10]))) if len(semis) else None,
                     'pace': words / max(.3, line.end - line.start)})
    valid = [r for r in rows if r]
    if not valid:
        return []
    median = lambda key: float(np.median([r[key] for r in valid if r[key] is not None] or [0]))
    base = {k: median(k) for k in ('loud', 'pitch', 'lively', 'pace')}
    out = []
    for r in valid:
        notes = []
        d = r['loud'] - base['loud']
        if d > 3: notes.append(f'louder (+{d:.0f} dB)')
        elif d < -3: notes.append(f'quieter ({d:.0f} dB)')
        if r['pitch'] is not None:
            p = r['pitch'] - base['pitch']
            if p > 1.5: notes.append(f'higher pitch (+{p:.0f} st)')
            elif p < -1.5: notes.append(f'lower pitch ({p:.0f} st)')
        if r['lively'] is not None:
            if r['lively'] > base['lively'] * 1.35: notes.append('very expressive intonation')
            elif r['lively'] < base['lively'] * .65: notes.append('flat, monotone delivery')
        ratio = r['pace'] / max(base['pace'], 1e-6)
        if ratio > 1.25: notes.append('fast')
        elif ratio < .75: notes.append('slow, deliberate')
        out.append({'id': r['id'], 'voice': ', '.join(notes) or 'normal delivery'})
    return out
