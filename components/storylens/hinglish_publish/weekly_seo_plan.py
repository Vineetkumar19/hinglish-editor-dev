"""Generate the owner's 1-4 approved weekly packages with the local V8 model."""
import hashlib
import json

from . import metadata
from .discovery import SCHEMA as DISCOVERY_SCHEMA, clean

V8_MODEL = 'storylens-publishing:14b-v8-candidate'
ANGLES=['search','comparison','cause','takeaway']


def evidence_bank(transcript):
    from .prepare_post import text_chunks
    spans=[span for line in transcript.splitlines() if line.strip() for span in text_chunks(line,350)]
    return [{'id':f'e{i:04d}','quote':span} for i,span in enumerate(spans,1)]


def schema(weeks, evidence_ids=None):
    if type(weeks) is not int or not 1 <= weeks <= 4:
        raise ValueError('Choose between one and four weeks.')
    return {'type':'object','additionalProperties':False,'properties':{
        'variants':{'type':'array','minItems':weeks,'maxItems':weeks,'items':{
            'type':'object','additionalProperties':False,'properties':{
                'week':{'type':'integer','minimum':1,'maximum':weeks},
                'angle':{'type':'string','enum':ANGLES},
                'title':{'type':'string','minLength':1,'maxLength':100},
                'description':{'type':'string','minLength':1,'maxLength':5000},
                'tags':{'type':'array','maxItems':15,'items':{'type':'string','maxLength':80}},
                'reason':{'type':'string','minLength':1,'maxLength':300},
                'evidence_id':{'type':'string',**({'enum':evidence_ids} if evidence_ids else {'pattern':'^e[0-9]{4}$'})},
                'thumbnail':DISCOVERY_SCHEMA['properties']['thumbnail']},
            'required':['week','angle','title','description','tags','reason','evidence_id','thumbnail']}}},'required':['variants']}


def validate(value, weeks, transcript, bank=None):
    schema(weeks)
    rows=value.get('variants') if isinstance(value,dict) else None
    if not isinstance(rows,list) or len(rows)!=weeks:
        raise ValueError('Provide exactly one complete package for each selected week.')
    result=[];seen=set()
    bank=evidence_bank(transcript) if bank is None else bank
    quotes={row['id']:row['quote'] for row in bank}
    for i,row in enumerate(rows,1):
        if not isinstance(row,dict) or type(row.get('week')) is not int or row['week']!=i:
            raise ValueError('Keep the weekly packages in order, beginning with week one.')
        if row.get('angle')!=ANGLES[i-1]:
            raise ValueError('Use the selected distinct angle for each week: search, comparison, cause, takeaway. Repeated synonyms are not new angles.')
        import re
        evidence=quotes.get(row.get('evidence_id'))
        if not isinstance(evidence,str):raise ValueError('Choose a valid source evidence ID for each weekly angle; never rewrite the quote.')
        evidence=clean(evidence,500,'the exact spoken evidence')
        normalized=lambda value:re.sub(r'\s+',' ',value).strip().casefold()
        if len(evidence)<8 or normalized(evidence) not in normalized(transcript):
            raise ValueError('Every weekly angle needs a short EXACT verbatim excerpt from spoken_content, not a translated or invented summary.')
        description=row.get('description')
        if isinstance(description,str) and not re.search(r'\bweek\s*[1-4]\b',transcript,re.I):
            description=re.sub(r'^\s*Week\s*[1-4]\s*[:\-–—]\s*','',description,flags=re.I)
        copy=metadata.normalize_source_hashtags(metadata.normalize_youtube_hashtags(metadata.validate({
            'title':row.get('title'),'description':description,'tags':row.get('tags'),'instagram_caption':''})),transcript)
        if copy['title'].casefold() in seen:
            raise ValueError('Give each week a distinct title angle.')
        seen.add(copy['title'].casefold())
        if len(copy['tags'])>15 or not 3<=copy['description'].count('#')<=5:
            raise ValueError('Each week needs focused search tags and 3-5 relevant hashtags.')
        metadata.validate_source_copy(copy,transcript)
        # Observed V8 error: it turns roster continuity into an invented claim
        # about never producing talent. Require source terminology for that
        # stronger player-development history; ask for a narrower claim instead.
        unsupported_production = re.search(r'\b(?:have|has|had)\s+(?:yet\s+to|never|not)\s+(?:produc\w*|develop\w*)\b.{0,120}\b(?:star|player|performer)\b',copy['description'],re.I)
        unsupported_absence = re.search(r'\b(?:have|has|had)\s+(?:never|not)\s+had\b.{0,100}\b(?:star|player|performer)\b',copy['description'],re.I) and not re.search(r'\b(?:retain\w*|continu\w*|roster|remain\w*|stayed)\b',copy['description'],re.I)
        if (unsupported_production or unsupported_absence) and not re.search(r'\b(?:produc\w*|develop\w*)\b',transcript,re.I):
            raise ValueError(f'Week {i}: remove the unsupported player-production/development history. The source discusses retention/roster continuity and identity; write that narrower explanation, not have yet to produce or have not produced a performer.')
        thumb=row.get('thumbnail')
        if not isinstance(thumb,dict):raise ValueError('Each week needs its own thumbnail brief.')
        thumb={key:clean(thumb.get(key),300,'the thumbnail brief') for key in ['text','subject','composition','style']}
        if len(thumb['text'].split())>5:raise ValueError('Use up to five readable thumbnail words per week.')
        if re.search(r'\b(sound|music|audio|foley)\b',thumb['style'],re.I):raise ValueError('Thumbnail style must describe visuals, not sound.')
        metadata.validate_source_copy({'title':thumb['text']},transcript)
        result.append({'week':i,'angle':row['angle'],**{k:copy[k] for k in ['title','description','tags']},
            'thumbnail':thumb,'reason':clean(row.get('reason'),300,'the weekly explanation'),
            'evidence_id':row['evidence_id'],'evidence':evidence})
    return result


def generate(brain, root, transcript, current, context, preferences, weeks, progress=print):
    bank=evidence_bank(transcript)
    spec=schema(weeks,[row['id'] for row in bank])
    if V8_MODEL not in brain.name:
        raise ValueError('Weekly SEO planning is reserved for the approved V8 publishing model. V14 was not used.')
    data={'weeks':weeks,'spoken_content':transcript,'existing_metadata':current,
          'creator_profile':context,'writing_preferences':preferences,
          'source_evidence':bank,
          'weekly_angles':[{'week':i+1,'angle':angle} for i,angle in enumerate(ANGLES[:weeks])]}
    system=('Prepare exactly the selected number of weekly YouTube title-description-search-tag packages in English. '
        'These are sequential7day packages for the SAME video, not new uploads or an A/B experiment. '
        'Use only the actual supplied speech. Keep opinions framed as analysis. Do not invent statistics, '
        'dates, player identities, claims, chapters, links, search volumes or ranking promises. '
        'Give each week a genuinely different source-supported angle; do not merely add Week1/2 to the title. '
        'Use these angle roles in order: search answers the core question; comparison contrasts actual '
        'examples or expectations from the speech; cause focuses on a DIFFERENT concrete contributing '
        'factor mentioned in the speech; takeaway focuses on the viewer\'s meaningful conclusion. '
        'For example a team story might separately address results, named-team comparison, roster '
        'continuity and fan recognition ONLY if those facts are actually spoken. Do not make every '
        'week a synonym for one missing-star-player or brand-value claim. For a narrow source, use '
        'different honest framing instead of inventing additional events or facts. '
        'Never include planning labels such as Week1 or Week2 in public titles or descriptions. '
        'For each angle select the evidence_id of its relevant source_evidence excerpt. The executor '
        'preserves the exact Hinglish quote; never retype or translate it. Write only claims that '
        'excerpt and the full speech actually support. '
        'A franchise having big names but lacking a retained long-term face does NOT mean it has '
        'never had or produced talented/star players. Do not write have yet to produce/develop a '
        'standout performer when the speech says the roster keeps changing. Preserve that distinction. '
        'Each description should be concise, unique, search-friendly, with a strong opening and3-5relevant '
        'hashtags at the end. Tags are focused names/phrases, not keyword stuffing. '
        'Each thumbnail has1-5words complementary to that week\'s title and an accurate subject/composition. '
        'Style describes visual colour, contrast, typography and photographic treatment, never sound/music. '
        'Retain full creator guidance and existing approved resource links. Return the specified JSON.')
    for attempt in range(2):
        progress(f'V8 is preparing {weeks} weekly SEO package'+('s' if weeks>1 else ''))
        try:
            value=brain.json(system,data,spec,max_tokens=min(7000,1600*weeks+500),think=False)
            # Repair a specifically identified row without regenerating all four
            # packages. The full source and creator guidance remain available.
            for repair in range(2):
                try:
                    rows=validate(value,weeks,transcript,bank)
                    break
                except ValueError as error:
                    import re
                    identified=re.match(r'Week ([1-4]):',str(error))
                    if repair or not identified:raise
                    index=int(identified[1])-1
                    progress(f'V8 is correcting the source claim in week {index+1}')
                    replacement=brain.json('Correct only the identified weekly package using the exact supplied speech. '
                        'Follow the validation correction literally. Distinguish never having talent from not retaining '
                        'a lasting franchise face. Describe the actual roster-continuity explanation when that is '
                        'what the source says. Keep its assigned angle and evidence ID, 3-5 relevant hashtags, '
                        'and a complementary visual thumbnail brief. Return only the corrected variant JSON.',
                        {**data,'invalid_variant':value['variants'][index],'validation_correction':str(error)},
                        {'type':'object','additionalProperties':False,'properties':{'variant':spec['properties']['variants']['items']},'required':['variant']},
                        max_tokens=1600,think=False)
                    value={**value,'variants':[replacement['variant'] if i==index else row for i,row in enumerate(value['variants'])]}
            metadata.review_grounding(brain,{'title':' | '.join(r['title'] for r in rows),
                'description':'\n\n'.join(r['description']+'\nThumbnail: '+r['thumbnail']['text'] for r in rows),
                'weekly_evidence':[{'week':r['week'],'quote':r['evidence']} for r in rows],'tags':[]},transcript,
                extra_rules='Check the causal relationships, not just the presence of player/team names. '
                'A lack of a retained long-term franchise icon is NOT evidence that a team never had '
                'or has yet to produce/develop a star or dominant performer. If the speech mentions '
                'big names arriving and the roster repeatedly changing, reject that invented player-development '
                'history and require the actual roster-continuity/identity explanation. Source opinions '
                'are not measured league rankings or financial brand-value measurements.')
            from .description_policy import apply
            for row in rows:
                row['description']=apply(root,context.get('profile','general'),row)['description']
            digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
            return {'status':'ready','weeks':weeks,'variants':rows,'revision':digest,'model':brain.name,'evidence_bank':bank,
                'limitation':'Sequential weekly changes, not a controlled A/B test or a ranking guarantee.'}
        except (ValueError,TypeError,KeyError) as error:
            data['correction']=str(error)
    raise ValueError('V8 could not verify every weekly package. Your existing video and publishing text are kept. Try generating the plan again.')
