"""Keep natural source pauses and safe word handles; never time-stretch speech."""
import re
from .core import Span


# lead, tail, pause threshold, paragraph lead, paragraph tail (seconds)
PRESETS = {'tight': (.08, .12, .30, .08, .12),
           'natural': (.18, .35, .65, .25, .55),
           'relaxed': (.25, .45, .85, .30, .65)}


def paced_spans(rows, transcripts, mode):
    """Preserve short sentence endings otherwise lost to a script wording gap."""
    by_id = {t.media.id: t for t in transcripts}
    selected = [r['selected']['span'] for r in rows if r.get('selected')]
    result = {}
    for row in rows:
        if not row.get('selected'): continue
        s = row['selected']['span']
        words = by_id[s.media_id].words
        last = s.last
        if mode != 'tight' and not re.search(r'[.!?।]["\u201d\u2019]*$', words[last - 1].text):
            candidate_last = last
            # Only a short attached ending up to punctuation, not an unrelated
            # next sentence, a restart after a pause, or another selected clause.
            for i in range(last, min(last + 3, len(words))):
                if words[i].start - words[i - 1].end > .18 or words[i].end - s.end > .85: break
                if any(other.media_id == s.media_id and other.first <= i < other.last for other in selected): break
                if not words[i].aligned: break
                if re.search(r'[.!?।]["\u201d\u2019]*$', words[i].text):
                    candidate_last = i + 1
                    break
            last = candidate_last
        effective = Span(s.id, s.media_id, s.first, last, s.start, words[last - 1].end,
                         ' '.join(w.text for w in words[s.first:last]), s.context, s.aligned)
        result[row['index']] = effective
        row['cut_text'] = effective.text
        row['restored_ending'] = ' '.join(w.text for w in words[s.last:last])
    return result


def handles(row, selected_rows, mode):
    lead, tail, threshold, paragraph_lead, paragraph_tail = PRESETS[mode]
    index = selected_rows.index(row)
    if index == 0 or selected_rows[index - 1].get('paragraph_index') != row.get('paragraph_index'):
        lead = paragraph_lead
    if index == len(selected_rows) - 1 or selected_rows[index + 1].get('paragraph_index') != row.get('paragraph_index'):
        tail = paragraph_tail
    return lead, tail, threshold
