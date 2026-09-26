"""Retrieve complete spoken phrases, then verify their intended meaning.

Retrieval is linear in the corpus size per idea; it does not enumerate all word
substrings. Script context never becomes invented source text or timestamps.
"""
from pathlib import Path
import re

from .core import choose_sequence, fact_concerns
from .coverage import normalized, text_evidence, span
from .core import script_ideas
from hinglish_cut.text import tokens


def meaning_units(text):
    # A comma is part of one script sentence. Splitting there allowed an early
    # take to supply its first half while a later retake supplied the second.
    # Sentence-level decisions make "keep the last complete take" enforceable.
    result = []
    for paragraph, line in enumerate(script_ideas(text)):
        pieces = [p.strip() for p in re.split(
            r'(?<=[?!।])["\u201d\u2019]*\s+|(?<!\.)\.(?!\.)["\u201d\u2019]*\s+', line) if tokens(p)]
        grouped = []
        i = 0
        while i < len(pieces):
            piece = pieces[i]
            # Short answers and chained rhetorical questions are one thought.
            while (piece.rstrip().endswith('?') and i + 1 < len(pieces)
                   and len(normalized(pieces[i + 1])) <= 3):
                i += 1
                piece += ' ' + pieces[i]
            grouped.append(piece)
            i += 1
        # A repeated cue belongs to the sentence that explains it: for example,
        # "Chair? Chair ka..." and "Bed. Bed mast hai." Keeping these together
        # stops the cue from becoming a separate, unmatched timeline clip.
        cue_merged = []
        i = 0
        while i < len(grouped):
            current = grouped[i]
            current_words = normalized(current)
            if (i + 1 < len(grouped) and len(current_words) <= 2 and current_words
                    and normalized(grouped[i + 1])[:1] == current_words[:1]):
                current += ' ' + grouped[i + 1]
                i += 1
            cue_merged.append(current)
            i += 1
        grouped = cue_merged
        merged = []
        i = 0
        while i < len(grouped):
            end = i
            while end < len(grouped) and len(normalized(grouped[end])) == 1:
                end += 1
            if end - i >= 3:
                merged.append(' '.join(grouped[i:end]))
                i = end
            else:
                merged.append(grouped[i])
                i += 1
        for idea in merged:
            result.append({'index': len(result), 'paragraph_index': paragraph,
                           'paragraph_text': line, 'idea': idea})
    return result


def phrase_spans(transcript):
    """Phrase boundaries come from the recording, independent of the script.

    Keep alternative joins across expressive pauses: 'third ... same' must not
    lose its predicate, nor swallow the next 'fourth ... same' by accident.
    """
    words = transcript.words
    if not words: return []
    edges = [0]
    for i, w in enumerate(words[:-1]):
        following = words[i + 1]
        coarse = not w.aligned and not following.aligned and (w.start, w.end) == (following.start, following.end)
        gap = following.start - w.end
        # A pause in the middle of a noun phrase is NOT an utterance ending.
        # Short pauses can introduce a new clause with an explicit discourse
        # lead-in. Keep expressive 'ek ... alag struggle' and 'third ... same'.
        lead_in = normalized(following.text)[:1]
        clause_start = gap >= .25 and lead_in in (['aur'], ['lekin'], ['but'], ['and'], ['yahan'], ['to'],
                                                  ['tab'], ['then'], ['however'], ['phir'], ['isliye'])
        if not coarse and (gap >= 1.2 or clause_start or re.search(r'[,.!?;।]["\u201d\u2019]*$', w.text)):
            edges.append(i + 1)
        elif not coarse and w.end - words[edges[-1]].start >= 18:
            edges.append(i + 1)
    edges.append(len(words))
    spans = []
    for i, a in enumerate(edges[:-1]):
        for j in range(i + 1, min(i + 7, len(edges))):
            b = edges[j]
            if j > i + 1 and (words[b - 1].end - words[a].start > 35 or
                             words[edges[j - 1]].start - words[edges[j - 1] - 1].end > 3):
                break
            spans.append(span(transcript, a, b))
    return spans


def retrieve_phrases(units, transcripts, settings, encoder, progress=print):
    import numpy as np
    corpus = [(t, s, order) for order, t in enumerate(transcripts) for s in phrase_spans(t)]
    if not corpus: return [[] for _ in units]
    vectors = encoder.encode([s.text for _, s, _ in corpus], progress)
    queries = encoder.encode([u['idea'] for u in units], progress)
    pools = []
    for unit, query in zip(units, queries):
        similarities = vectors @ query
        # Bounded reranking: never construct a full script x corpus matrix.
        shortlist = np.argsort(-similarities)[:min(48, len(corpus))]
        ranked = []
        for j in shortlist:
            t, s, order = corpus[j]
            source_tokens = tokens(s.text)
            if len(normalized(unit['idea'])) > 3:
                if len(source_tokens) < 3: continue
                if (source_tokens[-1] in {'ek', 'a', 'an', 'mein', 'me', 'pe', 'par', 'aur', 'and', 'or', 'ki', 'ke', 'ka'}
                        and normalized(s.text)[-1:] != normalized(unit['idea'])[-1:]):
                    continue
            evidence = text_evidence(unit['idea'], s.text)
            similarity = float(similarities[j])
            score = .75 * similarity + .25 * evidence['score']
            ranked.append({'span': s, 'source_name': Path(t.media.path).name,
                           'source_order': order, 'source_frame_rate': float(t.media.rate),
                           'similarity': similarity, 'score': score, 'evidence': evidence,
                           'eligible': False, 'issues': []})
        ranked.sort(key=lambda c: -c['score'])
        pool = []
        # Retain boundary alternatives AND distinct occurrences. Long joined
        # spans must not crowd all shorter, clean retakes out of the shortlist.
        maximum = max(6, settings.candidates_per_line)
        for limit, quota in ((1, 3), (3, maximum)):
            for c in ranked:
                if c in pool: continue
                s = c['span']
                overlapping = sum(s.media_id == o['span'].media_id and
                    max(s.first, o['span'].first) < min(s.last, o['span'].last) for o in pool)
                if overlapping >= limit: continue
                pool.append(c)
                if len(pool) >= quota: break
            if len(pool) >= maximum: break
        pools.append(pool)
    return pools


def prefer_latest(units, pools, settings):
    for unit, pool in zip(units, pools):
        if len(normalized(unit['idea'])) <= 3: continue
        if sum(normalized(u['idea']) == normalized(unit['idea']) for u in units) > 1: continue
        eligible = [c for c in pool if c['eligible']]
        if len(eligible) < 2:
            continue
        # Every eligible option already passed the complete-meaning check for
        # this exact, unique script sentence. The user's rule is deterministic:
        # the final recorded occurrence wins, including across separate files.
        anchor = max(eligible, key=lambda c: (c['source_order'], c['span'].start, c['span'].end))
        latest_order = anchor['source_order']
        same_occurrence = [c for c in eligible if c['source_order'] == latest_order
                           and c['span'].media_id == anchor['span'].media_id
                           and max(c['span'].first, anchor['span'].first) < min(c['span'].last, anchor['span'].last)]
        occurrence_start = min(c['span'].start for c in same_occurrence)
        latest_id = max(same_occurrence, key=lambda c: c['score'])['span'].id
        for earlier in eligible:
            a = earlier['span']
            old_file = earlier['source_order'] < latest_order
            old_occurrence = (earlier['source_order'] == latest_order
                              and a.media_id == anchor['span'].media_id
                              and a.end <= occurrence_start)
            if old_file or old_occurrence:
                earlier['eligible'] = False
                earlier['superseded_by'] = latest_id
                earlier['issues'].append('earlier_take_replaced_by_complete_later_take')


def apply_verdict(idea, candidate, verdict, settings):
    candidate['verdict'] = verdict
    expected = normalized(idea)
    actual = normalized(candidate['span'].text)
    issues = fact_concerns(' '.join(expected), ' '.join(actual), settings.protected_terms)
    ordinals = {'first': 1, 'pehla': 1, 'pahla': 1, 'second': 2, 'doosra': 2, 'dusra': 2,
                'third': 3, 'teesra': 3, 'tisra': 3, 'fourth': 4, 'chautha': 4}
    required_order = {ordinals[w] for w in expected if w in ordinals}
    spoken_order = {ordinals[w] for w in actual if w in ordinals}
    if required_order and spoken_order and not required_order.issubset(spoken_order):
        issues.append('different_ordinal_occurrence')
    if set(expected) & {'har', 'every', 'each'} and spoken_order and not set(actual) & {'har', 'every', 'each'}:
        issues.append('all_occurrences_not_one_numbered_occurrence')
    blocking = list(issues)
    # An ASR spelling such as an unresolved spoken amount is uncertainty, not
    # proof that an otherwise complete sentence should disappear. Explicitly
    # conflicting recognized quantities remain blocked, regardless of the LLM.
    expected_numbers = {w for w in expected if w.isdigit()}
    actual_numbers = {w for w in actual if w.isdigit()}
    if (blocking == ['numbers_need_review'] and expected_numbers and not actual_numbers
            and candidate['evidence']['recall'] >= .65 and verdict['status'] == 'complete'):
        blocking = []
        issues = ['quantity_unclear_in_transcript_listen_before_export']
    candidate['issues'] = issues
    candidate['eligible'] = verdict['status'] == 'complete' and not verdict['repeated'] and not blocking
    if verdict['repeated']: candidate['issues'].append('contains_repeated_attempt')


def arrange_meaning(text, transcripts, settings, encoder, judge, progress=print):
    units = meaning_units(text)
    pools = retrieve_phrases(units, transcripts, settings, encoder, progress)
    # Release embedding weights before loading the quantized judge on CPU.
    encoder.close()
    for unit, pool in zip(units, pools):
        if not pool: continue
        progress(f'Checking complete meaning {unit["index"] + 1}/{len(units)}: {unit["idea"][:65]}')
        # Whole-paragraph context made a small judge approve the paragraph's
        # topic instead of this individual clause. Compare only the requirement.
        if len(normalized(unit['idea'])) == 1:
            verdicts = [{'id': i, 'status': 'complete' if normalized(c['span'].text) == normalized(unit['idea']) else 'different',
                         'repeated': False, 'reason': 'Isolated cue requires a direct spoken occurrence.'}
                        for i, c in enumerate(pool)]
        else:
            verdicts = judge.compare(unit['idea'], [c['span'].text for c in pool])
        for c, v in zip(pool, verdicts):
            # Near-verbatim candidates can be overlooked when a batch includes
            # longer overlapping alternatives. Recheck that pair alone; never
            # upgrade it merely because it has high lexical overlap.
            e = c['evidence']
            if (v['status'] != 'complete' and e['recall'] >= .70 and e['precision'] >= .70
                    and e['content'] >= .70 and len(normalized(unit['idea'])) > 1):
                progress('  Rechecking a close spoken phrase independently')
                v = judge.compare(unit['idea'], [c['span'].text])[0]
            apply_verdict(unit['idea'], c, v, settings)
            # Favor compact complete thoughts over a span swallowing other ideas.
            c['score'] += .04 * c['evidence']['precision']
    prefer_latest(units, pools, settings)
    chosen, ambiguous = choose_sequence(pools, settings, len(transcripts) == 1)
    rows = []
    for unit, pool, selected in zip(units, pools, chosen):
        issues = list(selected['issues']) if selected else ['sentence_not_matched']
        if selected and not selected['span'].aligned: issues.append('timing_needs_listening_check')
        if unit['index'] in ambiguous: issues.append('alternative_occurrence_available')
        rows.append({**unit, 'selected': selected, 'alternatives': pool, 'issues': issues,
                     'selection_status': 'meaning_model_selected' if selected else 'unmatched'})
    return rows
