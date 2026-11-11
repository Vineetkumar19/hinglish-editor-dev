"""Reference observations and reusable editorial patterns are stored separately."""
from pathlib import Path
from urllib.parse import urlsplit
import math
import re

from hinglish_cinematic.curation import file_hash
from .curation_http import store


LABELS = {'setup','stakes','question','evidence','withheld payoff','handoff'}


def inspect_reference(value):
    import av

    uri=value.get('url','').strip()
    url=urlsplit(uri)
    if uri and (url.scheme!='https' or not url.netloc or url.username or url.password):
        raise ValueError('Enter the reference publication URL.')
    path=Path(value['path']).resolve()
    with av.open(str(path)) as container:
        if not container.streams.video or not container.duration:
            raise ValueError('Choose a local reference video with a known duration.')
        duration=container.duration/av.time_base
    return {'url':uri or path.as_uri(),'path':str(path),'hash':file_hash(path),'duration':duration}


def save_card(state, value):
    ref=inspect_reference(value['reference'])
    if value['input_hashes']!=[ref['hash']]:
        raise ValueError('Reference media changed after inspection.')
    if not re.fullmatch('[a-f0-9]{32}',value['id']):
        raise ValueError('Choose a valid reference card ID.')
    title=_text(value.get('title'),120)
    rows=value.get('events')
    patterns=value.get('patterns')
    if not title or not isinstance(rows,list) or not 1<=len(rows)<=200:
        raise ValueError('Enter a title and at least one observed event.')
    if not isinstance(patterns,list) or not 1<=len(patterns)<=30:
        raise ValueError('Enter at least one reusable editorial pattern.')
    normalized=[]
    last_cut=-1
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError('Enter observations as event objects.')
        start,end=row.get('start'),row.get('end')
        if (not all(type(x) in (int,float) and math.isfinite(x) for x in (start,end))
                or not last_cut < start < end <= ref['duration'] or start < 0):
            raise ValueError('Use ascending cut times and valid source ranges.')
        last_cut=start
        if row.get('role') not in LABELS or row.get('certainty') not in ('observed','uncertain'):
            raise ValueError('Choose a narrative label and uncertainty for each event.')
        normalized.append({**{key:_text(row.get(key,''),240) for key in
                             ('shot','text','sound','transition','narration')},
                           'start':start,'end':end,'role':row['role'],'certainty':row['certainty']})
    rhythm=value.get('rhythm',{})
    if not isinstance(rhythm,dict):
        raise ValueError('Enter a rhythm profile.')
    profile={key:_text(rhythm.get(key,''),240) for key in ('silence','speech_density','music_intensity')}
    profile['shot_lengths']=[round(row['end']-row['start'],3) for row in normalized]
    reusable=[]
    for i,pattern in enumerate(patterns,1):
        if not isinstance(pattern,dict):
            raise ValueError('Enter abstract patterns as objects.')
        constraint=_text(pattern.get('constraint'),280)
        evidence=pattern.get('evidence')
        if (not constraint or not isinstance(evidence,list) or not evidence
                or any(type(index) is not int or not 1<=index<=len(normalized) for index in evidence)):
            raise ValueError('Bind each abstract pattern to numbered source observations.')
        reusable.append({'id':str(i),'constraint':constraint,'evidence':sorted(set(evidence)),
                         'state':'pending'})
    payload={'title':title,'reference':ref,'events':normalized,'rhythm':profile,'patterns':reusable}
    return store(state).mutate(value['id'],'reference-style',value,lambda old:payload)


def review_pattern(state, value):
    decision=value.get('decision')
    reviewer=_text(value.get('reviewer'),80)
    if not reviewer or decision not in ('accepted','rejected'):
        raise ValueError('Record a reviewer and an explicit decision.')

    def change(card):
        if not card:
            raise ValueError('Save the reference card before reviewing it.')
        ref=card['reference']
        if value['input_hashes']!=[ref['hash']] or file_hash(ref['path'])!=ref['hash']:
            raise ValueError('Reference media changed. Review the current source first.')
        selected=next((row for row in card['patterns'] if row['id']==value['pattern_id']),None)
        if selected is None:
            raise ValueError('Choose a pattern from this card.')
        if decision=='accepted' and not any(card['events'][index-1]['certainty']=='observed' for index in selected['evidence']):
            raise ValueError('Confirm at least one source observation before accepting this pattern.')
        selected.update(state=decision,reviewer=reviewer)
        return card

    return store(state).mutate(value['id'],'reference-style',value,change)


def approved_context(database, card_id):
    card=database.get(card_id)
    if card['kind']!='reference-style':
        raise ValueError('Choose a reviewed reference style card.')
    ref=card['reference']
    if file_hash(ref['path'])!=ref['hash']:
        raise ValueError('Reference media changed. Review the current source first.')
    patterns=[row for row in card['patterns'] if row['state']=='accepted']
    if not patterns:
        raise ValueError('Choose a reference with at least one accepted pattern.')
    return {'card_id':card_id,'revision':card['revision'],'title':card['title'],'reference_hash':ref['hash'],
            'source_url':ref['url'],'patterns':patterns}


def _text(value, limit):
    if not isinstance(value,str) or len(value.strip())>limit:
        raise ValueError(f'Enter short notes of up to {limit} characters.')
    return value.strip()
