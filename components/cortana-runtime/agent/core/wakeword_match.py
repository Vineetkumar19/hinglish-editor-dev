"""Conservative phrase spotting, preserving the original multilingual command."""

import re
import unicodedata

_LEADERS = {"hey", "ok", "okay", "hi", "hello", "yo", "हे", "हेलो", "ओके"}
_CORTANA_VARIANTS = {
    "cortana", "cortona", "cortina", "kordana", "cartana", "gortana",
    "cordana", "courtana", "cortanna", "cortan", "coratana", "cotana",
    "kartana", "curtana", "coretana", "cortanaa", "gotana",
    "कोर्टाना", "कॉर्टाना", "कोरटाना", "कोर्टेना", "कार्टाना", "कॉरटाना",
}


def _levenshtein(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def match_wake_word(transcript: str, wake_word: str = "cortana", max_distance: int | None = None) -> dict:
    """Only a leading wake phrase activates; numbers, Hindi and punctuation stay intact.

    Phrase spotting is not speaker authentication. High-impact actions still require
    explicit on-screen approval, regardless of who said the wake word.
    """
    source = transcript or ""
    # Python's \w omits combining marks; explicitly retain the Devanagari block.
    tokens = list(re.finditer(r"[\w\u0900-\u097F']+", source, flags=re.UNICODE))
    expected = unicodedata.normalize("NFC", (wake_word or "cortana").casefold())
    cursor = 0
    while cursor < len(tokens) and tokens[cursor].group().casefold() in _LEADERS:
        cursor += 1
    if cursor >= len(tokens):
        return {"detected": False, "remainder": ""}

    def matches(candidate: str) -> bool:
        candidate = unicodedata.normalize("NFC", candidate.casefold()).strip("'")
        if candidate == expected:
            return True
        if expected == "cortana" and candidate in _CORTANA_VARIANTS:
            return True
        # One-character tolerance: the old distance of three accepted ordinary words.
        distance = 1 if max_distance is None else max(0, min(max_distance, 1))
        return len(candidate) >= 5 and _levenshtein(candidate, expected) <= distance

    for length in (1, 2):
        chosen = tokens[cursor:cursor + length]
        if len(chosen) != length:
            continue
        if matches("".join(token.group() for token in chosen)):
            remainder = source[chosen[-1].end():].lstrip(" \t\r\n,;:!?.।—-")
            return {"detected": True, "remainder": remainder}
    return {"detected": False, "remainder": ""}
