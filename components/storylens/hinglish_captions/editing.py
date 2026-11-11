"""Validate direct caption edits before spending time rendering or changing files."""
from dataclasses import replace
import math


def number(value, name, low, high):
    if isinstance(value,bool):raise ValueError(f'Invalid {name}')
    try:value=float(value)
    except (TypeError,ValueError):raise ValueError(f'Invalid {name}') from None
    if not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{name} must be between {low:g} and {high:g}')
    return value


def apply_timings(cues, rows, duration):
    if rows is None:return cues
    if not isinstance(rows,list) or len(rows)!=len(cues):raise ValueError('Caption timing count does not match')
    result=[];previous=0
    for index,(cue,row) in enumerate(zip(cues,rows),1):
        if not isinstance(row,dict):raise ValueError('Invalid caption timing')
        # The editor stores four decimal places. Snap only its sub-tick rounding
        # error; substantive out-of-range edits must still fail validation.
        def timestamp(value, name, low, high):
            value=number(value,name,low-.0001,high+.0001)
            return min(high,max(low,value))
        start=timestamp(row.get('start'),'caption start',0,duration)
        end=timestamp(row.get('end'),'caption end',0,duration)
        if previous-.0001<=start<previous:start=previous
        if start<previous-1e-6 or end-start<.04:raise ValueError('Caption timings overlap or are too short')
        words=row.get('words')
        if not isinstance(words,list) or len(words)!=len(cue.words):raise ValueError('Word timing count does not match the caption text')
        updated=[];word_end=start
        for word,timing in zip(cue.words,words):
            if not isinstance(timing,dict):raise ValueError('Invalid word timing')
            a=timestamp(timing.get('start'),'word start',start,end)
            b=timestamp(timing.get('end'),'word end',start,end)
            if word_end-.0001<=a<word_end:a=word_end
            if a<word_end-1e-6 or b-a<.01:raise ValueError(f'Words in caption {index} overlap or have invalid duration')
            updated.append(replace(word,start=a,end=b));word_end=b
        result.append(replace(cue,start=start,end=end,words=tuple(updated)));previous=end
    return result


def layouts_for(cues, rows, position=.7, size=1):
    if rows is None:rows=[{'x':.5,'y':position,'size':size} for _ in cues]
    if not isinstance(rows,list) or len(rows)!=len(cues):raise ValueError('Caption layout count does not match')
    if any(not isinstance(row,dict) for row in rows):raise ValueError('Invalid caption layout')
    return [{'x':number(row.get('x',.5),'horizontal position',0,1),
             'y':number(row.get('y',position),'vertical position',0,1),
             'size':number(row.get('size',size),'caption size',.08,4)}
            for row in rows]


def visible_events(cues, visibility):
    """Half-open intervals: no early next word or late previous word in gaps."""
    for index,cue in enumerate(cues):
        if visibility in ('spoken','styled_spoken'):
            for word in cue.words:
                start,end=max(cue.start,word.start),min(cue.end,word.end)
                if start<end:yield index,start,end,word.text
        else:yield index,cue.start,cue.end,cue.text
