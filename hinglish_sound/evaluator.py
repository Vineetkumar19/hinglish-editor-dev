"""The sound evaluator: every effect and music bed is LISTENED to before it is used, and the finished mix
is MEASURED. PASS/FAIL comes from fixed rules in code.

Per effect (CLAP heard the file):
  1. SOUNDS LIKE  the file must sound like the wanted type/intent ("deep boom" is not a cartoon boing,
                  a person talking, laughter or a music loop)
  2. TONE         no cartoon sound in a serious, emotional or informational video
Per music bed:
  3. NO SINGING   a song with vocals fights the speaker's words
  4. ENERGY       a calm section gets calm music, an energetic one gets movement (warning only)
Whole mix (numbers, no AI):
  5. LEVELS       each effect heard within its range next to the voice; music clearly under the speech;
                  master loudness about -14 LUFS; no clipping
  6. DENSITY      not more designed sounds than the budget; never two within the minimum gap"""
from dataclasses import dataclass, field, asdict

import numpy as np

from .library import SAMPLE_RATE, loudness_db
from .listen import SFX_VOCAB

# Which heard labels count as the right kind of sound for each effect type.
TYPE_LABELS = {
    'impact': ('boom', 'hit', 'bass drop'), 'whoosh': ('whoosh', 'reverse swell', 'message'),
    'riser': ('riser', 'reverse swell', 'drone'), 'poke': ('pop', 'click', 'notification', 'message', 'typing', 'camera'),
    'cute': ('ding', 'sparkle', 'success', 'pop'), 'retro': ('game', 'cash', 'success'),
    'awkward': ('fail', 'record scratch', 'cartoon'), 'suspense': ('heartbeat', 'ticking', 'drone'),
    'glitch': ('glitch', 'click'), 'vanish': ('poof', 'reverse swell', 'sparkle', 'whoosh'),
}
NOT_AN_EFFECT = ('voice', 'laugh', 'applause', 'crowd', 'animal', 'music')
SERIOUS_PALETTES = ('serious', 'emotional', 'informational')
EFFECT_RANGE = (-14.0, 3.0)      # heard loudness of an effect vs your words (dB)
MUSIC_UNDER_SPEECH = -8.0        # the bed must be at least this far under the words while you talk
MASTER_TARGET, MASTER_TOLERANCE = -14.0, 2.0


@dataclass
class SoundVerdict:
    passed: bool | None
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    heard: str = ''

    def to_dict(self):
        return asdict(self)

    @property
    def label(self):
        return 'NOT CHECKED' if self.passed is None else 'PASS' if self.passed else 'FAIL'


def check_effect(listener, vector, facts, sound_type, intent, palette):
    """Rules 1-2 for one effect file. `vector`: its CLAP audio vector; `facts`: what the index heard."""
    if listener is None or vector is None or not np.any(vector):
        return SoundVerdict(None, [], ['not listened to (the listening model is not available)'])
    names = list(SFX_VOCAB)
    sims = listener.similarity(vector, [SFX_VOCAB[n] for n in names] + [f'{intent}, {sound_type} sound effect'])
    wanted, labels = float(sims[-1]), sims[:-1]
    order = [names[i] for i in np.argsort(-labels)]
    best = order[0]
    heard = 'sounds like ' + ', '.join(order[:3])
    reasons, warnings = [], []
    right_kind = set(order[:3]) & set(TYPE_LABELS.get(sound_type, ()))
    if best in NOT_AN_EFFECT and best not in TYPE_LABELS.get(sound_type, ()):
        reasons.append(f'SOUNDS LIKE: it is {SFX_VOCAB[best]}, not a {sound_type} sound effect')
    elif not right_kind and wanted < float(labels.max()) - .02:
        reasons.append(f'SOUNDS LIKE: wanted "{intent}" ({sound_type}), it {heard}')
    elif not right_kind:
        warnings.append(f'closest to "{intent}", but it {heard}')
    if palette in SERIOUS_PALETTES and (facts or {}).get('cartoonish') and sound_type != 'awkward':
        reasons.append(f'TONE: a cartoon sound in a {palette} video')
    return SoundVerdict(not reasons, reasons, warnings, heard)


def check_music(facts, section_energy, mood):
    """Rules 3-4 for one music bed."""
    if not facts:
        return SoundVerdict(None, [], ['not listened to'])
    reasons, warnings = [], []
    if facts.get('vocals'):
        reasons.append('NO SINGING: this track has vocals; they fight your words')
    energy = facts.get('energy')
    if energy is not None:
        if section_energy <= 1 and energy > .6:
            warnings.append(f'ENERGY: a calm {mood} section but the track is busy ({energy:.1f})')
        if section_energy >= 3 and energy < .25:
            warnings.append(f'ENERGY: an energetic section but the track is very calm ({energy:.1f})')
    heard = ', '.join(facts.get('sounds_like', [])) + (f', ~{facts["bpm"]:.0f} BPM' if facts.get('bpm') else '')
    return SoundVerdict(not reasons, reasons, warnings, heard)


def _loudest(audio, window=.15):
    a = np.asarray(audio, np.float32)
    a = a.mean(axis=0) if a.ndim > 1 else a
    n = max(1, int(window * SAMPLE_RATE))
    if len(a) <= n:
        return 10 * np.log10(max(float(np.mean(a ** 2)) if len(a) else 0.0, 1e-18))
    energy = np.concatenate([[0.0], np.cumsum(a.astype(np.float64) ** 2)])
    return 10 * np.log10(max(float(((energy[n:] - energy[:-n]) / n).max()), 1e-18))


def words_level(voice, window=.15):
    a = np.asarray(voice, np.float32)
    n = max(1, int(window * SAMPLE_RATE))
    if len(a) <= n:
        return _loudest(a, window)
    energy = np.concatenate([[0.0], np.cumsum(a.astype(np.float64) ** 2)])
    power = ((energy[n:] - energy[:-n]) / n)[::n]
    loud = power[power > power.max() * 1e-4]
    return 10 * np.log10(max(float(np.percentile(loud if len(loud) else power, 90)), 1e-18))


def mix_qa(voice, bed, effects, master, speech_mask, cues, budget, gap):
    """Rules 5-6 on the rendered audio -> [{'check', 'passed', 'value'}].
    effects: [(start_sample, stereo array, cue)] as mixed; speech_mask: bool per sample (you are talking)."""
    rows = []
    words = words_level(voice)
    for start, audio, cue in effects:
        level = _loudest(audio) - words
        ok = EFFECT_RANGE[0] <= level <= EFFECT_RANGE[1]
        rows.append({'check': f'Effect at {cue.target:.1f}s ({cue.category}) heard vs your words',
                     'passed': bool(ok), 'value': f'{level:+.1f} dB (allowed {EFFECT_RANGE[0]:+.0f} to {EFFECT_RANGE[1]:+.0f})'})
    if bed is not None and speech_mask is not None and speech_mask.any():
        under = bed.mean(axis=0)[:len(speech_mask)][speech_mask[:bed.shape[1]]]
        level = loudness_db(under, SAMPLE_RATE) - loudness_db(np.asarray(voice)[speech_mask[:len(voice)]], SAMPLE_RATE)
        rows.append({'check': 'Music under your speech', 'passed': bool(level <= MUSIC_UNDER_SPEECH),
                     'value': f'{level:+.1f} dB vs your voice (must be {MUSIC_UNDER_SPEECH:+.0f} or lower)'})
    loud = loudness_db(np.asarray(master).mean(axis=0), SAMPLE_RATE)
    rows.append({'check': 'Master loudness', 'passed': bool(abs(loud - MASTER_TARGET) <= MASTER_TOLERANCE),
                 'value': f'{loud:.1f} dB (target {MASTER_TARGET:.0f})'})
    peak = 20 * np.log10(max(float(np.abs(master).max()), 1e-9))
    rows.append({'check': 'No clipping', 'passed': bool(peak <= -.5), 'value': f'peak {peak:.1f} dBFS'})
    designed = sorted(c.target for c in cues if c.source in ('ai', 'broll', 'zoom'))
    rows.append({'check': 'Number of sounds', 'passed': bool(len(designed) <= budget),
                 'value': f'{len(designed)} (budget {budget})'})
    close = [f'{a:.1f}s/{b:.1f}s' for a, b in zip(designed, designed[1:]) if b - a < gap - 1e-6]
    rows.append({'check': f'Spacing (at least {gap:.1f}s apart)', 'passed': not close,
                 'value': ', '.join(close[:4]) or 'ok'})
    return rows
