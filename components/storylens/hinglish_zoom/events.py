"""Turn planner moments (phrase + stressed word) into timed, well-spaced zoom events."""
from dataclasses import dataclass, replace
import re

from .curve import ZoomEvent


@dataclass
class ZoomMoment:
    phrase_id: int
    word: str          # the stressed word, as written in the phrase
    strength: int      # 3 punchline / 2 important / 1 calm story
    kind: str = 'emphasis'    # emphasis | reveal | story
    until_id: int = None      # last phrase of the point: zoomed in until it ends, then back to wide
    reason: str = ''          # the planner's reasoning (shown in the report)
    word_time: float = None   # exact source-word reference for repeated words in a phrase


def _norm(text):
    return re.sub(r'[^\w]+', '', text.casefold())


def locate_word(phrase, words, target):
    """The timeline Word inside `phrase` that matches `target` (first match), else the first content word."""
    inside = [w for w in words if w.start >= phrase.start - 1e-3 and w.end <= phrase.end + 1e-3]
    if not inside:
        return None
    wanted = _norm(target)
    for w in inside:
        if wanted and _norm(w.text) == wanted:
            return w
    for w in inside:
        if wanted and (wanted in _norm(w.text) or (_norm(w.text) and _norm(w.text) in wanted)):
            return w
    return next((w for w in inside if len(_norm(w.text)) > 3), inside[0])


def _has_word(phrase, words, target):
    wanted = _norm(target)
    return bool(wanted) and any(_norm(w.text) == wanted for w in words
                                if w.start >= phrase.start - 1e-3 and w.end <= phrase.end + 1e-3)


NEIGHBOUR_LINES = 2   # how far a mis-numbered stressed word may be looked for


def owner_phrase(phrases, words, moment):
    """The phrase that really contains the stressed word. A small model sometimes names the
    neighbouring line; then the nearest line (at most 2 away) containing the word is used.
    A word repeated much earlier or later in the video is never borrowed."""
    by_id = {p.id: p for p in phrases}
    named = by_id.get(moment.phrase_id)
    if named is not None and _has_word(named, words, moment.word):
        return named
    holders = [p for p in phrases if _has_word(p, words, moment.word)
               and abs(p.id - moment.phrase_id) <= NEIGHBOUR_LINES]
    if holders:
        return min(holders, key=lambda p: abs(p.id - moment.phrase_id))
    return named


def choose_kind(style, moment, previous):
    if style == 'smooth':
        # Importance controls the amount, not whether a complete move fits.
        # A four-second story push used to discard most fallback highlights
        # in short shots. Smooth always means a complete eased in/hold/out.
        return 'smooth'
    if moment.kind == 'reveal':
        return 'reveal'
    if style == 'punch':
        return 'impact' if moment.strength == 3 else 'punch'
    # mixed: strongest lines hit hard, important lines glide in, story lines slowly push.
    if moment.kind == 'story' or moment.strength == 1:
        return 'push'
    if moment.strength == 3:
        return 'punch' if previous == 'impact' else 'impact'
    return 'smooth'


def make_event(moment, phrase, word, style, level, profile, previous=None, until=None):
    kind = choose_kind(style, moment, previous)
    strength_level = {3: level, 2: 1 + (level - 1) * .85, 1: 1 + (level - 1) * .55}[moment.strength]
    t = word.start
    # Stay zoomed in for the whole point (to the end of its last phrase), then return to wide.
    point_end = max(phrase.end, until.end if until is not None else phrase.end) + .15
    hold_end = min(max(point_end, t + profile.hold_min), t + profile.hold_max)
    common = dict(text=phrase.text, word_text=word.text, strength=moment.strength)
    # Bigger zooms take a little longer so the on-screen speed stays comfortable.
    stretch = .8 + (strength_level - 1) * 2
    if kind == 'smooth':
        return ZoomEvent('smooth', max(0.0, t - profile.ramp_in * stretch), t, hold_end,
                         hold_end + profile.ramp_out * stretch, strength_level, **common)
    if kind in ('punch', 'impact'):
        return ZoomEvent(kind, t, t, hold_end, hold_end, strength_level, settle=profile.settle, **common)
    if kind == 'reveal':
        start = phrase.start
        return ZoomEvent('reveal', start, start, start, start + profile.reveal, strength_level, **common)
    # push: slow build across the phrase, reaching the level on the phrase's last beat
    start = phrase.start
    peak = min(max(phrase.end, start + 1.5), start + profile.push_max)
    return ZoomEvent('push', start, peak, peak, peak + profile.ramp_out, 1 + (strength_level - 1) * .6, **common)


def _blocked_share(event, blocked):
    core_start, core_end = event.start, max(event.hold_end, event.word + .3, event.end if event.kind == 'reveal' else 0)
    span = max(1e-6, core_end - core_start)
    covered = sum(max(0.0, min(core_end, b) - max(core_start, a)) for a, b in blocked)
    return covered / span


def schedule(events, profile, duration, blocked=()):
    """Most valuable chain of events that keeps the pacing rules; skips zooms hidden under B-roll."""
    # A section mostly hidden under B-roll is pointless; a partly covered one keeps its zoom around it.
    usable = [e for e in events if e.end <= duration + 1e-6 and e.start >= 0 and _blocked_share(e, blocked) < .6
              and (e.kind not in ('smooth','push') or (e.word-e.start>=.3 and e.end-e.hold_end>=.3))]
    usable.sort(key=lambda e: e.start)
    short = profile.cadence_max > 0
    fits = lambda a, b: (b.start >= a.end + profile.gap - 1e-6 and
                         (not short or (b.word - a.word >= profile.cadence_min - .25
                                        and (not a.text or not b.text or b.text != a.text))))
    value = lambda e: ({3:3.0,2:1.2,1:-1.0}[e.strength] if short else e.strength) + (.3 if e.kind in ('impact', 'reveal') else 0)
    late = lambda gap: 40 * max(0, gap - profile.cadence_max) if short else 0
    score, before = [], []
    for i, e in enumerate(usable):
        best, link = max(((score[j] - late(e.word - usable[j].word)
                          - (20 * max(0, e.start-usable[j].end-profile.wide_max) if profile.wide_max else 0), j)
                          for j in range(i) if fits(usable[j], e)),
                         default=(-100*max(0,e.word-profile.hook_deadline) if short and profile.hook_deadline else -late(e.word), None))
        score.append(best + value(e)); before.append(link)
    if not usable:
        return []
    i, chain = max(range(len(usable)), key=lambda k: score[k] - late(duration - usable[k].word)
                   - (20*max(0,duration-usable[k].end-profile.wide_max) if profile.wide_max else 0)), []
    while i is not None:
        chain.append(usable[i]); i = before[i]
    return chain[::-1]


MIN_RAMP = .35   # a smooth zoom needs at least this long to ease in after a shot change
MIN_HOLD = .5    # a zoomed piece shorter than this is not worth showing


def fit_to_shots(events, shots):
    """Keep one continuous eased cycle across cuts, without shortening its hold.

    The pipeline verifies and changes the subject anchor independently in each
    intersected shot. A cut is not permission to truncate a settled close view
    or move the emphasis away from the actual spoken word.
    Instant punch/reveal styles retain their cut-based behaviour.
    """
    pieces = []
    for e in events:
        if e.kind in ('smooth', 'push'):
            covered = sum(max(0, min(e.end,b)-max(e.start,a)) for a,b in shots)
            if covered >= e.end-e.start-.002:
                pieces.append(e)
            continue
        shot_index = next((i for i, (a, b) in enumerate(shots) if a - 1e-6 <= e.word < b), None)
        if shot_index is None:
            continue
        for i in range(shot_index, len(shots)):
            a, b = shots[i]
            if a >= e.hold_end:
                break                     # the ease-out tail after a cut is simply the wide shot
            if i == shot_index:
                start, word = max(e.start, a), e.word
            else:
                start = word = a
            hold_end = min(e.hold_end, b)
            end = min(e.end, b) if e.hold_end <= b else hold_end
            # A cut hides the return to wide. Keep the framing until that cut
            # instead of squeezing the remaining ease-out into a few frames.
            if e.hold_end < b < e.end:
                hold_end = end = b
            if hold_end - word < MIN_HOLD and e.kind != 'reveal':
                continue
            pieces.append(replace(e, start=start, word=word, hold_end=hold_end, end=end))
    return pieces


def build_events(moments, phrases, words, settings, profile, duration, blocked=(), shots=None, select=True):
    by_id = {p.id: p for p in phrases}
    events, previous = [], None
    for m in sorted(moments, key=lambda m: by_id[m.phrase_id].start if m.phrase_id in by_id else 0):
        phrase = owner_phrase(phrases, words, m)
        word = locate_word(phrase, words, m.word) if phrase else None
        if phrase is not None and m.word_time is not None:
            word = next((w for w in words if abs(w.start - m.word_time) < .001
                         and phrase.start-.001 <= w.start and w.end <= phrase.end+.001
                         and _norm(w.text) == _norm(m.word)), None)
        if not word:
            continue
        until_id = m.until_id
        if until_id is not None and phrase.id != m.phrase_id:     # the section moved with its word
            until_id = phrase.id + (until_id - m.phrase_id)
        until = by_id.get(until_id) if until_id is not None else None
        if until is not None and until.start < phrase.start:
            until = None
        event = make_event(m, phrase, word, settings.style, settings.level, profile, previous, until)
        events.append(event); previous = event.kind
        if profile.wide_max and event.kind=='smooth':
            # The model supplies meaningful spoken moments. The timing solver
            # can hold any of them for 3-5 s, rather than discarding an earlier
            # main point because the previous phrase happened to end late.
            ramp_out=event.end-event.hold_end
            for hold in (profile.hold_min,(profile.hold_min+profile.hold_max)/2,profile.hold_max):
                if abs(event.hold_end-event.word-hold)>.001:
                    events.append(replace(event,hold_end=event.word+hold,end=event.word+hold+ramp_out))
    # Fit candidates before choosing the chain. A discarded/shortened shot must
    # not consume a slot that a different meaningful moment could have filled.
    candidates = fit_to_shots(events, shots) if shots else events
    return schedule(candidates, profile, duration, blocked) if select else candidates


def jump_cut_baseline(clips, frames, fps, level):
    """Alternate normal / slightly-zoomed framing on every cut so jump cuts feel intentional.

    clips: [(start_frame, end_frame)] on the talking-head track, in order.
    """
    baseline = [1.0] * frames
    alt = 1 + (level - 1) * .6
    parity, last_end = 0, None
    for start, end in clips:
        if last_end is not None and start == last_end:
            if end - start >= fps * .8:      # very short clips keep the previous framing
                parity ^= 1
        else:
            parity = 0                       # a gap or the first clip starts at normal framing
        for f in range(max(0, start), min(frames, end)):
            baseline[f] = alt if parity else 1.0
        last_end = end
    return baseline
