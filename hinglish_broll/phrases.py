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
    return phrases
