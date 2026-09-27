from dataclasses import dataclass
from difflib import SequenceMatcher
import re


@dataclass(frozen=True)
class CaptionWord:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class CaptionCue:
    words: tuple[CaptionWord, ...]
    start: float
    end: float

    @property
    def text(self):
        return ' '.join(word.text for word in self.words)


def timed_words(words, duration):
    """Return monotonic word timings, distributing coarse ASR windows safely."""
    result = [CaptionWord(w.text.strip(), max(0.0, float(w.start)), min(duration, float(w.end)))
              for w in words if w.text.strip()]
    i = 0
    while i < len(result):
        j = i + 1
        while (j < len(result) and abs(result[j].start - result[i].start) < 1e-4
               and abs(result[j].end - result[i].end) < 1e-4):
            j += 1
        if j - i > 1:
            start, end = result[i].start, max(result[i].end, result[i].start + .12 * (j - i))
            weights = [max(1, len(re.sub(r'\W', '', word.text))) for word in result[i:j]]
            total = sum(weights)
            cursor = start
            for offset, weight in enumerate(weights):
                next_cursor = end if offset == len(weights) - 1 else cursor + (end - start) * weight / total
                result[i + offset] = CaptionWord(result[i + offset].text, cursor, next_cursor)
                cursor = next_cursor
                total -= weight
                start = cursor
        i = j
    fixed = []
    for word in result:
        start = max(word.start, fixed[-1].start + .01 if fixed else 0)
        end = max(start + .06, word.end)
        fixed.append(CaptionWord(word.text, start, min(duration, end)))
    return fixed


def build_cues(words, max_words=5, max_chars=34, max_seconds=2.8):
    cues, current = [], []
    for word in words:
        gap = word.start - current[-1].end if current else 0
        projected = len(' '.join(w.text for w in current + [word]))
        duration = word.end - current[0].start if current else 0
        if current and (gap > .48 or len(current) >= max_words or projected > max_chars or duration > max_seconds):
            cues.append(CaptionCue(tuple(current), current[0].start, current[-1].end + .08))
            current = []
        current.append(word)
        if re.search(r'[.!?।][\"\x27]?$' , word.text) and len(current) >= 2:
            cues.append(CaptionCue(tuple(current), current[0].start, current[-1].end + .08))
            current = []
    if current:
        cues.append(CaptionCue(tuple(current), current[0].start, current[-1].end + .08))
    # the short hold after the last word must never run into the next caption (two captions at once)
    return [CaptionCue(c.words, c.start, min(c.end, nxt.start)) if nxt is not None and c.end > nxt.start else c
            for c, nxt in zip(cues, cues[1:] + [None])]


def active_word(cue, seconds):
    for index, word in enumerate(cue.words):
        if word.start <= seconds < word.end:
            return index
    if seconds < cue.words[0].start:
        return 0
    return len(cue.words) - 1


def correct_with_reference(words, reference_script):
    """Use a loose script as a spelling dictionary without forcing its wording."""
    clean_script = re.sub(r'\[[^\]]*\]', ' ', reference_script or '')
    script_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", clean_script)
    if not script_tokens:
        return list(words), []

    def normal(value):
        return re.sub(r'[^a-z0-9]', '', value.casefold())

    indexed = [(token, normal(token)) for token in script_tokens if normal(token)]
    exact = {}
    for token, key in indexed:
        exact.setdefault(key, token)
    word_keys = []
    for word in words:
        match = re.match(r"^(\W*)(.*?)(\W*)$", word.text, flags=re.UNICODE)
        word_keys.append(normal(match.group(2) if match else word.text))

    corrected, changes = [], []
    for word_index, word in enumerate(words):
        match = re.match(r"^(\W*)(.*?)(\W*)$", word.text, flags=re.UNICODE)
        prefix, body, suffix = match.groups() if match else ('', word.text, '')
        key = normal(body)
        replacement = exact.get(key)
        if not replacement and len(key) >= 2:
            scored = []
            for reference_index, (token, candidate) in enumerate(indexed):
                if abs(len(candidate) - len(key)) > 3:
                    continue
                spelling = SequenceMatcher(None, key, candidate).ratio()
                context = 0.0
                for offset in (-2, -1, 1, 2):
                    wi, ri = word_index + offset, reference_index + offset
                    if 0 <= wi < len(word_keys) and 0 <= ri < len(indexed):
                        context = max(context, SequenceMatcher(None, word_keys[wi], indexed[ri][1]).ratio())
                scored.append((spelling + .15 * context, spelling, context, token))
            scored.sort(reverse=True)
            if scored:
                combined, spelling, context, token = scored[0]
                ref = next(r for r, (tok, _) in enumerate(indexed) if tok == token and
                           SequenceMatcher(None, key, indexed[r][1]).ratio() == spelling)
                sides = [SequenceMatcher(None, word_keys[word_index + o], indexed[ref + o][1]).ratio()
                         for o in (-1, 1) if 0 <= word_index + o < len(word_keys) and 0 <= ref + o < len(indexed)]
                both_sides = bool(sides) and min(sides) >= .6     # every existing neighbour matches the script too
                threshold = .64 if len(key) <= 3 and context >= .80 else .74
                runner_up = scored[1][0] if len(scored) > 1 else -1
                # a short everyday word ("kisi", "tak", "kiya") is only respelled when the words on BOTH sides match
                # the script there too; otherwise a loose script would change what was said ("kisi" -> "aisi")
                short_guess = len(key) <= 4 and normal(token) != key and not both_sides
                if spelling >= threshold and combined - runner_up >= .045 and not short_guess:
                    replacement = token
        new_text = prefix + (replacement or body) + suffix
        corrected.append(CaptionWord(new_text, word.start, word.end))
        if replacement and normal(new_text) != normal(word.text):
            changes.append({'heard': word.text, 'script_spelling': new_text,
                            'start': word.start, 'end': word.end})
    return corrected, changes


def retime_cue_text(cue, text):
    tokens = re.findall(r"\S+", (text or '').strip())
    if not tokens:
        return cue
    weights = [max(1, len(re.sub(r'\W', '', token))) for token in tokens]
    total_weight = sum(weights)
    duration = max(.08 * len(tokens), cue.end - cue.start)
    cursor = cue.start
    words = []
    used = 0
    for index, (token, weight) in enumerate(zip(tokens, weights)):
        used += weight
        end = cue.end if index == len(tokens) - 1 else cue.start + duration * used / total_weight
        words.append(CaptionWord(token, cursor, min(cue.end, max(cursor + .04, end))))
        cursor = words[-1].end
    return CaptionCue(tuple(words), cue.start, cue.end)
