from dataclasses import asdict
from difflib import SequenceMatcher
import math
from pathlib import Path

from hinglish_cut.text import tokens
from .core import spans_for, fact_concerns, verified, choose_sequence
from .models import Embedder


def retrieve(lines, transcripts, settings, root, progress=print, embedder=None):
    spans = [s for t in transcripts for s in spans_for(t)]
    names = {t.media.id: Path(t.media.path).name for t in transcripts}
    if not spans:
        return [[] for _ in lines]
    encoder = embedder or Embedder(settings, root)
    try:
        vectors = encoder.encode(lines + [s.text for s in spans], progress)
    finally:
        if embedder is None: encoder.close()
    scores = vectors[:len(lines)] @ vectors[len(lines):].T
    pools = []
    for i, line in enumerate(lines):
        candidates = []
        for j, span in enumerate(spans):
            similarity = float(scores[i, j])
            if not math.isfinite(similarity) or similarity < settings.similarity_floor:
                continue
            lexical = SequenceMatcher(None, tokens(line), tokens(span.text), autojunk=False).ratio()
            # Semantic score dominates. Shorter equally good spans avoid swallowing
            # the neighboring script idea, but paraphrases may use more words.
            score = .92 * similarity + .08 * lexical
            score -= max(0, len(tokens(span.text)) - max(20, len(tokens(line)) * 2)) * .0005
            candidates.append({'span': span, 'score': score, 'similarity': similarity, 'source_name': names[span.media_id],
                               'eligible': False, 'issues': fact_concerns(line, span.text, settings.protected_terms)})
        candidates.sort(key=lambda c: (-c['score'], c['span'].last - c['span'].first, c['span'].id))
        # Keep endpoint variants AND distinct occurrences. A wide near-duplicate
        # cannot use up all candidate slots and hide a different take.
        selected, variants = [], []
        for c in candidates:
            s = c['span']
            if any(s.media_id == x['span'].media_id and max(s.first, x['span'].first) < min(s.last, x['span'].last) for x in selected):
                variants.append(c)
            else:
                selected.append(c)
        limit = settings.candidates_per_line
        selected = selected[:max(1, limit - 1)] + variants[:1]
        pools.append(sorted(selected, key=lambda c: -c['score'])[:limit])
    return pools


def verify_candidates(lines, pools, verifier, settings, progress=print):
    for i, pool in enumerate(pools):
        for j, c in enumerate(pool):
            progress(f'Checking meaning: idea {i + 1}/{len(lines)}, option {j + 1}/{len(pool)}')
            span = c['span']
            try:
                result = verifier.check('match', expected=lines[i], spoken=span.text,
                                        script_context=' / '.join(lines[max(0, i - 1):i + 2]),
                                        spoken_context=span.context)
                c['verdict'] = result
                c['eligible'] = verified(result, settings) and not c['issues']
                if not verified(result, settings): c['issues'].append('meaning_not_verified')
            except Exception as error:
                c['issues'].append('verifier_unavailable_or_uncertain')
                c['verification_error'] = str(error)
    return pools


def select(lines, pools, settings, transcripts):
    chosen, ambiguous = choose_sequence(pools, settings, len(transcripts) == 1)
    rows = []
    for i, line in enumerate(lines):
        c = chosen[i] if i < len(chosen) else None
        issues = []
        if c is None: issues.append('no_verified_match')
        if i in ambiguous: issues.append('multiple_possible_occurrences')
        if c and not c['span'].aligned: issues.append('uncertain_word_alignment')
        rows.append({'idea': line, 'index': i, 'selected': c, 'issues': issues,
                     'alternatives': pools[i]})
    return rows
