"""Clause coverage and source-grounded selection for multi-clip paragraphs.

Every decision retains original word indices. A paragraph is never represented
by a single topical match. Embeddings rank alternatives; they cannot certify
that unspoken clauses were covered.
"""
from difflib import SequenceMatcher
from functools import lru_cache
import math
import re

from .core import Span, NUMBER_WORDS, fact_concerns, script_ideas, choose_sequence, spans_for
from hinglish_cut.text import tokens


NUMBERS = {**NUMBER_WORDS, 'ek': '1', 'eleven': '11', 'gyaarah': '11', 'gyarah': '11',
           'gyaara': '11', 'gyara': '11', 'barah': '12', 'baarah': '12', 'twelve': '12',
           'thirteen': '13', 'terah': '13', 'fourteen': '14', 'chaudah': '14',
           'fifteen': '15', 'pandrah': '15', 'sixteen': '16', 'solah': '16',
           'seventeen': '17', 'satrah': '17', 'eighteen': '18', 'atharah': '18',
           'nineteen': '19', 'unnis': '19'}
SPELLINGS = {'nahin': 'nahi', 'nhi': 'nahi', 'mein': 'me', 'main': 'mai', 'yahaan': 'yahan',
             'vah': 'woh', 'vo': 'woh', 'toh': 'to', 'par': 'pe', 'kuchh': 'kuch',
             'hain': 'hai', 'hoon': 'hu', 'ho': 'hu', 'karoon': 'karun', 'karu': 'karun'}
STOP = set('aaj ab hum mai main me pe par ki ke ka ko se hai hain hu ho hoon to toh '
           'aur yahan yahaan wahaan woh vah vo tum aap bhai bhaiya rahe raha rahi kar '
           'karne is isme ek koi na tab the a an of in to and i we you it this will be am are'.split())


def normalized(text):
    # Split fused compounds without changing the original transcript or timings.
    text = re.sub(r'(?i)night\s*life', 'nightlife', text)
    text = re.sub(r'(?i)street\s*light', 'streetlight', text)
    text = re.sub(r'(?i)khol\s*ke', 'khol ke', text)
    return [NUMBERS.get(w, SPELLINGS.get(w, w)) for w in tokens(text)]


@lru_cache(maxsize=50000)
def phonetic(word):
    word = re.sub(r'(.)\1+', r'\1', word)
    return word.replace('chh', 'ch').replace('ph', 'f').replace('bh', 'b').replace('dh', 'd')


@lru_cache(maxsize=50000)
def soundex(word):
    """A secondary spelling signal for ASR homophones, never sole evidence."""
    groups = {c: str(i) for i, chars in enumerate(('bfpv', 'cgjkqsxz', 'dt', 'l', 'mn', 'r'), 1)
              for c in chars}
    if not word: return ''
    codes, previous = [], groups.get(word[0], '')
    for ch in word[1:]:
        code = groups.get(ch, '')
        if code and code != previous: codes.append(code)
        if ch not in 'hw': previous = code
    return word[0] + ''.join(codes).ljust(3, '0')[:3]


@lru_cache(maxsize=150000)
def word_similarity(a, b):
    if a == b:
        return 1.0
    if any(x.isdigit() for x in a + b):
        return 0.0
    a, b = phonetic(a), phonetic(b)
    score = SequenceMatcher(None, a, b, autojunk=False).ratio()
    # Hindi ASR writes spoken English initials as one phonetic word. This is
    # retrieval evidence only; the meaning model must still verify the passage.
    letter_names=dict(zip('abcdefghijklmnopqrstuvwxyz',
        ('e','bi','si','di','i','ef','ji','ech','ai','je','ke','el','em',
         'en','o','pi','kyu','ar','es','ti','yu','vi','dablyu','eks','wai','zed')))
    for initials,spoken in ((a,b),(b,a)):
        if len(initials)==2 and all(c in letter_names for c in initials):
            if phonetic(''.join(letter_names[c] for c in initials))==spoken:
                score=max(score,.95)
    if min(len(a), len(b)) >= 4 and soundex(a) == soundex(b):
        score = max(score, .76)
    return score if score >= .64 else 0.0


def text_evidence(expected, actual):
    left, right = normalized(expected), normalized(actual)
    if not left or not right:
        return {'recall': 0., 'precision': 0., 'content': 0., 'score': 0., 'missing': left}
    weights = [0.35 if w in STOP else 1.0 for w in left]
    rw = [0.35 if w in STOP else 1.0 for w in right]
    pairs = sorted(((word_similarity(a, b), i, j) for i, a in enumerate(left)
                    for j, b in enumerate(right)), reverse=True)
    used_l, used_r, matched = set(), set(), {}
    for score, i, j in pairs:
        if score < .64 or i in used_l or j in used_r:
            continue
        used_l.add(i); used_r.add(j); matched[i] = score
    recall = sum(weights[i] * s for i, s in matched.items()) / sum(weights)
    precision = sum(rw[j] for j in used_r) / sum(rw)
    content_ids = [i for i, w in enumerate(left) if w not in STOP]
    content = sum(matched.get(i, 0) for i in content_ids) / max(1, len(content_ids))
    if not content_ids: content = recall
    # Recall measures completeness; extra repeated words lower precision.
    score = .60 * recall + .25 * precision + .15 * content
    return {'recall': recall, 'precision': precision, 'content': content, 'score': score,
            'missing': [w for i, w in enumerate(left) if w not in STOP and matched.get(i, 0) < .70]}


def clauses(text):
    """Keep paragraph identity while allowing it to draw from multiple files."""
    result = []
    for paragraph, line in enumerate(script_ideas(text)):
        # An ellipsis after a short lead-in ("Bhai...") stays with its clause.
        pieces = re.split(r'(?<=[?!।])["\u201d\u2019]*\s*|(?<!\.)\.(?!\.)["\u201d\u2019]*\s+|\s*[,;]\s*', line)
        units = []
        for piece in pieces:
            pending = ''
            for chunk in re.split(r'(?:\.{2,}|…)\s*', piece):
                pending = (pending + ' ' + chunk).strip()
                if len(tokens(pending)) >= 4:
                    units.append(pending); pending = ''
            if pending: units.append(pending)
        connected = []
        i = 0
        while i < len(units):
            unit = units[i]
            # A short answer belongs to its question, not to every other
            # occurrence of "Nahi" elsewhere in the recording.
            if (unit.rstrip().endswith('?') and i + 1 < len(units)
                    and normalized(units[i + 1]) in (['nahi'], ['yes'], ['haan'])):
                unit += ' ' + units[i + 1]; i += 1
            elif (normalized(unit) in (['bhai'], ['bhaiya']) and i + 1 < len(units)):
                unit += ' ' + units[i + 1]; i += 1
            elif (len(tokens(unit)) <= 2 and i + 1 < len(units)
                  and normalized(units[i + 1])[:1] in (['pe'], ['but'], ['lekin'])):
                unit += ' ' + units[i + 1]; i += 1
            connected.append(unit)
            i += 1
        for unit in connected:
            if tokens(unit):
                result.append({'index': len(result), 'paragraph_index': paragraph,
                               'paragraph_text': line, 'idea': unit})
    return result


def span(transcript, first, last):
    w = transcript.words
    return Span(f'{transcript.media.id}:{first}:{last}', transcript.media.id, first, last,
                w[first].start, w[last - 1].end, ' '.join(x.text for x in w[first:last]),
                ' '.join(x.text for x in w[max(0, first - 8):min(len(w), last + 8)]),
                all(x.aligned for x in w[first:last]))


def ranked_windows(idea, transcript):
    """Compact word windows prevent swallowing a restart or another sentence."""
    words = transcript.words
    maximum = max(4, min(60, len(normalized(idea)) * 2 + 4))
    found = []
    for first in range(len(words)):
        for last in range(first + 1, min(len(words), first + maximum) + 1):
            if last > first + 1 and words[last - 1].start - words[last - 2].end > 1.2:
                break
            if words[last - 1].end - words[first].start > 35:
                break
            actual = ' '.join(w.text for w in words[first:last])
            evidence = text_evidence(idea, actual)
            if evidence['score'] < .52 or evidence['content'] < .40:
                continue
            # Prefer actual phrase edges when scores are nearly equal.
            boundary = .008 * (first == 0 or words[first].start - words[first - 1].end > .35
                               or bool(re.search(r'[.?!,]$', words[first - 1].text)))
            boundary += .008 * (last == len(words) or words[last].start - words[last - 1].end > .35
                                or bool(re.search(r'[.?!,]$', words[last - 1].text)))
            found.append({'span': span(transcript, first, last), 'evidence': evidence,
                          'score': evidence['score'] + boundary})
    found.sort(key=lambda c: (-c['score'], c['span'].last - c['span'].first))
    distinct = []
    for candidate in found:
        s = candidate['span']
        if any(max(s.first, c['span'].first) < min(s.last, c['span'].last) for c in distinct):
            continue
        first, last = s.first, s.last
        prefix = first
        # Restore short grammatical lead-ins/tails at the phrase edges. Never
        # expand over another content word or a punctuated sentence boundary.
        for _ in range(3):
            if not first or re.search(r'[.?!,]$', words[first - 1].text): break
            if words[first].start - words[first - 1].end > .45: break
            if any(w not in STOP for w in normalized(words[first - 1].text)): break
            first -= 1
        leading = normalized(idea)[:2]
        prefix_words = normalized(' '.join(w.text for w in words[first:prefix]))
        at_phrase_start = first == 0 or words[first].start - words[first - 1].end > .45
        if not at_phrase_start and not any(w in leading for w in prefix_words):
            first = prefix
        for _ in range(2):
            if last == len(words) or re.search(r'[.?!,]$', words[last - 1].text): break
            if words[last].start - words[last - 1].end > .35: break
            if any(w not in STOP for w in normalized(words[last].text)): break
            last += 1
        candidate['span'] = span(transcript, first, last)
        candidate['evidence'] = text_evidence(idea, candidate['span'].text)
        distinct.append(candidate)
        if len(distinct) == 4: break
    return distinct


def build_pools(units, transcripts, settings, encoder=None, progress=print):
    from pathlib import Path
    pools = []
    order = {t.media.id: i for i, t in enumerate(transcripts)}
    for unit in units:
        progress(f'Covering sentence {unit["index"] + 1}/{len(units)}: {unit["idea"][:70]}')
        pool = []
        for t in transcripts:
            for c in ranked_windows(unit['idea'], t):
                c['source_name'] = Path(t.media.path).name
                c['source_order'] = order[t.media.id]
                c['source_frame_rate'] = float(t.media.rate)
                # Fact guards use the same written/spoken number vocabulary.
                c['issues'] = fact_concerns(' '.join(normalized(unit['idea'])),
                                           ' '.join(normalized(c['span'].text)), settings.protected_terms)
                e = c['evidence']
                c['eligible'] = e['recall'] >= .62 and e['content'] >= .60 and not c['issues']
                c['similarity'] = 0.
                c['verdict'] = {'reason': 'Matched source words; listen to any wording differences.'}
                pool.append(c)
        pool.sort(key=lambda c: -c['score'])
        pools.append(pool[:max(8, settings.candidates_per_line * 2)])
    if encoder:
        flat = [c for pool in pools for c in pool]
        # Meaning-only retrieval remains available for heavily paraphrased lines.
        # The old small judge falsely approved incomplete paragraphs; retrieval
        # alone therefore offers alternatives, never claims complete coverage.
        missing = [i for i, pool in enumerate(pools) if not any(c['eligible'] for c in pool)]
        fallback = [(t, s) for t in transcripts for s in spans_for(t)] if missing else []
        vectors = encoder.encode([u['idea'] for u in units] + [c['span'].text for c in flat]
                                 + [s.text for _, s in fallback], progress)
        offset = len(units)
        for i, pool in enumerate(pools):
            for c in pool:
                c['similarity'] = float(vectors[i] @ vectors[offset]); offset += 1
                c['score'] = .88 * c['score'] + .12 * c['similarity']
        for i in missing:
            ranked = sorted(((float(vectors[i] @ vectors[offset + j]), t, s)
                             for j, (t, s) in enumerate(fallback)), key=lambda x: -x[0])
            added = 0
            for similarity, t, s in ranked:
                if similarity < settings.similarity_floor: break
                if any(c['span'].id == s.id for c in pools[i]): continue
                issues = fact_concerns(' '.join(normalized(units[i]['idea'])),
                                       ' '.join(normalized(s.text)), settings.protected_terms)
                pools[i].append({'span': s, 'source_name': Path(t.media.path).name,
                                 'source_order': order[t.media.id], 'similarity': similarity,
                                 'score': similarity, 'evidence': text_evidence(units[i]['idea'], s.text),
                                 'eligible': False, 'issues': issues + ['meaning_only_candidate_listen_and_choose'],
                                 'verdict': {'reason': 'Similar meaning candidate; completeness needs listening review.'}})
                added += 1
                if added >= settings.candidates_per_line: break
    # Prefer a later COMPLETE attempt of the same sentence, not a later topic.
    for unit, pool in zip(units, pools):
        # Short answers, cues and scripted repetitions are not abandoned takes.
        if len(normalized(unit['idea'])) <= 3:
            continue
        if sum(normalized(other['idea']) == normalized(unit['idea']) for other in units) > 1:
            continue
        eligible = [c for c in pool if c['eligible']]
        for earlier in eligible:
            a = earlier['span']
            for later in eligible:
                b = later['span']
                later_order = (later['source_order'], b.start) > (earlier['source_order'], a.start)
                nearby = (0 <= b.start - a.end <= settings.retake_window if a.media_id == b.media_id
                          else 0 < later['source_order'] - earlier['source_order'] <= 2)
                if not later_order or not nearby or later['evidence']['recall'] < earlier['evidence']['recall'] - .10:
                    continue
                same = text_evidence(a.text, b.text)
                if same['recall'] >= .72 and same['precision'] >= .70:
                    earlier['superseded_by'] = b.id
                    earlier['eligible'] = False
                    earlier['issues'].append('earlier_take_replaced_by_complete_later_take')
                    break
        pool.sort(key=lambda c: -c['score'])
    return pools


def arrange_paragraphs(text, transcripts, settings, encoder=None, progress=print):
    units = clauses(text)
    pools = build_pools(units, transcripts, settings, encoder, progress)
    chosen, ambiguous = choose_sequence(pools, settings, len(transcripts) == 1)
    rows = []
    for unit, pool, selected in zip(units, pools, chosen):
        issues = []
        if selected is None: issues.append('sentence_not_matched')
        elif selected['evidence']['missing']:
            issues.append('wording_difference_check: ' + ', '.join(selected['evidence']['missing']))
        if selected and not selected['span'].aligned: issues.append('timing_needs_listening_check')
        if unit['index'] in ambiguous: issues.append('alternative_occurrence_available')
        rows.append({**unit, 'selected': selected, 'issues': issues, 'alternatives': pool})
    if encoder:
        retain_contextual_passages(rows, transcripts)
    return rows


def retain_contextual_passages(rows, transcripts):
    """Keep a bounded source passage in an uncertain draft gap, never certify it.

    A passage must touch a selected word range in the SAME paragraph and source,
    have no reused words/frames, and have retrieval evidence. Unanchored semantic
    guesses remain missing. Review flags distinguish this from a grounded match.
    """
    by_id = {t.media.id: t for t in transcripts}
    for i, row in enumerate(rows):
        if row['selected']:
            continue
        anchors = []
        if i and rows[i - 1]['paragraph_index'] == row['paragraph_index'] and rows[i - 1]['selected']:
            anchors.append(('after', rows[i - 1]['selected']['span']))
        if i + 1 < len(rows) and rows[i + 1]['paragraph_index'] == row['paragraph_index'] and rows[i + 1]['selected']:
            anchors.append(('before', rows[i + 1]['selected']['span']))
        possible = []
        for candidate in row['alternatives']:
            s = candidate['span']
            if candidate.get('similarity', 0) < .80:
                continue
            if candidate.get('issues') and any(x.startswith(('numbers_', 'negation_', 'protected_', 'participant_')) for x in candidate['issues']):
                continue
            if s.end - s.start > 15:
                continue
            anchored = any(a.media_id == s.media_id and
                           ((side == 'after' and a.last == s.first and 0 <= s.start - a.end <= 2.5) or
                            (side == 'before' and s.last == a.first and 0 <= a.start - s.end <= 2.5))
                           for side, a in anchors)
            if not anchored:
                continue
            chosen = [r['selected']['span'] for r in rows if r['selected']]
            fps = float(by_id[s.media_id].media.rate)
            if any(a.media_id == s.media_id and
                   (max(a.first, s.first) < min(a.last, s.last) or
                    min(a.end, s.end) - max(a.start, s.start) > 1 / fps + 1e-9) for a in chosen):
                continue
            possible.append(candidate)
        if possible:
            # Preserve the whole bounded utterance, rather than cherry-picking
            # just a matching "nahi" from an otherwise badly transcribed line.
            candidate = max(possible, key=lambda c: (c['span'].last - c['span'].first, c['similarity']))
            row['selected'] = candidate
            row['selection_status'] = 'unverified_context_passage'
            row['issues'] = ['Uncertain transcript: nearby source passage retained. Listen before keeping this take.']
