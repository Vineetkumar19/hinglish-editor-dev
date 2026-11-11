"""Rebind approved typography slots to new words without redesigning the style.

Reference text is an example, never a password that unlocks the actual design.
Only source indices are replaced; fonts, row anchors, emphasis and motion stay
with the saved slots. Speech timing always comes from the new cue.
"""
from copy import deepcopy
import math
from contextvars import ContextVar
from contextlib import contextmanager

source_text=ContextVar('caption_template_source',default='')
source_slot=ContextVar('caption_template_slot',default=-1)
PATTERN_REVISION=1


@contextmanager
def pattern_context(cue):
    text=source_text.set(cue.template_source or cue.text);slot=source_slot.set(cue.template_slot)
    try:yield
    finally:source_text.reset(text);source_slot.reset(slot)


def bind_patterns(cues,originals=None):
    """Freeze pattern identity before splitting or rendering a new script."""
    from dataclasses import replace
    rebinding=originals is not None
    originals=list(originals if rebinding else cues)
    result=[]
    for index,cue in enumerate(cues):
        matches=[old for old in originals if cue.words and old.start<=cue.words[0].start<old.end] if rebinding else []
        # Optional cue tails can overlap the following cue. The latest start
        # owns that word; a tail must never steal the next caption's pattern.
        origin=max(matches,key=lambda old:old.start) if matches else cue
        slot=origin.template_slot if origin.template_slot>=0 else (originals.index(origin) if origin in originals else index)
        result.append(replace(cue,template_source=origin.template_source or origin.text,template_slot=slot))
    return result


def patterned(function):
    from functools import wraps
    @wraps(function)
    def call(cue,*args,**kwargs):
        with pattern_context(cue):return function(cue,*args,**kwargs)
    return call


def stable_anchor(words,picker):
    """Retain a cue's emphasis slot when its wording is edited."""
    original=source_text.get().split()
    if not original or list(map(token,original))==list(map(token,words)):return None
    state=source_text.set('')
    try:index=picker(original)
    finally:source_text.reset(state)
    return min(len(words)-1,math.floor((index+.5)*len(words)/len(original)))


def token(value):
    return ''.join(c for c in str(value).casefold() if c.isalnum())


def rebound(words):
    original=source_text.get()
    return bool(original and list(map(token,original.split()))!=list(map(token,words)))


def transfer(words, recipes):
    if not words or not recipes:
        return None
    original=source_text.get()
    numeric=any(token(w).isdigit() for w in (original.split() if original else words))
    candidates=[r for r in recipes if r.get('text')]
    # Do not apply a giant numeric layout to an ordinary sentence.
    compatible=[r for r in candidates if any(token(w).isdigit() for w in r['text'].split())==numeric]
    candidates=compatible or candidates
    saved=next((r for r in candidates if list(map(token,r['text'].split()))==list(map(token,original.split()))),None) if original else None
    target=original.split() if original else words
    source=saved or (candidates[source_slot.get()%len(candidates)] if source_slot.get()>=0 else min(enumerate(candidates),key=lambda pair:(abs(len(pair[1]['text'].split())-len(target)),pair[0]))[1])
    old=source['text'].split();n=len(words);m=len(old)
    mapping=[min(m-1,math.floor((i+.5)*m/n)) for i in range(n)]
    mains=[r for r in source.get('rows',[]) if r.get('role')=='main' or r.get('blue')]
    if mains and not any(j in mains[0]['words'] for j in mapping):
        hero=mains[0]['words'][0]
        mapping[min(range(n),key=lambda i:abs(mapping[i]-hero))]=hero
    out=deepcopy(source)
    for key in ('start','end','starts','sample_beats','display','hero_frame','replace_words'):
        out.pop(key,None)
    out.update(text=' '.join(words),template_pattern=source['text'],adapted=True)
    if 'rows' in out:
        rows=[]
        for row in source['rows']:
            ids=[i for i,j in enumerate(mapping) if j in row['words']]
            if not ids:continue
            new=deepcopy(row);new['words']=ids;new.pop('frame',None)
            for field in ('green',):
                if field in row:new[field]=[i for i in ids if mapping[i] in row[field]]
            for field in ('sizes','tones'):
                if isinstance(row.get(field),dict):new[field]={str(i):row[field][str(mapping[i])] for i in ids if str(mapping[i]) in row[field]}
                elif isinstance(row.get(field),list):new[field]=[row[field][row['words'].index(mapping[i])] for i in ids]
            rows.append(new)
        out['rows']=rows
    if 'runs' in source:
        out['runs']=[deepcopy(source['runs'][j]) for j in mapping]
        for i,run in enumerate(out['runs']):run['source_word']=old[mapping[i]]
    for field in ('hero','support_focus'):
        if isinstance(source.get(field),int) and source[field]>=0:
            out[field]=min(range(n),key=lambda i:abs(mapping[i]-source[field]))
    if isinstance(source.get('motion'),list):
        out['motion']=[deepcopy(source['motion'][j]) for j in mapping]
        for i,move in enumerate(out['motion']):
            move['start_word']=min(range(n),key=lambda k:abs(mapping[k]-move.get('start_word',mapping[i])))
    for decoration in out.get('decorations',[]):
        if 'trigger' in decoration:decoration['trigger']=min(range(n),key=lambda i:abs(mapping[i]-decoration['trigger']))
    return out
