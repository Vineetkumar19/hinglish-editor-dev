"""Find the shorts: the local AI reads the long video in parts and picks hook -> payoff moments; hard rules
check every answer (asked again with the exact problems, then repaired by the rules), and the best
non-overlapping moments are kept."""
from dataclasses import asdict, dataclass, field
import re

from hinglish_broll.phrases import build_phrases
from hinglish_eval import guard
from hinglish_eval.guard import Problem

from .settings import WINDOW_OVERLAP, WINDOW_SECONDS

# A short never starts on a word that continues an earlier thought.
CONNECTORS = {'aur', 'toh', 'to', 'so', 'and', 'but', 'lekin', 'par', 'magar', 'matlab', 'yaani', 'kyunki',
              'because', 'isliye', 'phir', 'fir', 'then', 'or', 'ya', 'also', 'plus', 'waise', 'ki', 'ke', 'ka',
              'ko', 'se', 'hai', 'tha', 'thi', 'the', 'hain', 'bhi', 'na', 'haan', 'okay', 'ok', 'uh', 'um'}
ENDS_OPEN = {'aur', 'and', 'but', 'lekin', 'ki', 'ke', 'ka', 'ko', 'se', 'toh', 'to', 'jo', 'jab', 'agar', 'kyunki',
             'because', 'the', 'a', 'an', 'of', 'in', 'par', 'mein', 'ne'}
CALLS_TO_ACTION = ('subscribe', 'bell icon', 'like kar', 'like karo', 'comment kar', 'comment box', 'channel ko',
                   'description mein', 'link in', 'sponsor')
LOOKS_BACK = ('jaise maine', 'maine pehle', 'as i said', 'pehle bataya', 'upar bataya', 'pichle video', 'last video')
PAD_IN, PAD_OUT = .12, .30          # breathing room before the first and after the last word of a piece
GENERIC_TITLES = {'highlight', 'short', 'video', 'clip', 'untitled', 'title'}


@dataclass
class Short:
    title: str
    pieces: list                    # [(start, end)] seconds in the long video, in time order
    lines: list                     # [(first_line_id, last_line_id)] per piece
    why: str = ''
    hook: str = ''
    score: float = 0.0
    text: str = ''
    part: int = 0                   # which 5-minute part the AI found it in

    @property
    def duration(self):
        return sum(e - s for s, e in self.pieces)

    def to_dict(self):
        return {**asdict(self), 'pieces': [list(p) for p in self.pieces], 'lines': [list(p) for p in self.lines],
                'duration': round(self.duration, 2)}


def _clock(seconds):
    m, s = divmod(int(max(0, seconds)), 60)
    return f'{m}:{s:02d}'


def _words_of(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def make_lines(words, start=None, end=None):
    """Sentence-sized lines (the AI picks by line id); only lines inside the From-To range."""
    lines = build_phrases(words, pause=.5, max_words=22, max_seconds=9.0)
    if start is not None:
        lines = [l for l in lines if l.start >= start - .05]
    if end is not None:
        lines = [l for l in lines if l.end <= end + .05]
    from hinglish_broll.phrases import Phrase
    return [Phrase(i, l.start, l.end, l.text) for i, l in enumerate(lines)]


def snap(words, first_line, last_line, source_duration=None):
    """(start, end) of a run of lines, cut in the gaps between words (never inside a word)."""
    if source_duration is not None and not 0 <= first_line.start < last_line.end <= source_duration:
        raise ValueError('Selected speech falls outside the source video')
    inside = [i for i, w in enumerate(words) if first_line.start - 1e-3 <= w.start and w.end <= last_line.end + 1e-3]
    if not inside:
        return first_line.start, last_line.end
    a, b = inside[0], inside[-1]
    start = words[a].start - PAD_IN
    if a > 0:
        start = max(start, (words[a - 1].end + words[a].start) / 2)
    end = words[b].end + PAD_OUT
    if b + 1 < len(words):
        end = min(end, (words[b].end + words[b + 1].start) / 2)
    return max(0.0, start), min(end,source_duration) if source_duration is not None else end


def cap_padding(words,pieces,maximum):
    """Enforce the export cap by removing breathing room, never spoken words."""
    result=[list(p) for p in pieces];excess=sum(e-s for s,e in result)-maximum
    if excess<=0:return [tuple(p) for p in result]
    for piece in reversed(result):
        inside=[w for w in words if piece[0]-1e-6<=w.start and w.end<=piece[1]+1e-6]
        if not inside:continue
        shave=min(excess,max(0,piece[1]-inside[-1].end));piece[1]-=shave;excess-=shave
        shave=min(excess,max(0,inside[0].start-piece[0]));piece[0]+=shave;excess-=shave
        if excess<=1e-6:break
    if excess>1e-6:raise ValueError('The selected spoken moment exceeds the maximum Short duration; choose a shorter complete moment.')
    return [tuple(p) for p in result]


def windows(lines, size=WINDOW_SECONDS, overlap=WINDOW_OVERLAP):
    """Overlapping parts of about `size` seconds (by line time)."""
    if not lines:
        return []
    parts, begin = [], lines[0].start
    last = lines[-1].end
    while True:
        part = [l for l in lines if l.start >= begin - 1e-3 and l.end <= begin + size + 1e-3]
        if part:
            parts.append(part)
        if begin + size >= last:
            break
        begin += size - overlap
    return parts


SUMMARY_SYSTEM = '''You read the transcript of a long Hinglish (Hindi + English) YouTube video.
Say in English what the whole video is about (topic), who it is for (audience), and list its main points,
in order, one short sentence each. Use the real names said in the video.'''
SUMMARY_SCHEMA = {'type': 'object', 'properties': {
    'topic': {'type': 'string'}, 'audience': {'type': 'string'},
    'main_points': {'type': 'array', 'items': {'type': 'string'}}},
    'required': ['topic', 'audience', 'main_points']}

PICK_SYSTEM = '''You are a top short-form video editor for a Hinglish YouTube creator. You get one part of
a long video as a transcript: one line per sentence, "[id] time (seconds) text". Pick the moments that work best as standalone
YouTube Shorts / Instagram Reels of {min_len:.0f}-{max_len:.0f} seconds.

A great short:
- STARTS WITH A HOOK: a surprising fact, a bold claim, a question, a conflict, a big number, an emotional
  moment or a strong "story begins" line. Never start on a word that continues an earlier sentence
  (aur, toh, so, and, but, lekin, matlab, kyunki, phir, ki, ke...) or in the middle of a thought.
- MAKES SENSE ALONE to someone who never saw the long video (no "jaise maine pehle bataya", no
  unexplained he/she/woh/usne that points to something earlier).
- HAS A PAYOFF: it ends on the answer, the result, the punchline or a strong closing line: a finished
  thought, never mid-sentence.
- Is about ONE topic.

A short is 1 to {pieces} pieces. A piece is a run of consecutive lines [first_id, last_id]. Join pieces only
to cut a boring middle out of the same story (for example the hook line + the answer a bit later); pieces are
in time order and never overlap. Lines that follow each other are ONE piece ([4, 12], not [4, 6], [7, 12]):
use a second piece only when you skip lines in between. Two shorts never share lines. The total of the pieces' seconds must be {min_len:.0f}-{max_len:.0f}.
Skip the intro, the outro, sponsor reads and "like / subscribe / comment" requests.

For each short give:
- title: 3-8 words, the curiosity hook for a Shorts title, in the viewer's language (English or Hinglish in
  Roman letters). It must be TRUE to what is said: never put two people/teams together that the line
  compares or opposes (if Rohit did in 10 years what took Dhoni 16, the title is about Rohit beating Dhoni's
  time, not "Rohit & Dhoni"). Prefer the surprising fact or question over a chapter name ("MI's 2014 season").
  No emojis, no hashtags.
- why: one sentence: why a stranger keeps watching and what the payoff is.
- score: 1-10, honest: how likely a stranger watches to the end and shares it.
Give up to {count} shorts from this part, best first. Give fewer (or none) if this part has no strong moment:
a weak short is worse than no short. Titles already used in other parts are listed: do not repeat those moments.'''


def pick_schema(count, line_ids=None):
    line_schema={'type':'integer'}
    if line_ids is not None:line_schema['enum']=sorted(set(line_ids))
    return {'type': 'object', 'additionalProperties':False, 'properties': {'shorts': {'type': 'array', 'maxItems': count, 'items': {
        'type': 'object', 'additionalProperties':False, 'properties': {
            'why': {'type': 'string','pattern':r'^[^\r\n]{1,240}$'},
            'title': {'type': 'string','pattern':r'^[^\r\n]{1,100}$'},
            'pieces': {'type': 'array', 'minItems': 1, 'maxItems': 3,
                       'items': {'type': 'array', 'minItems': 2, 'maxItems': 2, 'items': line_schema}},
            'score': {'type': 'integer','enum':list(range(1,11))}},
        'required': ['why', 'title', 'pieces', 'score']}}}, 'required': ['shorts']}


def transcript(part):
    """Compact numbered lines for the AI: "[12] 3:05 (4.2s) the words"."""
    return '\n'.join(f'[{l.id}] {_clock(l.start)} ({l.end - l.start:.1f}s) {l.text}' for l in part)


def length_help(part, settings):
    """Models are bad at adding up seconds: say how many lines a short of the right length usually is."""
    average = sum(l.end - l.start for l in part) / max(1, len(part))
    low, high = max(1, round(settings.min_length / average)), max(1, round(settings.max_length / average))
    return (f'Lines here are about {average:.1f}s each, so one {settings.min_length:.0f}-{settings.max_length:.0f}s '
            f'short is about {low}-{high} lines in total. Add up the (seconds) of your lines before answering.')


def _pieces_of(raw):
    out = []
    for p in raw.get('pieces') or []:
        if isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(x, int) for x in p):
            out.append((int(p[0]), int(p[1])))
        else:
            out.append(None)
    return out


def _length(pieces, by_id, words):
    return sum(snap(words, by_id[a], by_id[b])[1] - snap(words, by_id[a], by_id[b])[0] for a, b in pieces)


def _text(pieces, by_id):
    return ' … '.join(' '.join(by_id[i].text for i in range(a, b + 1)) for a, b in pieces)


def _first_word(text):
    words = _words_of(text)
    return words[0] if words else ''


def _problems(raw, ids, by_id, words, settings):
    """Hard / soft problems of one short (raw AI answer), by rule."""
    problems = []
    title = str(raw.get('title') or '').strip()
    pieces = _pieces_of(raw)
    label = f'"{title[:40] or "untitled"}"'
    if not pieces or None in pieces:
        return [Problem('shorts.pieces', f'{label}: pieces must be [first_id, last_id] pairs of line ids')]
    if len(pieces) > settings.pieces:
        problems.append(Problem('shorts.pieces', f'{label}: at most {settings.pieces} piece(s) per short'))
    for a, b in pieces:
        if a not in ids or b not in ids:
            return problems + [Problem('shorts.ids', f'{label}: line ids {a}-{b} are not in this part')]
        if b < a:
            return problems + [Problem('shorts.order', f'{label}: a piece ends before it starts ({a}-{b})')]
    for (a1, b1), (a2, b2) in zip(pieces, pieces[1:]):
        if a2 <= b1:
            problems.append(Problem('shorts.order', f'{label}: pieces must be in time order and not overlap'))
    if problems:
        return problems
    seconds = _length(pieces, by_id, words)
    if not settings.min_length - 1.5 <= seconds <= settings.max_length + 1.5:
        problems.append(Problem('shorts.length', f'{label} is {seconds:.0f}s: it must be {settings.min_length:.0f}-'
                                                 f'{settings.max_length:.0f}s (add or remove lines)'))
    first = _first_word(by_id[pieces[0][0]].text)
    if first in CONNECTORS:
        problems.append(Problem('shorts.hook_start', f'{label} starts with "{first}", which continues an earlier '
                                                     'thought: start on the hook line'))
    text = _text(pieces, by_id).lower()
    cta = [c for c in CALLS_TO_ACTION if c in text]
    if cta:
        problems.append(Problem('shorts.no_cta', f'{label} contains "{cta[0]}" (a like/subscribe/sponsor part)'))
    if not 2 <= len(title.split()) <= 12 or title.lower().strip(' .!') in GENERIC_TITLES:
        problems.append(Problem('shorts.title', f'{label}: give a real 3-8 word title'))
    last = _words_of(by_id[pieces[-1][1]].text)
    if last and last[-1] in ENDS_OPEN:
        problems.append(Problem('shorts.complete_end', f'{label} ends on "{last[-1]}" (mid-sentence): end on the '
                                                       'finished thought', hard=False))
    back = [b for b in LOOKS_BACK if b in text]
    if back:
        problems.append(Problem('shorts.alone', f'{label} says "{back[0]}": it must make sense alone', hard=False))
    if not isinstance(raw.get('score'), int) or not 1 <= raw['score'] <= 10:
        problems.append(Problem('shorts.score', f'{label}: score must be 1-10', hard=False))
    return problems


def plan_rules(part, words, settings):
    ids = {l.id for l in part}
    by_id = {l.id: l for l in part}

    def checker(answer):
        if not isinstance(answer,dict) or not isinstance(answer.get('shorts'),list):
            return [Problem('shorts.answer','Return the required shorts array; a missing model answer is not an empty selection.')]
        found = []
        for raw in (answer or {}).get('shorts') or []:
            found += _problems(raw, ids, by_id, words, settings)
        return found
    return checker


def plan_repair(part, words, settings):
    """What the model could not fix, the rules fix: trim/extend to the length range, skip a connector
    start, drop what still breaks a hard rule."""
    ids = sorted(l.id for l in part)
    by_id = {l.id: l for l in part}

    def fix(raw):
        pieces = _pieces_of(raw)
        if not pieces or None in pieces or any(a not in by_id or b not in by_id or b < a for a, b in pieces):
            return None
        pieces = sorted(pieces)[:settings.pieces]
        merged = [pieces[0]]
        for a, b in pieces[1:]:
            if a <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        pieces = merged
        # skip connector / call-to-action lines at the start while the short stays long enough
        while (_first_word(by_id[pieces[0][0]].text) in CONNECTORS and pieces[0][0] < pieces[0][1]
               and _length([(pieces[0][0] + 1, pieces[0][1])] + pieces[1:], by_id, words) >= settings.min_length):
            pieces[0] = (pieces[0][0] + 1, pieces[0][1])
        # too long: drop lines from the end
        while _length(pieces, by_id, words) > settings.max_length + 1.5:
            a, b = pieces[-1]
            if b > a:
                pieces[-1] = (a, b - 1)
            elif len(pieces) > 1:
                pieces.pop()
            else:
                return None
        # too short: add the lines that follow the last piece (the payoff usually comes right after)
        while _length(pieces, by_id, words) < settings.min_length - 1.5:
            a, b = pieces[-1]
            if b + 1 in by_id and b + 1 <= ids[-1]:
                pieces[-1] = (a, b + 1)
            elif pieces[0][0] - 1 in by_id and _first_word(by_id[pieces[0][0] - 1].text) not in CONNECTORS:
                pieces[0] = (pieces[0][0] - 1, pieces[0][1])
            else:
                return None
            if _length(pieces, by_id, words) > settings.max_length + 1.5:
                return None
        title = str(raw.get('title') or '').strip()
        if not 2 <= len(title.split()) <= 12 or title.lower() in GENERIC_TITLES:
            title = ' '.join(_words_of(by_id[pieces[0][0]].text)[:6]).capitalize() or 'Highlight'
        return {**raw, 'pieces': [list(p) for p in pieces], 'title': title}

    def repair(answer):
        if not isinstance(answer,dict) or not isinstance(answer.get('shorts'),list):return answer,[]
        kept, fixes = [], []
        for raw in (answer or {}).get('shorts') or []:
            if not [p for p in _problems(raw, set(ids), by_id, words, settings) if p.hard]:
                kept.append(raw)
                continue
            fixed = fix(raw)
            if fixed is not None and not [p for p in _problems(fixed, set(ids), by_id, words, settings) if p.hard]:
                kept.append(fixed)
                fixes.append(f'fixed "{str(raw.get("title"))[:40]}"')
            else:
                fixes.append(f'dropped "{str(raw.get("title"))[:40]}"')
        return {**(answer or {}), 'shorts': kept}, fixes
    return repair


def join_touching(pieces):
    """[0,1] + [2,6] is one continuous run of lines: keep it as one clip (no tiny cut between sentences)."""
    joined = []
    for a, b in sorted(pieces):
        if joined and a <= joined[-1][1] + 1:
            joined[-1] = (joined[-1][0], max(b, joined[-1][1]))
        else:
            joined.append((a, b))
    return joined


def _overlap(a, b):
    """Share of the shorter short that is also in the other one."""
    common = sum(max(0.0, min(e1, e2) - max(s1, s2)) for s1, e1 in a.pieces for s2, e2 in b.pieces)
    return common / max(1e-6, min(a.duration, b.duration))


def select(candidates, target, max_overlap=.15):
    """Best first, never two shorts about the same moment; returned in video order."""
    chosen = []
    for c in sorted(candidates, key=lambda c: (-c.score, c.pieces[0][0])):
        if len(chosen) >= target:
            break
        if all(_overlap(c, k) <= max_overlap for k in chosen):
            chosen.append(c)
    return sorted(chosen, key=lambda c: c.pieces[0][0])


def available_parts(lines, words, settings, excluded, source_duration):
    """Keep contiguous unused speech; a removed line must never be joined across."""
    runs, run = [], []
    for line in lines:
        start, end = snap(words, line, line, source_duration)
        blocked = any(min(end, b) > max(start, a) for a, b in excluded)
        if blocked or (run and line.id != run[-1].id + 1):
            if run: runs.append(run)
            run = []
        if not blocked: run.append(line)
    if run: runs.append(run)
    return [part for run in runs for part in windows(run)
            if part[-1].end - part[0].start >= settings.min_length - 1.5]


def find_shorts(brain, words, settings, progress=print, script='', scale=1.0,
                source_duration=None,max_overlap=.15,excluded=()):
    """-> (shorts, summary, lines). `scale` comes from the quality check (fewer / more shorts next time)."""
    lines = make_lines(words, settings.start, settings.end)
    if source_duration is not None:
        # Unavailable speech cannot become a candidate. Only optional breathing
        # room may be capped; never trim a selected spoken word to fit the file.
        lines=[line for line in lines if 0<=line.start<line.end<=source_duration]
    if not lines:
        raise ValueError('No speech was found in this video (or in the chosen From-To part)')
    span = lines[-1].end - lines[0].start
    target = settings.target(span, scale)
    from hinglish_niche.profiles import current_profile
    gaming=current_profile()=='gaming'
    think = settings.device == 'cuda' and not gaming
    text = ' '.join(l.text for l in lines)
    from hinglish_cut.feature_context import limits
    feature=getattr(brain,'context_feature',None)
    expanded=bool(isinstance(feature,str) and getattr(brain,'root',None) and limits(brain.root,feature))
    if len(text) > 12000 and not expanded:
        third = 4000
        middle = len(text) // 2
        text = text[:third] + ' ... ' + text[middle - third // 2: middle + third // 2] + ' ... ' + text[-third:]
    progress('Local AI is reading the whole video')
    summary_data = {'transcript': text}
    if script.strip():
        from hinglish_visuals.script import script_context
        summary_data['creator_script'] = script_context(script)
    def summary_rules(answer):
        return [] if isinstance(answer,dict) and all(k in answer for k in SUMMARY_SCHEMA['required']) else [
            Problem('shorts.summary','Return topic, audience and main_points; an unfinished model response is not a summary.')]
    if expanded:
        from hinglish_cut.source_context import complete_summary
        summary_data['transcript']=complete_summary(brain, text, progress)
    summary = guard.ask_checked(brain.json, SUMMARY_SYSTEM, summary_data, SUMMARY_SCHEMA, summary_rules,
                                label='video summary', feature='shorts', progress=progress, max_tokens=700,**({'think':False} if gaming else {}))
    if summary_rules(summary):raise ValueError('The local model returned no complete video summary. No empty selection was accepted.')
    progress(f'  Topic: {summary.get("topic", "")}')
    shorts = []
    for attempt in range(3):
        blocked = list(excluded) + [p for short in shorts for p in short.pieces]
        parts = available_parts(lines, words, settings, blocked, source_duration)
        if not parts or len(shorts) >= target: break
        missing = target - len(shorts)
        per_part = max(2, min(8, (missing + len(parts) - 1) // len(parts) + 1))
        if attempt:
            progress(f'Looking for {missing} more complete, unused moment(s) ({len(shorts)}/{target} selected)')
        found = pick_candidates(brain, words, settings, summary, lines, parts, per_part,
                                progress, think, blocked, source_duration, attempt)
        shorts = select(shorts + found, target, max_overlap=max_overlap)
    progress(f'Chose {len(shorts)} short(s) (aim: {target})')
    return shorts, summary, lines


def pick_candidates(brain, words, settings, summary, lines, parts, per_part,
                    progress, think, excluded, source_duration, attempt=0):
    candidates, titles = [], []
    for n, part in enumerate(parts, 1):
        progress(f'Finding hook moments in part {n}/{len(parts)} ({_clock(part[0].start)}-{_clock(part[-1].end)})')
        data = {'video_topic': summary.get('topic', ''), 'video_main_points': summary.get('main_points', [])[:12],
                'part': f'{_clock(part[0].start)} to {_clock(part[-1].end)} of a {_clock(lines[-1].end)} video',
                'titles_already_used': titles[-30:],
                'length_help': length_help(part, settings),
                'transcript': transcript(part),
                'previously_used_source_seconds':list(excluded),
                'selection_rule':'Choose fresh moments outside the previously used source ranges.' if excluded else ''}
        system = PICK_SYSTEM.format(min_len=settings.min_length, max_len=settings.max_length,
                                    pieces=settings.pieces, count=per_part)
        repair = plan_repair(part, words, settings)

        def ask(system, payload, schema, **options):
            # lengths and connector starts are fixed by the rules straight away (models can't add up
            # seconds; asking again costs minutes): the model is only asked again for what rules can't fix
            answer, fixes = repair(brain.json(system, payload, schema, **options))
            if fixes:
                progress(f'  Rules adjusted {len(fixes)} pick(s) to the length range')
            return answer
        answer = guard.ask_checked(ask, system, data, pick_schema(per_part,[line.id for line in part]),
                                   plan_rules(part, words, settings), label=f'shorts pass {attempt+1} part {n}', feature='shorts',
                                   progress=progress, repair=repair, max_tokens=2200, think=think)
        if not isinstance(answer,dict) or not isinstance(answer.get('shorts'),list):
            raise ValueError('The local model returned no complete clip selections. This is not a finding that the video has no suitable moments.')
        by_id = {l.id: l for l in part}
        checker = plan_rules(part, words, settings)
        for raw in answer.get('shorts') or []:
            if [p for p in checker({'shorts': [raw]}) if p.hard]:
                continue
            pieces = join_touching([tuple(p) for p in raw['pieces']])
            try:bounded=cap_padding(words,[snap(words, by_id[a], by_id[b],source_duration) for a,b in pieces],settings.max_length)
            except ValueError:
                progress('  Excluded a moment whose spoken words exceed the export duration cap')
                continue
            if any(min(b,y)>max(a,x) for a,b in bounded for x,y in excluded):
                continue
            short = Short(title=str(raw['title']).strip(), lines=pieces,
                          pieces=bounded,
                          why=str(raw.get('why', '')).strip(), hook=by_id[pieces[0][0]].text,
                          score=float(raw.get('score') or 5), text=_text(pieces, by_id), part=n)
            candidates.append(short)
            titles.append(short.title)
        progress(f'  {len(answer.get("shorts") or [])} moment(s) found here')
    return candidates
