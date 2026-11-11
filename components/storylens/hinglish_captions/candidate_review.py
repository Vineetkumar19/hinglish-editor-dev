"""The local model selects corrections by immutable candidate IDs, never reversed edit fields."""
from difflib import SequenceMatcher
import re


def context_entities(brain,words):
    """Let the local model supply cricket spellings beyond the creator's saved examples."""
    from .proofread import entity_similarity
    text=' '.join(w.text for w in words)
    if not re.search(r'\b(?:IPL|cricket|bowling|batsman|batter|wickets?|Mumbai|Pollard|Hussey|KKR|CSK|RCB)\b',text,re.I):return []
    schema={'type':'object','additionalProperties':False,'properties':{'entities':{
        'type':'array','maxItems':12,'items':{'type':'string'}}},'required':['entities']}
    system=('List canonical spellings of cricket TEAMS and PLAYERS actually referred to by this speech. '
        'Use your cricket knowledge to recognize imperfect Roman-Hinglish pronunciations. Return only a list of names, not corrected sentences or before/after edits. '
        'Do not list unrelated famous players, infer a match/score/year, or add anyone not supported by the heard words. Empty list is valid.')
    from hinglish_niche.profiles import use
    with use({'profile':'general'}):answer=brain.json(system,{'speech':text[:12000]},schema,max_tokens=300,think=False)
    found=[]
    entities=answer.get('entities',[])
    if not isinstance(entities,list):return []
    for entity in entities:
        if not isinstance(entity,str) or not re.fullmatch(r"[A-Za-z][A-Za-z '.-]{1,65}",entity):continue
        count=len(entity.split())
        if not 2<=count<=4:continue
        if any(entity_similarity(' '.join(w.text for w in words[a:a+width]),entity,False)
               for width in range(max(1,count-1),count+2) for a in range(len(words)-width+1)):
            found.append(entity)
    return list(dict.fromkeys(found))


def choose(brain,words,ref,evidence,progress):
    from .proofread import entity_similarity,phonetic,numeric_values
    from .numbers import key
    from .audio_evidence import suspicious
    examples={(key(r['heard']),key(r['canonical'])) for r in ref.get('recognition_examples',[])}
    canonical_keys={key(n) for n in ref['cricket_entities']}
    valid_terms={key(n) for n in ref.get('cricket_terms',[])}
    candidates=[]
    seen=set()
    def add(a,b,after,kind,quote=''):
        before=' '.join(w.text for w in words[a:b+1])
        if key(before)==key(after):return
        if kind=='entity' and key(before) in canonical_keys:return
        if kind=='cricket_term' and key(before) in valid_terms:return
        identity=(a,b,key(after))
        if identity in seen:return
        seen.add(identity)
        candidates.append({'id':str(len(candidates)),'start_index':a,'end_index':b,
            'original':before,'proposed':after,'kind':kind,'evidence_quote':quote,
            'nearby_speech':' '.join(w.text for w in words[max(0,a-5):b+6])})
    discovered=context_entities(brain,words)
    # A recognizer spelling repeated by the model is not a new canonical name.
    discovered=[n for n in discovered if not any(key(n)!=key(c) and entity_similarity(n,c,True)
        for c in ref['cricket_entities'])]
    for canonical in dict.fromkeys(ref['cricket_entities']+discovered):
        count=len(canonical.split())
        for width in range(max(1,count-1),count+2):
            for a in range(len(words)-width+1):
                b=a+width-1;original=' '.join(w.text for w in words[a:b+1])
                original_tokens=[key(w.text) for w in words[a:b+1]]
                canonical_tokens=[key(t) for t in canonical.split()]
                if width>count and any(original_tokens[j:j+count]==canonical_tokens for j in range(width-count+1)):
                    continue  # Never consume Hindi words beside an already correct name.
                example=(key(original),key(canonical)) in examples
                if example or entity_similarity(original,canonical,canonical in ref['cricket_entities']):add(a,b,canonical,'entity')
    for i,word in enumerate(words):
        for canonical in ref['roman_spellings']:
            if SequenceMatcher(None,phonetic(word.text),phonetic(canonical)).ratio()>=.8:add(i,i,canonical,'spelling')
        if suspicious(word.text):
            middle=(word.start+word.end)/2
            for window in evidence:
                if not window['start']<=middle<=window['end']:continue
                for value in set(window['supported_digits']):
                    if re.fullmatch(r'(?:0|[1-9]\d{0,6})',value) and value in numeric_values(window['transcript']):
                        add(i,i,value,'number',window['transcript'])
    for term in ref.get('cricket_terms',[]):
        count=len(term.split())
        for a in range(len(words)-count+1):
            before=' '.join(w.text for w in words[a:a+count])
            if any(c.isdigit() for c in before) or len(phonetic(term))<5:continue
            if SequenceMatcher(None,phonetic(before),phonetic(term)).ratio()>=.88:
                add(a,a+count-1,term,'cricket_term')
    accepted=[]
    system=('You are the LOCAL Storylens caption reviewer. Select valid corrections from immutable candidates. '
        'Each original is the recognizer output; proposed is a possible corrected spelling/value. Return only accepted_ids. '
        'Accept a proposed canonical cricket entity when its heard name and surrounding cricket sentence support that identity. '
        'Creator-confirmed recognition examples are spelling memory, not permission to change a different person or team. '
        'Preserve Hindi: a Roman spelling such as kaafi is not an English translation. '
        'Cricket terms are spelling suggestions only; reject unrelated Hindi words even if they sound similar. '
        'For numerical candidates, the evidence_quote comes from an independent LOCAL speech recognizer near that word. '
        'Accept only the value that matches that spoken evidence and nearby phrase; never use historical match knowledge. '
        'Reject uncertain candidates or conflicting alternatives. Do not reverse original/proposed, rewrite fields, or invent IDs.')
    for start in range(0,len(candidates),12):
        batch=candidates[start:start+12];ids=[r['id'] for r in batch]
        schema={'type':'object','additionalProperties':False,'properties':{'accepted_ids':{
            'type':'array','uniqueItems':True,'maxItems':len(ids),'items':{'type':'string','enum':ids}}},'required':['accepted_ids']}
        from hinglish_niche.profiles import use
        with use({'profile':'general'}):answer=brain.json(system,{'candidates':batch,'reference_spellings':ref},schema,max_tokens=350,think=False)
        selected=answer.get('accepted_ids',[])
        if not isinstance(selected,list) or any(not isinstance(i,str) for i in selected) or len(set(selected))!=len(selected) or any(i not in ids for i in selected):
            raise ValueError('The local caption model returned invalid correction IDs; original words are retained for review.')
        accepted.extend(r for r in batch if r['id'] in selected)
    # Independent bounded batches can accept two alternatives for the same
    # words. Have the local model resolve those alternatives together.
    for _ in range(2):
        conflicts={r['id'] for r in accepted for other in accepted if r['id']!=other['id']
            and max(r['start_index'],other['start_index'])<=min(r['end_index'],other['end_index'])}
        if not conflicts:break
        batch=[r for r in accepted if r['id'] in conflicts]
        schema={'type':'object','additionalProperties':False,'properties':{'accepted_ids':{
            'type':'array','uniqueItems':True,'items':{'type':'string','enum':sorted(conflicts)}}},'required':['accepted_ids']}
        progress('Local model resolving overlapping caption correction alternatives')
        with use({'profile':'general'}):
            answer=brain.json(system,{'candidates':batch,'validation_error':
                'These accepted edits overlap. Return only a mutually non-overlapping subset. '
                'Choose the whole name span when ASR split its syllables; reject alternatives with the wrong identity. '
                'Do not accept two edits covering the same word. Empty is valid if uncertain.'},schema,max_tokens=350,think=False)
        ids=answer.get('accepted_ids',[])
        if not isinstance(ids,list) or any(not isinstance(i,str) or i not in conflicts for i in ids) or len(ids)!=len(set(ids)):
            raise ValueError('The local caption model returned invalid correction IDs; original words are retained for review.')
        accepted=[r for r in accepted if r['id'] not in conflicts or r['id'] in ids]
    if any(max(r['start_index'],s['start_index'])<=min(r['end_index'],s['end_index'])
           for i,r in enumerate(accepted) for s in accepted[i+1:]):
        raise ValueError('The local model selected conflicting caption corrections. Original words are kept for review; no alternative was guessed.')
    if candidates:progress(f'Local model accepted {len(accepted)} of {len(candidates)} spelling/audio candidates')
    return accepted
