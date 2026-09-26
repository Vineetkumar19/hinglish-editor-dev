"""Mix voice + music sections + effects following the sound-design brain's numbers."""
from pathlib import Path
import wave

import numpy as np
import torch
import torchaudio.functional as AF

from .library import SAMPLE_RATE, decode, loudness_db
from .settings import (DUCK_ATTACK, DUCK_RELEASE, MUSIC_DUCK, MUSIC_EQ_DIP, MUSIC_IN_GAPS, PEAK_CEILING,
                       PULL_BACK_DB, SFX_BEHAVIOUR, SFX_CREST_KEEP, SFX_CREST_MAX, SFX_CREST_TRIM, SFX_PEAK_ROOM, SFX_UNDER_VOICE,
                       TARGET_LOUDNESS, VOICE_HPF)

HOP = 480   # 10 ms envelope resolution at 48 kHz
SECTION_CROSSFADE = 1.5


def db(x):
    return 10 ** (np.asarray(x, dtype=np.float32) / 20)


def peak_db(x):
    """Robust peak (99.95th percentile) so a single click does not decide the level."""
    a = np.abs(np.asarray(x, np.float32)).reshape(-1)
    return 20 * np.log10(max(float(np.percentile(a, 99.95)) if len(a) else 0.0, 1e-9))


def phone_weight(audio):
    """Roughly how a phone / laptop speaker hears it (K-weighting): no deep bass, a bit more presence."""
    t = torch.from_numpy(np.ascontiguousarray(np.atleast_2d(audio), dtype=np.float32))
    return AF.treble_biquad(AF.highpass_biquad(t, SAMPLE_RATE, 100.0), SAMPLE_RATE, 4.0, 1500.0).numpy()


def _window_power(x, window=.15):
    a = np.asarray(x, np.float32)
    a = a.mean(axis=0) if a.ndim > 1 else a
    n = max(1, int(window * SAMPLE_RATE))
    if len(a) <= n:
        return np.array([float(np.mean(a ** 2)) if len(a) else 0.0])
    energy = np.concatenate([[0.0], np.cumsum(a.astype(np.float64) ** 2)])
    return (energy[n:] - energy[:-n]) / n


def body_db(x, window=.15):
    """How loud a sound is heard on a phone: its loudest 150 ms, phone-weighted (peaks ignore the body,
    and deep bass that small speakers cannot play is not counted)."""
    return 10 * np.log10(max(float(_window_power(phone_weight(x), window).max()), 1e-18))


def syllable_db(voice, window=.15):
    """The loudness of your spoken words (90th percentile of 150 ms windows), phone-weighted: effects are
    set against this, not against the average that includes pauses and breaths."""
    power = _window_power(phone_weight(voice), window)[::HOP]
    loud = power[power > power.max() * 1e-4]
    return 10 * np.log10(max(float(np.percentile(loud if len(loud) else power, 90)), 1e-18))


def highpass(audio, cutoff):
    t = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))
    return AF.highpass_biquad(t, SAMPLE_RATE, cutoff).numpy()


def eq_dip(audio, centre, gain, q):
    t = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))
    return AF.equalizer_biquad(t, SAMPLE_RATE, centre, gain, q).numpy()


def speech_envelope(voice, voice_db, rate=SAMPLE_RATE):
    """0..1 per sample: 1 while the speaker talks, smoothed like a sidechain (fast attack, slow release)."""
    mono = np.asarray(voice, np.float32)
    n = len(mono) // HOP
    if n == 0:
        return np.zeros(len(mono), np.float32)
    rms = np.sqrt(np.mean(mono[:n * HOP].reshape(n, HOP) ** 2, axis=1) + 1e-12)
    active = (20 * np.log10(rms) > voice_db - 18).astype(np.float32)
    env = np.zeros(n, np.float32)
    up, down = HOP / (DUCK_ATTACK * rate), HOP / (DUCK_RELEASE * rate)
    level = 0.0
    for i, a in enumerate(active):
        level = min(1.0, level + up) if a > level else max(a, level - down)
        env[i] = level
    smooth = np.repeat(env, HOP)
    return np.pad(smooth, (0, max(0, len(mono) - len(smooth))), mode='edge')[:len(mono)]


def _fit_length(audio, length, crossfade=SAMPLE_RATE):
    """Loop seamlessly (equal-power crossfade) or trim to `length` samples."""
    if audio.shape[1] >= length:
        return audio[:, :length].copy()
    xf = min(crossfade, audio.shape[1] // 4)
    out = audio.copy()
    t = np.linspace(0, np.pi / 2, xf, dtype=np.float32)
    while out.shape[1] < length:
        tail = out[:, -xf:] * np.cos(t) + audio[:, :xf] * np.sin(t)
        out = np.concatenate([out[:, :-xf], tail, audio[:, xf:]], axis=1)
    return out[:, :length]


def _fade(audio, fade_in, fade_out):
    n = audio.shape[1]
    a, b = min(n, int(fade_in * SAMPLE_RATE)), min(n, int(fade_out * SAMPLE_RATE))
    if a: audio[:, :a] *= np.sin(np.linspace(0, np.pi / 2, a, dtype=np.float32))    # quarter-sine: no click
    if b: audio[:, -b:] *= np.cos(np.linspace(0, np.pi / 2, b, dtype=np.float32))
    return audio


def music_bed(sections, voice_db, envelope, total, pull_backs=(), trim_db=0.0):
    """sections: [{'start', 'end', 'path', 'loudness'}] covering the video. Each section is levelled on
    its own (so a louder track does not jump out), crossfaded into the next, EQ-carved for the voice,
    ducked under speech and dipped into a vacuum before the biggest reveals."""
    bed = np.zeros((2, total), np.float32)
    xf = int(SECTION_CROSSFADE * SAMPLE_RATE)
    for i, s in enumerate(sections):
        start = max(0, int(s['start'] * SAMPLE_RATE) - (xf // 2 if i else 0))
        end = min(total, int(s['end'] * SAMPLE_RATE) + (xf // 2 if i < len(sections) - 1 else 0))
        if end <= start:
            continue
        audio = _fit_length(decode(s['path']), end - start)
        # Level by the loudness of the part that actually plays (a quiet piano intro is much softer
        # than the track's average), so the bed sits where the brain says it should.
        audio *= db(voice_db + MUSIC_IN_GAPS - loudness_db(audio.mean(axis=0), SAMPLE_RATE) + trim_db)
        audio = _fade(audio, 1.0 if i == 0 else SECTION_CROSSFADE, 2.0 if i == len(sections) - 1 else SECTION_CROSSFADE)
        bed[:, start:end] += audio
    bed = eq_dip(bed, *MUSIC_EQ_DIP)
    gain_db = -MUSIC_DUCK * envelope[:total]
    for t in pull_backs:                    # vacuum: dip 0.45 s before the hit, recover over 0.35 s after
        a, hit, b = int((t - .45) * SAMPLE_RATE), int(t * SAMPLE_RATE), int((t + .35) * SAMPLE_RATE)
        ramp_in = int(.15 * SAMPLE_RATE)
        dip = np.zeros(total, np.float32)
        lo = max(0, a)
        if hit > lo:
            dip[lo:hit] = PULL_BACK_DB
            r = min(ramp_in, hit - lo)
            dip[lo:lo + r] = np.linspace(0, PULL_BACK_DB, r)
        if b > hit:
            dip[hit:min(b, total)] = np.linspace(PULL_BACK_DB, 0, min(b, total) - hit)
        gain_db = gain_db - dip
    return bed * db(gain_db)


def effect(cue, words_db, voice_peak, envelope, total):
    audio = decode(cue.path, limit=cue.length + .05)
    n = min(audio.shape[1], int(cue.length * SAMPLE_RATE))
    audio = _fade(audio[:, :n].copy(), .003, min(.08, cue.length / 4))
    cutoff = SFX_BEHAVIOUR.get(cue.category, {}).get('hpf')
    if cutoff:
        audio = highpass(audio, cutoff)
    # SFX bus compressor (brain §8): tame the sharpest transient so the body of the sound can come up.
    # Tiny clicks/pops are nearly all spike, so they are trimmed harder (never more than SFX_CREST_MAX).
    peak = peak_db(audio)
    trim = min(SFX_CREST_MAX, max(SFX_CREST_TRIM, peak - body_db(audio) - SFX_CREST_KEEP))
    audio = limiter(audio, ceiling_db=peak - trim)
    gain = words_db + cue.offset_db - body_db(audio)             # heard as loud as intended next to your words
    gain = min(gain, voice_peak + SFX_PEAK_ROOM - peak_db(audio))  # never a spike far above the voice
    start = int(cue.time * SAMPLE_RATE)
    n = max(0, min(audio.shape[1], total - start))
    duck = db(SFX_UNDER_VOICE * envelope[start:start + n])
    return start, audio[:, :n] * db(max(-40.0, min(30.0, gain))) * duck


def limiter(mix, ceiling_db=PEAK_CEILING, rate=SAMPLE_RATE):
    ceiling = float(db(ceiling_db))
    block = int(.005 * rate)
    n = mix.shape[1] // block + 1
    padded = np.pad(np.abs(mix).max(axis=0), (0, n * block - mix.shape[1]))
    peaks = padded.reshape(n, block).max(axis=1)
    gain = np.minimum(1.0, ceiling / np.maximum(peaks, 1e-9))
    release = np.exp(-block / (.15 * rate))
    for i in range(1, n):
        gain[i] = min(gain[i], 1 - (1 - gain[i - 1]) * release)
    for i in range(n - 2, -1, -1):
        gain[i] = min(gain[i], gain[i + 1] + (1 - gain[i + 1]) * (1 - release))
    return mix * np.repeat(gain, block)[:mix.shape[1]]


def write_wav(path, audio, rate=SAMPLE_RATE):
    audio = np.clip(np.atleast_2d(audio), -1, 1)
    pcm = (audio.T * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(pcm.shape[1]); out.setsampwidth(2); out.setframerate(rate)
        out.writeframes(pcm.tobytes())
    return Path(path)


def mix(voice, sections, cues, folder, pull_backs=(), trim_db=0.0):
    """voice: mono float32 at 48 kHz (the timeline's dialogue, unchanged in the stems).
    Stems (music bed + one file per effect) are levelled against the ORIGINAL voice, so the edit in
    Premiere/Resolve sounds like the preview before mastering."""
    folder = Path(folder); (folder / 'sound').mkdir(parents=True, exist_ok=True)
    total = len(voice)
    voice_db, voice_peak = loudness_db(voice, SAMPLE_RATE), peak_db(voice)
    words_db = syllable_db(voice)
    envelope = speech_envelope(voice, voice_db)
    clean_voice = highpass(voice[None, :], VOICE_HPF)[0]
    master = np.stack([clean_voice, clean_voice]).astype(np.float32)
    stems = {'music': None, 'effects': []}
    bed, placed = None, []
    if sections:
        bed = music_bed(sections, voice_db, envelope, total, pull_backs, trim_db)
        master += bed
        stems['music'] = str(write_wav(folder / 'sound' / 'music-bed.wav', bed))
    for n, cue in enumerate(cues, 1):
        start, audio = effect(cue, words_db, voice_peak, envelope, total)
        if audio.shape[1] == 0:
            continue
        master[:, start:start + audio.shape[1]] += audio
        placed.append((start, audio, cue))
        stems['effects'].append({'path': str(write_wav(folder / 'sound' / f'sfx-{n:02d}-{cue.category}.wav', audio)),
                                 'start': start / SAMPLE_RATE, 'length': audio.shape[1] / SAMPLE_RATE,
                                 'category': cue.category})
    loud = loudness_db(master.mean(axis=0), SAMPLE_RATE)
    master = limiter(master * db(TARGET_LOUDNESS - loud))
    preview = write_wav(folder / 'sound' / 'full-mix.wav', master)
    return {'voice_db': round(voice_db, 1), 'voice_peak': round(voice_peak, 1), 'stems': stems,
            'preview_mix': str(preview), 'master': master, 'bed': bed, 'effects': placed,
            'speech': envelope[:total] > .5}
