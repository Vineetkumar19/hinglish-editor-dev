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
        # Let the clip run over following phrases up to the profile maximum.
        end = min(start + profile.max_len, max(start + profile.min_len, phrase.end), latest)
        if end - start < profile.min_len - 1e-6:
            continue
        spoken = ' '.join(p.text for p in phrases if p.end > start and p.start < end)
        proposals.append(Slot(m, round(start, 3), round(end, 3), spoken or phrase.text))

    accepted, covered = [], 0.0
    budget = profile.max_coverage * duration
    for slot in sorted(proposals, key=lambda s: (-s.moment.priority, s.start)):
        if covered + slot.duration > budget + 1e-6:
            continue
        clash = any(slot.start < other.end + profile.min_gap and other.start < slot.end + profile.min_gap
                    or abs(slot.start - other.start) < profile.min_spacing for other in accepted)
        if clash:
            continue
        accepted.append(slot)
        covered += slot.duration
    return sorted(accepted, key=lambda s: s.start)
