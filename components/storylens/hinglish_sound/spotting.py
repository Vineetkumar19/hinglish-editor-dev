"""Resolve authored sound states against actual line evidence; never mute dialogue."""
import math
from dataclasses import replace

MODES = ('music', 'effects_only', 'voice_only')


def music_for_remix(plan, enabled):
    from copy import deepcopy
    plan.setdefault('all_music',deepcopy(plan.get('music',[])))
    return deepcopy([s for s in plan['all_music'] if s.get('path')]) if enabled else []


def explicit(rows):
    return isinstance(rows, list) and any(isinstance(r, dict) and 'mode' in r for r in rows)


def resolve_sections(rows, lines, seconds, moods):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Sound sections need a valid video duration')
    order = {line.id: n for n, line in enumerate(lines)}
    if not order or not isinstance(rows, list) or not rows:
        raise ValueError('Sound sections must cover the supplied lines')
    checked = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Sound section must be an object')
        a,b = row.get('from_id'),row.get('to_id')
        if type(a) is not int or type(b) is not int or a not in order or b not in order or order[b]<order[a]:
            raise ValueError('Sound section must use an ordered pair of supplied line IDs')
        mode = row.get('mode', 'music')
        if mode not in MODES or not isinstance(row.get('why'),str) or not row['why'].strip():
            raise ValueError('Choose music, effects_only or voice_only and explain the section')
        if mode == 'music' and row.get('mood') not in moods:
            raise ValueError('Music section mood must be available in the library')
        checked.append((order[a], order[b], dict(row,mode=mode)))
    checked.sort(key=lambda r:r[0])
    cursor,result = 0,[]
    for lo,hi,row in checked:
        if lo != cursor:
            raise ValueError('Sound sections overlap or leave unplanned lines')
        start = 0. if lo == 0 else float(lines[lo].start)
        end = float(lines[hi+1].start) if hi+1<len(lines) else float(seconds)
        if not math.isfinite(start) or not math.isfinite(end) or not 0<=start<end<=seconds:
            raise ValueError('Sound section timing falls outside the video')
        result.append(dict(row,start=start,end=end,strict_bounds=True))
        cursor = hi+1
    if cursor != len(lines):
        raise ValueError('Sound sections must cover every supplied line')
    return result


def mask_cues(cues, spans):
    """Retain the anchor and source alignment while trimming forbidden pre/tails."""
    if not spans:return list(cues),[]
    allowed = []
    for span in spans:
        if span['mode'] == 'voice_only':continue
        if allowed and abs(allowed[-1][1]-span['start'])<1e-6:
            allowed[-1] = (allowed[-1][0],span['end'])
        else:allowed.append((span['start'],span['end']))
    kept,dropped = [],[]
    for cue in cues:
        segment = next(((a,b) for a,b in allowed if a<=cue.target<b),None)
        if segment is None:
            dropped.append(dict(word=cue.word,type=cue.category,why='Intentional voice-only section'))
            continue
        a,b = segment
        start,end = max(a,cue.time),min(b,cue.time+cue.length)
        if end-start<.001:
            dropped.append(dict(word=cue.word,type=cue.category,why='No audible excerpt inside the sound section'))
            continue
        kept.append(replace(cue,time=start,length=end-start,source_offset=cue.source_offset+start-cue.time))
    return kept,dropped
