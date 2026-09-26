"""Output specs: the rules every feature's finished result must follow, measured from the real files.

evaluate(folder) finds the feature's plan file(s) in a result folder and returns an Evaluation.
A Check with a `fix` carries the correction the runner applies on the next attempt."""
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET

from .text import brands_in, text_words_in, word_in

FRAME = 1 / 30


@dataclass
class Check:
    rule: str
    title: str
    passed: bool
    hard: bool = True
    value: str = ''
    target: str = ''
    detail: str = ''
    fix: dict = field(default_factory=dict)      # {'feature': {...tune values...}, 'feedback': [...]}


@dataclass
class Evaluation:
    feature: str
    folder: str
    checks: list

    @property
    def hard_failed(self):
        return [c for c in self.checks if c.hard and not c.passed]

    @property
    def soft_failed(self):
        return [c for c in self.checks if not c.hard and not c.passed]

    @property
    def passed(self):
        return not self.hard_failed

    @property
    def score(self):
        """0-100: hard rules count 3x, soft rules 1x."""
        total = sum(3 if c.hard else 1 for c in self.checks) or 1
        good = sum(3 if c.hard else 1 for c in self.checks if c.passed)
        return round(100 * good / total)

    def to_dict(self):
        return {'feature': self.feature, 'folder': self.folder, 'passed': self.passed, 'score': self.score,
                'checks': [asdict(c) for c in self.checks]}


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _fmt(values, n=6):
    values = list(values)
    return ', '.join(str(v) for v in values[:n]) + (f' (+{len(values) - n} more)' if len(values) > n else '')


# ---- Timeline XML (every feature) -------------------------------------------------------------------------
def check_xml(path, allow_missing=()):
    """The timeline must import cleanly: valid clips, no overlaps on a track, all media present."""
    from hinglish_broll.timeline import path_from_pathurl
    name = Path(path).name
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        return [Check('xml.valid', f'{name} is a valid timeline', False, value=str(error))]
    sequence = root if root.tag == 'sequence' else root.find('.//sequence')
    if sequence is None:
        return [Check('xml.valid', f'{name} is a valid timeline', False, value='no <sequence>')]
    bad, overlaps, missing = [], [], set()
    for kind in ('video', 'audio'):
        for t, track in enumerate(sequence.findall(f'./media/{kind}/track'), 1):
            last_end = -1
            for item in track.findall('clipitem'):
                try:
                    start, end = int(float(item.findtext('start'))), int(float(item.findtext('end')))
                except (TypeError, ValueError):
                    continue
                if start < 0 or end < 0:          # -1 = next to a transition (allowed by FCP XML)
                    continue
                if end <= start:
                    bad.append(f'{kind[0].upper()}{t} @{start}')
                if start < last_end:
                    overlaps.append(f'{kind[0].upper()}{t} @{start}')
                last_end = max(last_end, end)
    for f in root.iter('file'):
        url = f.findtext('pathurl')
        if url:
            p = Path(path_from_pathurl(url))
            if not p.is_file() and p.name not in allow_missing:
                missing.add(p.name)
    return [
        Check('xml.clips', f'{name}: every clip has a positive length', not bad, value=_fmt(bad) or 'all ok'),
        Check('xml.no_overlap', f'{name}: no overlapping clips on a track', not overlaps,
              value=_fmt(overlaps) or 'none'),
        Check('xml.media', f'{name}: all media files exist', not missing, value=_fmt(sorted(missing)) or 'all found'),
    ]


# ---- Smart Clean --------------------------------------------------------------------------------------------
def clean_checks(folder, report):
    fps = 30.0
    render = report.get('render') or {}
    checks = []
    for key, title in (('detected_speech_preserved', 'No detected speech was cut'),
                       ('source_order_preserved', 'Clips stay in the original order'),
                       ('frame_bounds_valid', 'All cuts are inside the video')):
        checks.append(Check(f'clean.{key}', title, bool((report.get('checks') or {}).get(key))))
    if render.get('sample_rate'):
        video = render['video_frames'] / fps
        audio = render['audio_samples'] / render['sample_rate']
        checks.append(Check('clean.av_sync', 'Audio and video of the cleaned file have the same length',
                            abs(video - audio) <= FRAME * 1.5, value=f'{abs(video - audio) * 1000:.0f} ms apart',
                            target='<= 1 frame'))
        checks.append(Check('clean.length', 'Cleaned length matches the edit decisions',
                            abs(video - report.get('edited_seconds', video)) <= FRAME * 1.5,
                            value=f'{video:.2f}s vs {report.get("edited_seconds", 0):.2f}s'))
    share = report.get('removed_seconds', 0) / max(1e-6, report.get('original_seconds', 1))
    checks.append(Check('clean.not_aggressive', 'Not over-cut (at most 45% removed)', share <= .45, hard=False,
                        value=f'{share:.0%} removed'))
    short = [r for r in report.get('removed', []) if 0 < r.get('end_seconds', 0) - r.get('start_seconds', 0) < .1
             and r.get('start_seconds', 0) > 0]
    checks.append(Check('clean.no_micro_cuts', 'No tiny cuts shorter than 0.1 s inside the video (jumpy)', not short,
                        hard=False, value=f'{len(short)} tiny cuts'))
    for xml in Path(folder).glob('*.xml'):
        checks += check_xml(xml)
    return checks


# ---- Auto Captions ------------------------------------------------------------------------------------------
def caption_checks(folder, project):
    folder = Path(folder)
    cues = project.get('cues', [])
    duration = (project.get('media') or {}).get('duration', 0)
    portrait = project.get('height', 0) > project.get('width', 1)
    max_words, max_chars = (4, 28) if portrait else (6, 46)
    overlaps = [i for i, (a, b) in enumerate(zip(cues, cues[1:]), 1) if b['start'] < a['end'] - 1e-3]
    outside = [i for i, c in enumerate(cues, 1) if c['start'] < 0 or c['end'] > duration + .05 or c['end'] <= c['start']]
    long_cues = [i for i, c in enumerate(cues, 1) if len(c.get('words', [])) > max_words
                 or len(' '.join(w['text'] for w in c.get('words', []))) > max_chars + 2]
    slow = [i for i, c in enumerate(cues, 1) if c['end'] - c['start'] > 3.2]
    flicker = [i for i, c in enumerate(cues, 1) if c['end'] - c['start'] < .2]
    untimed = [i for i, c in enumerate(cues, 1)
               if any(w['start'] < c['start'] - .05 or w['end'] > c['end'] + .05 or w['end'] < w['start']
                      for w in c.get('words', []))]
    empty = [i for i, c in enumerate(cues, 1) if not ''.join(w['text'] for w in c.get('words', [])).strip()]
    fast = [i for i, c in enumerate(cues, 1)
            if len(' '.join(w['text'] for w in c.get('words', []))) / max(.2, c['end'] - c['start']) > 22]
    checks = [
        Check('captions.order', 'Captions never overlap each other', not overlaps, value=_fmt(overlaps) or 'none'),
        Check('captions.inside', 'Every caption is inside the video', not outside, value=_fmt(outside) or 'all'),
        Check('captions.size', f'At most {max_words} words / {max_chars} letters per caption', not long_cues,
              value=_fmt(long_cues) or 'all ok'),
        Check('captions.duration', 'No caption stays longer than ~3 s', not slow, value=_fmt(slow) or 'all ok'),
        Check('captions.flicker', 'No caption flashes shorter than 0.2 s', not flicker, value=_fmt(flicker) or 'none'),
        Check('captions.word_timing', 'Every word is timed inside its caption', not untimed, value=_fmt(untimed) or 'ok'),
        Check('captions.not_empty', 'No empty captions', not empty, value=_fmt(empty) or 'none'),
        Check('captions.readable', 'Readable speed (<= 22 letters per second)', not fast, hard=False,
              value=_fmt(fast) or 'all ok'),
    ]
    transcript = folder / 'transcript.txt'
    if transcript.is_file():
        spoken = len(transcript.read_text(encoding='utf-8').split())
        shown = sum(len(c.get('words', [])) for c in cues)
        checks.append(Check('captions.coverage', 'Every spoken word is captioned (>= 95%)',
                            spoken == 0 or shown / spoken >= .95, value=f'{shown}/{spoken} words'))
    srt = folder / 'captions.srt'
    if srt.is_file():
        blocks = [b for b in srt.read_text(encoding='utf-8-sig').strip().split('\n\n') if b.strip()]
        checks.append(Check('captions.srt', 'The .srt file has every caption', len(blocks) == len(cues),
                            value=f'{len(blocks)} vs {len(cues)}'))
    for xml in folder.glob('*SEQUENCE.xml'):
        checks += check_xml(xml)
    return checks


# ---- B-roll ------------------------------------------------------------------------------------------------
def broll_checks(folder, project):
    from hinglish_broll.places import conflicts
    from hinglish_broll.ranker import DECENT_MATCH as DECENT
    from hinglish_broll.settings import profile_for
    folder = Path(folder)
    duration = project['timeline']['duration']
    profile = profile_for(duration, project.get('density', 'medium'))
    from hinglish_broll.places import video_country
    country = video_country(project.get('summary') or {})
    slots = [s for s in project.get('slots', []) if s.get('chosen') and s.get('clip')]
    shown = sum(s['end'] - s['start'] for s in slots)
    needed = max(1, math.floor(duration / (12 if profile.name == 'short' else 60)))
    fix_more = {'broll': {'count_scale': 1.5}, 'feedback': [
        f'Too little B-roll last time ({len(slots)} clips in {duration:.0f}s). Choose MORE moments: every named '
        'place, food, object, vehicle and action, spread over the whole video.']}
    lengths = [f'{s["start"]:.1f}s' for s in slots if not profile.min_len - .05 <= s['end'] - s['start'] <= profile.max_len + .05]
    close = [f'{b["start"]:.1f}s' for a, b in zip(slots, slots[1:])
             if b['start'] - a['start'] < profile.min_spacing - .05 or b['start'] - a['end'] < profile.min_gap - .05]
    edge = [f'{s["start"]:.1f}s' for s in slots if s['start'] < profile.hook - .05 or s['end'] > duration - profile.tail + .05]
    weak = [f'{s["start"]:.1f}s ({s["chosen"].get("score", 0):.2f})' for s in slots
            if s['chosen'].get('source') != 'library' and s['chosen'].get('score', 1) < DECENT - 1e-6]
    short_clip = [f'{s["start"]:.1f}s' for s in slots
                  if s['chosen'].get('duration', 99) - s['chosen'].get('offset', 0) < s['end'] - s['start'] - .05]
    missing = [s['clip'] for s in slots if not (folder / s['clip']).is_file()]
    brands = [f'{s["start"]:.1f}s: {", ".join(brands_in(" ".join(s.get("queries", []))))}' for s in slots
              if brands_in(' '.join(s.get('queries', [])))]
    texty = [f'{s["start"]:.1f}s' for s in slots if text_words_in(s.get('visual', ''))]
    foreign = [f'{s["start"]:.1f}s' for s in slots
               if country and conflicts(f'{s["chosen"].get("title", "")} {s["chosen"].get("page_url", "")}', country)]
    ids = [s['chosen'].get('id') for s in slots]
    repeats = sorted({i for i in ids if ids.count(i) > 1})
    checks = [
        Check('broll.enough', f'Enough B-roll (at least {needed} clips)', len(slots) >= needed,
              value=f'{len(slots)} clips, {shown / max(duration, 1e-6):.0%} of the video', target=f'>= {needed}',
              fix=fix_more if len(slots) < needed else {}),
        Check('broll.not_too_much', f'B-roll covers at most {profile.max_coverage:.0%} (your face stays the star)',
              shown <= profile.max_coverage * duration + .5, value=f'{shown / max(duration, 1e-6):.0%}',
              fix={'broll': {'count_scale': .7}} if shown > profile.max_coverage * duration + .5 else {}),
        Check('broll.line_length', f'Each clip lasts as long as its spoken line ({profile.min_len}-{profile.max_len} s)',
              not lengths, value=_fmt(lengths) or 'all ok'),
        Check('broll.spacing', 'Face time between clips', not close, value=_fmt(close) or 'all ok'),
        Check('broll.hook_tail', f'Face shown in the first {profile.hook}s and last {profile.tail}s', not edge,
              value=_fmt(edge) or 'ok'),
        Check('broll.match', f'Every stock clip matches its moment (score >= {DECENT})', not weak,
              value=_fmt(weak) or 'all good'),
        Check('broll.clip_length', 'Every clip is long enough for its moment', not short_clip,
              value=_fmt(short_clip) or 'ok'),
        Check('broll.files', 'All B-roll media files exist', not missing, value=_fmt(missing) or 'all found'),
        Check('broll.no_brands', 'No brand names in search phrases', not brands, value=_fmt(brands) or 'none'),
        Check('broll.filmable', 'Visuals are filmable (no text/logos)', not texty, value=_fmt(texty) or 'ok'),
        Check('broll.country', f'Footage fits the country ({country or "not set"})', not foreign,
              value=_fmt(foreign) or 'ok'),
        Check('broll.unique', 'No clip is used twice', not repeats, hard=False, value=_fmt(repeats) or 'none'),
    ]
    for xml in folder.glob('BROLL_SEQUENCE.xml'):
        checks += check_xml(xml)
    return checks


# ---- Smart Zoom ------------------------------------------------------------------------------------------------
def zoom_checks(folder, plan):
    from hinglish_zoom.settings import STRENGTH
    folder = Path(folder)
    settings, profile = plan['settings'], plan['profile']
    curve = plan.get('curve') or [1.0]
    anchors = plan.get('anchors') or []
    events = plan.get('events', [])
    cuts = {round(b, 2) for a, b in plan.get('shots', [])} | {round(a, 2) for a, b in plan.get('shots', [])}
    fps = 30.0
    level = STRENGTH.get(settings.get('strength'), 1.12)
    at_cut = lambda t: any(abs(t - c) <= 1.5 / fps for c in cuts)
    zoomed = sum(v > 1.004 for v in curve) / max(1, len(curve))
    steps = [abs(b - a) for a, b in zip(curve, curve[1:])]
    ramp_frames = max(1.0, profile['ramp_in'] * fps)
    max_step = (level - 1) / ramp_frames * 2.2
    jumps = [f'{i / fps:.2f}s' for i, s in enumerate(steps, 1) if s > max_step and not at_cut(i / fps)]
    # a zoom that goes in and straight back out (< 1 s) is a "pulse" - the jittery look the editor hated
    pulses, i = [], 0
    while i < len(curve):
        if curve[i] > 1.004:
            j = i
            while j < len(curve) and curve[j] > 1.004:
                j += 1
            if (j - i) / fps < 1.0 and not at_cut(i / fps) and not at_cut(j / fps):
                pulses.append(f'{i / fps:.1f}s')
            i = j
        else:
            i += 1
    smooth = settings.get('style') == 'smooth'
    ramps = [f'{e["start"]:.1f}s' for e in events if e.get('kind') == 'smooth' and (
        (e['word'] - e['start'] < .3 and not at_cut(e['start'])) or
        (e['end'] - e['hold_end'] < .3 and not at_cut(e['end'])))]
    # sections split at a shot change continue on the next shot: judge the joined section
    sections = []
    for e in sorted(events, key=lambda e: e['start']):
        if sections and abs(e['start'] - sections[-1]['end']) <= 1.5 / fps:
            sections[-1] = {**sections[-1], 'end': e['end'], 'hold_end': e['hold_end']}
        else:
            sections.append(dict(e))
    holds = [f'{s["start"]:.1f}s ({s["hold_end"] - s["word"]:.1f}s)' for s in sections
             if not profile['hold_min'] - .3 <= s['hold_end'] - s['word'] <= profile['hold_max'] + .3]
    gaps = [f'{b["start"]:.1f}s' for a, b in zip(sections, sections[1:]) if b['start'] - a['end'] < profile['gap'] - .05]
    words = [f'{e["start"]:.1f}s "{e.get("word_text")}"' for e in events if not word_in(e.get('word_text', ''), e.get('text', ''))]
    frames = [i for i, v in enumerate(curve) if v > 1.004]
    faced = sum(1 for i in frames if i < len(anchors) and anchors[i]) / max(1, len(frames))
    duration = len(curve) / fps
    expected = duration / profile['spacing']
    fewer = {'zoom': {'count_scale': .7}, 'feedback': [
        'Last time too much of the video was zoomed. Choose FEWER sections: only the strongest points.']}
    more = {'zoom': {'count_scale': 1.4}, 'feedback': [
        'Last time there were too few zooms. Choose a few more important points, spread across the video.']}
    checks = [
        Check('zoom.level', f'Zoom never goes past {level:.0%} and never below 100%',
              max(curve) <= level + .005 and min(curve) >= .999, value=f'{min(curve):.3f}-{max(curve):.3f}'),
        Check('zoom.mostly_wide', 'Most of the video stays wide (<= 50% zoomed)', zoomed <= .5,
              value=f'{zoomed:.0%} zoomed', fix=fewer if zoomed > .5 else {}),
        Check('zoom.no_jumps', 'No sudden scale jumps (except on a cut)', not jumps or not smooth,
              value=_fmt(jumps) or 'smooth'),
        Check('zoom.no_pulse', 'No in-and-straight-out pulses shorter than 1 s', not pulses,
              value=_fmt(pulses) or 'none'),
        Check('zoom.eased', 'Smooth zooms ease in and out over >= 0.3 s', not ramps, value=_fmt(ramps) or 'all eased'),
        Check('zoom.hold', f'Zoom holds for the whole point ({profile["hold_min"]}-{profile["hold_max"]} s)', not holds,
              value=_fmt(holds) or 'all ok'),
        Check('zoom.gap', f'At least {profile["gap"]} s of wide framing between zooms', not gaps,
              value=_fmt(gaps) or 'ok'),
        Check('zoom.word', 'Each zoom lands on a word that is really said there', not words, value=_fmt(words) or 'ok'),
        Check('zoom.face', 'Zooms are centred on your face (face found in >= 80% of zoomed frames)',
              not settings.get('face', True) or faced >= .8, value=f'{faced:.0%}'),
        Check('zoom.count', 'A sensible number of zooms for the length',
              expected * .35 <= len(sections) <= expected * 1.5 + 1, hard=False,
              value=f'{len(sections)} zooms', target=f'about {expected:.0f}',
              fix=(fewer if len(sections) > expected * 1.5 + 1 else more if len(sections) < expected * .35 else {})),
    ]
    for xml in folder.glob('ZOOMED_SEQUENCE.xml'):
        checks += check_xml(xml)
    return checks


# ---- Sound Design ---------------------------------------------------------------------------------------------
def sound_checks(folder, plan):
    import numpy as np
    from hinglish_sound.library import audible_span, loudness_db
    from hinglish_sound.mix import body_db, peak_db
    from hinglish_sound.settings import DENSITY, PEAK_CEILING, SFX_BEHAVIOUR, SFX_PEAK_ROOM, TARGET_LOUDNESS
    import wave

    def read(path):
        with wave.open(str(path)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, w.getnchannels()).T / 32767.0

    folder = Path(folder)
    settings = plan.get('settings', {})
    cues = plan.get('cues', [])
    lines = plan.get('lines', [])
    duration = max([l['end'] for l in lines] + [c['time'] + c['length'] for c in cues] + [1.0])
    form = 'short' if duration <= 180 else 'long'
    every, gap = DENSITY[form][settings.get('density', 'medium')]
    ai = [c for c in cues if c.get('source') == 'ai']
    checks = []
    effects = (plan.get('stems') or {}).get('effects', [])
    words_db = plan.get('words_db')
    if effects and words_db is not None:
        quiet, deficits = [], []
        for c, s in zip(cues, effects):
            audio = read(s['path'])
            target = words_db + c['offset_db']
            got = body_db(audio)
            capped = peak_db(audio) >= plan.get('voice_peak', 0) + SFX_PEAK_ROOM - .6
            if got < target - 3 and not capped:
                quiet.append(f'{c["target"]:.1f}s {c["category"]} ({got - target:+.0f} dB)')
                deficits.append(target - got)
        fix = {'sound': {'effect_gain_db': round(min(8.0, float(np.median(deficits))), 1)}} if deficits else {}
        checks.append(Check('sound.audible', 'Every effect is clearly audible next to your voice (within 3 dB of its '
                                             'level)', len(quiet) <= len(effects) * .1,
                            value=_fmt(quiet) or 'all audible', fix=fix))
    else:
        checks.append(Check('sound.audible', 'Every effect is clearly audible next to your voice', True, hard=False,
                            value='not measured (run made before the evaluator)'))
    tiny = [Path(c['path']).name for c in cues if audible_span(c['path']) < .06]
    checks.append(Check('sound.not_tiny', 'No effect is a click too short to hear (< 60 ms)', not tiny,
                        value=_fmt(tiny) or 'none'))
    designed = [c for c in cues if c.get('source') != 'layer']     # speech sounds + whooshes/booms on edits
    need = max(2, round(duration / every * .6))
    checks.append(Check('sound.plenty', f'Plenty of sounds (>= {need}; about one every {every:g} s)',
                        len(designed) >= need or not settings.get('effects', True),
                        value=f'{len(designed)} sounds ({len(ai)} on words)',
                        fix={'sound': {'count_scale': 1.5}, 'feedback': [
                            f'Last time only {len(ai)} sound moments were chosen; the editor wants about '
                            f'{round(duration / every)} audible sounds spread over the whole video.']}
                        if len(designed) < need else {}))
    crowded = [f'{b["target"]:.1f}s' for a, b in zip(ai, ai[1:]) if b['target'] - a['target'] < gap - .02]
    checks.append(Check('sound.spacing', f'Never two speech sounds within {gap} s', not crowded,
                        value=_fmt(crowded) or 'ok'))
    offbeat = []
    for c, s in zip(cues, effects):
        # single-peak sounds only (pops, chimes and glitches have several transients)
        if c['category'] not in ('impact', 'whoosh', 'riser', 'vanish') or c['time'] <= 0:
            continue
        mono = read(s['path']).mean(axis=0).astype(np.float64)
        n = int(.05 * 48000)
        if len(mono) <= n:
            continue
        energy = np.concatenate([[0.0], np.cumsum(mono ** 2)])
        loudest = s['start'] + (np.argmax(energy[n:] - energy[:-n]) + n / 2) / 48000
        if abs(loudest - c['target']) > .05:
            offbeat.append(f'{c["target"]:.2f}s {c["category"]} ({(loudest - c["target"]) * 1000:+.0f} ms)')
    checks.append(Check('sound.sync', 'Each hit / whoosh / riser peaks on its word or cut (within 50 ms)',
                        not offbeat, value=_fmt(offbeat) or 'all in sync'))
    cuts = [float(e.split()[2].split('-')[0]) for e in plan.get('events', []) if e.startswith('B-roll cutaway')]
    silent = [f'{t:.1f}s' for t in cuts if not any(abs(c['target'] - t) <= .85 for c in cues)]
    checks.append(Check('sound.edit_sounds', 'Every B-roll cut has a whoosh', not silent or not settings.get('transitions', True),
                        value=_fmt(silent) or 'all covered'))
    music = plan.get('music', [])
    if settings.get('music', True):
        covered = bool(music) and music[0]['start'] <= .1 and music[-1]['end'] >= duration - .15 and all(
            b['start'] - a['end'] <= .1 for a, b in zip(music, music[1:]))
        checks.append(Check('sound.music_cover', 'Music runs under the whole video', covered,
                            value=f'{len(music)} section(s)'))
        if form == 'short':
            checks.append(Check('sound.music_changes', 'At most 2 music sections in a Reel', len(music) <= 2,
                                value=str(len(music))))
        bed = (plan.get('stems') or {}).get('music')
        if bed and Path(bed).is_file() and plan.get('voice_db') is not None:
            level = loudness_db(read(bed).mean(axis=0), 48000) - plan['voice_db']
            fix = {'sound': {'music_trim_db': round(-11 - level, 1)}} if not -17 <= level <= -7 else {}
            checks.append(Check('sound.music_level', 'Music sits under the voice (7-17 dB quieter)', not fix,
                                value=f'{level:+.1f} dB vs voice', target='-7 to -17 dB', fix=fix))
    mix = folder / 'sound' / 'full-mix.wav'
    if mix.is_file():
        master = read(mix)
        peak = 20 * math.log10(max(float(np.abs(master).max()), 1e-9))
        loud = loudness_db(master.mean(axis=0), 48000)
        checks.append(Check('sound.ceiling', f'Master never goes over {PEAK_CEILING} dB', peak <= PEAK_CEILING + .2,
                            value=f'{peak:.1f} dB'))
        checks.append(Check('sound.loudness', f'Master loudness about {TARGET_LOUDNESS} (streaming)',
                            abs(loud - TARGET_LOUDNESS) <= 2.5, hard=False, value=f'{loud:.1f} dB'))
    checks.append(Check('sound.pull_back', 'Pull-back-and-punch used at most twice',
                        len(plan.get('pull_backs', [])) <= 2, value=str(len(plan.get('pull_backs', [])))))
    runs = [f'{a["target"]:.1f}s {a["category"]}' for a, b, c in zip(ai, ai[1:], ai[2:])
            if a['category'] == b['category'] == c['category']]
    checks.append(Check('sound.variety', 'Effects vary (never the same type 3 times in a row)', not runs, hard=False,
                        value=_fmt(runs) or 'varied'))
    if plan.get('palette') in ('serious', 'emotional'):
        silly = [Path(c['path']).name for c in cues if any(w in c['path'].lower() for w in ('funny', 'cartoon', 'silly'))]
        checks.append(Check('sound.palette', 'No cartoon sounds in a serious story', not silly, hard=False,
                            value=_fmt(silly) or 'none'))
    for xml in folder.glob('SOUND_SEQUENCE.xml'):
        checks += check_xml(xml)
    return checks


# ---- Eye Contact ----------------------------------------------------------------------------------------------
def eye_checks(folder, plan):
    from hinglish_eyecontact.media import probe
    folder = Path(folder)
    checks = [Check('eye.real_engine', 'NVIDIA Eye Contact really ran (not a simulation)', not plan.get('simulated'),
                    hard=False, value='simulated' if plan.get('simulated') else 'NVIDIA Maxine')]
    for f in plan.get('files', []):
        name = Path(f['source']).name
        target = Path(f['target'])
        if not target.is_file():
            checks.append(Check('eye.file', f'{name}: eye-contact copy exists', False, value='missing'))
            continue
        src, out = probe(f['source']), probe(target)
        checks.append(Check('eye.length', f'{name}: same length as the original',
                            abs(src.duration - out.duration) <= 1.5 / float(src.rate),
                            value=f'{out.duration:.3f}s vs {src.duration:.3f}s'))
        checks.append(Check('eye.audio', f'{name}: original audio kept', len(out.audio) == len(src.audio),
                            value=f'{len(out.audio)} vs {len(src.audio)} tracks'))
        checks.append(Check('eye.frames', f'{name}: NVIDIA fixed every frame', f['fixed'] >= f['frames'] - 2,
                            value=f'{f["fixed"]}/{f["frames"]}'))
        checks.append(Check('eye.size', f'{name}: same picture size', (out.width, out.height) == (src.width, src.height),
                            value=f'{out.width}x{out.height}'))
    for xml in folder.glob('EYE_CONTACT_SEQUENCE.xml'):
        text = xml.read_text(encoding='utf-8')
        relinked = all(Path(f['target']).name in text for f in plan.get('files', []))
        checks.append(Check('eye.relinked', 'Timeline points to the eye-contact copies', relinked))
        checks += check_xml(xml)
    return checks


# ---- Finding and running the right spec ------------------------------------------------------------------------
PLANS = [('sound-plan.json', 'sound', sound_checks), ('zoom-plan.json', 'zoom', zoom_checks),
         ('broll-project.json', 'broll', broll_checks), ('caption-project.json', 'captions', caption_checks),
         ('eyecontact-plan.json', 'eyecontact', eye_checks), ('report.json', 'clean', clean_checks)]


def model_checks(folder):
    """The model guard's record for this result: rules the AI still broke after its retries."""
    path = Path(folder) / 'model-checks.json'
    if not path.is_file():
        return []
    checks = []
    for call in _load(path):
        tries = len(call['tries'])
        left = call.get('final_problems') or [p for p in call['tries'][-1]['problems'] if p['hard']]
        fixed = call.get('repaired') or []
        value = (f'{call["final_hard"]} broken' if call['final_hard'] else 'ok') + f' · {tries} tr{"y" if tries == 1 else "ies"}' +                 (f' · {len(fixed)} fixed by the rules' if fixed else '')
        detail = '; '.join(p['message'] for p in left) if call['final_hard'] else '; '.join(fixed)
        checks.append(Check(f'model.{call["feature"] or "ai"}', f'AI answer "{call["label"]}" follows the rules',
                            call['final_hard'] == 0, value=value, detail=detail[:600]))
    return checks


def evaluate(folder):
    """All evaluations for a result folder (it may hold several timelines, one sub-folder each)."""
    folder = Path(folder)
    found = []
    for place in [folder] + sorted(p for p in folder.iterdir() if p.is_dir()):
        for name, feature, spec in PLANS:
            path = place / name
            if not path.is_file():
                continue
            data = _load(path)
            if feature == 'clean' and 'removed' not in data:
                continue
            try:
                checks = spec(place, data)
            except Exception as error:          # a spec bug must never hide a result
                checks = [Check(f'{feature}.evaluator', 'Evaluator could read this result', False, hard=False,
                                value=f'{type(error).__name__}: {error}')]
            found.append(Evaluation(feature, str(place), checks + model_checks(place)))
            break
    return found
