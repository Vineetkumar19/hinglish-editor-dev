"""Output specs: the rules every feature's finished result must follow, measured from the real files.

evaluate(folder) finds the feature's plan file(s) in a result folder and returns an Evaluation.
A Check with a `fix` carries the correction the runner applies on the next attempt."""
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET

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
        if any(check.rule=='captions.valid_recognition' and not check.passed for check in self.checks):
            return 0
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
        root = SafeET.parse(path).getroot()
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
    lyrics=project.get('caption_content')=='lyrics'
    max_words, max_chars = (5,34) if lyrics else (4, 28) if portrait else (6, 46)
    overlaps = [i for i, (a, b) in enumerate(zip(cues, cues[1:]), 1) if b['start'] < a['end'] - 1e-3]
    outside = [i for i, c in enumerate(cues, 1) if c['start'] < 0 or c['end'] > duration + .05 or c['end'] <= c['start']]
    long_cues = [i for i, c in enumerate(cues, 1) if len(c.get('words', [])) > max_words
                 or len(' '.join(w['text'] for w in c.get('words', []))) > max_chars + 2]
    max_seconds=6 if lyrics else 3.2
    slow = [i for i, c in enumerate(cues, 1) if c['end'] - c['start'] > max_seconds]
    flicker = [i for i, c in enumerate(cues, 1) if c['end'] - c['start'] < .2]
    untimed = [i for i, c in enumerate(cues, 1)
               if any(w['start'] < c['start'] - .05 or w['end'] > c['end'] + .05 or w['end'] < w['start']
                      for w in c.get('words', []))]
    empty = [i for i, c in enumerate(cues, 1) if not ''.join(w['text'] for w in c.get('words', [])).strip()]
    fast = [i for i, c in enumerate(cues, 1)
            if len(' '.join(w['text'] for w in c.get('words', []))) / max(.2, c['end'] - c['start']) > 22]
    from hinglish_cut.recognition_quality import placeholder_transcript
    text=' '.join(word['text'] for cue in cues for word in cue.get('words',[]))
    finite=all(math.isfinite(float(value)) for cue in cues for word in cue.get('words',[]) for value in (word['start'],word['end']))
    checks = [
        Check('captions.order', 'Captions never overlap each other', not overlaps, value=_fmt(overlaps) or 'none'),
        Check('captions.inside', 'Every caption is inside the video', not outside, value=_fmt(outside) or 'all'),
        Check('captions.size', f'At most {max_words} words / {max_chars} letters per caption', not long_cues,
              value=_fmt(long_cues) or 'all ok'),
        Check('captions.duration', 'Lyric phrases stay within 6 s' if lyrics else 'No caption stays longer than ~3 s', not slow, value=_fmt(slow) or 'all ok'),
        Check('captions.flicker', 'No caption flashes shorter than 0.2 s', not flicker, value=_fmt(flicker) or 'none'),
        Check('captions.word_timing', 'Every word is timed inside its caption', not untimed, value=_fmt(untimed) or 'ok'),
        Check('captions.not_empty', 'No empty captions', not empty, value=_fmt(empty) or 'none'),
        Check('captions.valid_recognition','Caption text is not an invalid recognizer placeholder',bool(text.strip()) and not placeholder_transcript(text)),
        Check('captions.finite_timing','Caption word timings are finite',finite),
        Check('captions.readable', 'Readable speed (<= 22 letters per second)', not fast, hard=False,
              value=_fmt(fast) or 'all ok'),
    ]
    transcript = folder / 'transcript.txt'
    if transcript.is_file():
        spoken = len(transcript.read_text(encoding='utf-8').split())
        shown = sum(len(c.get('words', [])) for c in cues)
        checks.append(Check('captions.coverage', 'Every transcribed word is included (not an audio-accuracy check)',
                            spoken == 0 or shown / spoken >= .95, value=f'{shown}/{spoken} words'))
    warnings=(project.get('transcription') or {}).get('warnings',[])
    if warnings:
        checks.append(Check('captions.transcription_review','Transcription and timing warnings reviewed',False,
                            hard=False,value='; '.join(warnings),detail='Layout checks do not establish that the lyric transcription is correct.'))
    srt = folder / 'captions.srt'
    if srt.is_file():
        blocks = [b for b in srt.read_text(encoding='utf-8-sig').strip().split('\n\n') if b.strip()]
        expected=sum(len(cue.get('words',[])) for cue in cues) if project.get('word_visibility') in ('spoken','styled_spoken') else len(cues)
        checks.append(Check('captions.srt', 'The .srt file has every timed word' if project.get('word_visibility') in ('spoken','styled_spoken') else 'The .srt file has every caption',len(blocks)==expected,
                            value=f'{len(blocks)} vs {expected}'))
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
    if project.get('audio_only_test') is True or project.get('review_options') is True:
        from dataclasses import replace
        profile=replace(profile,hook=0.,tail=0.,min_gap=0.,min_spacing=0.,
                        max_coverage=1. if project.get('review_options') else profile.max_coverage)
    from hinglish_broll.places import video_country
    country = video_country(project.get('summary') or {})
    slots = [s for s in project.get('slots', []) if s.get('chosen') and s.get('clip')]
    shown = sum(s['end'] - s['start'] for s in slots)
    needed = max(1, math.floor(duration / (12 if profile.name == 'short' else 60)))
    needed=max(needed,project.get('requested_count',0))
    # A count shortfall is not permission to invent more cutaways. Preserve
    # the diagnostic failure without repeating expensive quota-driven runs.
    fix_more={}
    from hinglish_broll.placement import MIN_LINE
    lengths = [f'{s["start"]:.1f}s' for s in slots if not MIN_LINE - .05 <= s['end'] - s['start'] <= profile.max_len + .05]
    if project.get('review_options') is True:
        lengths=[f'{s["start"]:.1f}s' for s in slots
                 if not (math.isfinite(s['start']) and math.isfinite(s['end'])
                         and 0<=s['start']<s['end']<=duration)]
    close = [f'{b["start"]:.1f}s' for a, b in zip(slots, slots[1:])
             if b['start'] - a['start'] < profile.min_spacing - .05 or b['start'] - a['end'] < profile.min_gap - .05]
    edge = [f'{s["start"]:.1f}s' for s in slots if s['start'] < profile.hook - .05 or s['end'] > duration - profile.tail + .05]
    weak = [f'{s["start"]:.1f}s ({s["chosen"].get("score", 0):.2f})' for s in slots
            if s['chosen'].get('source') != 'library' and s['chosen'].get('score', 1) < DECENT - 1e-6]
    short_clip = [f'{s["start"]:.1f}s' for s in slots
                  if s.get('source_duration',s['chosen'].get('duration',99)) -
                     s.get('source_in',s['chosen'].get('offset',0)) < s['end'] - s['start'] - .05]
    missing = [s['clip'] for s in slots if not (folder / s['clip']).is_file()]
    brands = [f'{s["start"]:.1f}s: {", ".join(brands_in(" ".join(s.get("queries", []))))}' for s in slots
              if brands_in(' '.join(s.get('queries', [])))]
    texty = [f'{s["start"]:.1f}s' for s in slots if text_words_in(s.get('visual', ''))]
    foreign = [f'{s["start"]:.1f}s' for s in slots
               if country and conflicts(f'{s["chosen"].get("title", "")} {s["chosen"].get("page_url", "")}', country)]
    ids = [s['chosen'].get('id') for s in slots]
    repeats = sorted({i for i in ids if ids.count(i) > 1})
    checks = [
        Check('broll.videos_only', 'Every cutaway is a video',
              all(s['chosen'].get('kind','video')=='video' for s in slots)),
        Check('broll.context_verified', 'Downloaded footage passed the speech-context check',
              all(any(c.get('id')==s['chosen'].get('id') and c.get('passed') is True
                      for c in s.get('checks',[])) for s in slots)),
        Check('broll.enough', f'Enough B-roll (at least {needed} clips)', len(slots) >= needed,
              value=f'{len(slots)} clips, {shown / max(duration, 1e-6):.0%} of the video', target=f'>= {needed}',
              fix=fix_more if len(slots) < needed else {}),
        Check('broll.not_too_much', f'B-roll covers at most {profile.max_coverage:.0%} (your face stays the star)',
              shown <= profile.max_coverage * duration + .5, value=f'{shown / max(duration, 1e-6):.0%}',
              fix={'broll': {'count_scale': .7}} if shown > profile.max_coverage * duration + .5 else {}),
        Check('broll.line_length', ('Each keyword interval has valid original timeline bounds' if project.get('review_options') is True else f'Each clip follows its spoken line ({MIN_LINE}-{profile.max_len} s)'),
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
    if plan.get('pacing') == 'cuts':
        from hinglish_zoom.cut_pacing import checks as cut_checks
        checks = cut_checks(plan, Check)
        from hinglish_zoom.effects_quality import checks as effects_checks
        checks += effects_checks(folder,plan,Check)
        for xml in Path(folder).glob('ZOOMED_SEQUENCE.xml'):
            checks += check_xml(xml)
        return checks
    from hinglish_zoom.settings import STRENGTH
    folder = Path(folder)
    settings, profile = plan['settings'], plan['profile']
    curve = plan.get('curve') or [1.0]
    anchors = plan.get('anchors') or []
    events = plan.get('events', [])
    cuts = {round(b, 2) for a, b in plan.get('shots', [])} | {round(a, 2) for a, b in plan.get('shots', [])}
    fps = float(plan.get('fps', 30.0))
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
    ramps = [f'{e["start"]:.1f}s' for e in events if e.get('kind') in ('smooth', 'push') and (
        e['word'] - e['start'] < .3 or e['end'] - e['hold_end'] < .3)]
    # sections split at a shot change continue on the next shot: judge the joined section
    sections = []
    for e in sorted(events, key=lambda e: e['start']):
        if sections and abs(e['start'] - sections[-1]['end']) <= 1.5 / fps:
            sections[-1] = {**sections[-1], 'end': e['end'], 'hold_end': e['hold_end']}
        else:
            sections.append(dict(e))
    holds = [f'{s["start"]:.1f}s ({s["hold_end"] - s["word"]:.1f}s)' for s in sections
             if (s['hold_end'] - s['word'] > profile['hold_max'] + .3 or
                 s['hold_end'] - s['word'] < profile['hold_min'] - .05)]
    for s in sections:
        plateau=curve[max(0,int(-(-s['word']*fps//1))):min(len(curve),int(s['hold_end']*fps)+1)]
        if plateau and 'level' in s and any(abs(v-s['level'])>.0003 for v in plateau):
            holds.append(f'{s["word"]:.1f}s: rendered curve does not maintain the close hold')
    wide_max=profile.get('wide_max',0)
    gaps = [f'{a["end"]:.1f}-{b["start"]:.1f}s ({b["start"]-a["end"]:.1f}s wide)'
            for a,b in zip(sections,sections[1:])
            if b['start']-a['end'] < profile['gap']-.05 or
               (wide_max and b['start']-a['end'] > wide_max+.05)]
    for a,b in zip(sections,sections[1:]):
        wide=curve[max(0,int(-(-a['end']*fps//1))):min(len(curve),int(b['start']*fps)+1)]
        if any(abs(v-1)>.0003 for v in wide):
            gaps.append(f'{a["end"]:.1f}s: wide hold is interrupted')
    words = [f'{e["start"]:.1f}s "{e.get("word_text")}"' for e in events if not word_in(e.get('word_text', ''), e.get('text', ''))]
    frames = [i for i, v in enumerate(curve) if v > 1.004]
    faced = sum(1 for i in frames if i < len(anchors) and anchors[i]) / max(1, len(frames))
    duration = len(curve) / fps
    if wide_max and sections and duration-sections[-1]['end'] > wide_max+.05:
        gaps.append(f'ending stays wide for {duration-sections[-1]["end"]:.1f}s')
    # The owner's settled 3-5 s close/wide holds replace the old short pulse
    # budget. Movement is neither a close hold nor a wide hold. Long videos
    # still keep their sparse, mostly-wide key-point pacing.
    moving=sum(max(0,e['word']-e['start'])+max(0,e['end']-e['hold_end']) for e in sections)
    settled_close=sum(max(0,e['hold_end']-e['word']) for e in sections)/max(1e-6,duration-moving)
    balanced=(settled_close <= profile['hold_max']/(profile['hold_max']+profile['gap'])
              +profile.get('hook_deadline',0)/max(1,duration)) if wide_max else zoomed<=.5
    expected = duration / max(1e-6,profile['spacing'])
    cadence_min, cadence_max = profile.get('cadence_min', 0), profile.get('cadence_max', 0)
    cadence_problems = []
    if cadence_max:
        import math
        expected = max(1, math.ceil(max(0,duration-profile.get('hook_deadline',0))/cadence_max))
        peaks = [e['word'] for e in sorted(events, key=lambda e: e['word'])]
        if len(peaks) < expected:
            cadence_problems.append(f'{len(peaks)} complete zooms; about {expected} needed')
        for a, b in zip(peaks, peaks[1:]):
            if not cadence_min - .25 <= b - a <= cadence_max + .25:
                cadence_problems.append(f'{a:.1f}-{b:.1f}s: {b-a:.1f}s between zooms')
        if not peaks or peaks[0] > cadence_max or duration - peaks[-1] > cadence_max:
            cadence_problems.append('an opening or ending section has no nearby zoom')
    fewer = {'zoom': {'count_scale': .7}, 'feedback': [
        'Last time too much of the video was zoomed. Choose FEWER sections: only the strongest points.']}
    more = {'zoom': {'count_scale': 1.4}, 'feedback': [
        'Last time there were too few zooms. Choose a few more important points, spread across the video.']}
    checks = [
        Check('zoom.level', f'Zoom never goes past {level:.0%} and never below 100%',
              max(curve) <= level + .005 and min(curve) >= .999, value=f'{min(curve):.3f}-{max(curve):.3f}'),
        Check('zoom.mostly_wide', ('Close and wide holds stay balanced; movement is counted separately' if wide_max
                                 else 'Most of the video stays wide (<= 50% zoomed)'), balanced,
              value=f'{settled_close:.0%} of settled framing close' if wide_max else f'{zoomed:.0%} zoomed',
              fix=fewer if not balanced else {}),
        Check('zoom.no_jumps', 'No sudden scale jumps (except on a cut)', not jumps or not smooth,
              value=_fmt(jumps) or 'smooth'),
        Check('zoom.no_pulse', 'No in-and-straight-out pulses shorter than 1 s', not pulses,
              value=_fmt(pulses) or 'none'),
        Check('zoom.eased', 'Smooth zooms ease in and out over >= 0.3 s', not ramps, value=_fmt(ramps) or 'all eased'),
        Check('zoom.hold', f'Close framing holds for {profile["hold_min"]}-{profile["hold_max"]} s, including across cuts', not holds,
              value=_fmt(holds) or 'all ok'),
        Check('zoom.gap', (f'{profile["gap"]}-{wide_max} s of stable wide framing between zooms' if wide_max
                          else f'At least {profile["gap"]} s of wide framing between zooms'), not gaps,
              value=_fmt(gaps) or 'ok'),
        Check('zoom.word', 'Each zoom lands on a word that is really said there', not words, value=_fmt(words) or 'ok'),
        Check('zoom.face', ('Zooms use a verified face or locally verified speaker (>= 80% of zoomed frames)'
                           if 'speaker' in plan.get('anchor_kinds', []) else
                           'Zooms are centred on your face (face found in >= 80% of zoomed frames)'),
              not settings.get('face', True) or faced >= .8, value=f'{faced:.0%}'),
        Check('zoom.count', 'A sensible number of zooms for the length',
              profile['name'] == 'long' or expected * .35 <= len(sections) <= expected * 1.5 + 1, hard=False,
              value=f'{len(sections)} zooms', target='major script points only' if profile['name'] == 'long' else f'about {expected:.0f}',
              fix=({} if profile['name'] == 'long' else
                   fewer if len(sections) > expected * 1.5 + 1 else more if len(sections) < expected * .35 else {})),
    ]
    if cadence_max:
        checks.append(Check('zoom.cadence', f'No short-video section goes more than {cadence_max:g} seconds without a complete zoom',
                            not cadence_problems, value=_fmt(cadence_problems) or f'{len(events)} regularly spaced zooms',
                            detail='Choose another supported spoken highlight when a shot or unclear face prevents a complete zoom.',
                            fix=more if cadence_problems else {}))
        deadline=profile.get('hook_deadline',0)
        if deadline:
            checks.append(Check('zoom.hook', f'The opening hook zoom lands within the first {deadline:g} seconds',
                                bool(events) and min(e['word'] for e in events)<=deadline+1/fps,
                                value=f"{min(e['word'] for e in events):.2f}s" if events else 'no opening hook',
                                fix=more if not events or min(e['word'] for e in events)>deadline+1/fps else {}))
    else:
        checks.append(Check('zoom.keypoints', 'Long-video zooms emphasise major script points only',
                            all(e.get('strength', 2) >= 2 for e in events), value=f'{len(events)} key points; no timed quota'))
    from hinglish_zoom.effects_quality import checks as effects_checks
    checks += effects_checks(folder,plan,Check)
    for xml in folder.glob('ZOOMED_SEQUENCE.xml'):
        checks += check_xml(xml)
    return checks


# ---- Sound Design ---------------------------------------------------------------------------------------------
def sound_checks(folder, plan):
    import numpy as np
    from hinglish_sound.library import audible_span, loudness_db
    from hinglish_sound.mix import body_db, peak_db, full_body_db
    from hinglish_sound.settings import DENSITY, PEAK_CEILING, SFX_BEHAVIOUR, SFX_PEAK_ROOM, SFX_MAX_OVER_WORDS, TARGET_LOUDNESS
    import wave

    def read(path):
        with wave.open(str(path)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, w.getnchannels()).T / 32767.0

    folder = Path(folder)
    settings = plan.get('settings', {})
    cues = plan.get('cues', [])
    layered = bool(settings.get('layered', False))
    composed = bool(plan.get('composition_version',0))
    lines = plan.get('lines', [])
    duration = max([l['end'] for l in lines] + [c['time'] + c['length'] for c in cues] + [1.0])
    form = 'short' if duration <= 180 else 'long'
    every, gap = DENSITY[form][settings.get('density', 'medium')]
    ai = [c for c in cues if c.get('source') in ('ai','speech')]
    checks = []
    sound_stems=plan.get('stems') or {}
    measured_stems=sound_stems.get('analysis',sound_stems)
    effects = measured_stems.get('effects', [])
    exported_effects=(sound_stems.get('editor') or sound_stems).get('effects',[])
    words_db = plan.get('words_db')
    if effects and words_db is not None:
        quiet, deficits = [], []
        for index,(c, s) in enumerate(zip(cues, effects)):
            if index>=len(exported_effects) or not np.any(read(exported_effects[index]['path'])):
                quiet.append(f'{c["target"]:.1f}s {c["category"]} (exported layer is missing or silent)')
                continue
            audio = read(s['path'])
            target = words_db + c['offset_db']
            layer_trim=min(0.,float(s.get('layer_trim_db',0.))) if layered else 0.
            max_duck=min(0.,float(s.get('speech_duck_db',-4. if layered else 0.)))
            if layered:
                # Share gain across complementary layers and allow the mixer's
                # intentional 4 dB speech duck; never boost it back automatically.
                target += layer_trim
            got = body_db(audio)
            # The safety ceilings are applied BEFORE layer gain and speech duck.
            # Compare the exported stem to those reduced ceilings, including the
            # full-band bass limit that phone-weighted loudness cannot represent.
            capped = peak_db(audio) >= plan.get('voice_peak', 0) + SFX_PEAK_ROOM + layer_trim + max_duck - .6
            full_words=plan.get('words_full_db')
            if full_words is not None:
                capped = capped or full_body_db(audio) >= full_words + SFX_MAX_OVER_WORDS + layer_trim + max_duck - .6
            if got < target - (7 if layered else 3) and not capped:
                quiet.append(f'{c["target"]:.1f}s {c["category"]} ({got - target:+.0f} dB)')
                deficits.append(target - got)
        fix = {'sound': {'effect_gain_db': round(min(8.0, float(np.median(deficits))), 1)}} if deficits else {}
        audible_title = ('Effects retain their intended level after group gain and speech ducking' if layered else
                         'Every effect is clearly audible next to your voice (within 3 dB of its level)')
        checks.append(Check('sound.audible', audible_title, len(quiet) <= len(effects) * .1,
                            value=_fmt(quiet) or 'all audible', fix=fix))
    else:
        checks.append(Check('sound.audible', 'Every effect is clearly audible next to your voice', True, hard=False,
                            value='not measured (run made before the evaluator)'))
    tiny = [Path(c['path']).name for c in cues if audible_span(c['path']) < .06]
    checks.append(Check('sound.not_tiny', 'No effect is a click too short to hear (< 60 ms)', not tiny,
                        value=_fmt(tiny) or 'none'))
    designed = [c for c in cues if c.get('source') != 'layer']     # words + whooshes/booms on edits
    if layered:
        designed = list({c.get('group_id') or str(c['target']): c for c in cues
                         if c['category'] != 'ambience'}.values())
    budget = plan.get('budget') or max(2, math.ceil(duration / every))
    gap = plan.get('gap', gap)
    checks.append(Check('sound.budget', (f'At most {budget} motivated action groups' if layered else
                                       f'Fewer, motivated sounds (at most {budget}, about one every {every:g} s)'),
                        len(designed) <= budget + 1, value=f'{len(designed)} sounds ({len(ai)} on words)',
                        fix={'sound': {'count_scale': .8}} if len(designed) > budget + 1 else {}))
    need = max(1, round(budget * .4))
    checks.append(Check('sound.enough', f'Not an empty mix (>= {need} sounds when there are real triggers)',
                        len(designed) >= need or not settings.get('effects', True), hard=False,
                        value=f'{len(designed)} sounds'))
    placed = sorted(designed, key=lambda c: c['target'])
    crowded = [f'{b["target"]:.1f}s' for a, b in zip(placed, placed[1:]) if b['target'] - a['target'] < gap - .02]
    if composed:
        seen=set();crowded=[]
        for c in cues:
            key=(c.get('group_id'),c.get('role'),c['path'],round(c['time'],3))
            if key in seen:crowded.append(f'duplicate layer at {c["time"]:.2f}s')
            seen.add(key)
    checks.append(Check('sound.spacing', 'Measured anchors can cluster; no duplicate layers' if composed else f'Action groups at least {gap:g} s apart' if layered else
                        f'Never two sounds within {gap:g} s', not crowded,
                        value=_fmt(crowded) or 'ok'))
    unmotivated = [f'{c["target"]:.1f}s "{c.get("word", "")}"' for c in ai
                   if c.get('line') and not word_in(c.get('word', ''), c['line'])]
    checks.append(Check('sound.motivated', 'Every speech layer is anchored to words really said in its line' if composed else 'Every speech sound lands on a word really said in its line', not unmotivated,
                        value=_fmt(unmotivated) or 'all motivated'))
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
    checks.append(Check('sound.sync', 'Each hit / whoosh / riser peaks at its planned landing (within 50 ms)' if composed else 'Each hit / whoosh / riser peaks on its word or cut (within 50 ms)',
                        not offbeat, value=_fmt(offbeat) or 'all in sync'))
    music = plan.get('music', [])
    if settings.get('music', True):
        covered = bool(music) and music[0]['start'] <= .1 and music[-1]['end'] >= duration - .15 and all(
            b['start'] - a['end'] <= .1 for a, b in zip(music, music[1:]))
        checks.append(Check('sound.music_cover', 'Music runs under the whole video', covered,
                            value=f'{len(music)} section(s)'))
        if form == 'short':
            checks.append(Check('sound.music_changes', 'At most 2 music sections in a Reel', len(music) <= 2,
                                value=str(len(music))))
        bed = measured_stems.get('music')
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
        editor=sound_stems.get('editor') or (sound_stems if sound_stems.get('mastering',{}).get('shared_master_gain') else None)
        if editor:
            native=np.zeros_like(master)
            for path,start in [(editor['voice'],0),*([(editor['music'],0)] if editor.get('music') else []),
                               *[(e['path'],round(e['start']*48000)) for e in editor.get('effects',[])]]:
                clip=read(path);count=min(clip.shape[1],native.shape[1]-start)
                native[:,start:start+count]+=clip[:,:count]
            native_peak=20*math.log10(max(float(np.abs(native).max()),1e-9))
            difference=float(np.max(np.abs(native-master)))
            checks.append(Check('sound.editor_ceiling','Editable sound layers retain master headroom',native_peak<=PEAK_CEILING+.05,value=f'{native_peak:.2f} dBFS'))
            checks.append(Check('sound.editor_match','Editable layers reconstruct the finished mix',difference<.001,value=f'maximum PCM difference {difference:.6f}'))
    limit = 1 if form == 'short' else 2
    checks.append(Check('sound.pull_back', f'Pull-back-and-punch used at most {limit}x',
                        len(plan.get('pull_backs', [])) <= limit, value=str(len(plan.get('pull_backs', [])))))
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


# ---- Smart Visuals ---------------------------------------------------------------------------------------------
def visuals_checks(folder, project):
    folder = Path(folder)
    slots = project.get('slots', [])
    if project.get('review_options'):
        options=[o for s in slots for o in s.get('options',[])]
        missing=[o.get('id') for o in options if not (folder/o.get('asset','')).is_file()]
        unchecked=[o.get('id') for o in options if (o.get('evaluation') or {}).get('passed') is not True]
        oversized=[s['index'] for s in slots if len(s.get('options',[]))>5]
        shortfalls=[s['label'] for s in slots if len(s.get('options',[]))<5]
        checks=[Check('visuals.references_files','All offered reference files were downloaded',not missing,value=_fmt(missing) or 'all found'),
            Check('visuals.references_vision','All offered references passed local identity and context checks',not unchecked,value=_fmt(unchecked) or 'all checked'),
            Check('visuals.references_limit','No keyword has more than five choices',not oversized,value=_fmt(oversized) or 'ok'),
            Check('visuals.references_coverage','Every keyword has five verified choices',bool(slots) and not shortfalls,
                hard=False,value=_fmt(shortfalls) or ('no named subjects' if not slots else 'five per keyword'))]
        for xml in folder.glob('VISUALS_SEQUENCE.xml'):checks+=check_xml(xml)
        return checks
    placed = [s for s in slots if s.get('clip')]
    duration = project['timeline']['duration']
    unchecked = [s['label'] for s in placed if (s.get('evaluation') or {}).get('passed') is None]
    failed = [s['label'] for s in placed if (s.get('evaluation') or {}).get('passed') is False]
    missing = [s['clip'] for s in placed if not (folder / s['clip']).is_file()]
    overlaps = []
    for display in ('fullscreen', 'popup'):
        same = sorted((s for s in placed if s.get('display') == display), key=lambda s: s['start'])
        overlaps += [f'{b["start"]:.1f}s' for a, b in zip(same, same[1:]) if b['start'] < a['end'] - 1e-3]
    outside = [s['label'] for s in placed if s['start'] < 0 or s['end'] > duration + .05 or s['end'] <= s['start']]
    lengths = [f'{s["label"]} {s["end"] - s["start"]:.1f}s' for s in placed if not .8 <= s['end'] - s['start'] <= 10]
    credits = folder / 'CREDITS.txt'
    text = credits.read_text(encoding='utf-8') if credits.is_file() else ''
    uncredited = [s['label'] for s in placed if s['label'] not in text]
    checks = [
        Check('visuals.evaluated', 'Every placed picture/video passed the vision check', not failed,
              value=_fmt(failed) or 'all passed'),
        Check('visuals.checked', 'Every placed picture/video was really looked at (vision model running)',
              not unchecked, hard=False, value=_fmt(unchecked) or 'all checked'),
        Check('visuals.files', 'All visual files exist', not missing, value=_fmt(missing) or 'all found'),
        Check('visuals.no_overlap', 'Visuals of the same kind never overlap', not overlaps, value=_fmt(overlaps) or 'none'),
        Check('visuals.inside', 'Every visual is inside the video', not outside, value=_fmt(outside) or 'ok'),
        Check('visuals.length', 'Each visual stays 0.8-10 s (readable, not stuck)', not lengths, hard=False,
              value=_fmt(lengths) or 'ok'),
        Check('visuals.credits', 'CREDITS.txt names every visual used (licence / attribution)', not uncredited,
              value=_fmt(uncredited) or 'all credited'),
        Check('visuals.found', 'Most planned moments got a real visual (>= 50%)',
              not slots or len(placed) / len(slots) >= .5, hard=False, value=f'{len(placed)}/{len(slots)} placed'),
    ]
    for xml in folder.glob('VISUALS_SEQUENCE.xml'):
        checks += check_xml(xml)
    return checks


# ---- Long to Shorts -------------------------------------------------------------------------------------------
def _probe_short(path):
    import av
    try:
        with av.open(str(path)) as c:
            v = c.streams.video[0] if c.streams.video else None
            return {'width': v.codec_context.width if v else 0, 'height': v.codec_context.height if v else 0,
                    'audio': bool(c.streams.audio), 'seconds': float(c.duration or 0) / av.time_base}
    except Exception:
        return None


def shorts_checks(folder, project):
    from hinglish_shorts.find import CALLS_TO_ACTION, CONNECTORS, ENDS_OPEN, GENERIC_TITLES
    folder = Path(folder)
    settings = project['settings']
    shorts = project.get('shorts', [])
    words = [(t, s, e) for t, s, e in project.get('words', [])]
    lo, hi = settings['min_length'], settings['max_length']
    lengths, cut_words, overlaps, hooks, ends, titles, ctas, files, formats = [], [], [], [], [], [], [], [], []

    def said(s, e):
        return [w for w in words if s <= (w[1] + w[2]) / 2 < e]
    for sh in shorts:
        label = f'#{sh["index"]}'
        seconds = sum(e - s for s, e in sh['pieces'])
        if not sh.get('added') and not lo - 1.6 <= seconds <= hi + 1.6:
            lengths.append(f'{label} {seconds:.0f}s')
        for s, e in sh['pieces']:
            for edge in (s, e):
                inside = [w for w in words if w[1] + .03 < edge < w[2] - .03]
                if inside:
                    cut_words.append(f'{label} "{inside[0][0]}" at {edge:.2f}s')
        first = said(*sh['pieces'][0])
        if first and first[0][0].lower().strip('.,!?') in CONNECTORS and not sh.get('added'):
            hooks.append(f'{label} "{first[0][0]}"')
        last = said(*sh['pieces'][-1])
        if last and last[-1][0].lower().strip('.,!?') in ENDS_OPEN and not sh.get('added'):
            ends.append(f'{label} "{last[-1][0]}"')
        title = str(sh.get('shown_title') or sh.get('title') or '')
        if not 2 <= len(title.split()) <= 12 or title.lower() in GENERIC_TITLES:
            titles.append(f'{label} "{title}"')
        text = ' '.join(w[0] for s, e in sh['pieces'] for w in said(s, e)).lower()
        if any(c in text for c in CALLS_TO_ACTION):
            ctas.append(label)
        for key in ('mp4', 'xml'):
            if not sh.get(key) or not (folder / sh[key]).is_file():
                files.append(f'{label} {key}')
        facts = _probe_short(folder / sh['mp4']) if sh.get('mp4') and (folder / sh['mp4']).is_file() else None
        if facts and (facts['width'], facts['height']) != (1080, 1920) or facts and not facts['audio'] or \
                facts and abs(facts['seconds'] - seconds) > .25:
            formats.append(f'{label} {facts["width"]}x{facts["height"]} {facts["seconds"]:.1f}s'
                           f'{"" if facts["audio"] else " no sound"}')
    for i, a in enumerate(shorts):
        for b in shorts[i + 1:]:
            common = sum(max(0.0, min(e1, e2) - max(s1, s2)) for s1, e1 in a['pieces'] for s2, e2 in b['pieces'])
            shortest = min(sum(e - s for s, e in a['pieces']), sum(e - s for s, e in b['pieces']))
            if shortest and common / shortest > .3:
                overlaps.append(f'#{a["index"]} and #{b["index"]}')
    video_minutes = project['video']['duration'] / 60
    from hinglish_shorts.settings import COUNT_PER_MINUTE
    count = str(settings.get('count', 'medium'))
    wanted = int(count) if count.isdigit() else max(1, round(video_minutes * COUNT_PER_MINUTE.get(count, .5)))
    few = len(shorts) < max(1, round(wanted * .6))
    checks = [
        Check('shorts.found', 'At least one short was made', bool(shorts), value=f'{len(shorts)} shorts'),
        Check('shorts.count', f'About as many shorts as asked ({wanted})', not few, hard=False,
              value=f'{len(shorts)} of {wanted}',
              fix={'shorts': {'count_scale': 1.4}, 'feedback': [
                  f'Only {len(shorts)} of {wanted} shorts: give every good hook moment in each part, not only the best one.']}
              if few else {}),
        Check('shorts.length', f'Every short is {lo:.0f}-{hi:.0f} s', not lengths, value=_fmt(lengths) or 'all ok'),
        Check('shorts.whole_words', 'No cut inside a word (start and end fall between words)', not cut_words,
              value=_fmt(cut_words) or 'all clean'),
        Check('shorts.no_overlap', 'No two shorts are about the same moment', not overlaps, value=_fmt(overlaps) or 'none'),
        Check('shorts.hook_start', 'Every short starts on a hook, not on "aur / toh / so / but"', not hooks,
              value=_fmt(hooks) or 'all ok',
              fix={'feedback': ['Some shorts started on a connector word (' + _fmt(hooks) + '): start on the hook line.']}
              if hooks else {}),
        Check('shorts.complete_end', 'Every short ends on a finished thought', not ends, hard=False,
              value=_fmt(ends) or 'all ok'),
        Check('shorts.titles', 'Every short has a real 2-12 word title', not titles, value=_fmt(titles) or 'all ok'),
        Check('shorts.no_cta', 'No short is a like / subscribe / sponsor part', not ctas, value=_fmt(ctas) or 'none'),
        Check('shorts.files', 'Every short has its MP4 and its editable sequence', not files, value=_fmt(files) or 'all found'),
        Check('shorts.format', 'Every MP4 is 1080x1920 with sound and the planned length', not formats,
              value=_fmt(formats) or 'all ok'),
    ]
    for sh in shorts:
        if sh.get('xml') and (folder / sh['xml']).is_file():
            checks += check_xml(folder / sh['xml'])
    return checks


# ---- AI Images / AI Video -------------------------------------------------------------------------------------------
def aigen_checks(folder, project):
    """Rules for both tools (each has its own project file and report)."""
    from PIL import Image
    from hinglish_aigen.pipeline import chosen_file
    from hinglish_aigen.plan import _names, names_in
    from hinglish_aigen.settings import SIZES
    folder = Path(folder)
    kind = project.get('kind', 'image')
    moments = [m for m in project.get('moments', []) if not m.get('removed')]
    names = _names(project.get('entities') or {})
    missing, failed, unchecked, named, sizes, errors, no_clip = [], [], [], [], [], [], []
    for m in moments:
        label = f'#{m["index"]}'
        file = chosen_file(m)
        if not file:
            errors.append(label)
            continue
        if not (folder / file).is_file():
            missing.append(label)
            continue
        video = m.get('video') or {}
        if kind == 'video':
            if not video.get('file') or video.get('error'):
                no_clip.append(label)
            verdict = video.get('verdict')
        else:
            verdict = next((o for o in m.get('options', []) if o['id'] == m.get('chosen')), {}).get('verdict')
        if verdict is None and project.get('evaluator', 'off') != 'off':
            unchecked.append(label)
        elif verdict is not None and not verdict.get('passed'):
            failed.append(f'{label} ({"; ".join(verdict.get("reasons", []))[:60]})')
        found = names_in(m.get('prompt', '') + ' ' + m.get('motion', ''), names)
        if found:
            named.append(f'{label} "{found[0]}"')
        if file.endswith('.png'):
            try:
                with Image.open(folder / file) as im:
                    want = SIZES[project.get('aspect', '16:9')]
                    if abs(im.width / im.height - want[0] / want[1]) > .05:
                        sizes.append(f'{label} {im.width}x{im.height}')
            except Exception:
                missing.append(label)
    what = 'picture' if kind == 'image' else 'clip'
    checks = [
        Check(f'ai{kind}.found', f'At least one {what} was made', bool(moments) and len(errors) < len(moments),
              value=f'{len(moments) - len(errors)} of {len(moments)}'),
        Check(f'ai{kind}.made', f'Every moment got its {what} (no GPU errors)', not errors and not no_clip,
              value=_fmt(errors + no_clip) or 'all made'),
        Check(f'ai{kind}.files', f'Every chosen {what} exists', not missing, value=_fmt(missing) or 'all found'),
        Check(f'ai{kind}.passed', f'Every chosen {what} passed the vision check', not failed, hard=False,
              value=_fmt(failed) or 'all passed',
              fix={'feedback': ['Some results failed the vision check (' + _fmt(failed) + '): write simpler, more '
                                'concrete prompts with one clear subject' + (' and one simple movement' if kind == 'video' else '') + '.']}
              if failed else {}),
        Check(f'ai{kind}.checked', f'Every {what} was really looked at (vision model running)', not unchecked, hard=False,
              value=_fmt(unchecked) or 'all checked'),
        Check(f'ai{kind}.no_real_names', 'No prompt names a real person or brand', not named, value=_fmt(named) or 'none'),
        Check(f'ai{kind}.format', 'Pictures have the right shape (16:9 / 9:16 / 1:1)', not sizes, value=_fmt(sizes) or 'all ok'),
    ]
    if project.get('xml') and (folder / project['xml']).is_file():
        checks += check_xml(folder / project['xml'])
    return checks

def motion_checks(folder, project):
    """Motion Graphics: every graphic rendered and readable, only numbers that were said, the full video complete."""
    import av
    from hinglish_motion.plan import NUMBER_FIELDS, has_number
    from hinglish_motion.creative import TEMPLATES as creative_templates, STYLES as creative_styles
    folder = Path(folder)
    scenes = sorted((s for s in project.get('scenes', []) if not s.get('removed')), key=lambda s: s['start'])
    lines = {l['id']: l['text'] for l in project.get('lines', [])}
    missing, layout, invented, sizes, overlaps = [], [], [], [], []
    for s in scenes:
        label = f'#{s["index"]} {s["template"]}'
        if not s.get('file') or not (folder / s['file']).is_file() or not s.get('still') or not (folder / s['still']).is_file():
            missing.append(label)
        elif not ((s['mode'] == 'overlay') == s['file'].endswith('.mov')):
            sizes.append(f'{label} wrong file type')
        else:
            try:
                with av.open(str(folder / s['file'])) as c:
                    v = c.streams.video[0]
                    if (v.width, v.height) != (project['width'], project['height']):
                        sizes.append(f'{label} {v.width}x{v.height}')
            except Exception:
                missing.append(label)
        if s.get('layout'):
            layout.append(f'{label}: {s["layout"][0]}')
        said = ' '.join(lines.get(i, '') for i in (s['line'], s['line'] + 1))
        shown = [s['data'].get(f) for f in NUMBER_FIELDS if s['data'].get(f)]
        if shown and not has_number(said):
            invented.append(f'{label} "{shown[0]}"')
    for a, b in zip(scenes, scenes[1:]):
        if a['start'] + a['duration'] > b['start'] + .05:
            overlaps.append(f'#{a["index"]}/#{b["index"]}')
    counts = {}
    for s in scenes:
        counts[s['template']] = counts.get(s['template'], 0) + 1
    same = max(counts.values()) if counts else 0
    checks = [
        Check('motion.found', 'At least one motion graphic was made', bool(scenes), value=f'{len(scenes)} graphics'),
        Check('motion.files', 'Every graphic has its video file and preview', not missing, value=_fmt(missing) or 'all found'),
        Check('motion.format', 'Every graphic matches the timeline size (cards are transparent .mov)', not sizes,
              value=_fmt(sizes) or 'all ok'),
        Check('motion.layout', 'All text fits inside its box and the frame', not layout, value=_fmt(layout) or 'all fit',
              fix={'feedback': ['Some text did not fit (' + _fmt(layout) + '): write shorter titles and labels.']} if layout else {}),
        Check('motion.no_invented_numbers', 'Every number shown is said in that line', not invented,
              value=_fmt(invented) or 'none invented',
              fix={'feedback': ['Numbers were shown that are not said (' + _fmt(invented) + '): only show numbers from the line.']}
              if invented else {}),
        Check('motion.no_overlap', 'No two graphics are on screen at the same time', not overlaps, value=_fmt(overlaps) or 'none'),
        Check('motion.variety', 'Template variety follows the selected style', project.get('style') in creative_styles or len(scenes) < 4 or same <= max(2, len(scenes) // 2),
              hard=False, value=', '.join(f'{k} x{v}' for k, v in sorted(counts.items(), key=lambda x: -x[1])[:4]),
              fix={'feedback': ['Use a wider variety of templates (big_number, versus, stamp, list, quote...).']}),
    ]
    # Explicit typography/procedural styles do not require stock photos. Retain
    # the original picture requirement for every ordinary asset-based scene.
    asset_scenes = [s for s in scenes if s['template'] not in creative_templates]
    pictured = [s for s in asset_scenes if s.get('assets')]
    lost = [f'#{s["index"]}' for s in scenes for a in s.get('assets') or [] if not (folder / a.get('file', '-')).is_file()]
    if asset_scenes:
        checks.append(
        Check('motion.pictures', 'Motion graphics are built from pictures (cut-outs, photos, clips), not only text',
              len(pictured) >= .5 * len(asset_scenes), value=f'{len(pictured)} of {len(asset_scenes)} asset-based scenes',
              fix={'feedback': ['Too many scenes were only text: build them from real people, objects, photos and clips.']}))
    checks += [
        Check('motion.asset_files', 'Every picture a scene uses exists', not lost, value=_fmt(lost) or 'all found'),
    ]
    if project.get('full') or project.get('standalone'):
        problem = ''
        target = folder / (project.get('standalone_file') or 'MOTION_GRAPHICS.mp4')
        if not target.is_file():
            problem = 'missing'
        else:
            try:
                with av.open(str(target)) as c:
                    v = c.streams.video[0]
                    seconds = float(v.frames / v.average_rate) if v.frames else float(c.duration or 0) / 1e6
                    if abs(seconds - project['seconds']) > .25:
                        problem = f'{seconds:.1f} s of {project["seconds"]:.1f} s'
                    elif project.get('timeline') and not c.streams.audio:
                        problem = 'no sound'
            except Exception as error:
                problem = str(error)[:80]
        checks.append(Check('motion.standalone', 'MOTION_GRAPHICS.mp4 covers the whole video' +
                            (' with your voice' if project.get('timeline') else ''), not problem, value=problem or 'complete'))
    if project.get('xml') and (folder / project['xml']).is_file():
        checks += check_xml(folder / project['xml'])
    return checks

# ---- Finding and running the right spec ------------------------------------------------------------------------
def script_checks(folder, project):
    folder=Path(folder)
    rows=project.get('rows',[])
    placed=sum(bool(r.get('selected')) for r in rows)
    title=('All script requirements have a confirmed source passage' if placed==len(rows) and rows
           else f'{len(rows)-placed} script requirements still need a source match' if rows
           else 'No spoken script requirements were found')
    checks=[Check('script.coverage',title,
                  bool(rows) and placed==len(rows),value=f'{placed}/{len(rows)} placed',
                  detail='Unmatched requirements remain absent from the draft; review the source matches before continuing.'),
            Check('script.sources','All supplied source videos were analyzed',not project.get('errors'),
                  value=str(project.get('errors') or 'complete'))]
    xml=folder/'EDITED_SEQUENCE.xml'
    checks+=check_xml(xml) if xml.is_file() else [Check('script.timeline','Edited timeline exists',False)]
    return checks


PLANS = [('motion-project.json', 'motion', motion_checks), ('aiimage-project.json', 'aiimage', aigen_checks), ('aivideo-project.json', 'aivideo', aigen_checks),
         ('shorts-project.json', 'shorts', shorts_checks), ('sound-plan.json', 'sound', sound_checks), ('visuals-project.json', 'visuals', visuals_checks), ('zoom-plan.json', 'zoom', zoom_checks),
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
            if name=='report.json' and data.get('kind')=='assemble':
                feature,spec='script',script_checks
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
