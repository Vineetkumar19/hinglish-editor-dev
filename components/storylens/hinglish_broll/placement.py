"""Turn planner moments into non-overlapping B-roll slots that follow the timing profile."""
from dataclasses import dataclass


@dataclass
class Moment:
    phrase_id: int
    visual: str             # what should be on screen, in English
    queries: list[str]      # English stock search phrases
    priority: int = 2       # 3 = strongly benefits from B-roll, 1 = optional
    quote: str = ''         # words copied from the line this B-roll illustrates
    meaning: str = ''       # the planner's English reading of that line
    subject: str = ''       # exact named identity required in the video
    context: str = ''       # complete English thought across ASR fragment boundaries


@dataclass
class Slot:
    moment: Moment
    start: float
    end: float
    text: str               # what is being said during the slot
    phrase_words: int = 0   # size of the phrase the planner chose (not of the overlap)

    @property
    def duration(self):
        return self.end - self.start


MIN_LINE = 1.0     # shortest B-roll that still reads as a shot


def line_span(moment, phrase, lines):
    """Exact time of the spoken line the moment's quote comes from (inside its planner phrase).

    B-roll must play only while that line is spoken: it starts with the line and never runs into
    the next line. A short line may extend into the following silence, never into speech."""
    import re
    tokens = lambda text: [t for t in re.sub(r'[^\w]+', ' ', text.casefold()).split() if t]
    inside = [l for l in lines if l.start >= phrase.start - 1e-3 and l.end <= phrase.end + 1e-3] or \
             [l for l in lines if l.end > phrase.start and l.start < phrase.end]
    if not inside:
        return None
    wanted = tokens(moment.quote)
    score = lambda l: sum(t in set(tokens(l.text)) for t in wanted) / max(1, len(wanted))
    line = max(inside, key=score) if wanted else inside[0]
    following = [l.start for l in lines if l.start >= line.end - 1e-3]
    next_speech = min(following) if following else float('inf')
    end = max(line.end, min(line.start + MIN_LINE, next_speech))
    return line.start, end


def place(moments, phrases, profile, duration, lines=None):
    by_id = {p.id: p for p in phrases}
    earliest, latest = profile.hook, duration - profile.tail
    proposals = []
    for m in moments:
        phrase = by_id.get(m.phrase_id)
        if phrase is None:
            continue
        if lines:
            span = line_span(m, phrase, lines)
            if span is None:
                continue
            start = max(span[0], earliest)
            end = min(span[1], start + profile.max_len, latest)
            if end - start < MIN_LINE - 1e-6:
                continue
            spoken = ' '.join(l.text for l in lines if l.end > start and l.start < end)
            proposals.append(Slot(m, round(start, 3), round(end, 3), spoken, len(phrase.text.split())))
            continue
        start = max(phrase.start, earliest)
        # Cover the phrase (at least the ideal length), running over the next words up to the maximum.
        end = min(start + profile.max_len, max(start + profile.ideal, phrase.end), latest)
        if end - start < profile.min_len - 1e-6:
            continue
        spoken = ' '.join(p.text for p in phrases if p.end > start and p.start < end)
        proposals.append(Slot(m, round(start, 3), round(end, 3), spoken or phrase.text, len(phrase.text.split())))

    chosen = best_combination(proposals, profile)
    # Respect the coverage budget by dropping the least valuable clips first.
    budget = profile.max_coverage * duration
    while chosen and sum(s.duration for s in chosen) > budget + 1e-6:
        chosen.remove(min(chosen, key=lambda s: (value(s), -s.start)))
    return sorted(chosen, key=lambda s: s.start)


def value(slot):
    # Priority dominates; among equals, a longer spoken phrase usually carries more to show.
    return slot.moment.priority + min(slot.phrase_words, 12) / 40


def scene_family(slot):
    """Keep venue variety when a requested clip count trims the larger plan."""
    import re
    text=slot.moment.visual.casefold()
    for family,pattern in [('cafe',r'\bcaf[eé]|coffee shop'),('club',r'nightclub|\bclub\b'),
                           ('bar',r'\bbar\b|\blounge\b|\bpub\b'),
                           ('shops',r'shutter|\bshops?\b|storefront'),
                           ('street',r'\bstreet\b|\bhighway\b|\broad\b|cityscape')]:
        if re.search(pattern,text):return family
    return text


def cap_diverse_slots(slots,count):
    """Remove redundant scene families before dropping the only cafe/club shot."""
    from collections import Counter
    kept=list(slots)
    while len(kept)>count:
        families=Counter(scene_family(s) for s in kept)
        redundant=[s for s in kept if families[scene_family(s)]>1]
        kept.remove(min(redundant or kept,key=lambda s:(value(s),-s.start)))
    return kept


def best_combination(proposals, profile):
    """Most valuable chain of slots that keeps face time between neighbours.

    Sorted by start, if every neighbour pair fits then every pair fits (gaps and spacing only grow),
    so a chain DP over "best chain ending at slot i" is exact.
    """
    slots = sorted(proposals, key=lambda s: s.start)
    fits = lambda a, b: b.start >= a.end + profile.min_gap - 1e-6 and b.start - a.start >= profile.min_spacing - 1e-6
    score, before = [], []
    for i, slot in enumerate(slots):
        options = [(score[j], j) for j in range(i) if fits(slots[j], slot)]
        best, link = max(options, default=(0.0, None))
        score.append(best + value(slot)); before.append(link)
    if not slots:
        return []
    i, chain = max(range(len(slots)), key=lambda k: score[k]), []
    while i is not None:
        chain.append(slots[i]); i = before[i]
    return chain[::-1]
