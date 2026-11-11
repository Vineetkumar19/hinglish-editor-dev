from dataclasses import dataclass, replace
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
    template_source: str = ''
    template_slot: int = -1

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
    # A greedy five-word split can leave a single dependent word in the next
    # frame (5+1) or detach the noun from its question (5+3).  Balance adjacent
    # pieces of the same spoken sentence while preserving every timing.
    balanced = []
    index = 0
    while index < len(cues):
        left = cues[index]
        if index + 1 < len(cues):
            right = cues[index + 1]
            gap = right.words[0].start - left.words[-1].end
            left_ends_sentence = bool(re.search(r'[.!?।]["\x27]?$', left.words[-1].text))
            combined = list(left.words + right.words)
            if (not left_ends_sentence and gap <= .48 and len(left.words) == max_words
                    and len(right.words) < max_words and len(combined) <= max_words * 2):
                candidates = []
                for split in range(max(1, len(combined) - max_words), min(max_words, len(combined) - 1) + 1):
                    first, second = combined[:split], combined[split:]
                    char_overflow = (max(0, len(' '.join(word.text for word in first)) - max_chars)
                                     + max(0, len(' '.join(word.text for word in second)) - max_chars))
                    duration_overflow = (max(0, first[-1].end - first[0].start - max_seconds)
                                         + max(0, second[-1].end - second[0].start - max_seconds))
                    candidates.append((char_overflow * 10 + duration_overflow * 10
                                       + abs(len(first) - len(second)), split))
                split = min(candidates)[1]
                first, second = combined[:split], combined[split:]
                balanced.append(CaptionCue(tuple(first), first[0].start, first[-1].end + .08))
                balanced.append(CaptionCue(tuple(second), second[0].start, second[-1].end + .08))
                index += 2
                continue
        balanced.append(left)
        index += 1
    # Keep the final word's measured timing, but stop a readability tail at
    # the next slide. Otherwise an 80 ms hold can paint two complete layouts
    # together even when speech words themselves do not overlap.
    return [replace(cue, end=max(cue.words[-1].end,
                                min(cue.end, balanced[i + 1].start)))
            if i + 1 < len(balanced) else cue
            for i, cue in enumerate(balanced)]


def active_word(cue, seconds):
    for index, word in enumerate(cue.words):
        if word.start <= seconds < word.end:
            return index
    if seconds < cue.words[0].start:
        return 0
    return len(cue.words) - 1


_HERO_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'of', 'to', 'in', 'on', 'at', 'for',
    'from', 'with', 'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being',
    'aur', 'jo', 'toh', 'to', 'hi', 'hai', 'hain', 'tha', 'thi', 'the', 'na',
    'mein', 'me', 'ka', 'ki', 'ke', 'ko', 'se', 'pe', 'par', 'bhi', 'ye',
    'yeh', 'woh', 'wo', 'usme', 'isme',
    'iska', 'uska', 'ek', 'bas', 'sirf', 'ab', 'tab', 'phir', 'kya', 'kyun',
    'main', 'mai', 'hum', 'ham', 'tum', 'aap', 'tu', 'mera', 'mere', 'meri',
    'tumhara', 'tumhare', 'tumhari', 'hamara', 'hamare', 'hamari',
}
_NEGATIONS = {'nahi', 'nahin', 'not', 'never', 'no'}
_PERCENT_WORDS = {'percent', 'percentage', 'pratishat'}


def _hero_token(value):
    return re.sub(r'[^a-z0-9%]', '', str(value).casefold())


def important_word_index(words):
    """Choose the visually dominant word by meaning, never by line position alone.

    The renderer needs a quick local decision for every caption frame.  This scorer
    strongly rejects grammar/connective words, rewards concrete long words and
    numbers, and keeps a small later-word preference for natural Hinglish phrasing.
    """
    if not words:
        return 0
    values = [getattr(word, 'text', word) for word in words]
    cleaned = [_hero_token(value) for value in values]
    scores = []
    for index, (raw, token) in enumerate(zip(values, cleaned)):
        position_bonus = (index / max(1, len(values) - 1)) * 5.0
        score = len(token) * 2.0 + position_bonus
        if token in _HERO_STOPWORDS:
            score -= 100
        if token in _NEGATIONS:
            score -= 45
        if index + 1 < len(cleaned) and cleaned[index + 1] in _NEGATIONS:
            score += 20
        if any(character.isdigit() for character in token):
            score += 25
        if len(token) <= 2 and not any(character.isdigit() for character in token):
            score -= 16
        if str(raw).isupper() and len(token) <= 3 and not any(character.isdigit() for character in token):
            score -= 7
        if token.endswith(('tion', 'sion')):
            score += 8
        elif token.endswith('ment'):
            score += 5
        elif token.endswith('ed'):
            score += 4
        elif token.endswith('ing'):
            score += 3
        if token.endswith('ly'):
            score -= 5
        scores.append(score)
    best = max(range(len(scores)), key=lambda index: scores[index])
    if scores[best] < -20:
        best = max(range(len(cleaned)), key=lambda index: (len(cleaned[index]), index))
    return best


def hero_span(words):
    """Return the important word span as ``(start, end)`` with an exclusive end."""
    if not words:
        return 0, 0
    values = [getattr(word, 'text', word) for word in words]
    cleaned = [_hero_token(value) for value in values]
    start = important_word_index(values)
    end = start + 1
    if any(character.isdigit() for character in cleaned[start]):
        if end < len(cleaned) and cleaned[end] in _PERCENT_WORDS:
            end += 1
    elif cleaned[start] in _PERCENT_WORDS and start and any(character.isdigit() for character in cleaned[start - 1]):
        start -= 1
    if end < len(cleaned) and cleaned[end] in _NEGATIONS:
        end += 1
    return start, end


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
                threshold = .64 if len(key) <= 3 and context >= .80 else .74
                runner_up = scored[1][0] if len(scored) > 1 else -1
                if spelling >= threshold and combined - runner_up >= .045:
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
    if len(tokens)==len(cue.words):
        from dataclasses import replace
        return replace(cue,words=tuple(replace(word,text=token) for word,token in zip(cue.words,tokens)),template_source=cue.template_source or cue.text)
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
    return CaptionCue(tuple(words), cue.start, cue.end, cue.template_source or cue.text,cue.template_slot)
