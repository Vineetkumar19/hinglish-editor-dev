from dataclasses import asdict
from pathlib import Path

from hinglish_cut.cutting import make_cuts
from hinglish_cut.media import assemble_audio
from hinglish_cut.text import tokens
from .core import cleanup_proposals, cleanup_verdict, fact_concerns, subtract_ranges, verified


def assess_cleanup(transcript, settings, verifier, progress=print, semantic_scores=None):
    proposals = cleanup_proposals(transcript, settings, semantic_scores)
    accepted_word_ranges = []
    # Latest-first makes three confirmed attempts collapse to the final one.
    proposals.sort(key=lambda p: -p['first'])
    for i, p in enumerate(proposals):
        p['approved'] = False
        if not p['eligible']:
            p['review_reason'] = 'Uncertain timing or context; kept for review'
            continue
        if any(max(p['first'], a) < min(p['last'], b) for a, b in accepted_word_ranges):
            p['review_reason'] = 'Overlaps another proposed removal'
            continue
        progress(f'Checking {p["kind"]} {i + 1}/{len(proposals)}: {p["text"][:65]}')
        try:
            if p['kind'] == 'filler':
                result = verifier.check('filler', target=p['text'], context=p['context'])
            else:
                if fact_concerns(p['text'], p['replacement'], settings.protected_terms):
                    p['review_reason'] = 'Facts may differ between attempts; kept'
                    continue
                result = verifier.check('retake', earlier=p['text'], later=p['replacement'], context=p['context'])
            p['verdict'] = result
            p['approved'] = cleanup_verdict(p['kind'], result, settings, target=p['text'],
                                             earlier=p.get('text', ''), later=p.get('replacement', ''))
            if p['approved']:
                accepted_word_ranges.append((p['first'], p['last']))
        except Exception as error:
            p['review_reason'] = str(error)
    return sorted(proposals, key=lambda p: p['first'])


def cleanup_cuts(transcript, settings, proposals):
    config = settings.speech_settings()
    if transcript.words:
        # Keep ALL source speech, including VAD regions without a usable transcript.
        from hinglish_clean.detection import plan_cuts, CleanSettings
        speech = [tuple(region) for region in transcript.speech] + [(w.start, w.end) for w in transcript.words]
        base = plan_cuts(transcript.media, speech, CleanSettings())
    else:
        from hinglish_clean.detection import plan_cuts, CleanSettings
        base = plan_cuts(transcript.media, transcript.speech, CleanSettings())
    approved = [p for p in proposals if p.get('approved')]
    cuts = subtract_ranges(base, [p['bounds'] for p in approved])
    # No removal may touch a non-target word, including coarse alignments.
    rate = float(transcript.media.rate)
    for i, word in enumerate(transcript.words):
        if any(p['first'] <= i < p['last'] for p in approved):
            continue
        if any(max(word.start, a / rate) < min(word.end, b / rate) for p in approved for a, b in [p['bounds']]):
            raise ValueError('Cleanup would touch a neighboring word; refusing cut')
    return base, cuts


def verify_cleanup_audio(transcript, proposals, wav, output, settings, recognize, verifier, progress=print):
    """Check local cut neighborhoods, avoiding hour-long context truncation.

    A failed check restores that proposal. This stage does not infer missing
    fillers: only actual ASR words with usable audio alignment are candidates.
    """
    media = {transcript.media.id: transcript.media}
    paths = {transcript.media.id: wav}
    words = transcript.words
    for p in proposals:
        if not p.get('approved'):
            continue
        progress(f'Listening back around {p["kind"]} at {words[p["first"]].start:.1f}s')
        first = max(0, p['first'] - 6)
        last = min(len(words), max(p['last'] + 6, p.get('replacement_last', 0)))
        if words[last - 1].end - words[first].start > 55:
            p['approved'] = False
            p['review_reason'] = 'Verification span too long; original kept'
            continue
        expected = ' '.join(w.text for i, w in enumerate(words[first:last], first)
                            if not p['first'] <= i < p['last'])
        context_cuts = make_cuts(transcript, first, last, settings.speech_settings(), conservative=True)
        edited = subtract_ranges(context_cuts, [p['bounds']])
        audio = Path(output) / f'check-{p["id"].replace(":", "-")}.wav'
        assemble_audio(edited, media, paths, audio)
        p['preview'] = audio.name
        try:
            actual = recognize(audio)
            p['heard_after'] = actual
            if not tokens(actual) or fact_concerns(expected, actual, settings.protected_terms):
                raise ValueError('Replay transcription has missing or changed facts')
            result = verifier.check('preservation', expected=expected, spoken=actual)
            p['replay_verdict'] = result
            if not verified(result, settings):
                raise ValueError('Replay meaning could not be verified')
        except Exception as error:
            p['approved'] = False
            p['review_reason'] = 'Restored: ' + str(error)
    return proposals
