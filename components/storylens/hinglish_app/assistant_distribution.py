"""Local-model routing for saved Shorts to paired YouTube and local Chrome accounts."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import re
import time
import uuid

IST=timezone(timedelta(hours=5,minutes=30))

WORKFLOW={
    'timezone':'Asia/Kolkata','daily_time':'19:00','shorts_max_seconds':50,
    'shorts_count':'Use the number of standalone worthwhile clips actually found; seven is an example, not padding.',
    'cricket':'Long source -> standalone portrait Shorts -> cricket YouTube and Instagram at matching daily slots. Long video: YouTube only.',
    'gaming':'Original stream -> entertaining 10-15 minute highlights -> Shorts FROM the highlights -> gaming YouTube and Instagram. Highlights: YouTube only.',
    'destinations':{'cricket':{'youtube':'Fantasy Legends','instagram':'fantasy_legends91'},
                    'gaming':{'youtube':'Vineet Kumar','instagram':'vineet_editz19'}},
    'instagram':'Local due-time Chrome uploads, not a native Instagram cloud schedule. Laptop awake, editor and Chrome running, internet and signed-in accounts required. One tab switches accounts sequentially. Actual posting can lag the nominal slot.',
    'rules':'Recall saved exports across chats. Never recreate files just to publish them. For a same-clip test, select one saved clip and both Instagram profiles; do not substitute separate clips or queue whole batches. Saved files are not posting tasks: persist the requested future slots after authorization. Keep all original source files. Long videos never go to Instagram. New schedules require future slots. Existing authorized Instagram jobs that have not started remain due after offline time and post in release order when Storylens and Chrome reconnect. Never replay an uncertain submission. Queued is not published; verify each receipt separately.'}


def context(root):
    path=Path(root)/'config.workflow.local.json'
    return json.loads(path.read_text('utf-8')) if path.exists() else WORKFLOW


def eligible(text,snapshot=None):
    from .assistant_contracts import account_check
    if account_check(text):return False
    from .assistant_publishing_context import intent_text,relevant
    text=intent_text(text)
    text=re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',' ',text,flags=re.I)
    if re.search(r'\b(youtube|yt)\b',text,re.I) and not re.search(r'\b(insta(?:gram)?|ig|both platforms)\b',text,re.I):return False
    review=(snapshot or {}).get('publishing_review') or {}
    if review.get('instagram_rows') and relevant(text):return True
    return bool(re.search(r'\b(insta(?:gram)?|ig|reels?|both platforms|all four)\b',text,re.I)
                and re.search(r'\b(schedul\w*|daily|consecutive|queue|post|upload|publish)\b',text,re.I))


def shorts_count_limit(text):
    """Use the same owner-requested clip cap in model constraints and validation."""
    words={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twelve':12}
    match=re.search(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s+(?:standalone\s+|portrait\s+|vertical\s+)*(?:reels?|shorts?|shots?|clips?)\b',text,re.I)
    return int(match[1]) if match and match[1].isdigit() else words[match[1].casefold()] if match else 7


def validate_edit_plan(parsed,text,workflow):
    steps=parsed['steps']
    negative=' '.join(m[0] for m in re.finditer(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',text,re.I))
    if re.search(r'\b(?:shorts|reels)\b',negative,re.I) and any(s['tool']=='shorts' for s in steps):
        raise ValueError('The user excluded portrait Shorts. Return the requested gaming highlights tool only, without a Shorts step.')
    if re.search(r'\b(?:upload|schedule|publish|publishing)\b',negative,re.I) and any(s['tool'] in ('distribute','publish') or
        s['tool']=='instagram' and s['options'].get('instagram_action')!='inspect' for s in steps):
        raise ValueError('The user excluded publishing. Do not add upload, scheduling or distribution tools.')
    if re.search(r'\bmemes\b',negative,re.I) and any(s['tool']=='gaming' and s['options'].get('memes',True) for s in steps):
        raise ValueError('The user excluded memes. Set gaming.memes to false.')
    if not any(s['tool']=='distribute' for s in steps):return
    last=steps[-1]['options'];errors=[]
    if last.get('distribution_profile') not in ('cricket','gaming'):errors.append('Set distribute.distribution_profile to the requested cricket or gaming destination, independently of the active UI profile.')
    try:datetime.strptime(last.get('first_date',''),'%Y-%m-%d')
    except ValueError:errors.append('Set distribute.first_date to the requested YYYY-MM-DD.')
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',last.get('clock','')):errors.append('Set distribute.clock to HH:MM IST; default 19:00.')
    from .assistant_publishing_context import schedule_literals
    explicit=schedule_literals(text)
    expected=explicit.get('first_date','')
    if expected and last.get('first_date')!=expected:errors.append('Preserve the explicit requested first_date: '+expected)
    if explicit.get('clock'):
        expected_clock=explicit['clock']
        if last.get('clock')!=expected_clock:errors.append('Preserve the explicit requested clock: '+expected_clock)
    target=shorts_count_limit(text)
    if explicit.get('end_date'):
        capacity=(datetime.fromisoformat(explicit['end_date'])-datetime.fromisoformat(explicit['first_date'])).days+1
        target=min(target,capacity)
    for step in steps:
        if step['tool']=='shorts':
            if not 1<=step['options'].get('count',0)<=target:errors.append(f'Set shorts.count no greater than the requested {target}; never invent extra clips.')
            if not 5<=step['options'].get('max_seconds',0)<=workflow['shorts_max_seconds']:errors.append('Set shorts.max_seconds to 50 or less.')
    tools=[s['tool'] for s in steps]
    paired_shorts=re.search(r'\bshorts\b[^.!?]{0,160}\bboth\b[^.!?]{0,160}(?:youtube[^.!?]{0,80}instagram|instagram[^.!?]{0,80}youtube)',text,re.I)
    if paired_shorts and last.get('distribution_platforms')!='paired':errors.append('Set the SHORTS platforms to paired. YouTube-only describes the long highlights, not the Shorts.')
    if 'gaming' in tools and 'shorts' in tools and tools.index('gaming')>tools.index('shorts') and re.search(r'from (?:those|the) highlights',text,re.I):errors.append('Create gaming highlights first, then extract Shorts from those highlights.')
    if errors:raise ValueError(' '.join(errors))


def gaming_recipe_requested(text):
    # Negative scope restrictions are not affirmative requests for the bundled
    # Shorts/publishing recipe. Let the general local planner handle these.
    text=re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',' ',text,flags=re.I)
    return bool(re.search(r'\b(stream|livestream)\b',text,re.I) and re.search(r'\bhighlights?\b',text,re.I)
        and re.search(r'\b(shorts|shots)\b',text,re.I) and re.search(r'\b(schedul\w*|publish|upload|posting)\b',text,re.I))


def gaming_highlights_requested(text):
    positive=re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',' ',text,flags=re.I)
    minutes=re.findall(r'\b(\d+)\s*[- ]?minutes?\b',positive,re.I)
    if any(not 10<=int(n)<=15 for n in minutes):return False
    return bool(re.search(r'\b(?:gaming|stream|livestream)\b',positive,re.I) and re.search(r'\b(?:highlights?|entertaining|entertainment|main parts|main moments)\b',positive,re.I)
        and not re.search(r'\b(?:shorts|shots|reels?|upload|schedul\w*|publish\w*|posting)\b',positive,re.I))


def gaming_highlights(brain,root,text,history,memory,attachments=()):
    """A standalone compilation has no implicit Shorts or publishing steps."""
    from hinglish_niche.profiles import use
    negative=' '.join(m[0] for m in re.finditer(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',text,re.I))
    no_memes=bool(re.search(r'\bmemes\b',negative,re.I))
    schema={'type':'object','additionalProperties':False,'properties':{
        'action':{'type':'string','enum':['edit','clarify','explain']},'reply':{'type':'string','maxLength':300},
        'target_minutes':{'type':'integer','minimum':10,'maximum':15},
        'memes':{'type':'boolean',**({'enum':[False]} if no_memes else {})}},
        'required':['action','reply','target_minutes','memes']}
    if attachments and re.match(r'^\s*(?:use|create|make|cut|edit|extract|turn|please)\b',text,re.I):
        schema['properties']['action']['enum']=['edit']
    data={'request':text,'conversation':history[-6:],'shared_memory':memory or {},'workflow':context(root),
          'attached_media':list(attachments),'tool_capabilities':{'gaming':{
              'reads_attached_local_video':True,'full_stream_analysis':True,'local_model_selects_moments':True,
              'exports':['landscape highlights MP4','editable timeline','moment reasons']}}}
    for _ in range(2):
        with use({'profile':'general'}):
            answer=brain.json('You are the tool planner INSIDE Storylens, not a standalone chatbot. '
                'The authorized attached_media are already readable by the local gaming tool. You return tool arguments; '
                'the editor runner reads the source and renders the actual files. Never refuse with "text-based AI", '
                '"cannot access your filesystem" or "cannot edit/render videos": those are implemented tool capabilities. '
                'Plan only the requested local 10-15 minute gaming highlights compilation. '
                'Select a target duration in that range. The gaming tool reads the full source, and a local model chooses entertaining moments. '
                'This is one landscape MP4 and editable timeline, not portrait Shorts. Do not add publishing, scheduling or other tools. '
                'Action edit for a request to create highlights, explain for questions, clarify only conflicting requests. '
                'Honor explicit exclusions; memes false if excluded. Missing media is handled by the editor, not a reason to refuse this plan.',
                data,schema,max_tokens=400,think=False)
        if answer.get('action') in ('clarify','explain'):
            return {'reply':answer['reply'] if answer['action']=='explain' else '',
                    'question':answer['reply'] if answer['action']=='clarify' else '', 'combine':False,'steps':[]}
        parsed={'reply':answer.get('reply',''),'question':'','combine':False,'steps':[{'tool':'gaming','options':{
            'target_minutes':answer.get('target_minutes'),'memes':answer.get('memes')}}]}
        try:
            if answer.get('action')!='edit' or type(answer.get('target_minutes')) is not int or not 10<=answer['target_minutes']<=15 or type(answer.get('memes')) is not bool:raise ValueError('Return an edit with 10-15 target_minutes and a boolean memes choice.')
            validate_edit_plan(parsed,text,context(root));return parsed
        except ValueError as error:data.update(invalid_answer=answer,validation_error=str(error))
    raise ValueError('The local model could not validate the highlights-only plan; no edit or publishing started.')


def gaming_recipe(brain,root,text,history,memory):
    """The saved workflow is fixed; local inference supplies its task-specific arguments."""
    from hinglish_niche.profiles import use
    workflow=context(root)
    schema={'type':'object','additionalProperties':False,'properties':{
        'action':{'type':'string','enum':['edit','clarify','explain']},'reply':{'type':'string','maxLength':160},
        'target_minutes':{'type':'integer','minimum':10,'maximum':15},
        'shorts_count':{'type':'integer','minimum':1,'maximum':40},
        'max_seconds':{'type':'integer','minimum':11,'maximum':50},
        'destination_profile':{'type':'string','enum':['cricket','gaming']},
        'shorts_platforms':{'type':'string','enum':['paired','youtube','instagram']},
        'first_date':{'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'},
        'clock':{'type':'string','pattern':r'^(?:[01]\d|2[0-3]):[0-5]\d$'},'include_longform':{'type':'boolean'}},
        'required':['action','reply','target_minutes','shorts_count','max_seconds','destination_profile','shorts_platforms','first_date','clock','include_longform']}
    # Literal user choices are tool constraints, just like a named subtitle
    # template. Do not let a later "long video YouTube only" override them.
    explicit_pair=re.search(r'\bshorts\b[^.!?]{0,160}\bboth\b[^.!?]{0,160}(?:youtube[^.!?]{0,80}instagram|instagram[^.!?]{0,80}youtube)',text,re.I)
    if explicit_pair:schema['properties']['shorts_platforms']['enum']=['paired']
    system=('You are the local Storylens gaming workflow planner. The approved recipe is original livestream -> '
        '10-15 minute entertaining highlights -> up to the requested number of portrait Shorts FROM THOSE HIGHLIGHTS -> '
        'one reviewed daily publishing plan. The highlights go ONLY to YouTube. shorts_platforms applies ONLY to Shorts. Example highlights YouTube-only and Shorts BOTH YouTube and Instagram means shorts_platforms paired, include_longform true. '
        'Set action edit for a request to do this. Missing attachments are handled by the editor; do not ask again in this call. '
        'Action explain for questions/cancellation/do-not-execute; clarify only genuinely conflicting instructions. '
        'Preserve the requested destination profile, count cap, maximum seconds, start date and daily clock. '
        'Example up to seven means shorts_count 7, never 10. 7 p.m. IST means clock 19:00, not a timestamp. '
        'Defaults: target_minutes 15, shorts_count 7, max_seconds 50, gaming destination, paired platforms, '
        'daily 19:00, next future slot unless explicit date given. Include_longform true when asked to upload highlights. '
        'The count is a maximum; fewer worthwhile clips are allowed. Reply briefly with the next step, never claim an edit or upload completed. '
        'All semantic selection is done by local models; the app tools execute only this bounded recipe.')
    data={'workflow':workflow,'conversation':history[-6:],'shared_memory':memory or {},'current_time':datetime.now(IST).isoformat(),'request':text}
    for attempt in range(2):
        with use({'profile':'general'}):answer=brain.json(system,data,schema,max_tokens=500,think=False)
        try:
            if answer['action']!='edit':return {'reply':answer['reply'],'question':answer['reply'] if answer['action']=='clarify' else '', 'combine':False,'steps':[]}
            if answer['destination_profile'] not in ('cricket','gaming') or answer['shorts_platforms'] not in ('paired','youtube','instagram'):raise ValueError('Choose supplied destinations and platforms.')
            if type(answer['target_minutes']) is not int or not 10<=answer['target_minutes']<=15:raise ValueError('Highlights must be 10-15 minutes.')
            parsed={'reply':answer['reply'],'question':'','combine':False,'steps':[
                {'tool':'gaming','options':{'target_minutes':answer['target_minutes']}},
                {'tool':'shorts','options':{'count':answer['shorts_count'],'max_seconds':answer['max_seconds'],'shorts_look':'template'}},
                {'tool':'distribute','options':{'distribution_profile':answer['destination_profile'],'distribution_platforms':answer['shorts_platforms'],
                    'first_date':answer['first_date'],'clock':answer['clock'],'include_longform':answer['include_longform']}}]}
            validate_edit_plan(parsed,text,workflow)
            return parsed
        except (ValueError,TypeError,KeyError) as error:data.update(invalid_answer=answer,validation_error=str(error))
    raise ValueError('The local model could not validate this workflow. No edit or publishing task was started.')


def decision(brain,text,cards,memory,workflow):
    from .distribution_schedule import contract,normalize
    text=normalize(text)
    schedule=contract(text,workflow)
    # An explicitly identified saved batch does not require every archived
    # export in the model's context. Preserve all owner guidance and the exact
    # requested batch facts; keep the other batches on disk.
    named_cards=[c for c in cards if re.search(r'(?<![\w-])'+re.escape(c['id'])+r'(?![\w-])',text,re.I)]
    if named_cards:cards=named_cards
    current=(memory or {}).get('active_task',{}).get('current_campaign','')
    if (current and re.search(r'\b(?:this|these|those|them)\b',text,re.I)
        and not re.search(r'\b(?:another|different|all batches|both batches)\b|[\\/]|\.mp4',text,re.I)):
        explicit=any(c['id']!=current and Path(c.get('source','')).stem and
            re.search(r'(?<!\w)'+re.escape(Path(c['source']).stem)+r'(?!\w)',text,re.I) for c in cards)
        active=[c for c in cards if c['id']==current and c['available_for_upload']]
        if active and not explicit:cards=active
    ids=[c['id'] for c in cards];ready={c['id'] for c in cards if c['available_for_upload']}
    destination_clauses=[]
    for clause in re.split(r'(?<=[.!?;])\s+|\n',text):
        if re.search(r'\b(?:do not|don.t|leave)\b.*\b(?:change|unchanged|post|upload|schedule)\b',clause,re.I):continue
        if (re.search(r'\balready\s+(?:published|posted)\b',clause,re.I)
            and not re.match(r'\s*(?:please\s+)?(?:post|upload|publish|schedule|queue)\b',clause,re.I)):continue
        destination_clauses.append(clause)
    destination_text=' '.join(destination_clauses) or text
    from .delivery_request import destination_text as correction_destination,profiles as requested_profiles
    destination_text=correction_destination(destination_text)
    named_handles={token.casefold().rstrip('.') for token in re.findall(r'(?<![\w.])@?([A-Za-z0-9_][A-Za-z0-9._]*)',destination_text)}
    named_profiles=requested_profiles(destination_text,workflow)
    # Platforms and destination overrides are separate scopes. "Both YouTube
    # and Instagram" never authorizes both creator accounts. Bind explicit
    # platform names before asking the model to resolve the saved batch.
    positive_destination=re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',' ',destination_text,flags=re.I)
    from .assistant_publish_intent import platforms as requested_platforms
    explicit_platforms=requested_platforms(destination_text)
    paired_explicit=len(explicit_platforms)==2 and bool(re.search(
        r'\bboth\s+(?:platforms|youtube|yt|instagram|insta|ig)\b|'
        r'\b(?:youtube|yt)\s+(?:and|&)\s+(?:instagram|insta|ig)\b|'
        r'\b(?:instagram|insta|ig)\s+(?:and|&)\s+(?:youtube|yt)\b',positive_destination,re.I))
    override_requested=bool(named_profiles or re.search(r'\b(?:cricket|gaming)\b',positive_destination,re.I))
    summaries=[{**{k:c[k] for k in ('id','source','status','targets','clip_count','export_count','available_for_upload','instagram_queued_count','instagram_published_count') if k in c},
                'clips':[{k:v[k] for k in ('index','title','duration') if k in v} for v in c['clips']]} for c in cards]
    schema={'type':'object','additionalProperties':False,'properties':{
        'action':{'type':'string','enum':['prepare','status','clarify','other']},
        'campaign_ids':{'type':'array','items':{'type':'string','enum':ids or ['']},'maxItems':4},
        'platforms':{'type':'array','items':{'type':'string','enum':['youtube','instagram']},'maxItems':2},
        'clip_indices':{'type':'array','items':{'type':'integer','minimum':1},'maxItems':40,'description':'Exact saved clip indices; empty selects the entire batch.'},
        'destination_profiles':{'type':'array','items':{'type':'string','enum':['cricket','gaming']},'maxItems':2,'description':'Normally empty, preserving each batch destination. For an explicit same-video Instagram test, select both profiles.'},
        'first_date':{'type':'string','pattern':r'^(?:|\d{4}-\d{2}-\d{2})$','description':'YYYY-MM-DD, or empty to use saved dates'},
        'clock':{'type':'string','pattern':r'^(?:|(?:[01]\d|2[0-3]):[0-5]\d)$','description':'HH:MM IST only, never a full timestamp; empty to use saved dates'},
        'question':{'type':'string','maxLength':600},'reply':{'type':'string','maxLength':1400}},
        'required':['action','campaign_ids','platforms','clip_indices','destination_profiles','first_date','clock','question','reply']}
    import copy
    variants=[]
    for actions in (['prepare','other'],['status'],['clarify']):
        variant=copy.deepcopy(schema);variant['properties']['action']['enum']=actions
        if actions!=['clarify']:variant['properties']['question']={'type':'string','enum':['']}
        if actions!=['status']:variant['properties']['reply']={'type':'string','enum':['']}
        variants.append(variant)
    schema={'oneOf':variants}
    positive=re.sub(r"\b(?:do not|don't|never|without)\b[^.!?\n]*",' ',text,flags=re.I)
    read_only=bool(re.match(r'\s*(?:what|which|is|are|has|have|tell|report|show)\b',positive,re.I)
        and re.search(r'\b(?:status|progress|receipt)\b',positive,re.I)
        and not re.search(r'\b(?:post|upload|publish|reschedule|schedule|queue)\b',positive,re.I))
    # Dates and clocks are literal application inputs, not model-authored
    # strings. The previous model repeatedly put ISO timestamps in both fields.
    for variant in variants:
        for key in ('first_date','clock'):
            variant['properties'].pop(key)
            variant['required'].remove(key)
        if named_profiles:
            variant['properties']['destination_profiles']={'type':'array','uniqueItems':True,
                'items':{'type':'string','enum':named_profiles},
                'minItems':len(named_profiles),'maxItems':len(named_profiles)}
        elif not override_requested:
            variant['properties']['destination_profiles']['maxItems']=0
        if paired_explicit:
            variant['properties']['platforms'].update(minItems=2,maxItems=2,uniqueItems=True)
    if read_only:
        schema=next(v for v in variants if v['properties']['action']['enum']==['status'])
        schema['properties']['reply']['minLength']=1
    system=('You are the local Storylens distribution planner. Resolve the latest request using saved batches and workflow. '
        'A specifically named Instagram handle selects only its mapped profile, even when the user says second/other channel. '
        'The Chrome executor can switch between configured Instagram accounts and verify the real signed-in account. '
        'Past sign-in errors in memory are not evidence of current login state. Do not ask the creator to switch accounts before the executor checks. '
        'prepare means the user wants a review for actual scheduling/posting, including "how can I schedule these existing clips on Instagram". '
        'status means a question about existing results or an explanation of architecture, not a request to execute. '
        'other means a NEW edit/extraction or cancellation; clarify only if needed. '
        'An Instagram-only request selects platforms [instagram], never youtube too. Both platforms means youtube and instagram. '
        'Changing the dates of these/same Shorts preserves their saved destinations. Both platforms does NOT mean both creator profiles. '
        'An explicit execution request with a ready batch and resolved future dates needs prepare, not a repeated permission question. '
        'For both cricket and gaming select their separate finished batches; do not put one gaming batch on all accounts. '
        'EXCEPTION: when explicitly testing the SAME existing clip on both Instagram accounts, choose ONE ready source batch, '
        'ONE clip_indices entry from that batch, destination_profiles [cricket,gaming], and platforms [instagram]. '
        'Cricket footage may be posted to the gaming Instagram when the user explicitly requests this test. '
        'For normal whole-batch schedules use empty clip_indices. A named gaming/cricket Instagram account '
        'sets destination_profiles to that profile regardless of the footage topic. '
        'Batches run IN PARALLEL: seven cricket plus seven gaming Shorts cover the SAME seven days, not fourteen days. '
        'Only available_for_upload batches with all files are ready; planned candidates are not exports. '
        'Already uploaded YouTube videos are reusable for Instagram. Do not regenerate or reupload them. '
        'The application owns schedule_contract; never output first_date, clock, timestamps or dates. '
        'immediate_first means clip 1 now. With interval_seconds, following clips use that interval; otherwise they use daily slots. '
        'immediate_all means every selected clip is queued now, handled sequentially by Chrome. '
        'Published Instagram clips are completed receipts, never new uploads; a new timing request applies only to unposted clips. '
        'A request for one now and the second tomorrow selects TWO clips, not just one. '
        'Select every enumerated release; required_clip_count is the exact number requested when nonzero. '
        'Use the current conversation batch for this/these Shorts; older recalled chats cannot replace it. '
        'Use saved dates if the user says match the YouTube dates. Otherwise schedule_contract owns the default time or random evening window; '
        'Storylens tools save each exact random minute separately before review. Preserve explicit dates/times; never silently shift a past start. '
        'For a new schedule without a date use today if its requested time is still future, otherwise tomorrow. '
        'Question MUST be empty except action clarify. An explicit channel choice resolves the destination; do not ask to confirm it again. '
        'Preparation offers the exact batch review, which already includes the final authorization step. '
        'Other uses empty arrays and dates. Never claim publication or queueing happened here. '
        'Use human source names in questions, never internal campaign IDs. For status, reply with the supplied workflow/receipt facts; '
        'queued and published are different. Do not claim execution. The latest request overrides older chat choices.')
    from .distribution_schedule import enumerated_slots
    required_count=len(schedule.get('clip_slots',[])) or (enumerated_slots(text) if schedule['immediate_first'] else 0)
    data={'workflow':workflow,'shared_memory':memory,'saved_batches':summaries,'schedule_contract':schedule,
          'explicit_instagram_profiles':named_profiles,
          'explicit_platforms':explicit_platforms,
          'preserve_saved_destinations':not override_requested,
          'executor_capabilities':{'switch_configured_instagram_accounts':True,'verify_live_account_before_upload':True},
          'required_clip_count':required_count,'request':text}
    if read_only:
        data['response_contract']='Read-only status request. Return action status and answer from the supplied per-video receipts. No permission or repeated question is needed; say unavailable for missing evidence.'
    from .assistant_plan_context import compact,ask
    data=compact(data)
    for attempt in range(2):
        from hinglish_niche.profiles import use
        with use({'profile':'general'}):answer=ask(brain,system,data,schema,max_tokens=900,think=False)
        try:
            answer={**answer,**schedule}
            action=answer['action'];chosen=answer['campaign_ids'];platforms=answer['platforms']
            if read_only and (action!='status' or not answer.get('reply','').strip()):
                raise ValueError('Return status with a factual answer from the supplied receipts. Do not repeat the creator’s status question or ask permission to read saved state.')
            if action not in ('prepare','status','clarify','other'):raise ValueError('Unknown action')
            if not isinstance(chosen,list) or len(chosen)!=len(set(chosen)) or any(i not in ids for i in chosen):raise ValueError('Choose exact saved batch IDs without duplicates.')
            if any(p not in ('youtube','instagram') for p in platforms) or len(set(platforms))!=len(platforms):raise ValueError('Choose exact platforms.')
            if paired_explicit and action in ('prepare','clarify') and set(platforms)!=set(explicit_platforms):
                raise ValueError('Both explicitly named platforms must be selected: YouTube and Instagram. This does not add any destination accounts.')
            # Naming the batch's own channel is not a YouTube account override.
            # Keep its verified channel IDs; overrides remain Instagram-only.
            native_profiles={t['profile'] for card in cards if card['id'] in chosen for t in card.get('targets',[])}
            native_destination=bool('youtube' in platforms and named_profiles and set(named_profiles)==native_profiles)
            if native_destination:answer['destination_profiles']=[]
            if not override_requested and answer.get('destination_profiles'):
                raise ValueError('Preserve the selected batch destinations; no account override was requested. Set destination_profiles to empty.')
            if action=='prepare' and (not chosen or not platforms or any(i not in ready for i in chosen)):raise ValueError('Preparation needs ready exported batches and explicit platforms.')
            if named_profiles and not native_destination and sorted(answer.get('destination_profiles',[]))!=sorted(named_profiles):
                raise ValueError('Use exactly the explicitly named Instagram profiles: '+str(named_profiles)+'. The other/second channel does not mean both channels.')
            if action=='clarify' and re.search(r'log.?in|sign(?:ed)?[ -]?in|switch accounts?',answer.get('question',''),re.I):
                raise ValueError('Return prepare for this executable posting request. The Chrome executor switches the configured account and checks live login. Historical errors cannot establish a present sign-in failure.')
            validate_selection(answer,cards)
            if (action=='clarify' and len(ready)==1 and paired_explicit
                and schedule.get('first_date') and not override_requested
                and re.match(r'\s*(?:please\s+)?(?:schedule|reschedule)\b',positive,re.I)):
                raise ValueError('The current ready batch, both platforms and future daily dates are already specified. Return prepare, preserving the saved destinations; do not ask for permission again.')
            if (action=='clarify' and chosen and platforms and all(i in ready for i in chosen)
                and named_profiles and not read_only
                and re.search(r'\b(?:post|upload|publish|queue|schedule)\b',positive,re.I)
                and not re.match(r'\s*(?:what|which|why|how|is|are)\b',positive,re.I)
                and answer.get('clip_indices')):
                raise ValueError('This explicit posting command already authorizes the selected ready clip, named Instagram destination and resolved schedule. Return prepare with those selections; do not ask for the same authorization again.')
            if action=='prepare' and required_count:
                selected=answer.get('clip_indices',[])
                count=len(selected) if selected else sum(len(c['clips']) for c in cards if c['id'] in chosen)
                if count!=required_count:
                    raise ValueError(f'The request enumerates {required_count} clip releases. Select exactly {required_count} clips, including the immediate first clip and all following releases.')
            one_clip=bool(re.search(r'\b(?:exactly\s+(?:one|1)|single|just\s+one|same\s+(?:one\s+)?)\b.{0,35}\b(?:video|clip|short)\b',text,re.I))
            if action=='prepare' and one_clip and not schedule['immediate_first'] and (len(chosen)!=1 or len(answer.get('clip_indices',[]))!=1):raise ValueError('Exactly one saved clip was requested. Select one ready campaign and one clip index, not the entire batch.')
            if answer['first_date']:datetime.strptime(answer['first_date'],'%Y-%m-%d')
            if answer['clock'] and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',answer['clock']):raise ValueError('Clock must be HH:MM.')
            if action=='clarify' and not answer['question'].strip():raise ValueError('Ask the missing information.')
            if action!='clarify' and answer['question'].strip():raise ValueError('Set question to empty for prepare/status/other; the batch review handles final authorization. Do not ask again for already specified destinations.')
            return answer
        except (KeyError,TypeError,ValueError) as error:
            data.update(invalid_answer=answer,validation_error=str(error))
    raise ValueError('The local planner could not resolve the saved batches. No publishing tasks were created.')


def validate_selection(spec,cards):
    indices=spec.get('clip_indices',[]);profiles=spec.get('destination_profiles',[])
    if not isinstance(indices,list) or any(type(i) is not int or i<1 for i in indices) or len(indices)!=len(set(indices)):
        raise ValueError('Select unique exact saved clip indices.')
    if not isinstance(profiles,list) or any(p not in ('cricket','gaming') for p in profiles) or len(profiles)!=len(set(profiles)):
        raise ValueError('Choose unique known destination profiles.')
    if profiles and spec['platforms']!=['instagram']:
        raise ValueError('Destination overrides are limited to Instagram-only requests; YouTube must stay unchanged.')
    destinations=spec.get('clip_destinations')
    if destinations:
        if len(spec['campaign_ids'])!=1 or spec['platforms']!=['instagram'] or spec.get('include_longform'):
            raise ValueError('Per-Reel destinations require one Instagram-only saved delivery.')
        card=next((c for c in cards if c['id']==spec['campaign_ids'][0]),None)
        selected={str(i) for i in indices} if indices else {str(c['index']) for c in (card or {}).get('clips',[])}
        if not isinstance(destinations,dict) or set(destinations)!=selected or any(p not in profiles for p in destinations.values()):
            raise ValueError('Every selected Reel needs exactly one reviewed destination account.')
    if indices:
        if len(spec['campaign_ids'])!=1:raise ValueError('Clip selection requires exactly one source batch.')
        card=next((c for c in cards if c['id']==spec['campaign_ids'][0]),None)
        if not card or any(i not in {c['index'] for c in card['clips']} for i in indices):raise ValueError('A selected clip is not in the saved batch.')


def stage(assistant,session_id,spec):
    from .campaign_memory import resolve,catalog
    from hinglish_publish.store import fingerprint
    from hinglish_publish.features import instagram_text_mode
    request=spec.get('request') or (assistant.snapshot(session_id).get('pipeline') or {}).get('request','')
    if not request:
        snapshot=assistant.snapshot(session_id)
        request=next((m.get('text','') for m in snapshot.get('messages',[])
                      if m.get('id')==snapshot.get('active_request_message_id')),'')
    from .publishing_times import window,choose as choose_release
    random_window=window(request,context(assistant.root))
    if spec.get('immediate_all') or spec.get('relative_delay_seconds') or spec.get('interval_seconds') or spec.get('clip_slots'):random_window=None
    text_mode=instagram_text_mode(assistant.root,request)
    validate_selection(spec,catalog(assistant))
    publisher=assistant.state.publisher;bridge=assistant.state.local_browser
    accounts={};rows=[];reels=[];pending=[]
    relative_start=(datetime.now(IST)+timedelta(seconds=spec['relative_delay_seconds'])) if spec.get('relative_delay_seconds') else None
    interval_start=datetime.now(IST) if spec.get('immediate_first') and spec.get('interval_seconds') else None
    for campaign_id in spec['campaign_ids']:
        folder,campaign,card=resolve(assistant,campaign_id)
        if not card['available_for_upload']:raise ValueError('The selected batch is not ready.')
        targets=([{'profile':p} for p in spec['destination_profiles']] if spec.get('destination_profiles') else card['targets'])
        selected=[c for c in campaign['clips'] if not spec.get('clip_indices') or c['index'] in spec['clip_indices']]
        if spec.get('clip_slots') and len(selected)!=len(spec['clip_slots']):
            raise ValueError('The number of selected clips must match the explicitly requested release times. Nothing was queued.')
        for target in targets:
            profile=target['profile']
            if profile not in ('cricket','gaming'):raise ValueError('Unknown destination profile.')
            account=publisher.accounts(profile)['youtube'];handle=bridge.snapshot()['accounts'].get(profile,'')
            if ('youtube' in spec['platforms'] or spec.get('include_longform')) and (not account['connected'] or account['id']!=target['id']):raise ValueError('Reconnect the intended YouTube channel.')
            if 'instagram' in spec['platforms'] and not handle:raise ValueError('Save the '+profile+' Instagram username in Chrome connection first.')
            accounts[profile]=account
            media=[]
            if spec.get('include_longform'):
                media += [(c,'long',0) for c in campaign.get('long_videos',[])]
            media += [(c,'short',i) for i,c in enumerate(selected)]
            for clip,kind,index in media:
                if kind=='short' and spec.get('clip_destinations') and spec['clip_destinations'][str(clip['index'])]!=profile:
                    continue
                path=Path(clip['video']).resolve()
                if not path.is_relative_to(folder) or fingerprint(path)!=clip['fingerprint']:raise ValueError('A reviewed export changed.')
                if 'youtube' in spec['platforms'] or kind=='long':
                    ensure_youtube_copy(assistant,session_id,clip,profile,folder,campaign,request)
                original=datetime.fromisoformat(clip['publish_at'])
                start=datetime.strptime(spec['first_date'],'%Y-%m-%d').date() if spec['first_date'] else None
                clock=spec['clock']
                immediate=bool(kind=='short' and (spec.get('immediate_all') or spec.get('immediate_first') and index==0))
                private_only=bool(kind=='long' and spec.get('longform_private'))
                offset=index-1 if spec.get('immediate_first') and kind=='short' else index
                due=datetime.combine(start+timedelta(days=max(0,offset)),original.timetz()) if start else original
                if clock:due=due.replace(hour=int(clock[:2]),minute=int(clock[3:]),second=0,microsecond=0)
                if kind=='long' and random_window:
                    long_clock=context(assistant.root)['daily_time']
                    due=due.replace(hour=int(long_clock[:2]),minute=int(long_clock[3:]))
                if kind=='short' and spec.get('clip_slots'):
                    due=datetime.fromisoformat(spec['clip_slots'][index]['publish_at'])
                if kind=='short' and relative_start:
                    due=relative_start+(timedelta(seconds=index*spec['interval_seconds']) if spec.get('interval_seconds') else timedelta(days=index))
                elif kind=='short' and interval_start:
                    due=interval_start+timedelta(seconds=index*spec['interval_seconds'])
                elif kind=='short' and spec.get('interval_seconds') and not spec.get('immediate_first'):
                    due=due-timedelta(days=index)+timedelta(seconds=index*spec['interval_seconds'])
                reference=campaign_id+':'+profile+':'+str(clip['index'])
                saved=bridge.saved_reel(reference,handle,path) if 'instagram' in spec['platforms'] and kind=='short' else None
                instagram_complete=bool(saved and saved['status']=='published' and saved.get('url'))
                youtube_due=instagram_due=due
                if kind=='short' and not immediate and random_window:
                    key=clip['fingerprint']+':'+profile
                    if 'youtube' in spec['platforms']:
                        youtube_due=choose_release(folder,key+':youtube',due.date().isoformat(),random_window)
                    if 'instagram' in spec['platforms'] and not instagram_complete:
                        instagram_due=choose_release(folder,key+':instagram',due.date().isoformat(),random_window)
                    due=youtube_due if 'youtube' in spec['platforms'] else instagram_due
                lead=5 if spec['platforms']==['instagram'] and kind=='short' else 60
                if not immediate and not (instagram_complete and spec['platforms']==['instagram']) and (due.tzinfo is None or due.timestamp()<=time.time()+lead):raise ValueError('A release time has passed or is too close. Ask for a new future start; nothing was queued.')
                if spec.get('end_date') and due.date().isoformat()>spec['end_date']:
                    raise ValueError('The selected videos exceed the requested date range at one per day. Nothing was queued.')
                common={'profile':profile,'channel':account.get('name',profile),'kind':kind,'source':card['source'],
                    'duration':clip['duration'],'metadata':clip['metadata'],'publish_at':'' if immediate or private_only else due.isoformat(),
                    'private_only':private_only,
                    'immediate':immediate,
                    'campaign':str(folder),'video':str(path),'fingerprint':clip['fingerprint']}
                if spec.get('verify_account_switches'):
                    other='gaming' if profile=='cricket' else 'cricket'
                    via=publisher.accounts(other)['youtube']
                    if not via.get('connected'):raise ValueError('Connect the alternate YouTube channel before the requested switch test.')
                    common['switch_via']={'channel_id':via['id'],'channel_name':via['name'].strip()}
                    common['instagram_switch_via']=bridge.snapshot()['accounts'].get(other,'')
                    if 'instagram' in spec['platforms'] and not common['instagram_switch_via']:
                        raise ValueError('Save the alternate Instagram account before the requested switch test.')
                if 'youtube' in spec['platforms'] or kind=='long':
                    youtube_common=common
                    if spec.get('youtube_check_only'):
                        youtube_common={**common,'immediate':False,'publish_at':original.isoformat()}
                    pending.append((youtube_common,{'platform':'youtube','profile':profile,'kind':kind,'video':str(path),
                        'fingerprint':clip['fingerprint'],'metadata':clip['metadata'],'visibility':'private','duration':clip['duration'],
                        'width':1080,'height':1920,'brain':campaign['model'],'thumbnail':'','thumbnail_fingerprint':'','video_url':'','campaign':str(folder),
                        **({'private_copy_scope':str(folder)} if private_only else {})}))
                if 'instagram' in spec['platforms'] and kind=='short':
                    if not immediate and not instagram_complete and (instagram_due.tzinfo is None or instagram_due.timestamp()<=time.time()+5):
                        raise ValueError('The Instagram release time has passed. Choose a future date; existing receipts are preserved.')
                    caption=clip['metadata'].get('instagram_caption','').strip()
                    if len(caption)>2200:raise ValueError('The Instagram caption exceeds 2,200 characters.')
                    if saved and not re.search(r'\b(?:titles?|captions?|hash\s*tags?|text)\b',request,re.I):
                        caption=saved.get('caption','')  # A date edit alone cannot erase post copy.
                    elif text_mode=='title':caption=clip['metadata']['title']
                    elif text_mode=='none':caption=''
                    common['metadata']={**clip['metadata'],'instagram_caption':caption}
                    reel={**common,'publish_at':'' if immediate else instagram_due.isoformat(),
                          'id':reference,'account':handle,'caption':caption,'status':'draft',
                          'previously_published':instagram_complete}
                    if saved:reel['browser_job_id']=saved['id']
                    if instagram_complete:
                        reel.update(status='published',url=saved['url'],caption=saved.get('caption',''),
                            publish_at=saved.get('publish_at',''),immediate=not bool(saved.get('publish_at')))
                    reels.append(reel)
    if spec.get('clip_destinations'):
        reels.sort(key=lambda r:(r['publish_at'],r['id']))
    # No drafts are written until all media, accounts and future dates validate.
    for common,item in pending:
        job_id=publisher.store.add_batch([item])[0];job=publisher.store.get(job_id)
        if job['status'] in ('draft','blocked') and not job.get('remote'):
            publisher.store.change(job_id,due=time.time() if common['immediate'] or common['private_only'] else datetime.fromisoformat(common['publish_at']).timestamp(),campaign=common['campaign'])
        if job.get('remote') and job.get('campaign')!=common['campaign']:
            raise ValueError('This export matches a previously uploaded video. Its existing release is preserved; select a different new moment before publishing.')
        rows.append({**common,'id':job_id,'status':job['status'],'url':job.get('remote',{}).get('url','')})
    review={'id':uuid.uuid4().hex,'ids':[r['id'] for r in rows],'accounts':accounts,'rows':rows,'instagram_rows':reels,
        'state':'review','visibility':'private','created':time.time(),'upload_requested':True,'schedule':True,
        'distribution':True,'campaign':rows[0]['campaign'] if rows else '', 'allow_reschedule':bool(spec['first_date'] or spec['clock']),
        'account_switch_retry':True,'random_window':random_window}
    with assistant.lock:
        review['request_message_id']=assistant._get(session_id).get('active_request_message_id')
        pipeline=assistant._get(session_id).get('pipeline') or {}
        from .assistant_publish import confirmation
        continuing=bool(pipeline.get('automatic') and (not rows or confirmation(pipeline.get('request',''),review,assistant.root,execution=True)))
        review['automatic']=continuing
        previous=assistant._get(session_id).get('publishing_review')
        if previous:
            history=list(assistant._get(session_id).get('publishing_review_history',[]))
            history.append(previous)
            assistant._update(session_id,publishing_review_history=history[-10:])
        assistant._update(session_id,publishing_review=review,status='needs_review',selected='publish',stage='Review paired platform schedules.')
        assistant._message(session_id,'assistant',
            ('Your video is ready. Continuing with the requested upload.' if continuing else
             'Your videos are ready. Review the destinations and times below, then confirm.'),publishing_review=review)


def arm(assistant,session_id,review):
    """Only called after the user confirms this exact review, independently of YT limits."""
    from hinglish_publish.store import fingerprint
    bridge=assistant.state.local_browser
    existing={}
    for row in review.get('instagram_rows',[]):
        # YouTube recovery must not re-arm, move, or reject an already armed
        # Instagram slot just because its date has since arrived.
        if row.get('browser_job_id'):
            job=bridge.get(row['browser_job_id'])
            from .assistant_upload_recovery import same_instant
            same_slot=(row.get('immediate') and not job.get('publish_at')) or same_instant(job.get('publish_at',''),row['publish_at'])
            if (job.get('reference')!=row['id'] or job.get('account')!=row['account']
                or job.get('video')!=row['video']):
                raise ValueError('The saved Instagram receipt does not match this reviewed slot.')
            if job.get('status')=='published' and job.get('url'):
                row.update(status='published',url=job['url'],publish_at=job.get('publish_at',''),
                    immediate=not bool(job.get('publish_at')),caption=job.get('caption',''))
                existing[row['id']]=job
                continue
            if same_slot:
                existing[row['id']]=job
                continue
            # Presentation reconnects the existing job by media identity. A
            # newly authorized date change must update that job, not reject
            # its old date or create a second upload. enqueue rechecks under
            # its lock so a concurrent claim cannot be rescheduled mid-post.
            safe_pause=(job.get('status')=='needs_review' and job.get('last_phase') in ('queued','running'))
            if (not review.get('allow_reschedule') or (job.get('status')!='queued' and not safe_pause)
                or job.get('submission_started') is not False or job.get('stop')):
                raise ValueError('This Reel is already posting or cannot safely change times. Check its saved result before retrying. Existing posts will not be uploaded again.')
        if bridge.snapshot()['accounts'].get(row['profile'])!=row['account']:raise ValueError('The Instagram destination changed. Prepare a fresh review.')
        if fingerprint(row['video'])!=row['fingerprint']:raise ValueError('The reviewed Instagram export changed.')
        if not row.get('immediate') and datetime.fromisoformat(row['publish_at']).timestamp()<=time.time()+5:raise ValueError('The Instagram slot has passed. Choose a future schedule.')
    from .assistant_social import chrome_caption
    for row in review.get('instagram_rows',[]):
        job=existing.get(row['id']) or bridge.enqueue('reel',row['account'],row['video'],chrome_caption(row['caption']),session_id,
                           authorized=True,publish_at=row['publish_at'],reference=row['id'],switch_via=row.get('instagram_switch_via',''))
        row.update(browser_job_id=job['id'],status=job['status'])
        assistant._update(session_id,publishing_review=review)
    # Exercise the signed-in account switch now without posting a future Reel.
    if not review.get('account_check_ids'):
        checks=[]
        for row in review.get('instagram_rows',[]):
            if row.get('instagram_switch_via') and not checks:
                task=bridge.enqueue('inspect',row['account'],session=session_id,authorized=True,switch_via=row['instagram_switch_via'],reference=review['id']+':switch-check')
                checks.append(task['id'])
        if checks:
            review['account_check_ids']=checks;assistant._update(session_id,publishing_review=review)


def followup(assistant,session_id,text,progress):
    from .delivery_request import correction_text
    text=correction_text(assistant.snapshot(session_id),text,context(assistant.root))
    if not eligible(text,assistant.snapshot(session_id)):return False
    from .campaign_memory import catalog
    from hinglish_visuals.brain import open_brain
    from hinglish_publish.campaign import RecordedBrain
    from hinglish_cut.gpu_lock import gpu_lock
    cards=catalog(assistant,session_id)
    # Explicitly naming an export grants access to that saved manifest, not
    # the conversation that produced it. Do not fall through to a large
    # general planner simply because it was created in another chat.
    named=[card for card in catalog(assistant) if re.search(r'(?<![\w-])'+re.escape(card['id'])+r'(?![\w-])',text,re.I)]
    if named:cards=named
    if not cards:return False
    instagram=assistant.state.local_browser.snapshot()['jobs']
    for card in cards:
        related=[j for j in instagram if j.get('reference','').startswith(card['id']+':')]
        card.update(instagram_queued_count=sum(j['status'] in ('queued','running','sharing') for j in related),
                    instagram_published_count=sum(j['status']=='published' for j in related))
    with assistant.state.work_lock,gpu_lock(assistant.root):
        brain=open_brain(assistant.root,'ollama',progress=progress)
        try:
            folder=assistant.folder/('distribution-decisions-'+session_id);folder.mkdir(parents=True,exist_ok=True)
            spec=decision(RecordedBrain(brain,folder),text,cards,assistant.context_memory(text,session_id),context(assistant.root))
            model=brain.name
        finally:brain.close()
    if spec['action']=='other':return False
    assistant._update(session_id,brain=model)
    if spec['action']=='prepare':
        assistant._update(session_id,distribution_pending=None)
        ensure_instagram_copy(assistant,spec,progress)
        positive=re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',' ',text,flags=re.I)
        direct=bool(re.search(r'\b(?:post|upload|publish|schedule|reschedule|queue)\b',positive,re.I)
            and not re.search(r'\b(?:how|why|draft|preview|review first|ask me first)\b',positive,re.I))
        with assistant.lock:
            assistant._update(session_id,pipeline={'version':1,'request':text,'automatic':direct,
                'phase':'review','attempts':0,'next_retry':0,'authorized_review':'','created':time.time()})
            stage(assistant,session_id,spec)
            # A direct command authorizes this validated selection on any of
            # the requested platforms. The common publishing path still checks
            # saved declarations, exact accounts, files and remote receipts.
            if direct:
                review=assistant.snapshot(session_id)['publishing_review']
                from .assistant_pipeline import prepared
                prepared(assistant,session_id,review)
    elif spec['action']=='clarify':
        assistant._update(session_id,distribution_pending={'request':text})
        assistant._message(session_id,'assistant',spec['question'],question=True);assistant._update(session_id,status='idle',stage='')
    else:
        assistant._message(session_id,'assistant',spec.get('reply') or 'YouTube schedules are saved on YouTube after verification. Instagram uses a persistent local due-time Chrome queue, '
            'which requires the laptop awake and Storylens, Chrome and the signed-in accounts available. A queue entry is not proof of publication. '
            'Ask me to schedule the saved cricket/gaming batches on Instagram, YouTube, or both, with a future start date and daily time.')
        assistant._update(session_id,status='idle',stage='')
    return True


def ensure_instagram_copy(assistant,spec,progress):
    """A YouTube-only export may only have a placeholder Instagram title."""
    if 'instagram' not in spec['platforms']:return
    from hinglish_publish.features import instagram_text_mode
    if instagram_text_mode(assistant.root,spec.get('request',''))=='none':return
    from .campaign_memory import resolve
    from hinglish_publish.metadata import generate_instagram
    from .assistant_publish import transcripts
    from .durable_json import write
    with assistant.state.work_lock:
        for campaign_id in spec['campaign_ids']:
            folder,campaign,_=resolve(assistant,campaign_id)
            for clip in campaign['clips']:
                if spec.get('clip_indices') and clip['index'] not in spec['clip_indices']:continue
                caption=clip['metadata'].get('instagram_caption','')
                if 3<=len(re.findall(r'(?<!\w)#[A-Za-z][A-Za-z0-9_]*',caption))<=5 and len(caption)<=2200:continue
                path=Path(clip['video'])
                transcripts(assistant.root,[path],progress)
                result,_=generate_instagram(assistant.root,path,progress=progress)
                clip['metadata']['instagram_caption']=result['instagram_caption']
                write(folder/'campaign.json',campaign)


def from_outputs(assistant,session_id,options,text,progress):
    """Register only real local editing outputs, with copy supplied by the local model."""
    from hinglish_niche.profiles import Profiles,use
    from hinglish_publish.campaign import slots
    snapshot=assistant.snapshot(session_id);profile=options.get('distribution_profile',snapshot.get('profile','general'))
    if profile not in ('cricket','gaming'):raise ValueError('Choose the cricket or gaming profile for paired distribution.')
    files=snapshot.get('shorts_paths',[])
    if not files:raise ValueError('No finished Shorts are saved. Finish the Shorts step before scheduling.')
    planned=next((s['options'].get('count') for s in reversed(snapshot.get('steps',[])) if s['tool']=='shorts'),None)
    if str(planned).isdigit() and len(files)<int(planned):
        raise ValueError(f'Only {len(files)} of {planned} requested Shorts are ready. No uploads started; complete the batch or request fewer clips.')
    clock=options.get('clock') or context(assistant.root)['daily_time']
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',clock):raise ValueError('Use HH:MM for the daily slot.')
    first=options.get('first_date')
    if not first:
        now=datetime.now(IST);start=now.replace(hour=int(clock[:2]),minute=int(clock[3:]),second=0,microsecond=0)
        if start.timestamp()<=time.time()+60:start+=timedelta(days=1)
        first=start.date().isoformat()
    dates=slots(len(files),first,clock)
    if options.get('end_date') and dates[-1][:10]>options['end_date']:
        raise ValueError('The new Shorts exceed the requested daily date range. Exports are kept; no uploads started.')
    platforms={'paired':['youtube','instagram'],'youtube':['youtube'],'instagram':['instagram']}[options.get('distribution_platforms','paired')]
    selected=[(v,'short',i+1) for i,v in enumerate(files)]
    if options.get('include_longform'):
        long_sources=snapshot.get('highlights_paths',[]) if profile=='gaming' else snapshot.get('original_paths',[])
        if not long_sources:raise ValueError('The long-form output is missing; it will not be guessed from the Shorts.')
        selected += [(long_sources[0],'long',0)]
    with assistant.state.work_lock,use(Profiles(assistant.root).context(profile)):
        from .assistant_handoff import prepare
        folder,clips,longs,model=prepare(assistant,session_id,selected,profile,platforms,dates,text,progress)
    account=assistant.state.publisher.accounts(profile)['youtube']
    campaign={'status':'reviewed','source':(snapshot.get('original_paths') or files)[0],
        'targets':[{'profile':profile,'id':account['id'],'name':account['name']}],
        'clips':clips,'long_videos':longs,'model':model}
    from .durable_json import write
    write(folder/'campaign.json',campaign)
    assistant._update(session_id,campaign=str(folder))
    from .assistant_youtube_check import requested as youtube_check
    from .distribution_schedule import contract
    check_only=youtube_check(text)
    instagram_schedule=contract(text,context(assistant.root))
    # The review and automatic continuation are one state transition. A poll or
    # second prompt must not observe an idle review between these two actions.
    with assistant.lock:
        stage(assistant,session_id,{'campaign_ids':[folder.name],'platforms':platforms,'first_date':first,'clock':clock,'end_date':options.get('end_date',''),
                                  'include_longform':bool(options.get('include_longform')),
                                  'longform_private':bool(options.get('longform_private')),
                                  'verify_account_switches':bool(options.get('verify_account_switches')),
                                  'immediate_first':instagram_schedule['immediate_first'],
                                  'youtube_check_only':check_only,
                                  **{k:instagram_schedule[k] for k in ('relative_delay_seconds','interval_seconds','clip_slots','immediate_all') if k in instagram_schedule},
                                  'request':text})
        review=assistant.snapshot(session_id).get('publishing_review')
        if review:
            review['youtube_check_only']=check_only
            result=(snapshot.get('edit_publish_checkpoint') or {}).get('result') or snapshot.get('last_result') or {}
            if result.get('folder'):review['edit_result_folder']=str(Path(result['folder']).resolve())
            assistant._update(session_id,publishing_review=review,edit_publish_checkpoint=None)
            from .assistant_pipeline import prepared
            prepared(assistant,session_id,review)


def register_long(root,folder,video,profile,notes,due,progress):
    import shutil
    from hinglish_publish.store import fingerprint
    from hinglish_shorts.source import open_video
    path=Path(folder)/'long-youtube.mp4';shutil.copy2(video,path)
    facts=open_video(path);meta,model=prepare_copy(root,path,profile,notes,progress,False)
    return {'index':0,'video':str(path),'fingerprint':fingerprint(path),'duration':facts.duration,'publish_at':due,'metadata':meta}


def ensure_youtube_copy(assistant,session_id,clip,profile,folder,campaign,request=''):
    if clip['metadata'].get('copy_scope')!='instagram_title_hashtags':return
    # Prepare a real YouTube description when that platform is requested later;
    # a Reel-only request must not depend on this work.
    with assistant.state.work_lock:
        meta,_=prepare_copy(assistant.root,Path(clip['video']),profile,request,
            lambda m:assistant._progress(session_id,m),instagram=False,youtube=True)
    clip['metadata']={**meta,'instagram_caption':clip['metadata'].get('instagram_caption','')}
    from .durable_json import write
    write(folder/'campaign.json',campaign)


def prepare_copy(root,path,profile,notes,progress,instagram=True,transcribe=True,youtube=True,source_title=''):
    from hinglish_publish.description_policy import apply as description_policy
    from .assistant_publish import transcripts
    from hinglish_publish.metadata import generate_youtube,generate_instagram
    from hinglish_publish.features import features,instagram_text_mode,title_hashtags
    policy=features(root)
    text_mode=instagram_text_mode(root,notes)
    if (policy['publishing_copy']=='minimal' and text_mode!='title_hashtags') or (not youtube and text_mode in ('title','none')):
        # The name comes from the local selector's completed export. It is
        # sufficient YouTube metadata and introduces no extra writing model.
        title=re.sub(r'^\d+\s*[-_]\s*','',source_title or Path(path).stem).replace('-',' ').strip()[:100]
        title=title or Path(path).stem[:100]
        caption=title if instagram and instagram_text_mode(root,notes)=='title' else ''
        meta={'title':title,'description':title,'instagram_caption':caption,'tags':[]}
        return description_policy(root,profile,meta) if youtube else meta,'Local selected clip title'
    if transcribe:transcripts(root,[Path(path)],progress)
    meta={};model=''
    if youtube:
        meta,model=generate_youtube(root,path,profile=profile,notes=notes,progress=progress,
            **({'source_title':source_title} if source_title else {}))
    if instagram:
        if text_mode in ('title','title_hashtags') and meta.get('title'):
            meta['instagram_caption']=title_hashtags(meta) if text_mode=='title_hashtags' else meta['title']
            return meta,model
        caption,caption_model=generate_instagram(root,path,notes=notes,progress=progress,profile=profile)
        if not youtube and caption.get('title'):return caption,caption_model
        meta['instagram_caption']=caption['instagram_caption']
        if not youtube:
            # Instagram has a caption, not separate public title/description
            # fields. Reuse the local model's caption for the review label.
            text=caption['instagram_caption']
            meta.update(title=' '.join(text.split()[:7])[:100],description=text,
                        tags=re.findall(r'(?<!\w)#([A-Za-z][A-Za-z0-9_]*)',text))
            model=caption_model
    return meta,model
