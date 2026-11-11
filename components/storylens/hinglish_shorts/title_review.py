"""Local-model factual review against selected speech, before publication."""
import re
VERSION=4


def spelling_issues(title):
    """Ask the local model to resolve likely misspelled whole names, never rewrite here."""
    from hinglish_captions.proofread import references,entity_similarity
    from hinglish_captions.numbers import key
    ref=references()
    known={key(n) for n in ref['cricket_entities']}
    tokens=title.replace('’s','').replace("'s",'').split()
    issues=[]
    for name in ref['cricket_entities']:
        count=len(name.split())
        for start in range(len(tokens)-count+1):
            heard=' '.join(tokens[start:start+count]).strip('.,:!?')
            if key(heard) in known:continue
            if entity_similarity(heard,name,True):
                issues.append({'heard':heard,'reference':name})
    return issues


def short_heading(brain,text,years,progress):
    """A small word-budget tool, instead of asking a fact checker to truncate prose."""
    schema={'type':'object','additionalProperties':False,'properties':{'words':{
        'type':'array','minItems':2,'maxItems':6,'items':{'type':'string','pattern':r'^\S+$'}}},'required':['words']}
    from hinglish_captions.proofread import references
    data={'spoken_content':text[:9000],'allowed_years':sorted(years),'maximum_words':6,'reference_spellings':references()}
    system=('Write a short English headline about the MAIN TOPIC of this spoken clip. Return words as an array of 2-6 individual words. '
        'Use a self-contained noun phrase, not a sentence or comparison clause. Narrow the topic rather than squeezing every fact into the heading. '
        'Keep correct proper names. Do not include unsupported years, results or records. '
        'Never end on a preposition, conjunction, what, or an unfinished comparison. '
        'Style examples only: ["A", "Captain’s", "Rapid", "Rise"], ["A", "Team’s", "Turning", "Point"]. '
        'Do not copy the examples; choose the headline from the supplied speech.')
    for _ in range(2):
        progress('The local model is writing a compact headline within its word budget')
        answer=brain.json(system,data,schema,max_tokens=180,think=False)
        words=answer.get('words',[])
        if isinstance(words,list) and 2<=len(words)<=6 and all(isinstance(w,str) and w.strip() and len(w.split())==1 for w in words):
            title=' '.join(words)
            if len(title)<=90 and words[-1].casefold().strip('.,:!?') not in {'in','of','to','than','what','and','or','the','a','with','for'} and set(re.findall(r'\b(?:19|20)\d{2}\b',title))<=years and not spelling_issues(title):
                return title
        data['invalid_words']=words
        data['spelling_checks']=spelling_issues(' '.join(w for w in words if isinstance(w,str))) if isinstance(words,list) else []
        data['correction']=('Return a complete noun-phrase headline as 2-6 separate words; do not return a sentence or unsupported year. '
            'Correct the flagged name from reference_spellings when supported by speech. If its identity is uncertain, '
            'omit the player name and describe the supported topic instead. Do not repeat the rejected spelling.')
    raise ValueError('The local model could not fit a complete heading into six words; saved media is kept for review.')


def spoken_years(text):
    years=set(re.findall(r'\b(?:19|20)\d{2}\b',text))
    numbers={'ek':1,'do':2,'teen':3,'char':4,'chaar':4,'paanch':5,'panch':5,'chhah':6,'chhe':6,
        'saat':7,'aath':8,'nau':9,'das':10,'gyarah':11,'gyaarah':11,'barah':12,'baarah':12,
        'terah':13,'chaudah':14,'pandrah':15,'solah':16,'satrah':17,'atharah':18,
        'unnis':19,'unnees':19,'bees':20,'ikkis':21,'baais':22,'teis':23,'chaubis':24,'chaubees':24,'pachis':25,'pachchees':25,'chhabbis':26}
    for m in re.finditer(r'\bdo\s+haza+r\s+(\w+)\b',text,re.I):
        if m[1].lower() in numbers:years.add(str(2000+numbers[m[1].lower()]))
    return years


def review(brain,items,progress=print):
    progress('Local AI is checking the Shorts titles against their selected speech')
    ids=[item['index'] for item in items]
    schema={'type':'object','properties':{'titles':{'type':'array','minItems':len(ids),'maxItems':len(ids),
        'items':{'type':'object','properties':{'index':{'type':'integer','enum':ids},
            'title':{'type':'string','pattern':r'^\S+(?:\s+\S+){1,6}$'},'reason':{'type':'string'}},'required':['index','title','reason'],
            'additionalProperties':False}}},'required':['titles'],'additionalProperties':False}
    evidence={item['index']:spoken_years(item['text']) for item in items}
    headings={item['index']:(item['title'] if len(item['title'].split())<=7 else
        short_heading(brain,item['text'],evidence[item['index']],progress)) for item in items}
    from hinglish_captions.proofread import references
    data={'version':3,'reference_spellings':references(),'clips':[{**{k:item[k] for k in ('index','text')},
        'title':headings[item['index']],
        'heading_action':'keep_or_correct',
        'spoken_years':sorted(evidence[item['index']])} for item in items]}
    system=('Check only factual grounding of these Short titles against each clip\'s actual speech. '
        'Speech may be Hindi written in Roman letters. Translate number words carefully. '
        'spoken_years normalizes years said in Hindi into digits. A title year must be in that clip’s spoken_years. '
        'Do not use the filename, outside knowledge or other clips as evidence. '
        'Keep an already supported title unchanged ONLY if it fits the heading limit. Shorten long titles by meaning, never truncate a sentence. '
        'Use the reference spellings for supported cricket entities. Correct unsupported years, names, results or claims; '
        'when evidence is ambiguous, use a neutral title without the uncertain fact. '
        'Return every supplied index exactly once with a concise English heading of at most SEVEN words, preferably a short single line, and brief evidence reason. '
        'When shortening, prefer a self-contained noun-phrase headline. Do not leave an unfinished comparison such as achieved what someone took longer; express the topic in a complete headline instead. '
        'Never select different moments or change the speech. Do not polish supported titles just for style.')
    for _ in range(2):
        answer=brain.json(system,data,schema,max_tokens=650,think=False)
        rows=answer.get('titles',[])
        if (isinstance(rows,list) and len(rows)==len(ids) and
            {r.get('index') for r in rows if isinstance(r,dict)}==set(ids) and
            all(isinstance(r.get('title'),str) and 2<=len(r['title'].split())<=7 and len(r['title'])<=90
                and set(re.findall(r'\b(?:19|20)\d{2}\b',r['title']))<=evidence[r['index']] and not spelling_issues(r['title']) for r in rows)):
            return {r['index']:r for r in rows}
        data['validation_error']='Return one complete English heading of AT MOST SEVEN WORDS for every exact supplied index, without duplicates. Shorten by meaning; do not keep a long title. Unsupported year in a title MUST be removed or corrected to its own spoken_years. Do hazaar nau=2009; do hazaar solah=2016; these do not mean 2019.'
        data['spelling_checks']=[{'index':r.get('index'),'candidates':spelling_issues(r['title'])}
            for r in rows if isinstance(r,dict) and isinstance(r.get('title'),str)]
        data['validation_error']+=' Resolve likely misspelled player/team names using the reference and speech. If identity is uncertain, write a neutral title without that name.'
    # A linguistically valid but overlong answer needs the dedicated headline
    # writer, not silent text cropping or a hard-coded caption from Codex.
    if isinstance(rows,list) and len(rows)==len(ids) and {r.get('index') for r in rows if isinstance(r,dict)}==set(ids) and all(isinstance(r.get('title'),str) and not spelling_issues(r['title']) and set(re.findall(r'\b(?:19|20)\d{2}\b',r['title']))<=evidence[r['index']] for r in rows):
        by_id={item['index']:item for item in items}
        for row in rows:
            if not 2<=len(row['title'].split())<=7 or len(row['title'])>90:
                row['title']=short_heading(brain,by_id[row['index']]['text'],evidence[row['index']],progress)
        return {r['index']:r for r in rows}
    raise ValueError('The local model could not validate the Shorts title evidence. Exports are kept; publishing has not started.')


def ensure_project(root,project_file,progress=print,*,force=False):
    import json
    from hinglish_visuals.brain import open_brain
    from hinglish_shorts.pipeline import rebuild_project
    path=project_file
    project=json.loads(path.read_text('utf-8'))
    if not force and project.get('title_review',{}).get('version')==VERSION:
        transcripts(path,project);return
    brain=open_brain(root,'ollama',progress=progress)
    try:checked=review(brain,project['shorts'],progress)
    finally:brain.close()
    if any(checked[s['index']]['title']!=s['title'] for s in project['shorts']):
        progress('Applying the local model’s evidence-based title corrections')
        rebuild_project(path,{'shorts':[{**s,'title':checked[s['index']]['title']} for s in project['shorts']]},progress)
        project=json.loads(path.read_text('utf-8'))
    project['title_review']={'version':VERSION,'model':brain.name,'items':list(checked.values())}
    path.write_text(json.dumps(project,ensure_ascii=False,indent=2),'utf-8')
    transcripts(path,project)


def transcripts(path,project):
    from hinglish_cut.recognition_quality import checked_transcript
    for item in project['shorts']:
        # Reuse selected timed speech, including validated local spelling
        # corrections, instead of generating a new transcript for metadata.
        text=item.get('text','').strip()
        if project.get('caption_words') and item.get('pieces'):
            from hinglish_cut.model import Word
            from hinglish_captions.numbers import digits
            selected=[Word(t,s,e) for t,s,e in project['caption_words']
                if any(a<=(s+e)/2<b for a,b in item['pieces'])]
            text=' '.join(w.text for w in digits(selected))
        checked_transcript(text)
        (path.parent/item['mp4']).with_suffix('.txt').write_text(text,'utf-8')
