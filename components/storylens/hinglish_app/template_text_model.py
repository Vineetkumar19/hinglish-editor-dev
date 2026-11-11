"""Bounded contracts: native timing is evidence; scripts/model answers are data only."""
from difflib import SequenceMatcher
from array import array
import hashlib
import json
import math
import re
import unicodedata

VERSION=1
MAX_DURATION=7200
FUNCTION_WORDS=set('the a an is are was were and or but to of in on at for with from that this it as by be been being i we you he she they his her our their its have has had not so then than very also will would can could mein me hai hain tha thi aur ka ki ke ko se par pe ne ye yeh woh wo ek iska uska jo hi bhi kya ab lekin phir us iss hum aap tum'.split())

def signature(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()

def number(value,minimum,maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum<=value<=maximum:raise ValueError('Template Text: scan the current final composition again; its timing is invalid.')
    return value

def validate_snapshot(value):
    if not isinstance(value,dict) or value.get('version')!=VERSION:raise ValueError('Template Text: reopen Storylens and scan the final composition again.')
    if not all(isinstance(value.get(k),str) and 0<len(value[k])<=4096 for k in ('project_id','composition_id','fingerprint')):raise ValueError('Template Text: open the final composition and retry.')
    duration=number(value.get('duration'),.05,MAX_DURATION);number(value.get('fps'),1,240)
    templates=value.get('templates');audio=value.get('audio')
    if not isinstance(templates,list) or not 1<=len(templates)<=200:raise ValueError('Template Text: open a composition containing placed template layers.')
    count=0;template_ids=set()
    for template in templates:
        if not isinstance(template,dict) or not all(str(template.get(k,'')) for k in ('layer_id','source_id')):raise ValueError('Template Text: a placed template has changed. Scan again.')
        if str(template['layer_id']) in template_ids:raise ValueError('Template Text: duplicate placed-template identities. Scan again.')
        template_ids.add(str(template['layer_id']))
        if number(template.get('start'),0,duration)>=number(template.get('end'),0,duration):raise ValueError('Template Text: check the placed template duration.')
        texts=template.get('texts');seen=set()
        if not isinstance(texts,list):raise ValueError('Template Text: scan template lettering again.')
        for row in texts:
            count+=1
            if not isinstance(row,dict) or not isinstance(row.get('text'),str) or len(row['text'])>12000 or not isinstance(row.get('id'),str) or row['id'] in seen:raise ValueError('Template Text: an unsupported text slot was found. Check Technical details.')
            seen.add(row['id']);runs=row.get('runs',[])
            if not isinstance(runs,list) or len(runs)>128:raise ValueError('Template Text: this template has too many text timing sections.')
            for run in runs:
                start=number(run.get('start'),0,duration);end=number(run.get('end'),0,duration)
                if end<=start or start<template['start']-.04 or end>template['end']+.04:raise ValueError('Template Text: a text slot falls outside its placed template. Scan again.')
    if not 1<=count<=5000:raise ValueError('Template Text: no editable text was found, or this project exceeds 5,000 visible text slots.')
    if not isinstance(audio,list) or not 1<=len(audio)<=1000:raise ValueError('Template Text: no readable narration was found. Choose the final narrated video or audio in Settings.')
    for row in audio:
        if not isinstance(row,dict) or not isinstance(row.get('path'),str) or len(row['path'])>4096:raise ValueError('Template Text: choose the final narrated video or audio.')
        if number(row.get('start'),0,duration)>=number(row.get('end'),0,duration):raise ValueError('Template Text: check the final audio timing.')
        number(row.get('source_in'),0,86400);number(row.get('rate'),.05,20);number(row.get('gain',1),0,100)
    return value

def normal(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',str(text)).casefold() if c.isalnum())

def speech_normal(text):
    # Uroman emits long vowels/retroflex doubles (mumbaaii, thaa, kaaphii).
    # Canonicalize only the comparison key, never the owner's displayed words.
    value=normal(text).replace('ph','f').replace('w','v')
    return re.sub(r'([a-z])\1+',r'\1',value)

def align_script(script,observed,normalizer=normal):
    """Match exact spoken anchors; short fuzzy replacements require lexical support.

    Never distribute a whole script over video duration or bridge missing paragraphs.
    """
    tokens=script.split();a=[normalizer(t) for t in tokens];b=[normalizer(w['text']) for w in observed]
    # Weighted monotonic alignment handles long runs of Hindi/Roman spelling
    # differences and omitted ASR words. Two score rows plus one byte per pair
    # keep memory bounded; no full Python-object matrix or invented timestamps.
    if not a or not b:return []
    if len(a)*len(b)>40_000_000:raise ValueError('Template Text alignment: use a shorter final narration for this text pass.')
    def similarity(x,y):
        if x==y and x:return 30
        if min(len(x),len(y))<4 or any(c.isdigit() for c in x+y):return 0
        if min(len(x),len(y))/max(len(x),len(y))<.6:return 0
        ratio=SequenceMatcher(None,x,y,autojunk=False).ratio()
        return round(ratio*22) if ratio>=.72 else 0
    unique_a=set(a);unique_b=set(b)
    matches={x:{y:s for y in unique_b if (s:=similarity(x,y))} for x in unique_a}
    width=len(b)+1;directions=bytearray((len(a)+1)*width);previous=array('i',[0])*width
    for i,x in enumerate(a,1):
        current=array('i',[0])*width;row=matches[x];offset=i*width
        for j,y in enumerate(b,1):
            score=row.get(y,0);diagonal=previous[j-1]+score if score else -1
            if diagonal>=previous[j] and diagonal>=current[j-1]:current[j]=diagonal;directions[offset+j]=1
            elif previous[j]>=current[j-1]:current[j]=previous[j];directions[offset+j]=2
            else:current[j]=current[j-1];directions[offset+j]=3
        previous=current
    mapped=[];i=len(a);j=len(b)
    while i and j:
        direction=directions[i*width+j]
        if direction==1:
            mapped.append({**observed[j-1],'text':tokens[i-1],'script_index':i-1,'alignment':'matched' if a[i-1]==b[j-1] else 'phonetic'});i-=1;j-=1
        elif direction==2:i-=1
        else:j-=1
    return list(reversed(mapped))

def bridge_short_gaps(script,words):
    """Recover short ASR omissions between timed anchors, never whole paragraphs.

    These are estimated timings, recorded separately from directly matched words.
    Numeric facts must have direct speech evidence, not inferred gap timestamps.
    """
    tokens=script.split();result=[]
    for word in words:
        if result:
            previous=result[-1];first=previous['script_index']+1;last=word['script_index']
            gap=word['start']-previous['end'];missing=tokens[first:last]
            if (1<=len(missing)<=3 and .12*len(missing)<=gap<=2.0
                    and last-first==len(missing) and not any(re.search(r'\d',t) for t in missing)):
                for index,text in enumerate(missing):
                    result.append({'text':text,'script_index':first+index,
                                   'start':previous['end']+gap*index/len(missing),
                                   'end':previous['end']+gap*(index+1)/len(missing),
                                   'alignment':'bounded_interpolation'})
        result.append(word)
    return result


def heading_candidates(slot,vocabulary=None):
    """Give the local editor bounded, verbatim options, not free-form prose."""
    words=slot['words'];candidates=[];seen=set()
    filler=FUNCTION_WORDS|set('achha achhe achhi poori poora pahla pahli pahunch paati karta karti karte hota hoti hote hua hui hue katti again kaafi bahut sirf ho hone jaata jaati jaate tha thi'.split())
    for start in range(len(words)):
        for length in range(1,5):
            group=words[start:start+length]
            if len(group)!=length or any(w['script_index']!=group[0]['script_index']+i for i,w in enumerate(group)):continue
            tokens=[normal(w['text']) for w in group]
            if tokens[0] in filler or tokens[-1] in filler or not all(tokens):continue
            phrase=' '.join(w['text'] for w in group);key=tuple(tokens)
            font=slot.get('font_size',0);width=slot.get('bounds',{}).get('width',0)
            if font and width and width/max(1,len(phrase)*.5)<min(24,font*.55):continue
            if vocabulary is not None and key not in vocabulary and not (len(tokens)==1 and re.fullmatch(r'(?:19|20)\d{2}',tokens[0])):continue
            if key in seen:continue
            seen.add(key);candidates.append({'text':phrase,'word_indices':[w['script_index'] for w in group]})
    return candidates

def catalog_choice(slot,candidates,index):
    if type(index) is not int or index < -1 or index>=len(candidates):raise ValueError('Template Text: invalid heading selection. No text was applied.')
    row={'id':slot['id'],'role':'heading','action':'hide' if index==-1 else 'replace','word_indices':[] if index==-1 else candidates[index]['word_indices']}
    return validated_choices([slot],{'choices':[row]})[0]

def heading_priority(slot):
    """Prefer readable scene titles to long-lived decorative lettering."""
    duration=sum(r['end']-r['start'] for r in slot['runs'])
    return (slot.get('display_opacity',1)<.65, bool(slot.get('background_text')),
            round(duration,1), -min(slot.get('font_size',0),160),slot['id'])

def heading_overlap(a,b):
    overlap=min(a['end'],b['end'])-max(a['start'],b['start'])
    # A brief authored crossfade must not erase the following scene's heading.
    tolerance=min(.75,.2*min(a['end']-a['start'],b['end']-b['start']))
    return overlap>max(.001,tolerance)

def uncovered_headings(slots,actions):
    """Offer usable scene titles to the model; this is not a fill-every-slide quota."""
    lookup={s['id']:s for s in slots};occupied=[];result=[]
    for action in actions:
        if action['action']=='replace' and action.get('role')=='heading':
            occupied.extend(lookup[action['id']]['runs'])
    candidates=sorted((s for s in slots if s['policy']=='choose' and not s.get('existing_date') and not s.get('background_text') and s.get('projected',{}).get('usable',True)
                       and max(r['end']-r['start'] for r in s['runs'])>=1.5),key=heading_priority)
    for slot in candidates:
        if any(heading_overlap(a,b) for a in slot['runs'] for b in occupied):continue
        result.append(slot);occupied.extend(slot['runs'])
    return sorted(result,key=lambda s:min(r['start'] for r in s['runs']))


def build_slots(snapshot,words):
    result=[]
    for template in snapshot['templates']:
        for row in template['texts']:
            if not row.get('runs'):continue
            identifier=str(template['layer_id'])+'/'+row['id'];text=row.get('baseline_text',row['text']);count=len(text.split())
            stock=bool(re.search(r'copies\s+and\s+accessories|put here your content|some historical text goes here|no one will be reading|aftereffesct\s+photo slide|after effects\s+cs\d|^photo\s+(?:frame|full)\s*\d+\s*$|renname ae template',text,re.I))
            stock=stock or count>6 and bool(re.search(r'lorem\s+ipsum',text,re.I))
            year_ruler=len(set(re.findall(r'\b(?:1[0-9]{3}|20[0-9]{2})\b',text)))>=3
            empty=not text.replace('\u200b','').replace('\ufeff','').strip() and not row.get('expression') and not row.get('unsafe')
            policy='skip' if 'matte' in row.get('unsafe','').lower() or not row.get('enabled',True) else 'hide' if empty or count>18 or len(text)>180 or stock or year_ruler else 'skip' if row.get('expression') or row.get('unsafe') else 'choose'
            local=[w for w in words if any(r['start']<w['end'] and r['end']>w['start'] for r in row['runs'])]
            # A short surrounding spoken phrase is useful only when the title has an
            # extremely short entrance; never borrow a distant paragraph or date.
            if not local and row['runs']:
                start=min(r['start'] for r in row['runs']);end=max(r['end'] for r in row['runs'])
                local=[w for w in words if start-.5<w['end'] and end+.5>w['start']]
            if policy=='choose' and not local:policy='hide'
            if policy=='choose' and not any(normal(w['text']) not in FUNCTION_WORDS for w in local):policy='hide'
            existing_date=bool(re.search(r'\b(?:1[0-9]{3}|20[0-9]{2})\b',text))
            if policy=='choose' and existing_date and not any(re.search(r'(?<!\d)(?:1[0-9]{3}|20[0-9]{2})(?!\d)',w['text']) for w in local):policy='hide'
            result.append({'id':identifier,'template_layer_id':str(template['layer_id']),'text_id':row['id'],'name':row.get('name',''),
                'example_text':text,'font_size':row.get('font_size',0),'bounds':row.get('bounds',{}),'runs':row['runs'],
                'display_opacity':row.get('display_opacity',1),'background_text':row.get('background_text',False),
                'projected':row.get('projected',{}),
                'policy':policy,'max_words':6,'words':local,
                'existing_date':existing_date,
                'reason':'Expression-controlled or unsupported text is kept.' if policy=='skip' else 'Long filler or no aligned narration.' if policy=='hide' else ''})
    return result

def group_choices(slots):
    """Reuse identical echo decisions only when their timing/evidence also agree."""
    representatives=[];groups={};identities={}
    for slot in slots:
        payload={k:v for k,v in slot.items() if k not in ('id','template_layer_id','text_id')}
        key=signature(payload)
        if key not in identities:
            identities[key]=slot['id'];representatives.append(slot);groups[slot['id']]=[]
        groups[identities[key]].append(slot)
    return representatives,groups

def expand_choices(choices,groups):
    return [{**choice,**{k:slot[k] for k in ('id','template_layer_id','text_id')}}
            for choice in choices for slot in groups[choice['id']]]

def limit_visible_text(slots,actions):
    """Keep one main heading and one short support/date, never a wall of text."""
    lookup={s['id']:s for s in slots};kept={'heading':[],'support':[]};rejected=set()
    candidates=[a for a in actions if a['action']=='replace']
    candidates.sort(key=lambda a:heading_priority(lookup[a['id']]))
    for action in candidates:
        category='heading' if action['role']=='heading' else 'support'
        runs=lookup[action['id']]['runs']
        if any(heading_overlap(a,b) for a in runs for b in kept[category]):rejected.add(action['id'])
        else:kept[category].extend(runs)
    return [{**a,'action':'hide','text':'','word_indices':[]} if a['id'] in rejected else a for a in actions]

def keyed_request(slots):
    rows=[];properties={}
    for index,slot in enumerate(slots):
        key=str(index);words=slot.get('_planner_words',slot['words'])
        phrases=[];phrase=[];previous=None
        for word in words:
            if previous is not None and word['script_index']!=previous+1:
                if phrase:phrases.append(' '.join(phrase))
                phrase=[]
            phrase.append(word['text']);previous=word['script_index']
        if phrase:phrases.append(' '.join(phrase))
        rows.append({**{k:slot[k] for k in ('name','example_text','font_size','bounds','runs','max_words','existing_date') if k in slot},'id':key,'spoken_fragments':phrases})
        properties[key]={'type':'object','properties':{'role':{'type':'string','enum':['heading','support','date']},'text':{'type':'string','maxLength':80}},'required':['role','text'],'additionalProperties':False}
    return rows,{'type':'object','properties':{'choices':{'type':'object','properties':properties,'additionalProperties':False}},'required':['choices'],'additionalProperties':False}

def keyed_choices(slots,answer):
    choices=answer.get('choices') if isinstance(answer,dict) else None
    if not isinstance(choices,dict):raise ValueError('Template Text: the local model did not return a text plan.')
    mapped=[];lookup={str(i):s['id'] for i,s in enumerate(slots)}
    for key,value in choices.items():
        if key not in lookup or not isinstance(value,dict):raise ValueError('Template Text: an unknown text slot was returned.')
        slot=slots[int(key)];phrase=value.get('text','');tokens=[normal(w) for w in phrase.split()] if isinstance(phrase,str) else [];indices=[]
        words=slot.get('_planner_words',slot['words'])
        if 0<len(tokens)<=(6 if value.get('role')=='support' else 4) and all(tokens):
            for start in range(len(words)-len(tokens)+1):
                segment=words[start:start+len(tokens)]
                if [normal(w['text']) for w in segment]==tokens and all(segment[i]['script_index']==segment[0]['script_index']+i for i in range(len(segment))):
                    indices=[w['script_index'] for w in segment];break
        mapped.append({'id':lookup[key],'role':value.get('role'),'word_indices':indices})
    return sparse_choices(slots,{'choices':mapped})

def sparse_choices(slots,answer):
    """Omitted or unsupported wording means hide; unknown native identities fail."""
    rows=answer.get('choices') if isinstance(answer,dict) else None
    expected={s['id']:s for s in slots};selected={}
    if not isinstance(rows,list):raise ValueError('Template Text: the local model did not return a text plan. Retry; your project is unchanged.')
    for row in rows:
        if not isinstance(row,dict) or row.get('id') not in expected or row['id'] in selected:raise ValueError('Template Text: the model returned an unknown or repeated slot. Retry; your project is unchanged.')
        selected[row['id']]=row
    result=[]
    for slot in slots:
        row=selected.get(slot['id'])
        if row:
            try:
                result.extend(validated_choices([slot],{'choices':[{**row,'action':'replace'}]}));continue
            except ValueError:pass
        result.append({'id':slot['id'],'template_layer_id':slot['template_layer_id'],'text_id':slot['text_id'],'action':'hide','role':'body','text':'','word_indices':[]})
    return result

def validated_choices(slots,answer):
    rows=answer.get('choices') if isinstance(answer,dict) else None
    expected={s['id']:s for s in slots if s['policy']=='choose'}
    if not isinstance(rows,list) or len(rows)!=len(expected):raise ValueError('Template Text: the model did not finish all text slots. Retry; your project is unchanged.')
    output=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or row.get('id') not in expected or row['id'] in seen:raise ValueError('Template Text: the model returned an unknown or repeated slot. Retry; your project is unchanged.')
        seen.add(row['id']);slot=expected[row['id']];action=row.get('action');role=row.get('role');indices=row.get('word_indices',[])
        if action not in ('replace','hide') or role not in ('heading','date','support','body','decorative'):raise ValueError('Template Text: retry this text plan; no project changes were made.')
        lookup={w['script_index']:w['text'] for w in slot['words']}
        if action=='hide':indices=[]
        if not isinstance(indices,list) or any(type(i) is not int or i not in lookup for i in indices) or indices!=sorted(set(indices)):raise ValueError('Template Text: the model selected words outside this scene. Retry; your project is unchanged.')
        text=' '.join(lookup[i] for i in indices).strip()
        if action=='replace' and (not indices or len(indices)>min(slot['max_words'],4 if role in ('heading','date') else 6) or role in ('body','decorative') or not any(normal(lookup[i]) not in FUNCTION_WORDS for i in indices)):
            action='hide';indices=[];text=''
        if slot.get('existing_date') and role!='date' and action=='replace':action='hide';indices=[];text=''
        if role=='date' and action=='replace':
            if not re.search(r'(?<!\d)(?:1[0-9]{3}|20[0-9]{2})(?!\d)',text) or not all(re.fullmatch(r'[\d.,/–—-]+|\d{1,2}(?:st|nd|rd|th)',lookup[i].strip('.,;:'),re.I) or normal(lookup[i]) in ('january','february','march','april','may','june','july','august','september','october','november','december') for i in indices):action='hide';indices=[];text=''
        output.append({'id':row['id'],'template_layer_id':slot['template_layer_id'],'text_id':slot['text_id'],'action':action,'role':role,'text':text,'word_indices':indices})
    return output
