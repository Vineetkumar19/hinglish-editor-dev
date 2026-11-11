"""Durable output recall from saved manifests, independent of chat history windows."""
import json
from pathlib import Path


def catalog(assistant,session_id=None):
    base=(assistant.root/'output/campaigns').resolve()
    allowed=None
    if session_id:
        snapshot=assistant.snapshot(session_id)
        allowed={Path(snapshot[k]).name for k in ('campaign','campaign_memory_ref','campaign_in_progress') if snapshot.get(k)}
        reviews=[snapshot.get('publishing_review') or {}]
        reviews += [m.get('publishing_review') or {} for m in snapshot.get('messages',[])]
        for review in reviews:
            if review.get('campaign'):allowed.add(Path(review['campaign']).name)
            allowed.update(Path(row['campaign']).name for row in review.get('rows',[])+review.get('instagram_rows',[]) if row.get('campaign'))
        # Completed files remain durable evidence even after chat prose is trimmed.
        paths=list(snapshot.get('last_paths',[]))+list(snapshot.get('shorts_paths',[]))
        paths += [p for m in snapshot.get('messages',[]) for p in m.get('videos',[])]
        allowed.update(Path(p).parent.name for p in paths if Path(p).parent.parent.resolve()==base)
    jobs=assistant.state.publisher.store.list()
    cards=[]
    for manifest in sorted(base.glob('*/campaign.json')):
        folder=manifest.parent.resolve()
        if not folder.is_relative_to(base):continue
        if allowed is not None and folder.name not in allowed and not folder.name.startswith(('chat-'+session_id+'-','edited-'+session_id+'-')):continue
        try:
            state=json.loads(manifest.read_text('utf-8'))
            clips=state.get('clips',[])
            if not clips:continue
            exports=[]
            for clip in clips:
                path=Path(clip['video']).resolve()
                exists=path.is_relative_to(folder) and path.is_file() and bool(path.stat().st_size)
                queued=next((j for j in jobs if j.get('campaign')==str(folder)
                             and j.get('fingerprint')==clip.get('fingerprint') and j['platform']=='youtube'),{})
                remote=queued.get('remote',{}) or clip.get('remote',{})
                exports.append({'index':clip['index'],'file':path.name,'exists':exists,
                    'title':clip.get('metadata',{}).get('title',clip.get('pick',{}).get('title','')),
                    'duration':clip.get('duration'),'publish_at':clip.get('publish_at',''),
                    'video_id':remote.get('id',''),'url':remote.get('url',''),
                    'schedule_verified':bool(remote.get('schedule_verified_at') or (
                        clip.get('scheduled_verified_at') and remote.get('id') and
                        remote.get('id')==clip.get('remote',{}).get('id') and
                        clip.get('remote_status',{}).get('publishAt')))})
            available=all(e['exists'] for e in exports)
            reviewed=state.get('status') in ('reviewed','uploaded_private','scheduled')
            cards.append({'id':folder.name,'source':Path(state.get('source','')).name,
                'status':state.get('status','unknown'),'targets':state.get('targets') or
                    [{'profile':state.get('profile','cricket'),'id':state.get('channel_id','')}],
                'clip_count':len(exports),'export_count':sum(e['exists'] for e in exports),
                'available_for_upload':available and reviewed,'clips':exports})
        except (ValueError,OSError,KeyError,TypeError):
            continue
    return cards


def resolve(assistant,campaign_id):
    """Only a catalog ID can supply paths; the model cannot invent an output folder."""
    card=next((c for c in catalog(assistant) if c['id']==campaign_id),None)
    if not card:
        raise ValueError('That saved campaign is unavailable. No new clips were generated.')
    folder=(assistant.root/'output/campaigns'/campaign_id).resolve()
    state=json.loads((folder/'campaign.json').read_text('utf-8'))
    return folder,state,card


def decide(brain,snapshot,text,cards,memory):
    """Constrain publishing tool arguments to ready exports, with one local-model repair."""
    from hinglish_niche.profiles import use
    ids=[c['id'] for c in cards]
    ready=[c['id'] for c in cards if c['available_for_upload']]
    from .assistant_publishing_context import active_context,reference_campaign,schedule_literals
    active=active_context(snapshot)
    bound=reference_campaign(snapshot,text,cards)
    if bound:
        # A resolved, current batch does not need unrelated archived requests or
        # old assistant explanations. Its receipt facts are already in cards.
        memory={k:v for k,v in memory.items() if k not in ('messages','runtime_facts','saved_media','active_task')}
        active['conversation']=[m for m in active['conversation'] if m.get('role')=='user']
    literals=schedule_literals(text)
    summaries=[]
    for card in sorted(cards,key=lambda c:(not c['available_for_upload'],c['id'])):
        summaries.append({k:card[k] for k in ('id','source','status','targets','clip_count','export_count','available_for_upload')})
        summaries[-1].update(
            uploaded_count=sum(bool(c['video_id']) for c in card['clips']),
            scheduled_count=sum(c['schedule_verified'] for c in card['clips']),
            example_titles=[c['title'] for c in card['clips'][:2]])
    # Keep missing batches referencable so a named missing source is not forced
    # into another ready batch by the JSON grammar. Publishing readiness is
    # validated below, before any caller can stage a review.
    schema={'type':'object','properties':{
        'action':{'type':'string','enum':['schedule','private','status','other','clarify']},
        'campaign_id':{'type':'string','enum':['']+([bound] if bound else ids)},
        'first_date':{'type':'string','pattern':r'^(?:|\d{4}-\d{2}-\d{2})$'},
        'end_date':{'type':'string','pattern':r'^(?:|\d{4}-\d{2}-\d{2})$'},
        'clip_indices':{'type':'array','items':{'type':'integer','minimum':1},'maxItems':40},
        'clock':{'type':'string','pattern':r'^(?:|(?:[01]\d|2[0-3]):[0-5]\d)$'},
        'question':{'type':'string','maxLength':600}},
        'required':['action','campaign_id','first_date','end_date','clock','clip_indices','question'],'additionalProperties':False}
    from .assistant_publishing_context import intent_text
    import re
    current=intent_text(text)
    from .assistant_publish_intent import fresh_upload
    fresh_request=fresh_upload(text)
    explicit_count=re.search(r'\b(\d+|seven|five|six|eight|nine|ten)\s+(?:(?:existing|saved|YouTube|YT)\s+)*(videos?|shorts?|clips?)\b',text,re.I)
    words={'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
    requested=int(explicit_count[1]) if explicit_count and explicit_count[1].isdigit() else words.get(explicit_count[1].casefold(),0) if explicit_count else 0
    if explicit_count and re.match(r'\s*(?:every\s*day|per day|a day|daily)\b',text[explicit_count.end():],re.I):requested=0
    if bound and re.search(r'\bschedul\w*\b',current,re.I) and not re.search(
            r'\b(how|why|explain|cancel|never|do not|don.t)\b',current,re.I):
        schema['properties']['action']['enum']=['schedule','clarify']
    # Literal dates and preserved review values are application inputs, not
    # another model decision. Exclude them from generation so a valid batch
    # choice cannot fail because the model copied an ISO clock from its memory.
    fixed={key:literals.get(key,'') for key in ('first_date','end_date','clock')
           if key in literals or bound or fresh_request}
    for key in fixed:
        del schema['properties'][key]
        schema['required'].remove(key)
    if literals.get('end_date'):
        from datetime import date
        capacity=(date.fromisoformat(literals['end_date'])-date.fromisoformat(literals['first_date'])).days+1
        if bound:
            card=next(c for c in cards if c['id']==bound)
            count=min(capacity,card['clip_count'])
            schema['properties']['clip_indices'].update(maxItems=count)
        if requested>capacity:schema['properties']['action']['enum']=['clarify']
    system=(
        'Resolve the latest request using the SAVED CAMPAIGN CATALOG across Storylens chats. '
        'This is file/task routing, not editing or metadata generation. The catalog is authoritative; '
        'old assistant claims and source names mentioned in chat memory may describe failed attempts. '
        'The active UI profile is not a destination restriction. '
        'Select the batch matching the requested channel and count. '
        'For schedule/private, campaign_id MUST be in ready_campaign_ids. A planned batch with zero '
        'exports is not the finished batch even if it has seven clip candidates. '
        'When the user says "the seven Shorts you have created for gaming", select an existing '
        'ready seven-export gaming batch, not an unfinished extraction attempt. '
        'If the user explicitly names an unavailable source/batch, ask about that missing batch; '
        'do not replace it with another source. If equally matching ready batches exist, clarify once. '
        'schedule means upload and schedule the existing exports. private means upload privately. '
        'status means ask about existing results/how scheduling works; select the referenced catalog ID. '
        'If all clips already have verified schedules, use status to avoid duplicate uploads. '
        'Reuse saved release dates unless the user explicitly changes them. '
        'The active_task current conversation/review outranks retrieved chat snippets. '
        'A correction such as "shedule them, 1 video per day, not all in a day" is action schedule '
        'for the current batch, not status, one clip, a fresh extraction or the old Instagram test. '
        'Understand common misspellings of schedule. This handler is YouTube-only; never redirect to Instagram '
        'because an archived chat mentioned it. Private uploads are not scheduled. '
        'Set first_date and clock only for an explicitly requested change, otherwise empty to preserve the active review. '
        'Use the current_time in active_task for today/tomorrow, never a date from an old chat. '
        'If the saved first release is in the past and no new future start is specified, clarify once for a future start. '
        'EXCEPTION: a new undated upload-now command uses fresh application timing defaults. Do not repeat an old date error or ask for a future date for that command. '
        'One per day means consecutive days at the same IST time. An explicit end_date is inclusive and MUST NOT be exceeded. '
        'For example October 20 through October 24 has FIVE daily slots, not seven. If seven videos exist, select '
        'the first five clip_indices in saved order and leave the remaining two unscheduled/private. '
        'clip_indices is empty to select the whole batch only when it fits the request. Never extend an explicit end date. '
        'other means an unrelated request, cancellation, or explicit NEW extraction/source selection. '
        'clarify means an ambiguous/missing batch or missing release information; ask one specific question. '
        'For other/clarify use an empty campaign_id; otherwise use an exact supplied ID. '
        'question must be empty except for clarify. Do not perform any upload or create new clips.')
    system+=(' The shared_memory.saved_media records are real non-campaign editing outputs too. '
        'If the user is asking about or editing one of those completed outputs, choose other so the editor '
        'can handle it. Never claim that only saved_campaigns exist when saved_media includes the referenced video.')
    system+=(' Fields listed in fixed_schedule_values are already resolved application inputs. '
        'Do not generate those fields; follow the response schema. Select the batch, intent and '
        'clip_indices matching the inclusive daily capacity in explicit_schedule_values.')
    data={'shared_memory':memory,'saved_campaigns':summaries,'ready_campaign_ids':ready,
          'current_chat_campaign':Path(snapshot.get('campaign') or '').name,
          'active_task':active,'reference_campaign':bound,
          'explicit_schedule_values':literals,
          'fixed_schedule_values':fixed,
          'active_profile':snapshot.get('profile','general'),'request':text}
    if fresh_request:
        data['fresh_upload_timing']={'use_current_defaults':True,'requested_count':requested,
            'instruction':'Select the requested ready batch. The application resolves fresh timing for this new upload-now command; do not reuse an expired release date.'}
    for attempt in range(2):
        # Creator editing/reference context is irrelevant to selecting a saved output batch.
        with use({'profile':'general'}):
            answer=brain.json(system,data,schema,max_tokens=900)
        answer={**answer,**fixed}
        action=answer.get('action');chosen=answer.get('campaign_id');question=answer.get('question','')
        if action not in schema['properties']['action']['enum']:
            data.update(invalid_decision=answer,validation_error='This is a request to schedule the current batch. Return schedule, or clarify only a missing future release time.')
            continue
        if action=='clarify' and isinstance(question,str) and question.strip():
            if fresh_request and re.search(r'\b(?:release|schedule|future|date|time|passed|too close)\b',question,re.I):
                data.update(invalid_decision=answer,validation_error='This is a new upload-now command without an explicit date. Application defaults resolve fresh timing. Select the requested ready batch and exact clip count; do not repeat historical date errors.')
                continue
            # No operation will execute. Ignore unused model arguments instead
            # of rejecting a valid conflict question for an irrelevant clock.
            return {'action':'clarify','campaign_id':'','question':question,
                    'first_date':'','end_date':'','clock':'','clip_indices':[]}
        if any(answer.get(k,'')!=v for k,v in literals.items()) or (bound and any(
                answer.get(k,'')!=literals.get(k,'') for k in ('first_date','end_date','clock'))):
            data.update(invalid_decision=answer,validation_error='Preserve explicit_schedule_values exactly; empty fields preserve the current review. Never replace an explicit 7 p.m. with a saved 6 p.m. time.')
            continue
        if bound and action in ('schedule','private','status') and chosen!=bound:
            data.update(invalid_decision=answer,validation_error='The unqualified batch reference is bound to '+bound+'. Do not substitute an older campaign.')
            continue
        valid=(action in ('schedule','private') and chosen in ready and not question) or (
            action=='status' and chosen in ids and not question) or (
            action=='other' and chosen=='' and not question) or (
            action=='clarify' and chosen=='' and isinstance(question,str) and bool(question.strip()))
        if valid:
            try:
                from datetime import datetime
                import re
                if answer.get('first_date'):datetime.strptime(answer['first_date'],'%Y-%m-%d')
                if answer.get('clock') and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',answer['clock']):raise ValueError('Use HH:MM IST.')
                indices=answer.get('clip_indices',[])
                if not isinstance(indices,list) or any(type(i) is not int for i in indices) or len(indices)!=len(set(indices)):raise ValueError('Use unique clip indices.')
                if action in ('schedule','private'):
                    card=next(c for c in cards if c['id']==chosen)
                    available={c['index'] for c in card['clips']}
                    if any(i not in available for i in indices):raise ValueError('Select existing clip indices only.')
                    if requested and (len(indices) if indices else card['clip_count'])!=requested:
                        raise ValueError('Preserve the explicitly requested number of videos: '+str(requested))
                    if action=='schedule' and literals.get('end_date'):
                        count=min(capacity,card['clip_count'])
                        if len(indices)!=count:raise ValueError('This inclusive range has '+str(capacity)+' daily slots. Select '+str(count)+' existing clips and leave the rest private.')
            except (TypeError,ValueError):
                data.update(invalid_decision=answer,validation_error='Preserve the exact date range and select only its daily capacity using valid clip_indices. Use YYYY-MM-DD dates and HH:MM clock; empty fields preserve the review.')
                continue
            return answer
        data={**data,'invalid_decision':{k:answer.get(k) for k in ('action','campaign_id','question')},
              'validation_error':'Publishing requires an exact ready_campaign_ids entry. '
                  'Choose a matching READY batch, status with a catalog ID, or clarify if the requested batch is unavailable. '
                  'Never replace an explicitly requested missing source with a different source.'}
    raise ValueError('The local model could not select a ready saved batch. Saved exports remain unchanged; no upload started.')
