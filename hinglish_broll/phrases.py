"""Group timed words into short spoken phrases the planner can refer to by id."""
from dataclasses import dataclass

END_MARKS = ('.', '?', '!', '।')


@dataclass
class Phrase:
    id: int
    start: float
    end: float
    text: str


def build_phrases(words, pause=.4, max_words=10, max_seconds=4.5):
    phrases, current = [], []

    def flush():
        if current:
            phrases.append(Phrase(len(phrases), current[0].start, current[-1].end,
                                  ' '.join(w.text for w in current)))
            current.clear()

    for word in words:
        if current and (word.start - current[-1].end > pause or len(current) >= max_words
                        or word.end - current[0].start > max_seconds):
            flush()
        current.append(word)
        if word.text.rstrip().endswith(END_MARKS):
            flush()
    flush()
    return merge_short(phrases)


def merge_short(phrases, min_words=4, max_gap=.9, max_seconds=7.0):
    """Join fragments like "Haan ji." or "Bhai nahin thi." to a neighbour so meaning survives."""
    merged = []
    for p in phrases:
        prev = merged[-1] if merged else None
        short = len(p.text.split()) < min_words or (prev and len(prev.text.split()) < min_words)
        if prev and short and p.start - prev.end <= max_gap and p.end - prev.start <= max_seconds:
            merged[-1] = Phrase(prev.id, prev.start, p.end, prev.text + ' ' + p.text)
        else:
            merged.append(p)
    return [Phrase(i, p.start, p.end, p.text) for i, p in enumerate(merged)]
