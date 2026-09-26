from dataclasses import dataclass, field
from collections import Counter
from difflib import SequenceMatcher
import math
import re

from hinglish_cut.model import Settings, Selection, Cut
from hinglish_cut.text import tokens


@dataclass
class SemanticSettings:
    embedding_model: str = 'intfloat/multilingual-e5-small'
    judge_model: str = 'Qwen/Qwen2.5-1.5B-Instruct'
    device: str = 'cpu'
    cpu_threads: int = 4
    offline: bool = True
    candidates_per_line: int = 4
    similarity_floor: float = .70
    ambiguity_margin: float = .025
    verification_threshold: float = .85
    order: str = 'auto'
    retake_window: float = 45
    protected_terms: list[str] = field(default_factory=list)
    pacing: str = 'natural'
    speech_backend: str = 'swift'
    matching_backend: str = 'word_coverage'

    def __post_init__(self):
        if self.speech_backend not in ('swift', 'turbo') or self.matching_backend not in ('word_coverage', 'meaning'):
            raise ValueError('Unsupported speech or matching backend')
        if self.pacing not in ('tight', 'natural', 'relaxed'):
            raise ValueError('Pacing must be tight, natural or relaxed')
        if self.device not in ('cpu', 'cuda') or self.order not in ('auto', 'continuous', 'chunks'):
            raise ValueError('Invalid device or ordering mode')
        for name in ('similarity_floor', 'ambiguity_margin', 'verification_threshold'):
            if not math.isfinite(getattr(self, name)) or not 0 <= getattr(self, name) <= 1:
                raise ValueError(f'Invalid {name}')
        if not 1 <= self.candidates_per_line <= 12 or not 1 <= self.cpu_threads <= 32:
            raise ValueError('Invalid candidate count or CPU threads')
        if not 1 <= self.retake_window <= 120:
            raise ValueError('Retake window must be 1-120 seconds')

    def speech_settings(self):
        # Never import the corrections tailored to the original Rapido script.
        return Settings(device=self.device, cpu_threads=self.cpu_threads, offline=self.offline,
                        judge_model=self.judge_model, vad_threshold=.35, min_silence=.30,
                        pre_padding=.08, post_padding=.12, aliases={'nahin': 'nahi', 'mein': 'me'})


@dataclass
class Span:
    id: str
    media_id: str
    first: int
    last: int
    start: float
    end: float
    text: str
    context: str
    aligned: bool


def script_ideas(text):
    # A line is one idea. Do not break "Har. Single. Ride." into four ideas.
    return [line.strip() for line in text.splitlines() if tokens(line)]


def spans_for(transcript, combined=True):
    words = transcript.words
    if not words:
        return []
    units = []
    first = 0
    for i, word in enumerate(words):
        gap = words[i + 1].start - word.end if i + 1 < len(words) else math.inf
        duration = word.end - words[first].start
        punctuation = bool(re.search(r'[.!?।][\"\x27]?$' , word.text))
        if i == len(words) - 1 or gap >= .55 or (punctuation and i - first >= 2) or duration >= 18:
            # Coarse fallback words share a whole analysis window: keep them together.
            same_coarse = (i + 1 < len(words) and not word.aligned and not words[i + 1].aligned
                           and (word.start, word.end) == (words[i + 1].start, words[i + 1].end))
            if not same_coarse:
                units.append((first, i + 1))
                first = i + 1
    spans = []
    for i, (a, _) in enumerate(units):
        for j in range(i, min(len(units), i + (4 if combined else 1))):
            b = units[j][1]
            start, end = words[a].start, words[b - 1].end
            if j > i and (end - start > 55 or words[units[j][0]].start - words[units[j - 1][1] - 1].end > 3):
                break
            spans.append(Span(f'{transcript.media.id}:{a}:{b}', transcript.media.id, a, b, start, end,
                              ' '.join(w.text for w in words[a:b]),
                              ' '.join(w.text for w in words[max(0, a - 12):min(len(words), b + 12)]),
                              all(w.aligned for w in words[a:b])))
    return spans


NUMBER_WORDS = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
                'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
                'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50', 'sixty': '60',
                'seventy': '70', 'eighty': '80', 'ninety': '90', 'hundred': '100',
                'teen': '3', 'tin': '3', 'chaar': '4', 'char': '4', 'paanch': '5',
                'das': '10', 'bees': '20', 'tees': '30', 'chaalis': '40', 'chalis': '40',
                'pachaas': '50', 'pachas': '50'}
NEGATIVE = {'nahi', 'nahin', 'nhi', 'not', 'never', 'no', 'without', 'mat', 'नहीं', 'मत', 'बिना', 'bina'}
SUBJECTIVE_FIRST = {'main', 'mai', 'maine', 'hum', 'humne', 'i', 'we', 'मैं', 'हम'}
OBJECTIVE_FIRST = {'mujhe', 'mujhse', 'mujhko', 'hume', 'humein', 'humse', 'me', 'us', 'मुझे', 'मुझसे', 'हमें'}


def fact_concerns(expected, actual, protected=()):
    # Unlike basic \w tokenization, preserve Hindi vowel marks in negations.
    import regex
    import unicodedata
    def fact_tokens(text):
        text = unicodedata.normalize('NFKC', text).casefold().replace("n't", ' not')
        return regex.findall(r'\d+(?:[.,]\d+)*|[\p{L}\p{M}]+', text)
    a, b = fact_tokens(expected), fact_tokens(actual)
    def numbers(words):
        result = []
        units = {'baar', 'bar', 'times', 'time', 'rupee', 'rupees', 'rupaye', 'minute', 'minutes', 'ghante', 'hours', 'din', 'days'}
        for i, w in enumerate(words):
            # "do" can mean give. Interpret it as two only next to a quantity unit.
            if w == 'do' and i + 1 < len(words) and words[i + 1] in units:
                result.append('2')
            elif w in NUMBER_WORDS or any(x.isdigit() for x in w):
                result.append(NUMBER_WORDS.get(w, w))
        return Counter(result)
    issues = []
    if numbers(a) != numbers(b):
        issues.append('numbers_need_review')
    if bool(NEGATIVE.intersection(a)) != bool(NEGATIVE.intersection(b)):
        issues.append('negation_needs_review')
    # Obvious participant-role changes must not depend on a small LLM noticing
    # them. This is a conservative review signal, not a full Hindi parser.
    role_groups = [
        (SUBJECTIVE_FIRST, OBJECTIVE_FIRST),
        ({'aap', 'tum', 'tu', 'aapne', 'tumne', 'आप', 'तुम'},
         {'aapko', 'aapse', 'tumko', 'tumhe', 'tumse', 'tujhe', 'आपको', 'आपसे', 'तुम्हें'}),
    ]
    def exclusive_role(words, subjects, objects):
        subject, object_ = bool(subjects.intersection(words)), bool(objects.intersection(words))
        return 'subject' if subject and not object_ else 'object' if object_ and not subject else None
    for subjects, objects in role_groups:
        left, right = exclusive_role(a, subjects, objects), exclusive_role(b, subjects, objects)
        if left and right and left != right:
            issues.append('participant_roles_need_review')
            break
    for term in protected:
        ts = fact_tokens(term)
        def contains(seq):
            return any(seq[i:i + len(ts)] == ts for i in range(len(seq)))
        if ts and contains(a) and not contains(b):
            issues.append('protected_term_missing:' + term)
    return issues


def safe_filler_word(text):
    """Sounds eligible for automatic deletion; reactions remain review-only."""
    word = ''.join(tokens(text))
    return bool(re.fullmatch(r'u+m+|u+h+|erm+', word))


def cleanup_verdict(kind, result, settings, *, target='', earlier='', later=''):
    """Combine fallible model output with conservative deletion rules."""
    if not verified(result, settings) or result.get('safe_to_remove') is not True:
        return False
    if kind == 'filler':
        return safe_filler_word(target)
    if kind != 'retake' or fact_concerns(earlier, later, settings.protected_terms):
        return False
    # Broken restarts and materially shorter attempts cannot replace the first.
    if re.search(r'(?:\.{2,}|…|\b(?:aur|and|or|ya|lekin|but)\s*)$', later.strip(), re.I):
        return False
    left, right = tokens(earlier), tokens(later)
    return SequenceMatcher(None, left, right, autojunk=False).ratio() >= .80


def verified(result, settings):
    return (result.get('equivalent') is True and result.get('complete') is True
            and result.get('contradiction') is False
            and result.get('confidence', 0) >= settings.verification_threshold)


def choose_sequence(pools, settings, single_source=False):
    """Global sequence: never reuse source words; optionally enforce forward time.

    Missing/unverified ideas stay visibly missing. Similarity is a ranking score,
    not an accuracy percentage. Return multiple global solutions for review.
    """
    continuous = settings.order == 'continuous' or (settings.order == 'auto' and single_source)
    beam = [(0.0, [], {})]
    for pool in pools:
        expanded = []
        for score, choices, used in beam:
            expanded.append((score - 1, choices + [None], used))
            for c in pool:
                if not c.get('eligible'):
                    continue
                span = c['span']
                previous = used.get(span.media_id, [])
                if any(max(span.first, a) < min(span.last, b) for a, b in previous):
                    continue
                # Distinct word indices can still share a coarse ASR interval.
                # Do not schedule overlapping speech and discover it at export.
                tolerance = 1 / c.get('source_frame_rate', 30)
                if any(other and other['span'].media_id == span.media_id
                       and min(span.end, other['span'].end) - max(span.start, other['span'].start) > tolerance + 1e-9
                       for other in choices):
                    continue
                if continuous and previous and span.first < max(b for _, b in previous):
                    continue
                next_used = {k: list(v) for k, v in used.items()}
                next_used.setdefault(span.media_id, []).append((span.first, span.last))
                # Context of adjacent selected ideas breaks ties without allowing
                # a merely nearby clip to override an unverified meaning.
                continuity = 0
                if choices and choices[-1] and choices[-1]['span'].media_id == span.media_id:
                    distance = span.start - choices[-1]['span'].end
                    if 0 <= distance <= 4:
                        continuity = .02
                expanded.append((score + 1 + c['score'] + continuity, choices + [c], next_used))
        beam = sorted(expanded, key=lambda state: state[0], reverse=True)[:32]
    if not beam:
        return [], []
    chosen = beam[0][1]
    ambiguous = []
    for i, c in enumerate(chosen):
        if c is None:
            continue
        for score, other, _ in beam[1:]:
            if beam[0][0] - score > settings.ambiguity_margin:
                break
            if other[i] is not None and other[i]['span'].id != c['span'].id:
                left, right = c['span'], other[i]['span']
                # Alternative endpoints of the same occurrence aren't two takes.
                overlap = left.media_id == right.media_id and max(left.first, right.first) < min(left.last, right.last)
                if not overlap:
                    ambiguous.append(i)
                    break
    return chosen, ambiguous


def subtract_ranges(cuts, ranges):
    result = []
    for cut in cuts:
        kept = [(cut.start_frame, cut.end_frame)]
        for a, b in ranges:
            new = []
            for x, y in kept:
                if a >= y or b <= x:
                    new.append((x, y))
                else:
                    if x < a: new.append((x, a))
                    if b < y: new.append((b, y))
            kept = new
        result.extend(Cut(cut.media_id, a, b, cut.line_index) for a, b in kept if b > a)
    return result


def deletion_bounds(transcript, first, last, retake=False):
    """Use gaps and outward protected neighbor frames, never slice a neighbor."""
    words = transcript.words
    selected = words[first:last]
    if not selected or any(not w.aligned for w in selected):
        return None
    fps = float(transcript.media.rate)
    low = max(0, selected[0].start - (.08 if retake else 0))
    high = min(transcript.media.duration, selected[-1].end + (.12 if retake else 0))
    if first:
        if words[first - 1].end > selected[0].start:
            return None
        low = max(low - (0 if retake else .03), words[first - 1].end + (.12 if retake else .08))
    if last < len(words):
        if words[last].start < selected[-1].end:
            return None
        high = min(high + (0 if retake else .03), words[last].start - .08)
    if low > selected[0].start or high < selected[-1].end:
        return None
    a, b = math.floor(low * fps), math.ceil(high * fps)
    if first and a / fps < words[first - 1].end:
        return None
    if last < len(words) and b / fps > words[last].start:
        return None
    limit = math.floor(transcript.media.duration * fps + 1e-6)
    return max(0, a), min(limit, b)


def cleanup_proposals(transcript, settings, semantic_scores=None):
    """Only proposals; a local verifier and replay check must authorize removal."""
    words = transcript.words
    proposals = []
    for i, w in enumerate(words):
        word = ''.join(tokens(w.text))
        strong = bool(re.fullmatch(r'u+m+|u+h+|erm+', word))
        expressive = word in {'oh', 'ah', 'hmm', 'hm', 'shh', 'shhh', 'अह', 'उह'}
        if strong or expressive:
            bounds = deletion_bounds(transcript, i, i + 1)
            proposals.append({'id': f'filler:{i}', 'kind': 'filler', 'first': i, 'last': i + 1,
                              'text': w.text, 'context': ' '.join(x.text for x in words[max(0, i - 10):i + 11]),
                              'bounds': bounds, 'eligible': bool(strong and bounds and .05 <= w.end - w.start <= .9 and w.score >= .2),
                              'reason': 'possible_hesitation' if strong else 'may_be_meaningful_expression'})
    spans = spans_for(transcript, combined=False)
    for i, earlier in enumerate(spans):
        for later in spans[i + 1:i + 4]:
            gap = later.start - earlier.end
            if gap > settings.retake_window:
                break
            left, right = tokens(earlier.text), tokens(later.text)
            if min(len(left), len(right)) < 5:
                continue
            similarity = SequenceMatcher(None, left, right, autojunk=False).ratio()
            semantic = (semantic_scores or {}).get((earlier.id, later.id), 0)
            cue = bool(re.search(r'\b(sorry|retake|dobara|phir se|again|restart)\b', later.context, re.I))
            if similarity < .55 and semantic < .88:
                continue
            adjacent = not any(s.start >= earlier.end and s.end <= later.start for s in spans if s.id not in (earlier.id, later.id))
            bounds = deletion_bounds(transcript, earlier.first, earlier.last, retake=True)
            proposals.append({'id': f'retake:{earlier.first}:{later.first}', 'kind': 'retake',
                              'first': earlier.first, 'last': earlier.last, 'text': earlier.text,
                              'replacement': later.text, 'replacement_first': later.first, 'replacement_last': later.last,
                              'context': earlier.context + ' / ' + later.context,
                              'bounds': bounds, 'eligible': bool(bounds and later.aligned and adjacent and gap <= 12
                                                              and (cue or similarity >= .90 or semantic >= .92)),
                              'reason': 'nearby_repeated_attempt', 'similarity': similarity, 'semantic_similarity': semantic})
    return proposals
