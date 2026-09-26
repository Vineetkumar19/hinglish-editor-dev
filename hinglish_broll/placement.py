"""Turn planner moments into non-overlapping B-roll slots that follow the timing profile."""
from dataclasses import dataclass


@dataclass
class Moment:
    phrase_id: int
    visual: str             # what should be on screen, in English
    queries: list[str]      # English stock search phrases
    priority: int = 2       # 3 = strongly benefits from B-roll, 1 = optional


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


def place(moments, phrases, profile, duration):
    by_id = {p.id: p for p in phrases}
    earliest, latest = profile.hook, duration - profile.tail
    proposals = []
    for m in moments:
        phrase = by_id.get(m.phrase_id)
        if phrase is None:
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
