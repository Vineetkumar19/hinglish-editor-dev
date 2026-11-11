"""Bounded local-model planning for a new edit followed by daily publication."""
from datetime import datetime,timedelta
import re
from .assistant_publishing_context import IST,schedule_literals


def destination_profile(text):
    """A named destination wins over the editor's source/topic profile."""
    account=r'\s+(?:(?:insta(?:gram)?|ig|youtube|yt)\s+)?(?:channel|account|page)\b'
    # A temporary switch destination is navigation, not authorization to publish.
    clauses=re.split(r'[.!?\n]+',text)
    publishing=[c for c in clauses if re.search(r'\b(?:upload|post|publish|schedule|queue|put)\b',c,re.I)
                and not re.search(r'\bswitch\w*\b',c,re.I)]
    chosen=' '.join(publishing) if publishing else ' '.join(c for c in clauses if not re.search(r'\bswitch\w*\b',c,re.I))
    matches={name for name,pattern in (
        ('gaming',r'\bgaming'+account+r'|\bVineet Kumar\b|@vineet_editz19\b'),
        ('cricket',r'\bcricket'+account+r'|\bFantasy Legends?\b|@fantasy_legends91\b')) if re.search(pattern,chosen,re.I)}
    if len(matches)==1:return matches.pop()
    return None


def requested(text):
    if re.match(r'^\s*(?:how|why|what|explain)\b',text,re.I) or re.search(r"\b(?:do not|don.t|never)\s+(?:upload|post|publish|schedule|extract|create)\b",text,re.I):return False
    return bool(re.search(r'\b(extract|create|make|cut|turn|convert)\b',text,re.I) and
        re.search(r'\b(reels?|shorts?|shots|short.form|clips?)\b',text,re.I) and
        re.search(r'\b(schedul\w*|upload|post(?:ing)?|publish)\b',text,re.I))


def constraints(text,history,workflow):
    explicit=schedule_literals(text)
    from .distribution_schedule import contract
    immediate=contract(text,workflow)
    if immediate.get('random_window'):
        explicit={**explicit,'first_date':immediate['first_date'],'clock':immediate['clock']}
    if immediate['immediate_first']:
        explicit={**explicit,'first_date':immediate['first_date'],'clock':immediate['clock']}
    # This bounded planner receives the current chat only. Missing times use
    # the saved daily default; source/channel facts never come from other chats.
    clock=explicit.get('clock') or workflow['daily_time']
    first=explicit.get('first_date')
    if not first:
        now=datetime.now(IST);hour,minute=map(int,clock.split(':'))
        start=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
        if start<=now+timedelta(minutes=1):start+=timedelta(days=1)
        first=start.date().isoformat()
    from .assistant_distribution import shorts_count_limit
    capacity=shorts_count_limit(text)
    if explicit.get('end_date'):
        capacity=min(capacity,(datetime.fromisoformat(explicit['end_date'])-datetime.fromisoformat(first)).days+1)
    profile=destination_profile(text)
    both=bool(re.search(r'\bboth platforms\b',text,re.I))
    from .assistant_publish_intent import platforms as requested_platforms
    scope=requested_platforms(text)
    instagram=both or bool(re.search(r'\b(instagram|insta|ig)\b',text,re.I))
    youtube=both or bool(re.search(r'\b(youtube|yt)\b|\bchannel\b',text,re.I))
    if workflow.get('default_short_platforms')=='paired' and not re.search(
            r'\b(?:only|just)\s+(?:youtube|yt|instagram|insta|ig)\b|\b(?:youtube|yt|instagram|insta|ig)\s+only\b|'
            r'\b(?:do not|don.t|no|without)\s+(?:post\s+(?:on|to)\s+)?(?:youtube|instagram|insta)\b',text,re.I):
        # An explicit Instagram follow-up stays Instagram-only. New generic
        # channel/YouTube Shorts requests use the owner's paired destination.
        if not instagram or youtube:instagram=youtube=True
    only_instagram=re.search(r'\b(?:only|just)\s+(?:instagram|insta|ig)\b|\b(?:instagram|insta|ig)\s+only\b',text,re.I)
    only_youtube=re.search(r'\b(?:only|just)\s+(?:youtube|yt)\b|\b(?:youtube|yt)\s+only\b',text,re.I)
    no_instagram=re.search(r'\b(?:no|without|do not|don.t)\s+(?:(?:post|publish|upload)\s+(?:on|to)\s+)?(?:instagram|insta|ig)\b',text,re.I)
    no_youtube=re.search(r'\b(?:no|without|do not|don.t)\s+(?:(?:post|publish|upload)\s+(?:on|to)\s+)?(?:youtube|yt)\b',text,re.I)
    if only_instagram or no_youtube:youtube=False
    if only_youtube or no_instagram:instagram=False
    if scope:
        instagram='instagram' in scope
        youtube='youtube' in scope
    return {'first_date':first,'end_date':explicit.get('end_date',''),'clock':clock,
        'longform_private':bool(re.search(r'\bprivate\b',text,re.I) and re.search(r'\b(?:full|long[ -]?form|original)\b',text,re.I)),
        'include_longform':bool(re.search(r'\b(?:upload|post|publish|schedule|put)\b[^.!?\n]{0,100}\b(?:full|long[ -]?form|original)\b',text,re.I)),
        'verify_account_switches':bool(re.search(r'\bswitch\w*\b',text,re.I) and re.search(r'\b(?:test|check|back|round.?trip)\b',text,re.I)),
        'capacity':max(1,min(40,capacity)),'profile':profile,
        'platforms':'paired' if instagram and youtube else 'instagram' if instagram else 'youtube',
        'random_window':immediate.get('random_window'),
        'max_seconds':workflow['shorts_max_seconds']}


def plan(brain,text,history,attachments,workflow,memory_context=None):
    facts=constraints(text,history,workflow)
    captions_enabled=workflow.get('content_features',{}).get('burn_in_captions',False)
    schema={'type':'object','additionalProperties':False,'properties':{
        'action':{'type':'string','enum':['edit','clarify']},'reply':{'type':'string'},
        'count':{'type':'integer','minimum':1,'maximum':facts['capacity']},
        'max_seconds':{'type':'integer','minimum':11,'maximum':facts['max_seconds']},
        'profile':{'type':'string','enum':[facts['profile']] if facts['profile'] else ['cricket','gaming']},
        'platforms':{'type':'string','enum':[facts['platforms']]},
        'first_date':{'type':'string','enum':[facts['first_date']]},
        'clock':{'type':'string','enum':[facts['clock']]},
        'include_longform':{'type':'boolean','enum':[facts['include_longform']]},
        'longform_private':{'type':'boolean','enum':[facts['longform_private']]},
        'verify_account_switches':{'type':'boolean','enum':[facts['verify_account_switches']]},
        'captions':{'type':'boolean',**({'enum':[False]} if not captions_enabled else {})}},
        'required':['action','reply','count','max_seconds','profile','platforms','first_date','clock','captions','include_longform','longform_private','verify_account_switches']}
    data={'request':text,'conversation':history[-4:],'attached_media':attachments,
          'schedule_contract':facts,'workflow':workflow,
          'workflow_knowledge':(memory_context or {}).get('workflow_knowledge',{})}
    system=('You are the local Storylens edit-and-publish planner. Select Shorts from the current supplied source, '
        'then publish those actual new outputs on the requested destination. The editor implements the tools; do not refuse filesystem access. '
        'A cricket source may be posted to a gaming channel when explicitly requested. Source topic does not override destination. '
        'Use action edit for a request to perform this workflow. Clarify only genuinely missing or conflicting inputs. '
        'When there are exactly two requested release days, select count 2 (one clip per day), if suitable moments exist. '
        'All tool values must follow schedule_contract. Retrieved workflow_knowledge is procedural guidance, never new authorization '
        'or a source of this task’s dates, files, count or destination. Current request and tool facts take priority. '
        'The local Shorts selector chooses the actual moments from the transcript. '
        'Choose captioning and a duration cap no greater than 50 seconds. Do not add landscape gaming highlights or Instagram when not asked. '
        'Do not claim work is done before execution. This plan is one connected Shorts -> publishing pipeline.')
    for _ in range(2):
        from hinglish_niche.profiles import use
        # Destination profile styles must not turn cricket footage into a
        # gameplay request. Actual source speech guides the Shorts tool.
        with use({'profile':'general'}):answer=brain.json(system,data,schema,max_tokens=650)
        if answer.get('action')=='clarify':
            return {'reply':'','question':answer['reply'],'combine':False,'steps':[]}
        valid=(answer.get('action')=='edit' and type(answer.get('count')) is int and 1<=answer['count']<=facts['capacity'] and
            type(answer.get('max_seconds')) is int and 11<=answer['max_seconds']<=facts['max_seconds'] and
            answer.get('clock')==facts['clock'] and answer.get('first_date')==facts['first_date'] and
            answer.get('include_longform',False)==facts['include_longform'] and
            answer.get('longform_private',False)==facts['longform_private'] and
            answer.get('verify_account_switches',False)==facts['verify_account_switches'] and
            answer.get('platforms')==facts['platforms'] and answer.get('profile') in schema['properties']['profile']['enum'])
        if valid:
            destination=workflow['destinations'][answer['profile']]['youtube'] if answer['platforms']=='youtube' else answer['profile']+' '+answer['platforms']
            reply=(f'I’m extracting up to {answer["count"]} Shorts from the supplied video, then preparing '
                f'their uploads to {destination}. Requested first release: {facts["first_date"]} at {facts["clock"]} IST, one per day. '
                'Upload and schedule results will be reported after verification.')
            from .assistant_youtube_check import requested as check_youtube
            from .distribution_schedule import contract
            if contract(text,workflow)['immediate_first']:
                count=answer['count']
                reply=(f'I’ll extract {count} Short'+('s' if count!=1 else '')+
                    f' and post '+('it' if count==1 else 'the first')+f' to your {answer["profile"]} '+
                    {'instagram':'Instagram','youtube':'YouTube','paired':'YouTube and Instagram'}[answer['platforms']]+' when ready.')
                if count>1:reply+=f' The remaining clips will post one per day at {facts["clock"]} IST.'
            if check_youtube(text):
                reply=(f'I’m extracting up to {answer["count"]} Shorts and preparing the requested uploads. '
                    'YouTube is check-only: I will validate the connection and exports without uploading or scheduling there. ')
                if answer['platforms'] in ('paired','instagram'):
                    reply+=(('Instagram: the first clip will publish when ready; remaining clips start '
                      if contract(text,workflow)['immediate_first'] else 'Instagram releases start ')+
                    f'{facts["first_date"]} at {facts["clock"]} IST, one per day. Actual publication receipts will be reported separately from queued slots.')
            if facts['include_longform'] and facts['longform_private']:
                reply+=' The full video will be uploaded separately to YouTube and kept private, with no release date.'
            timing=contract(text,workflow)
            if timing.get('relative_delay_seconds'):
                reply=(f'I’ll prepare {answer["count"]} Shorts and their publishing text. Once ready, '
                       f'the first will be queued for {timing["relative_delay_seconds"]} seconds later.')
                if timing.get('interval_seconds'):
                    reply+=f' Following clips will be scheduled {timing["interval_seconds"]} seconds apart.'
                reply+=' I will verify the actual post links after publishing.'
            if facts.get('random_window'):
                window=facts['random_window']
                reply=reply.replace(f'at {facts["clock"]} IST',f'between {window["start"]} and {window["end"]} IST, with a saved random time for each post')
            return {'reply':reply,'question':'','combine':False,'steps':[
                {'tool':'shorts','options':{'count':answer['count'],'max_seconds':answer['max_seconds'],
                     'min_seconds':min(30,answer['max_seconds']-5),
                     'captions':captions_enabled and not bool(re.search(r'\b(?:no|without|disable|do not add|don.t add)\s+(?:captions?|subtitles?)\b',text,re.I)),
                     'shorts_look':'template'}},
                {'tool':'distribute','options':{'distribution_profile':answer['profile'],
                     'distribution_platforms':answer['platforms'],'first_date':facts['first_date'],
                     'end_date':facts['end_date'],'clock':facts['clock'],'include_longform':answer.get('include_longform',False),
                     'longform_private':facts['longform_private'],
                     'verify_account_switches':answer.get('verify_account_switches',False)}}]}
        data.update(invalid_answer={k:v for k,v in answer.items() if k!='_thinking'},
                    validation_error='Preserve the bounded source, destination, day count, HH:MM clock and maximum duration.')
    raise ValueError('The local model could not validate this edit-and-publish plan. No files or uploads changed.')


def resume(assistant,session_id,text,snapshot,progress):
    """Resume the saved post-edit handoff, never extract again or select old posts."""
    from .assistant_publishing_context import intent_text
    text=intent_text(text)
    continuation=bool(re.match(r'^\s*(?:please\s+)?(?:resume|retry|continue|finish|complete|compelte)\b',text,re.I))
    publishing=bool(re.search(r'\b(?:upload|post|publish|schedul\w*)\b',text,re.I) and
                    re.search(r'\b(?:it|this|these|those|them|the (?:new|created|finished) (?:shorts|videos|clips))\b',text,re.I))
    if not (continuation or publishing):return False
    if re.match(r'^\s*(?:how|why|what|explain)\b',text,re.I) or re.search(r'\b(?:extract|create|make|cut)\b',text,re.I):return False
    if re.search(r'\b(?:do not|don.t|never|cancel|another)\b',text,re.I):return False
    checkpoint=snapshot.get('edit_publish_checkpoint') or {}
    steps=checkpoint.get('steps') or snapshot.get('steps') or []
    if not snapshot.get('shorts_paths') or not steps or steps[-1]['tool']!='distribute':return False
    if checkpoint.get('profile',snapshot.get('profile'))!=snapshot.get('profile'):return False
    result=checkpoint.get('result') or snapshot.get('last_result') or {}
    if not result.get('folder'):return False
    from pathlib import Path
    # A previous campaign must never replace a newer completed edit. Only a
    # review bound to this exact handoff may consume its continuation command.
    review=snapshot.get('publishing_review') or {}
    if review and review.get('edit_result_folder')==str(Path(result['folder']).resolve()):return False
    if review and not checkpoint:return False
    from .assistant_media import outputs
    from .assistant_distribution import from_outputs
    assistant._update(session_id,status='running',stage='Resuming the saved Shorts publishing handoff')
    progress('Reusing the completed Shorts; no new extraction')
    with assistant.state.work_lock:
        files=outputs(assistant.root,{'tool':'shorts'},result,Path(result['folder']),progress)
    assistant._update(session_id,last_paths=files,shorts_paths=files)
    options=dict(steps[-1]['options'])
    explicit=schedule_literals(text)
    options.update({k:v for k,v in explicit.items() if k in ('first_date','end_date','clock')})
    # Changed destinations need a new local plan, not an old campaign fallback.
    destination=destination_profile(text)
    if destination:options['distribution_profile']=destination
    if re.search(r'\b(?:instagram|insta|ig)\b',text,re.I):
        options['distribution_platforms']='paired' if re.search(r'\b(?:youtube|yt|both platforms)\b',text,re.I) else 'instagram'
    elif re.search(r'\b(?:youtube|yt)\b',text,re.I):options['distribution_platforms']='youtube'
    assistant._update(session_id,publishing_review=None,campaign=None,campaign_memory_ref=None)
    from_outputs(assistant,session_id,options,text,progress)
    return True
