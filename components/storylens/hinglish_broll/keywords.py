"""Human-choice search: discover visual keywords, anchored to original words."""
import re
import unicodedata
from .placement import Moment,Slot
from .planner import _clean_query,specific_subject
from .subjects import concrete_object,anchored_object,contextual_object
from hinglish_eval import guard
from hinglish_eval.guard import Problem


SCHEMA={'type':'object','properties':{'keywords':{'type':'array','items':{
    'type':'object','properties':{'word_index':{'type':'integer'},'keyword':{'type':'string'},
        'queries':{'type':'array','items':{'type':'string'}},
        'identity':{'type':'string'},'meaning':{'type':'string','maxLength':180}},
    'required':['word_index','keyword','queries','identity','meaning'],'additionalProperties':False}}},
    'required':['keywords'],'additionalProperties':False}

SYSTEM='''Discover visual search KEYWORDS for a human video editor. This is an OPTIONS BANK,
not a final automatic edit. Read the entire supplied speech and user preferences as source data.
Extract the concrete nouns/places/actions/visual concepts that can have useful video choices.
Search the concept mentioned, including illustrative bars/clubs/cafes/enjoyment even when the
narrator negates availability. The human chooses the final shot. Do not turn every term into an
empty street or impose a narrow final scene. Examples: nightlife -> nightclub / city night;
shops closed -> closed shops; people asleep -> person sleeping; lounge -> bar/lounge;
cafe -> cafe/coffee; enjoy -> people enjoying/celebrating. Keep these as DIFFERENT keywords.
ASR 'log soch chuke hote hain' in this nightlife story means people have gone to sleep; 'launch'
next to clubs means lounge. Find BOTH sleeping and lounge/club, anchored to their own words.
Return roughly requested_count diverse useful keywords across the WHOLE speech, including later
concepts, not only the opening. Several distinct keywords can belong to the same phrase id.
For each: word_index = the index of the ACTUAL source word naming that concept. For sleep choose
the word 'soch'/'so', for lounge choose 'launch', for club choose 'club', for cafe choose 'cafe',
for enjoyment choose 'enjoy'. Never choose the start of a sentence when the concept is spoken later.
keyword = concise English physical concept (1-5 words, not
a sentence, scene description or review comment); queries = 3 short physical stock-video search
terms/synonyms; identity = exact named person/landmark only if the speech names one, else EMPTY.
The supplied word table is authoritative. Do not copy text as an index. Do not use negative
search phrases such as 'no bar', 'lack of nightlife' or 'enjoyment invitation': search 'bar',
'nightlife', 'people having fun'. Closed shops is a physical state and is allowed.
Never put a whole scene description in identity. Never invent words or ids. Anchor the bar to
the lounge/bar/club words, not earlier words about sleeping. Do not add vocabulary lessons,
maps, another talking presenter or photos. No source selection yet: discover search terms only.'''
SYSTEM+='''\nKeep concrete spoken objects specific: fridge -> refrigerator, never kitchen appliances;
washing machine -> washing machine, never household life; bed -> bed, never a generic person.
Search a visible room/apartment interior for housing/accommodation, not abstract labels such
as flat availability problem, flat search frustration or bachelor status. Do not ask footage
to prove a generic room's rental contract or who is eligible to rent it. Prefer the explicitly
mentioned physical objects/actions throughout the video to multiple versions of one topic.'''
SYSTEM+='''\nResolve each word's SENSE from its sentence before searching. meaning is a short English
description of the actual physical subject intended here, not a repetition of an ambiguous word.
Use English translations in keyword and queries, not phonetic Hindi. For example, a household
fittings list uses water heater, wardrobe, ceiling fan and empty room; a geothermal travel story
can use natural geyser. Never mix these senses in one set of queries. A bare word match is not
contextual evidence. Do not guess a different occupation/event from an unclear ASR word; omit
uncertain concepts and prefer clearly spoken physical subjects elsewhere in the speech.'''
SYSTEM+='''\nA rental-room fittings list containing almari/wardrobe, geyser and fridge can contain
the phonetic ASR word "pan" where the speaker means "fan". Resolve that sense from the actual
sentence; do not invent a frying-pan cutaway without cooking context. If still uncertain,
omit that one ambiguous keyword. Do not borrow the preceding object's identity for this word.'''


def tokens(text):
    text=''.join(c for c in unicodedata.normalize('NFKD',str(text).casefold()) if not unicodedata.combining(c))
    return re.findall(r'\w+',text)


def anchor_words(anchor,phrase,words):
    wanted=tokens(anchor);have=[]
    for i,w in enumerate(words):
        if w.start>=phrase.start-1e-4 and w.end<=phrase.end+1e-4:
            have.extend((token,i) for token in tokens(w.text))
    for start in range(len(have)):
        for length in range(1,min(6,len(have)-start)+1):
            part=have[start:start+length]
            if wanted and ''.join(t for t,_ in part)==''.join(wanted):
                return part[0][1],part[-1][1]
    return None


def physical_query(text):
    """An illustrative options search retrieves the noun, even when absent."""
    text=_clean_query(text)
    text=re.sub(r'\b(?:lack|absence)\s+of\b',' ',text,flags=re.I)
    text=re.sub(r'\b(?:no|missing|without|unavailable)\b',' ',text,flags=re.I)
    text=re.sub(r'\bwi[\s-]*fi\b','wireless router',text,flags=re.I)
    text=re.sub(r'\bAC\b','air conditioner',text,flags=re.I)
    return ' '.join(text.split()).strip(' ,.-')


def physical_keyword(row, anchor='', context=''):
    """Translate search phrasing into a concrete concept, never pick an asset.

    The model can describe a narrator's rhetorical purpose instead of the
    mentioned subject. Venue nouns survive negation; abstract meta-discussion
    does not become a stock footage search for a vocabulary lesson.
    """
    from .internet import venue_query
    term=_clean_query(row.get('keyword',''),80)
    queries=[physical_query(q) for q in row.get('queries',[]) if physical_query(q)]
    current=tokens(anchor)[-1] if tokens(anchor) else ''
    object_name=(anchored_object(anchor) or
                 contextual_object(current+' '+term,context+' '+str(row.get('meaning',''))+' '+' '.join(queries)) or
                 concrete_object(term))
    if object_name:
        aliases={'refrigerator':['refrigerator','fridge interior','open refrigerator'],
                 'washing machine':['washing machine','laundry washing machine','washer drum'],
                 'wardrobe':['wardrobe','closet interior','clothes cupboard'],
                 'water heater':['water heater','bathroom water heater','hot water boiler'],
                 'ceiling fan':['ceiling fan','electric ceiling fan','ceiling fan spinning'],
                 'bed':['bed','bed mattress','bedroom bed']}
        return object_name,aliases.get(object_name,[object_name])
    if re.search(r'\b(?:chaar|char)\s+di[vw]aar\w*\b|\bfour walls\b',term,re.I):
        return 'empty room',['empty room','unfurnished room','bare apartment interior']
    if re.search(r'\b(?:flat|apartment)\b',term,re.I):
        return 'apartment interior',['apartment interior','small apartment','room interior']
    if re.search(r'\b(?:bachelor|pg)\b|rented.*room|room.*accommodation',term,re.I):
        return 'room interior',['room interior','small bedroom','shared room']
    venue=venue_query(term)
    if not venue and re.search(r'\bclub\b',term,re.I) and not re.search(r'\b(?:cricket|football|golf|tennis|rugby)\b',term,re.I):
        venue='nightclub interior'
    if venue:
        term=venue
        queries=[venue,venue.split()[0]]
    elif re.search(r'\benjoy\w*\b|\bfun\b|\bcelebrat\w*\b',term,re.I):
        term='people having fun';queries=['friends having fun','people celebrating','people laughing']
    elif re.search(r'\b(?:ask\w*|question\w*|inquir\w*|discussion|definition|meaning|invitation)\b',term,re.I):
        return '',[]
    else:
        term=physical_query(term)
        cricket=bool(re.search(r'\b(?:cricket|IPL|RCB)\b',' '.join([term]+queries),re.I))
        if cricket:
            # Stock libraries index visible actions, rather than a narrator's
            # abstract match phase or batting-order description. Keep named
            # teams/events intact; these aliases are generic illustrations.
            if re.fullmatch(r'(?:cricket )?batting (?:line[ -]?up|collapse)',term,re.I):term='cricket batting'
            elif re.fullmatch(r'(?:cricket )?final(?: match)?',term,re.I):term='cricket match'
            elif re.fullmatch(r'crowd reaction',term,re.I):term='cricket crowd'
            elif re.fullmatch(r'first wicket',term,re.I):term='cricket wicket'
        queries=[term]+queries
    return term,list(dict.fromkeys(queries))[:3]


def unresolved_household_pan(row, context):
    """Quarantine an ambiguous cooking sense; the model must resolve it or omit it.

    This never translates the source word into fan by controller fiat.
    """
    search=' '.join([str(row.get('keyword',''))]+[str(q) for q in row.get('queries',[])])
    if not re.search(r'\bpan\b',search,re.I):return False
    if re.search(r'\b(?:cook\w*|fry\w*|recipe\w*|utensil\w*|saucepan|tawa|kadhai)\b',context,re.I):return False
    groups=[r'\b(?:almaari|almari|almirah|wardrobe|cupboard)\b',r'\b(?:geyser|water heater)\b',
            r'\b(?:fridge|refrigerator)\b',r'\bwashing machine\b']
    return sum(bool(re.search(pattern,context,re.I)) for pattern in groups)>=2


def discover(llm,phrases,words,summary,count=10,brief='',progress=print):
    import copy
    schema=copy.deepcopy(SCHEMA)
    schema['properties']['keywords']['items']['properties']['word_index']['enum']=list(range(len(words)))
    def phrase_for(index):
        if type(index) is not int or not 0<=index<len(words):return None
        return next((p for p in phrases if p.start-1e-4<=words[index].start<p.end),None)
    def check(answer):
        out=[]
        for row in (answer or {}).get('keywords',[]):
            phrase=phrase_for(row.get('word_index'))
            if phrase_for(row.get('word_index')) is None:
                out.append(Problem('broll.keyword.id','Use only an actual integer word_index from the supplied word table.'))
            if not str(row.get('keyword','')).strip() or len(tokens(row.get('keyword','')))>7:
                out.append(Problem('broll.keyword.term','keyword must be a concise physical concept, not a sentence.'))
            # An explanation can accurately describe an absent object while
            # the actual search retrieves that physical object for the editor.
            search_fields=str(row.get('keyword',''))+' '+str(row.get('queries',[]))
            if re.search(r'\b(?:lack of|absence|invitation|no bar|no club|no lounge)\b',search_fields,re.I):
                out.append(Problem('broll.keyword.negative','Search the mentioned physical concept itself: bar, club, nightlife, people having fun. Do not search its absence.'))
            if phrase and unresolved_household_pan(row,phrase.text):
                out.append(Problem('broll.keyword.sense','Resolve the phonetic pan/fan ambiguity in this household-fixtures list from its sentence, or omit the uncertain keyword. Do not assume a cooking utensil.'))
        return out
    progress('Discovering visual keywords and their exact spoken-word times')
    attempts=[]
    def ask(*args,**kwargs):
        answer=llm.json(*args,**kwargs);attempts.append(answer);return answer
    def repair(answer):
        kept=[]
        for candidate in [r for a in attempts for r in a.get('keywords',[])]:
            phrase=phrase_for(candidate.get('word_index'))
            if phrase and unresolved_household_pan(candidate,phrase.text):continue
            term,queries=physical_keyword(candidate)
            if phrase_for(candidate.get('word_index')) is not None and term and queries:
                kept.append({**candidate,'keyword':term,'queries':queries})
        return {'keywords':kept},['Converted illustrative searches to physical subjects; retained valid word-anchored discoveries.']
    guard.ask_checked(ask,SYSTEM,{'video_context':summary,'requested_count':count,'user_direction':brief,
        'phrases':[{'text':p.text} for p in phrases],
        'words':[{'word_index':i,'word':w.text} for i,w in enumerate(words)]},schema,check,
        label='B-roll keyword discovery',feature='broll',progress=progress,max_tokens=2300,repair=repair)
    # A repair may add a valid missing concept while retaining one unrelated
    # fault. Preserve valid word-anchored discoveries from every attempt.
    by_word={}
    for row in [r for answer in attempts for r in answer.get('keywords',[])]:
        index=row.get('word_index');phrase=phrase_for(index)
        if phrase and unresolved_household_pan(row,phrase.text):continue
        # Join only the anchor and its preceding token for compounds such as
        # "washing machine". Do not borrow a different object mentioned later.
        anchor=' '.join(w.text for w in words[max(0,index-1):index+1]) if phrase else ''
        term,queries=physical_keyword(row,anchor,phrase.text+' '+str(summary) if phrase else '')
        if phrase is None or not queries or not term:continue
        start=words[index].start
        if index and anchored_object(anchor)==term and concrete_object(words[index].text)!=term:
            start=words[index-1].start
        specificity=len(set(tokens(words[index].text))&set(tokens(term)))
        if index not in by_word or specificity>by_word[index][0]:
            by_word[index]=(specificity,(start,words[index].end,phrase,row,queries,term))
    mapped=[]
    for item in sorted((v[1] for v in by_word.values()),key=lambda r:r[0]):
        # Adjacent paraphrases of the same venue are one keyword group, with
        # multiple source choices, rather than several redundant cutaways.
        if any(item[-1]==old[-1] and item[0]-old[0]<5 for old in mapped):continue
        mapped.append(item)
    mapped=mapped[:30];slots=[]
    for i,(start,anchor_end,phrase,row,queries,term) in enumerate(mapped):
        next_start=mapped[i+1][0] if i+1<len(mapped) else float('inf')
        end=min(max(anchor_end,min(phrase.end,start+3.5)),next_start)
        if end-start<.08:continue
        spoken=' '.join(w.text for w in words if w.end>start+1e-4 and w.start<end-1e-4)
        moment=Moment(phrase.id,term,queries[:3],2,spoken,str(row.get('meaning') or term),specific_subject(row.get('identity','')))
        slots.append(Slot(moment,round(start,3),round(end,3),spoken,len(tokens(spoken))))
    return slots
