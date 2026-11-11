"""Mix voice + music sections + effects following the sound-design brain's numbers."""
from pathlib import Path
import wave

import numpy as np
import torch
import torchaudio.functional as AF

from .library import SAMPLE_RATE, decode, loudness_db
from .settings import (DUCK_ATTACK, DUCK_RELEASE, MUSIC_DUCK, MUSIC_EQ_DIP, MUSIC_IN_GAPS, PEAK_CEILING,
                       NO_CREST_TRIM, PULL_BACK_DB, SFX_BEHAVIOUR, SFX_CREST_KEEP, SFX_CREST_MAX, SFX_MAX_OVER_WORDS,
                       SFX_CREST_RELEASE, SFX_CREST_TRIM, SFX_PEAK_ROOM, SFX_UNDER_VOICE,
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


def full_body_db(x, window=.15):
    """Loudest 150 ms with the bass included (how big headphones / speakers hear it)."""
    return 10 * np.log10(max(float(_window_power(x, window).max()), 1e-18))


def full_syllable_db(voice, window=.15):
    power = _window_power(voice, window)[::HOP]
    loud = power[power > power.max() * 1e-4]
    return 10 * np.log10(max(float(np.percentile(loud if len(loud) else power, 90)), 1e-18))


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
    if audio.shape[1] == 0:
        raise ValueError('Sound music file is silent')
    if audio.shape[1] < 4:
        return np.tile(audio, (1, length))[:, :length]
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
        strict=s.get('strict_bounds',False)
        start = max(0, int(s['start'] * SAMPLE_RATE) - (xf // 2 if i and not strict else 0))
        end = min(total, int(s['end'] * SAMPLE_RATE) + (xf // 2 if i < len(sections) - 1 and not strict else 0))
        if end <= start:
            continue
        source_offset = max(0, int(float(s.get('source_offset', 0)) * SAMPLE_RATE))
        audio = _fit_length(decode(s['path'])[:, source_offset:], end - start)
        # Level by the loudness of the part that actually plays (a quiet piano intro is much softer
        # than the track's average), so the bed sits where the brain says it should.
        audio *= db(voice_db + MUSIC_IN_GAPS - loudness_db(audio.mean(axis=0), SAMPLE_RATE) + trim_db)
        audio = _fade(audio, 1.0 if i == 0 else SECTION_CROSSFADE, 2.0 if i == len(sections) - 1 else SECTION_CROSSFADE)
        bed[:, start:end] += audio
    bed = eq_dip(bed, *MUSIC_EQ_DIP)
    if any(s.get('strict_bounds') for s in sections):
        allowed=np.zeros(total,np.float32)
        for s in sections:
            a,b=max(0,int(s['start']*SAMPLE_RATE)),min(total,int(s['end']*SAMPLE_RATE))
            allowed[a:b]=1.
        bed*=allowed
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


def effect(cue, words_db, voice_peak, envelope, total, words_full=None, layer_trim=0., duck_db=None):
    audio = decode(cue.path, limit=cue.length + max(0., getattr(cue, 'source_offset', 0)) + .05)
    trim = max(0, int(getattr(cue, 'source_offset', 0) * SAMPLE_RATE))
    audio = audio[:, trim:]
    if not audio.shape[1]:
        return int(cue.time * SAMPLE_RATE), audio
    n = min(audio.shape[1], int(cue.length * SAMPLE_RATE))
    from .processing import apply,validate
    processing=validate(getattr(cue,'processing',{}))
    audio=apply(audio[:,:n],processing)
    audio = _fade(audio, processing.get('fade_in',.5 if cue.category == 'ambience' else .003),
                  processing.get('fade_out',min(.7 if cue.category == 'ambience' else .08, cue.length / 4)))
    cutoff = SFX_BEHAVIOUR.get(cue.category, {}).get('hpf')
    if cutoff:
        audio = highpass(audio, cutoff)
    # SFX bus compressor (brain §8): tame the sharpest transient so the body of the sound can come up.
    # Tiny clicks/pops are nearly all spike, so they are trimmed harder (never more than SFX_CREST_MAX).
    if cue.category not in NO_CREST_TRIM:        # a riser's / whoosh's peak IS its climax: never flatten it
        peak = peak_db(audio)
        trim = min(SFX_CREST_MAX, max(SFX_CREST_TRIM, peak - body_db(audio) - SFX_CREST_KEEP))
        audio = limiter(audio, ceiling_db=peak - trim, release=SFX_CREST_RELEASE)
    gain = words_db + cue.offset_db - body_db(audio)             # heard as loud as intended next to your words
    gain = min(gain, voice_peak + SFX_PEAK_ROOM - peak_db(audio))  # never a spike far above the voice
    if words_full is not None:   # phone weighting ignores deep bass: never let a boom blast on headphones
        gain = min(gain, words_full + SFX_MAX_OVER_WORDS - full_body_db(audio))
    start = int(cue.time * SAMPLE_RATE)
    n = max(0, min(audio.shape[1], total - start))
    duck_amount=-processing['duck_db'] if 'duck_db' in processing else SFX_UNDER_VOICE if duck_db is None else duck_db
    duck = db(duck_amount * envelope[start:start + n])
    return start, audio[:, :n] * db(max(-40.0, min(30.0, gain + layer_trim))) * duck


def limiter(mix, ceiling_db=PEAK_CEILING, rate=SAMPLE_RATE, release=.15, return_gain=False):
    ceiling = float(db(ceiling_db))
    block = int(.005 * rate)
    n = mix.shape[1] // block + 1
    padded = np.pad(np.abs(mix).max(axis=0), (0, n * block - mix.shape[1]))
    peaks = padded.reshape(n, block).max(axis=1)
    gain = np.minimum(1.0, ceiling / np.maximum(peaks, 1e-9))
    release = np.exp(-block / (release * rate))
    for i in range(1, n):
        gain[i] = min(gain[i], 1 - (1 - gain[i - 1]) * release)
    for i in range(n - 2, -1, -1):
        gain[i] = min(gain[i], gain[i + 1] + (1 - gain[i + 1]) * (1 - release))
    gain=np.repeat(gain, block)[:mix.shape[1]]
    output=mix*gain
    return (output,gain) if return_gain else output


def write_wav(path, audio, rate=SAMPLE_RATE):
    audio = np.clip(np.atleast_2d(audio), -1, 1)
    pcm = (audio.T * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(pcm.shape[1]); out.setsampwidth(2); out.setframerate(rate)
        out.writeframes(pcm.tobytes())
    return Path(path)


def mix(voice, sections, cues, folder, pull_backs=(), trim_db=0.0, layered=False, dialogue_present=None, composed=False,source_audio=None):
    """Keep raw analysis stems and separate editor stems sharing the master gain envelope."""
    folder = Path(folder); (folder / 'sound').mkdir(parents=True, exist_ok=True)
    total = len(voice)
    if source_audio is not None:
        source_audio=np.asarray(source_audio,dtype=np.float32)
        if source_audio.shape!=(2,total) or not np.isfinite(source_audio).all():
            raise ValueError('Preserved source audio has different channels or timing; regenerate from the original video')
    has_dialogue = bool(len(voice) and np.max(np.abs(voice)) > .001) and dialogue_present is not False
    voice_db, voice_peak = (loudness_db(voice, SAMPLE_RATE), peak_db(voice)) if has_dialogue else (-20., -6.)
    words_db = syllable_db(voice) if has_dialogue else -18.
    words_full = full_syllable_db(voice) if has_dialogue else -18.
    envelope = speech_envelope(voice, voice_db) if has_dialogue else np.zeros(total, np.float32)
    clean_voice = highpass(voice[None, :], VOICE_HPF)[0]
    dialogue = np.stack([clean_voice, clean_voice]).astype(np.float32) if source_audio is None else source_audio.copy()
    master = dialogue.copy()
    stems = {'voice': str(write_wav(folder/'sound'/'dialogue.wav', master.copy())), 'music': None, 'effects': []}
    bed, placed = None, []
    if sections:
        bed = music_bed(sections, voice_db, envelope, total, pull_backs, trim_db)
        master += bed
        stems['music'] = str(write_wav(folder / 'sound' / 'music-bed.wav', bed))
    for n, cue in enumerate(cues, 1):
        count = sum(c.group_id == cue.group_id for c in cues) if layered and cue.group_id else 1
        # Composed layers already have explicit role levels. Dividing every
        # ingredient again erases the contrast of the designed ensemble.
        layer_trim = 0. if composed else -10 * np.log10(max(1, count))
        speech_duck=-2. if composed else -4. if layered else None
        start, audio = effect(cue, words_db, voice_peak, envelope, total, words_full,
                              layer_trim=layer_trim, duck_db=speech_duck)
        if audio.shape[1] == 0:
            continue
        master[:, start:start + audio.shape[1]] += audio
        placed.append((start, audio, cue))
        stems['effects'].append({'path': str(write_wav(folder / 'sound' / f'sfx-{n:02d}-{cue.category}.wav', audio)),
                                 'start': start / SAMPLE_RATE, 'length': audio.shape[1] / SAMPLE_RATE,
                                 'category': cue.category, 'group_id': cue.group_id, 'role': cue.role,
                                 'timing_precision': cue.timing_precision, 'uncertainty': cue.uncertainty,
                                 'processing':dict(cue.processing),'processing_baked':True,'sync':dict(cue.sync),
                                 'layer_trim_db': float(layer_trim), 'speech_duck_db':-cue.processing['duck_db'] if 'duck_db' in cue.processing else speech_duck or 0.})
    loud = loudness_db(master.mean(axis=0), SAMPLE_RATE)
    normalization=float(db(TARGET_LOUDNESS-loud))
    _,limit_gain=limiter(master*normalization,return_gain=True)
    gain=normalization*limit_gain
    # A cancellation in the full mix must not clip an individual PCM stem.
    component_peak=np.abs(dialogue).max(axis=0)
    if bed is not None:component_peak=np.maximum(component_peak,np.abs(bed).max(axis=0))
    for start,audio,_ in placed:
        end=start+audio.shape[1]
        component_peak[start:end]=np.maximum(component_peak[start:end],np.abs(audio).max(axis=0))
    gain=np.minimum(gain,.999/np.maximum(component_peak,1e-9))
    master=master*gain
    editor=folder/'sound'/'editor';editor.mkdir(exist_ok=True)
    exported={'voice':str(write_wav(editor/'dialogue.wav',dialogue*gain)),
              'voice_label':'Dialogue' if source_audio is None else 'Original audio (voice + existing music)',
              'music':str(write_wav(editor/'music-bed.wav',bed*gain)) if bed is not None else None,'effects':[],
              'mastering':{'version':1,'normalization_db':float(TARGET_LOUDNESS-loud),
                           'shared_master_gain':True,'peak_ceiling_db':PEAK_CEILING}}
    for stem,(start,audio,_) in zip(stems['effects'],placed):
        row=dict(stem)
        row['path']=str(write_wav(editor/Path(stem['path']).name,audio*gain[start:start+audio.shape[1]]))
        exported['effects'].append(row)
    # Canonical stems must be safe for older editor adapters too. Keep the
    # unmastered measurement files separately, never as the default export.
    exported['analysis']=stems
    stems=exported
    preview = write_wav(folder / 'sound' / 'full-mix.wav', master)
    return {'voice_db': round(voice_db, 1), 'voice_peak': round(voice_peak, 1), 'words_db': round(words_db, 2),
            'words_full_db': round(words_full, 2),
            'stems': stems,
            'preview_mix': str(preview), 'master': master, 'bed': bed, 'effects': placed,
            'speech': envelope[:total] > .5}
