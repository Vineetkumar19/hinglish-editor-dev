"""Chat entry point to the local long-video Shorts campaign workflow."""
from datetime import datetime
from pathlib import Path
import re
import uuid


def requested(text):
    """Broad tool eligibility only. The local model decides intent and destination."""
    # Exclusions are not authorization for the campaign workflow. In particular,
    # a local edit ending in "do not upload, publish, schedule" stays an edit.
    from .assistant_publish_intent import positive
    value=positive(text).casefold()
    if (re.search(r'\b(?:same|existing|saved|finished)\b',value)
        and re.search(r'\b(?:schedule|reschedule|queue|post|upload|publish)\b',value)
        and not re.search(r'\b(?:extract|create|make|cut|new|fresh)\b',value)):
        return False  # Routing a saved delivery must never start a new extraction.
    if re.search(r'\b(stream|livestream|gaming footage|gaming video)\b',value) and re.search(r'\b(highlights?|compilation)\b',value):return False
    return bool(re.search(r'\b(shorts?|clips?)\b',value) and
                re.search(r'\b(schedule|campaign|consecutive|every day|daily)\b',value))


PLAN_SCHEMA={'type':'object','additionalProperties':False,'properties':{
    'action':{'type':'string','enum':['prepare','clarify','preview','unsupported']},
    'reply':{'type':'string','maxLength':1600},
    'question':{'type':'string','maxLength':600},
    'source_folder_id':{'type':'integer'},
    'source_topic':{'type':'string','enum':['cricket','gaming','other']},
    'targets':{'type':'array','items':{'type':'string','enum':['cricket','gaming']},'maxItems':2},
    'first_date':{'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}$'},
    'clock':{'type':'string','pattern':r'^(?:[01]\d|2[0-3]):[0-5]\d$',
             'description':'Requested release time as HH:MM, e.g. 18:00 for 6 p.m. Never copy the current timestamp.'},
    'count':{'type':'integer','minimum':1,'maximum':12},
    'max_seconds_exclusive':{'type':'integer','minimum':11,'maximum':60},
    'different_source':{'type':'boolean'}},
    'required':['action','reply','question','source_folder_id','source_topic','targets',
                'first_date','clock','count','max_seconds_exclusive','different_source']}
PLAN_SCHEMA['properties'].update(platforms={'type':'array','items':{'type':'string','enum':['youtube','instagram']},'maxItems':2},include_longform={'type':'boolean'})
PLAN_SCHEMA['required']+=['platforms','include_longform']


def validate_plan(parsed):
    """Validate the tool arguments, never substitute our own semantic choices."""
    required=set(PLAN_SCHEMA['required'])-{'platforms','include_longform'}
    if not isinstance(parsed,dict) or not required.issubset(parsed) or set(parsed)-set(PLAN_SCHEMA['required']):
        raise ValueError('Return all and only the required campaign plan fields.')
    for key,rule in PLAN_SCHEMA['properties'].items():
        if key not in parsed:continue
        value=parsed[key]
        expected={'string':str,'integer':int,'boolean':bool,'array':list}[rule['type']]
        if type(value) is not expected:
            raise ValueError(f'{key} must be {rule["type"]}.')
        if 'enum' in rule and value not in rule['enum']:
            raise ValueError(f'{key} must be one of the allowed values.')
        if 'minimum' in rule and not rule['minimum']<=value<=rule['maximum']:
            raise ValueError(f'{key} is outside the supported bounds.')
        if 'pattern' in rule and not re.fullmatch(rule['pattern'],value):
            raise ValueError(f'{key} must match {rule["pattern"]}; clock is HH:MM, not the current timestamp.')
        if 'maxLength' in rule and len(value)>rule['maxLength']:
            raise ValueError(f'{key} is too long.')
    datetime.strptime(parsed['first_date'],'%Y-%m-%d')
    if len(parsed['targets'])>2 or any(p not in ('cricket','gaming') for p in parsed['targets']):
        raise ValueError('targets must contain only supplied channel profile IDs.')
    if 'platforms' in parsed and (not parsed['platforms'] or any(p not in ('youtube','instagram') for p in parsed['platforms'])):raise ValueError('Choose YouTube, Instagram, or both.')
    if parsed['action']=='clarify' and not parsed['question'].strip():
        raise ValueError('State the necessary clarification in question.')
    if parsed['action']!='clarify' and parsed['question']:
        raise ValueError('question must be empty unless action is clarify.')
    asks_for_copy=(r'(?:^|[.!?\n]\s*)(?:(?:please|kindly)\s+)?(?:provide|supply|send|give me)\b'
                   r'[^.!?\n]{0,100}\b(?:titles?|descriptions?)\b|'
                   r'\b(?:can you|could you|you need to|you must)\s+(?:provide|supply|send)\b'
                   r'[^.!?\n]{0,100}\b(?:titles?|descriptions?)\b')
    if re.search(asks_for_copy,parsed['reply']+'\n'+parsed['question'],re.I):
        raise ValueError('Storylens generates titles and descriptions from the footage. '
                         'Do not ask the user to supply them; state that the local model will write them.')


def context(assistant,text):
    """Supply real folder/account identities, never model-invented filesystem paths."""
    import json
    publisher=assistant.state.publisher
    folders=[]
    for profile in ('cricket','gaming'):
        raw=publisher.settings(profile=profile).get('source_root','')
        if not raw:
            continue
        base=Path(raw).resolve()
        if not base.is_dir():
            continue
        candidates=[base]
        # Test existing literal path prefixes; punctuation after a pasted path
        # belongs to the sentence. No recursive scan or arbitrary path access.
        for match in re.finditer(r'[A-Za-z]:[\\/][^\r\n"<>|]+',text):
            literal=match[0].strip()
            prefixes=[literal]+[literal[:m.start()].rstrip() for m in re.finditer(r'[,;]',literal)]
            for prefix in prefixes:
                path=Path(prefix).resolve()
                if path.is_relative_to(base) and path.is_dir():
                    candidates.append(path)
                    break
        for path in candidates:
            if any(f['path']==str(path) for f in folders):
                continue
            folders.append({'id':len(folders),'path':str(path),
                            'videos':[p.name for p in sorted(path.glob('*.mp4')) if p.resolve().is_relative_to(path)]})
    accounts=[]
    for profile in ('cricket','gaming'):
        account=publisher.accounts(profile).get('youtube',{})
        accounts.append({'profile':profile,**{k:account.get(k) for k in ('name','id','connected')}})
    previous=[]
    for manifest in (assistant.root/'output/campaigns').glob('*/campaign.json'):
        try:
            campaign=json.loads(manifest.read_text('utf-8'))
        except (OSError,ValueError):
            continue
        if campaign.get('source') and campaign.get('clips'):
            previous.append(campaign['source'])
    from .assistant_distribution import context as workflow_context
    return {'folders':folders,'accounts':accounts,'previous_sources':sorted(set(previous)),
            'distribution_workflow':workflow_context(assistant.root),
            'capabilities':{'extract_documentary_shorts':{'source_topics':['cricket'],
                            'destination_profiles':['cricket','gaming']},
                            'private_upload_review':True,'public_scheduling':'upload_then_optional_chrome_studio'}}


def active_turns(snapshot,text):
    """New full requests replace earlier campaigns; assistant guesses aren't facts."""
    users=[m['text'] for m in snapshot.get('messages',[]) if m['role']=='user']
    if not users or users[-1]!=text:
        users.append(text)
    starts=[i for i,value in enumerate(users) if requested(value)]
    if starts:
        users=users[starts[-1]:]
    elif snapshot.get('campaign_user_turns'):
        users=[*snapshot['campaign_user_turns'],text]
    return users[-12:]


def plan_with_model(recorder,turns,evidence,now,progress):
    """Read-only planner, also exercised against real local inference in diagnostics."""
    system=(
        'You are Storylens. Return JSON tool arguments for the ACTIVE task only. '
        'user_turns are chronological. The first is the task, the last is the latest instruction. '
        'Later user instructions REPLACE conflicting earlier values; retain unchanged values. '
        'A channel choice such as "gaming only" or "gaming channel (Vineet Kumar)" RESOLVES '
        'the destination. Set targets to ["gaming"], action prepare, question empty. Do not ask again. '
        'Both profiles are valid destinations for cricket footage. The source topic describes the footage, '
        'not its destination. Never infer destinations from source_topic, folder names, available accounts, '
        'or completed_campaign_sources. Only an explicit user request selects a destination. '
        'A fresh task replaces older campaigns. There is no requirement to post cricket footage on a cricket channel. '
        'Choose clarify only for information STILL missing or contradictory after applying all user corrections. '
        'If the task explicitly names both destinations without saying both or replacing one, ask once which destination. '
        'Choose preview for explanations, quotations, cancellations or instructions not to execute; do not execute them. '
        'Choose unsupported for unavailable source workflows. This tool extracts cricket documentary Shorts and '
        'can send the SAME exports to cricket, gaming, or both accounts. '
        'Use only supplied folder IDs and account profile IDs. Preserve the requested source folder, count, '
        'different_source, duration cap, first_date and release clock. Use India time. '
        'clock is the REQUESTED time in HH:MM: 6 p.m. means 18:00. current_time is only for resolving dates. '
        'Defaults when unspecified: up to seven worthwhile clips, below 50 seconds, 19:00, next future start. '
        'Use fewer clips if the source cannot support seven; do not pad. '
        'platforms selects only explicitly requested platforms; otherwise follow distribution_workflow paired platforms. '
        'include_longform is true only if the user also asks to upload the original long video, and it goes to YouTube only. '
        'Instagram slots use the local Chrome queue and require the laptop/editor/Chrome running at release time. '
        'The user reviews the batch once. The tools upload the new exports privately FIRST, '
        'then use the optional local Chrome Studio connection to schedule only the returned upload IDs. '
        'This requires enabling YouTube Studio access in the extension; missing setup blocks uploads before they start. '
        'The tools write titles, long relevant descriptions and hashtags from the selected footage. '
        'When the user requests titles and descriptions, generate them; do not ask the user to provide them. '
        'Do not say the user must manually schedule each video or go to a separate publisher. '
        'reply states that the next step is the upload-and-schedule review. '
        'Never claim uploads or schedules are already complete; only verified remote receipts establish success. '
        'For clarify, question must identify the missing information; for all other actions question is empty. '
        'Do not mention unavailable gaming-source editing when the requested source is cricket. '
        'No edits, uploads or scheduling happen during this planning call.')
    data={'user_turns':turns,'latest_instruction':turns[-1], 'current_time':now,
          **{k:v for k,v in evidence.items() if k!='previous_sources'},
          'completed_campaign_sources':evidence['previous_sources']}
    for attempt in range(2):
        parsed=recorder.json(system,data,PLAN_SCHEMA,max_tokens=1100)
        try:
            validate_plan(parsed)
            return parsed
        except ValueError as error:
            if attempt:
                raise ValueError('The local model returned invalid tool arguments; nothing was started: '+str(error))
            data={**data,'invalid_answer':parsed,'validation_error':str(error)}
            progress('Local model correcting its tool arguments…')


def interpret(assistant,session_id,text,progress):
    """The installed local LLM owns semantic planning and clarification wording."""
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_publish.campaign import IST,RecordedBrain
    from hinglish_visuals.brain import open_brain
    snapshot=assistant.snapshot(session_id)
    turns=active_turns(snapshot,text)
    evidence=context(assistant,'\n'.join(turns))
    evidence['shared_memory']=assistant.context_memory(text,session_id)
    with assistant.state.work_lock,gpu_lock(assistant.root):
        brain=open_brain(assistant.root,'ollama',progress=progress)
        try:
            recorder=RecordedBrain(brain,assistant.folder/('campaign-decisions-'+session_id))
            recorder.folder.mkdir(parents=True,exist_ok=True)
            parsed=plan_with_model(recorder,turns,evidence,datetime.now(IST).isoformat(),progress)
            model=brain.name
        finally:
            brain.close()
    assistant._update(session_id,brain=model,campaign_plan=parsed,campaign_context=evidence,campaign_user_turns=turns)
    return parsed,evidence


def execute(assistant,session_id,text,progress):
    from hinglish_publish.campaign import prepare, word_refine, review, finish_copy, quality, slots, IST
    spec,evidence=interpret(assistant,session_id,text,progress)
    if spec['action']!='prepare':
        with assistant.lock:
            assistant._message(session_id,'assistant',spec['reply']+('\n\n'+spec['question'] if spec['question'] else ''),
                               question=spec['action']=='clarify')
            assistant._update(session_id,status='idle',stage='',campaign_pending=spec if spec['action']=='clarify' else None)
        return
    if spec['source_topic']!='cricket':
        raise ValueError('The local model selected a source workflow this campaign tool cannot execute.')
    folder_info=next((f for f in evidence['folders'] if f['id']==spec['source_folder_id']),None)
    if not folder_info:
        raise ValueError('The local model must select an existing authorized source folder.')
    source=Path(folder_info['path'])
    targets=list(dict.fromkeys(spec['targets']))
    accounts={a['profile']:a for a in evidence['accounts']}
    if not targets or any(p not in accounts or not accounts[p]['connected'] for p in targets):
        raise ValueError('Connect the destination channel selected by the local model first.')
    spec['targets']=[accounts[p] for p in targets]
    spec['excluded_sources']=evidence['previous_sources'] if spec['different_source'] else []
    if type(spec['max_seconds_exclusive']) is not int or not 11<=spec['max_seconds_exclusive']<=60:
        raise ValueError('The local model returned an unsupported Short duration.')
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',spec['clock']) or not 1<=spec['count']<=12:
        raise ValueError('The local model returned an invalid campaign schedule.')
    from .assistant_distribution import context as workflow_context
    from .distribution_schedule import contract
    timing=contract(text,workflow_context(assistant.root))
    if timing.get('random_window'):
        spec.update(first_date=timing['first_date'],clock=timing['clock'])
    slots(spec['count'],spec['first_date'],spec['clock'])
    folder=assistant.root/'output/campaigns'/('chat-'+session_id+'-'+uuid.uuid4().hex[:8])
    assistant._update(session_id,status='running',selected='shorts',campaign_in_progress=str(folder),campaign_pending=None)
    assistant._message(session_id,'assistant',spec['reply'])
    def checked_progress(message):
        if assistant._stopped(session_id):
            raise ValueError('Campaign stopped. Saved decisions and finished exports are kept.')
        progress(message)
    with assistant.state.work_lock:
        result=prepare(assistant.root,source,folder,checked_progress,spec,plan_only=True)
        result=word_refine(assistant.root,folder,checked_progress)
        result=review(assistant.root,folder,checked_progress)
        result=finish_copy(assistant.root,folder,checked_progress)
        quality(folder)
    videos=[c['video'] for c in result['clips']]
    assistant._update(session_id,last_paths=videos,shorts_paths=videos,campaign=str(folder),campaign_in_progress=None,
                      stage='Exports ready; review the upload and release schedule.')
    assistant._message(session_id,'assistant',str(len(videos))+' Shorts prepared and checked by the local models. '
        'Planned dates: '+result['clips'][0]['publish_at']+' through '+result['clips'][-1]['publish_at']+
        '. These are local exports, not yet scheduled on YouTube. '
        'Review the batch below to upload these exact exports and schedule their new YouTube IDs.',videos=videos)
    if spec.get('platforms') and (spec['platforms']!=['youtube'] or spec.get('include_longform')):
        from .assistant_distribution import stage,register_long
        if spec.get('include_longform'):
            import json
            with assistant.state.work_lock:
                result['long_videos']=[register_long(assistant.root,folder,result['source'],targets[0],text,result['clips'][0]['publish_at'],progress)]
            (folder/'campaign.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
        stage(assistant,session_id,{'campaign_ids':[folder.name],'platforms':spec['platforms'],
                                  'first_date':spec['first_date'],'clock':spec['clock'],'include_longform':spec.get('include_longform',False),'request':text})
    else:stage_review(assistant,session_id,schedule=True)
    assistant._update(session_id,status='needs_review')


def stage_review(assistant,session_id,schedule=False,schedule_spec=None):
    """Offer the whole prepared campaign in the existing private-upload review UI."""
    import json
    import time
    from hinglish_publish.store import fingerprint
    publisher=assistant.state.publisher
    snapshot=assistant.snapshot(session_id)
    folder=Path(snapshot['campaign']).resolve()
    if not folder.is_relative_to((assistant.root/'output/campaigns').resolve()):
        raise ValueError('This campaign is outside the generated campaign folder')
    campaign=json.loads((folder/'campaign.json').read_text('utf-8'))
    if campaign['status']!='reviewed':
        raise ValueError('Complete the local campaign review before staging uploads.')
    targets=campaign.get('targets') or [{'profile':campaign.get('profile','cricket'),'id':campaign['channel_id']}]
    accounts={}
    for target in targets:
        profile=target['profile']
        if profile not in ('cricket','gaming'):
            raise ValueError('Unknown campaign destination')
        account=publisher.accounts(profile)['youtube']
        if not account['connected'] or account['id']!=target['id']:
            raise ValueError('Reconnect the intended campaign channel before staging uploads.')
        accounts[profile]=account
    rows=[]
    clips=campaign['clips']
    previous=snapshot.get('publishing_review') or {}
    request=next((m.get('text','') for m in snapshot.get('messages',[]) if m.get('id')==snapshot.get('active_request_message_id')),'')
    from .assistant_publish_intent import fresh_upload
    from .publishing_times import window,choose as choose_release
    from .assistant_distribution import context as workflow_context
    from .distribution_schedule import contract
    if schedule and fresh_upload(request):
        # Keep the existing upload/schedule flow, but resolve this new command's
        # future defaults instead of validating an obsolete export timestamp.
        timing=contract(request,workflow_context(assistant.root))
        schedule_spec={**(schedule_spec or {}),'first_date':timing['first_date'],'clock':timing['clock']}
    random_window=window(request,workflow_context(assistant.root)) if schedule else None
    if random_window and (schedule_spec or not previous.get('rows')):
        timing=contract(request,workflow_context(assistant.root))
        schedule_spec={**(schedule_spec or {}),'first_date':timing['first_date'],'clock':timing['clock']}
    if schedule and not schedule_spec and previous.get('campaign')==str(folder) and previous.get('rows'):
        # A plain resume retains the exact reviewed subset and ordering.
        fingerprints=[publisher.store.get(r['id'])['fingerprint'] for r in previous['rows']]
        chosen={c['fingerprint']:c for c in clips}
        clips=[chosen[key] for key in dict.fromkeys(fingerprints) if key in chosen]
        if len(clips)!=len(set(fingerprints)):
            raise ValueError('A previously reviewed clip is no longer in this campaign.')
    if schedule_spec and schedule_spec.get('clip_indices'):
        indices=schedule_spec['clip_indices']
        if len(indices)!=len(set(indices)) or any(i not in {c['index'] for c in clips} for i in indices):
            raise ValueError('Select existing unique campaign clip indices.')
        clips=[c for c in clips if c['index'] in indices]
    for profile,account in accounts.items():
        dates=[]
        if schedule:
            from .assistant_publishing_context import daily_dates
            previous=snapshot.get('publishing_review') or {}
            prior=[r['publish_at'] for r in previous.get('rows',[])
                   if r.get('profile')==profile and r.get('publish_at')]
            if previous.get('campaign')!=str(folder) or len(prior)!=len(clips):prior=None
            dates=daily_dates(clips,schedule_spec,prior)
            if random_window and (schedule_spec or not prior):
                dates=[choose_release(folder,c['fingerprint']+':'+profile+':youtube',due[:10],random_window).isoformat()
                       for c,due in zip(clips,dates)]
        for index,clip in enumerate(clips):
            path=Path(clip['video']).resolve()
            if not path.is_relative_to(folder) or fingerprint(path)!=clip['fingerprint']:
                raise ValueError('A campaign export changed after review')
            from .assistant_distribution import ensure_youtube_copy
            ensure_youtube_copy(assistant,session_id,clip,profile,folder,campaign,request)
            item={'platform':'youtube','profile':profile,'kind':'short','video':str(path),
                  'fingerprint':clip['fingerprint'],'metadata':clip['metadata'],'visibility':'private',
                  'duration':clip['duration'],'width':1080,'height':1920,'brain':campaign['model'],
                  'thumbnail':'','thumbnail_fingerprint':'','video_url':'','campaign':str(folder)}
            job_id=publisher.store.add_batch([item])[0]
            job=publisher.store.get(job_id)
            if job['status']=='draft' and not job.get('remote'):
                publisher.store.change(job_id,metadata=clip['metadata'],campaign=str(folder),visibility='private',
                    due=datetime.fromisoformat(dates[index]).timestamp() if schedule else job['due'])
                job=publisher.store.get(job_id)
            rows.append({'id':job_id,'profile':profile,'channel':account['name'],'kind':'short',
                         'source':Path(campaign['source']).name,'duration':clip['duration'],
                         'metadata':job['metadata'],'status':job['status'],'url':job.get('remote',{}).get('url',''),
                         'publish_at':dates[index] if schedule else ''})
    # Correct only unstarted Instagram drafts created by the old generic route
    # for these exact campaign files; unrelated queues and remote posts stay put.
    old_ids={i for m in snapshot.get('messages',[]) for i in m.get('publish_ids',[])}
    fingerprints={c['fingerprint'] for c in campaign['clips']}
    for queued in publisher.store.list():
        if (queued['id'] in old_ids and queued['platform']=='instagram' and queued['status']=='draft'
            and not queued.get('remote') and queued['fingerprint'] in fingerprints):
            publisher.cancel(queued['id'])
    previous=snapshot.get('publishing_review') or {}
    from .assistant_upload_recovery import same_instant
    prior_dates={r['id']:r.get('publish_at','') for r in previous.get('rows',[])}
    retained_authority=bool(previous.get('allow_reschedule') is True and previous.get('campaign')==str(folder)
        and rows and all(same_instant(r['publish_at'],prior_dates.get(r['id'],'')) for r in rows))
    review={'id':uuid.uuid4().hex,'ids':[r['id'] for r in rows],'accounts':accounts,
            'rows':rows,'state':'review','visibility':'private','created':time.time(),'upload_requested':True,
            'schedule':schedule,'campaign':str(folder),
            'allow_reschedule':bool(schedule_spec and any(schedule_spec.values())) or retained_authority}
    assistant._update(session_id,publishing_review=review,status='needs_review',selected='publish',
                      stage='Review uploads and scheduled release dates.' if schedule else 'Review private uploads.')
    uploaded=sum(bool(r['url']) for r in rows)
    assistant._message(session_id,'assistant','Review all '+str(len(rows))+' YouTube Shorts below. '+
        (f'{uploaded} already have upload receipts and will be reused; {len(rows)-uploaded} still need uploading. '
         'The plan releases one Short per day at the same India time. Only verified YouTube release dates count as scheduled. '
         'Confirm this review to apply the schedule to these exact videos.' if schedule else 'These uploads will remain private.'),
        publishing_review=review,browser_setup=schedule)
    if schedule and len(clips)<len(campaign['clips']):
        assistant._message(session_id,'assistant',f'The requested range covers {len(clips)} videos, one per day. '
            f'The remaining {len(campaign["clips"])-len(clips)} videos are not included and their existing visibility is unchanged.')


def followup(assistant,session_id,text,progress):
    """The local model routes references to the finished campaign, never generic redrafting."""
    from .assistant_contracts import account_check
    if account_check(text):return False
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_visuals.brain import open_brain
    from hinglish_publish.campaign import RecordedBrain
    from .campaign_memory import catalog,resolve,decide
    snapshot=assistant.snapshot(session_id)
    # Eligibility only: the local model decides whether this means reuse or new work.
    from .assistant_publishing_context import relevant
    if not relevant(text):
        return False
    cards=catalog(assistant,session_id)
    if not cards and not snapshot.get('campaign'):return False
    with assistant.state.work_lock,gpu_lock(assistant.root):
        brain=open_brain(assistant.root,'ollama',progress=progress)
        try:
            folder=assistant.folder/('campaign-decisions-'+session_id);folder.mkdir(parents=True,exist_ok=True)
            answer=decide(RecordedBrain(brain,folder),snapshot,text,cards,
                          assistant.context_memory(text,session_id))
            model=brain.name
        finally:brain.close()
    if answer['action']=='other':return False
    assistant._update(session_id,brain=model)
    if answer['action']=='clarify':
        if not answer['question'].strip():raise ValueError('The local model must identify the missing campaign information.')
        assistant._message(session_id,'assistant',answer['question'],question=True)
        assistant._update(session_id,status='idle',stage='');return True
    folder,campaign,card=resolve(assistant,answer['campaign_id'])
    if answer['action'] in ('schedule','private') and not card['available_for_upload']:
        assistant._message(session_id,'assistant',f'The selected batch from {card["source"]} is no longer ready: '
                           f'{card["export_count"]}/{card["clip_count"]} files exist; review status is {card["status"]}. '
                           'Saved exports are unchanged. No new extraction or upload started.')
        assistant._update(session_id,status='needs_review',stage='Review the saved campaign exports.');return True
    videos=[c['video'] for c in campaign['clips']]
    assistant._update(session_id,campaign=str(folder),campaign_memory_ref=card['id'],last_paths=videos,shorts_paths=videos)
    if answer['action'] in ('schedule','private'):
        spec={k:answer.get(k,'') for k in ('first_date','end_date','clock')}
        if answer.get('clip_indices'):spec['clip_indices']=answer['clip_indices']
        # Publish the review/continuation state atomically; a client must not
        # start another request in the gap before an authorized schedule runs.
        with assistant.lock:
            if answer['action']=='schedule' and any(spec.values()):
                stage_review(assistant,session_id,schedule=True,schedule_spec=spec)
            else:stage_review(assistant,session_id,schedule=answer['action']=='schedule')
            if answer['action']=='schedule':
                from .assistant_schedule import continue_uploaded
                continue_uploaded(assistant,session_id,text)
        return True
    if answer['action']=='status':
        assistant._message(session_id,'assistant',f'I found {card["export_count"]} saved exports from {card["source"]}. '
            f'{sum(bool(c["video_id"]) for c in card["clips"])} have upload receipts and '
            f'{sum(c["schedule_verified"] for c in card["clips"])} have verified release dates.')
        assistant._update(session_id,status='idle',stage='');return True
    return False
