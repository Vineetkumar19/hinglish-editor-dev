"""When each visual plays.

Full screen: exactly the spoken line (B-roll rules: hook protected, face time between cutaways).
Pop-up:      lands on the word that NAMES the person/brand ("...order kiya Zomato se" -> the logo pops
             on "Zomato"), holds ~2 s, never over a full-screen visual, same entity again only much later."""
from difflib import SequenceMatcher
import re

from hinglish_broll.placement import Slot, best_combination, line_span, place, value

REPEAT_GAP = 45.0      # seconds before the same logo/face may pop up again


def _tok(text):
    return [t for t in re.sub(r'[\W_]+', ' ', str(text).casefold()).split() if t]


def _same_word(a, b):
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    return min(len(a), len(b)) >= 4 and SequenceMatcher(None, a, b).ratio() >= .75


def mention_time(words, start, end, mention, fallback_names=()):
    """Start time of the first word inside [start, end) that matches the mention (ASR spelling tolerated)."""
    inside = [w for w in words if start - .05 <= w.start < end]
    for wanted in [_tok(mention)] + [_tok(n) for n in fallback_names]:
        if not wanted:
            continue
        for i, w in enumerate(inside):
            got = _tok(w.text)
            if got and _same_word(got[0], wanted[0]):
                if len(wanted) == 1 or (i + 1 < len(inside) and any(_same_word(t, wanted[1]) for t in _tok(inside[i + 1].text))):
                    return w.start
                if len(wanted[0]) >= 4:
                    return w.start
    return None


def overlaps(start, end, ranges, pad=0.0):
    return any(start < b + pad and end > a - pad for a, b in ranges)


def full_slots(moments, phrases, lines, profile, duration, blocked=()):
    """Full-screen slots; moments whose line is already covered by B-roll on the timeline are skipped."""
    by_id = {p.id: p for p in phrases}
    free = []
    for m in moments:
        phrase = by_id.get(m.phrase_id)
        span = line_span(m, phrase, lines) if phrase else None
        if span and not overlaps(span[0], span[1], blocked):
            free.append(m)
    return place(free, phrases, profile, duration, lines)


def popup_slots(moments, phrases, lines, words, profile, duration, taken=(), names=None):
    """Pop-up slots starting on the mention. `taken`: full-screen ranges; `names`: entity key -> names."""
    by_id = {p.id: p for p in phrases}
    proposals = []
    for m in moments:
        phrase = by_id.get(m.phrase_id)
        span = line_span(m, phrase, lines) if phrase else None
        if not span:
            continue
        at = mention_time(words, span[0], span[1], m.mention, (names or {}).get(m.entity, ()))
        start = max(0.0, (at if at is not None else span[0]) - .12)
        end = min(start + profile.max_len, max(start + profile.ideal, span[1]), duration - profile.tail)
        # "Gandhi ji..." face card, then his footage: the card ends just before the full-screen visual.
        following = [a for a, b in taken if a >= start]
        if following:
            end = min(end, min(following) - .15)
        if end - start < profile.min_len - 1e-6 or overlaps(start, end, taken):
            continue
        spoken = ' '.join(l.text for l in lines if l.end > start and l.start < end)
        proposals.append(Slot(m, round(start, 3), round(end, 3), spoken or phrase.text, len(phrase.text.split())))
    # a spoken list ("Rapido? Zomato? Swiggy?"): each card ends when the next item is said, so every item
    # gets its own card instead of one card hiding the rest
    proposals.sort(key=lambda s: s.start)
    for n, slot in enumerate(proposals):
        later = [p.start for p in proposals[n + 1:] if p.start > slot.start + 1e-3]
        if later and later[0] < slot.end and later[0] - slot.start >= profile.min_len - 1e-6:
            slot.end = round(later[0], 3)
    chosen = best_combination(proposals, profile)
    last_seen, kept = {}, []
    for slot in sorted(chosen, key=lambda s: s.start):
        key = slot.moment.entity
        if key in last_seen and slot.start - last_seen[key] < REPEAT_GAP:
            continue
        last_seen[key] = slot.start
        kept.append(slot)
    budget = profile.max_coverage * duration
    while kept and sum(s.duration for s in kept) > budget + 1e-6:
        kept.remove(min(kept, key=lambda s: (value(s), -s.start)))
    return kept
