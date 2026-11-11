"""One chat request, one local model plan, then durable publishing stages."""
import json
from pathlib import Path
import re


def supervise(assistant, stop):
    """Optional upload-only recovery when unrelated workflow supervision is off."""
    import logging
    while not stop.wait(5):
        recover_delivery(assistant)
        for path in assistant.folder.glob('*.json'):
            if not re.fullmatch(r'[a-f0-9]{16}',path.stem):continue
            try:
                saved=json.loads(path.read_text('utf-8'))
                if not (saved.get('upload_workflow') or {}).get('auto_resume') or saved.get('stop'):continue
                resume_tick(assistant,path.stem,assistant.snapshot(path.stem))
            except Exception:
                logging.getLogger(__name__).exception('Saved uploading recovery failed for %s',path.stem)


def recover_delivery(assistant):
    """Future authorized Reels outlive the chat that buffered them.

    Restore the existing bounded delivery service even when no chat is active.
    No new jobs, authorizations or retries are created here.
    """
    try:
        from .prepare_post_http import service
        service(assistant.state, recover_delivery=True)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Authorized publishing delivery recovery failed')


def requested(text):
    from .assistant_prepare_post import _help, _positive
    value = _positive(text)
    return (not _help(text) and bool(re.search(r'\bcricket\b', value, re.I))
            and bool(re.search(r'\b(?:long|documentary|long-form)\b', value, re.I))
            and bool(re.search(r'\b(?:shorts|reels)\b', value, re.I))
            and bool(re.search(r'\b(?:extract|create|make|generate)\b', value, re.I))
            and bool(re.search(r'\b(?:upload|post|publish|schedule)\b', value, re.I)))


def plan(root, text, video, thumbnail, folder, progress):
    from hinglish_visuals.brain import open_brain
    from hinglish_niche.profiles import Profiles, use
    from hinglish_publish.prepare_post_runtime import RecordedBrain
    from hinglish_publish.prepare_post_budget import PublishingBudget
    context = Profiles(root).context('cricket')
    from hinglish_cut.model_preferences import preferences
    brain = open_brain(root, 'ollama', model=preferences(root).get('publishing_model','qwen3:8b'), progress=progress)
    brain.cache_enabled = False
    recorded = RecordedBrain(brain, folder, context)
    brain.request_guard = PublishingBudget(root, brain, folder, recorded, progress)
    schema = {'type': 'object', 'additionalProperties': False, 'properties': {
        'profile': {'type': 'string', 'enum': ['cricket']},
        'video': {'type': 'string', 'enum': [video]},
        'thumbnail': {'type': 'string', 'enum': [thumbnail]},
        'count': {'type': 'integer', 'minimum': 1, 'maximum': 40},
        'long_release': {'type': 'string', 'enum': ['post_now', 'schedule']},
        'shorts_release': {'type': 'string', 'enum': ['schedule']},
        'steps': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['profile', 'video', 'thumbnail', 'count', 'long_release', 'shorts_release', 'steps']}
    try:
        with use(context):
            result = recorded.json(
                'Plan this explicit cricket uploading request using the existing Prepare and Post tools. Return JSON. '
                'Use only the supplied exact file paths. Empty thumbnail means none. Copy the requested Shorts count. '
                'Default long_release to schedule unless the owner explicitly requests immediate long publication. '
                'Shorts and Reels are scheduled together. The exact steps are prepare_long, release_long, '
                'prepare_shorts, schedule_youtube_shorts, queue_instagram_reels, in that order. '
                'Each stage has saved inputs/results; no previous chat transcript or model conversation is needed.',
                {'owner_request': text, 'selected_video': video, 'selected_thumbnail': thumbnail},
                schema, max_tokens=800, think=False)
        return result, brain.name
    finally:
        brain.close()


def followup(assistant, session_id, text, selected, progress, message_id):
    if not selected and resume_request(assistant,session_id,text,progress,message_id):
        return True
    if not requested(text):
        return False
    from .assistant_sources import literal_locations
    from .assistant_prepare_post import MEDIA, IMAGES, NUMBERS
    from .prepare_post_http import service, workflow_service
    from hinglish_app.durable_json import write
    from hinglish_app.user_messages import failure
    folder = Path(assistant.root) / 'output/publisher-prepare-post/assistant-workflows' / session_id / message_id
    folder.mkdir(parents=True, exist_ok=True)
    flow = None
    try:
        locations, words = literal_locations(text)
        paths = list(dict.fromkeys([Path(a['path']).resolve() for a in selected if a.get('path')] + locations))
        videos = [p for p in paths if p.is_file() and p.suffix.lower() in MEDIA]
        images = [p for p in paths if p.is_file() and p.suffix.lower() in IMAGES]
        if len(videos) != 1 or len(images) > 1:
            raise ValueError('Give one exact cricket video path and, optionally, one thumbnail path for this full workflow.')
        count_match = re.search(r'\b(\d+|'+'|'.join(NUMBERS)+r')\s+(?:shorts|reels)\b', words, re.I)
        if not count_match:
            raise ValueError('Give the exact number of Shorts/Reels for this full workflow.')
        count = int(count_match[1]) if count_match[1].isdigit() else NUMBERS[count_match[1].lower()]
        if not 1 <= count <= 40:
            raise ValueError('Choose between 1 and 40 Shorts.')
        assistant._update(session_id, status='running', selected='publish', stage='Local model is planning the saved uploading stages.')
        with assistant.state.work_lock:
            spec, model = plan(assistant.root, text, str(videos[0]), str(images[0]) if images else '', folder, progress)
        expected = ['prepare_long', 'release_long', 'prepare_shorts', 'schedule_youtube_shorts', 'queue_instagram_reels']
        # Windows accepts repeated separators/case aliases. Canonicalize only
        # after proving this is the exact already-selected filesystem object.
        supplied=spec.get('video')
        if isinstance(supplied,str) and Path(supplied).is_file() and Path(supplied).samefile(videos[0]):
            spec['video']=str(videos[0])
        if (spec.get('profile') != 'cricket' or spec.get('video') != str(videos[0])
                or spec.get('thumbnail') != (str(images[0]) if images else '') or spec.get('count') != count
                or spec.get('steps') != expected or spec.get('shorts_release') != 'schedule'
                or spec.get('long_release') not in ('schedule', 'post_now')):
            raise ValueError('The local model plan did not preserve the requested source, count or steps. No upload was started.')
        # Immediate release requires explicit wording, not a model inference.
        first = re.split(r'\bthen\b|\bafter that\b', words, maxsplit=1, flags=re.I)[0]
        immediate = bool(re.search(r'\b(?:post|publish|upload)\b.{0,30}\bnow\b', first, re.I))
        if spec['long_release'] != ('post_now' if immediate else 'schedule'):
            raise ValueError('The local model changed the long video’s release choice. No upload was started.')
        write(folder/'validated-plan.json', {'model': model, 'plan': spec, 'owner_request': text, 'intervention': False})
        engine = service(assistant.state, recover_delivery=False)
        workflow = workflow_service(assistant.state, engine)
        from hinglish_publish.workflow_timing import parse_request
        timing=parse_request(text)
        reuse = re.search(r'\breuse\s+(?:the\s+)?long\s+upload\s+([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])', text, re.I)
        fresh = bool(re.search(r'\b(?:start fresh|fresh test|from scratch)\b', text, re.I))
        flow = workflow.create({**spec, 'delivery_timing':timing, 'fresh_start':fresh, 'reuse_long_video_id':reuse[1] if reuse else '', 'authorize': True, 'request_id': 'ask-full-'+session_id+'-'+message_id})
        flow['assistant_plan'] = {'session': session_id, 'message_id': message_id, 'receipt': str(folder/'validated-plan.json'), 'model': model, 'owner_port': assistant.state.port}
        flow['automatic_recovery'] = {'enabled': True, 'attempts': 0}
        workflow.save(flow)
        assistant._update(session_id, brain=model, upload_workflow={'id': flow['id'], 'profile': 'cricket', 'plan': spec, 'auto_resume': True})
        assistant._message(session_id, 'assistant', 'Starting the long YouTube release, then '+str(count)+' Shorts for YouTube and the Instagram buffer.')
        with workflow.lock:
            workflow.running.add(flow['id'])
        try:
            execute(assistant, session_id, workflow, flow, progress)
        finally:
            with workflow.lock:
                workflow.running.discard(flow['id'])
    except Exception as error:
        issue = failure(error, feature='Uploading workflow')
        if flow:
            saved = workflow.get(flow['id'], 'cricket')
            saved.update(status='failed', message=issue['error'])
            saved.setdefault('errors', {})[saved.get('current_step', 'workflow')] = issue
            workflow.save(saved)
        assistant._update(session_id, status='needs_review', stage=issue['error'])
        assistant._message(session_id, 'assistant', issue['error'], error=True, error_details=issue.get('error_details', ''))
    return True


def retry_unplanned(assistant,session_id):
    """Retry the same authorized message before any durable upload flow exists."""
    import threading,time
    with assistant.lock:
        saved=assistant._get(session_id)
        if saved.get('status')!='needs_review' or saved.get('upload_workflow'):
            raise ValueError('This control only retries an unplanned request. Use its existing workflow checkpoint once posting has started.')
        message_id=saved.get('active_request_message_id')
        message=next((m for m in saved['messages'] if m.get('id')==message_id and m.get('role')=='user'),None)
        if not message or not requested(message.get('text','')):
            raise ValueError('No original authorized full publishing request was found.')
        folder=Path(assistant.root)/'output/publisher-prepare-post/assistant-workflows'/session_id/message_id
        if (folder/'validated-plan.json').exists():
            raise ValueError('A validated plan already exists. Keep its saved posting receipts and resume that workflow.')
        retries=saved.setdefault('unplanned_retries',[])
        if len(retries)>=2:raise ValueError('The bounded planning retry limit was reached. Keep the saved failure for review.')
        retries.append({'time':time.time(),'message_id':message_id,'new_prompt':False})
        saved.update(status='running',stop=False,stage='Retrying the original saved model plan; no new prompt.')
        assistant._save(saved)
    def progress(text):assistant._update(session_id,stage=str(text))
    threading.Thread(target=followup,args=(assistant,session_id,message['text'],[],progress,message_id),daemon=True,name='retry-saved-upload-plan').start()
    return assistant.snapshot(session_id)


def resume_saved(assistant,session_id):
    """Resume the owned failed flow without inserting another user message."""
    import threading
    snapshot=assistant.snapshot(session_id)
    saved=snapshot.get('upload_workflow') or {}
    if not saved.get('id'):raise ValueError('This request has no saved workflow. Retry its original planning step instead.')
    if snapshot.get('stop'):raise ValueError('This workflow was stopped. It has not been automatically rearmed.')
    message_id=snapshot.get('active_request_message_id')
    if not any(m.get('id')==message_id and m.get('role')=='user' for m in snapshot.get('messages',[])):
        raise ValueError('The original publishing authorization is unavailable.')
    with assistant.lock:
        pending=getattr(assistant,'_saved_upload_resume_requests',None)
        if pending is None:pending=set();assistant._saved_upload_resume_requests=pending
        if session_id in pending:return assistant.snapshot(session_id)
        pending.add(session_id)
    def work():
        try:
            resume_request(assistant,session_id,'resume workflow',lambda text:assistant._progress(session_id,text),message_id)
        except Exception as error:
            from .user_messages import failure
            issue=failure(error,feature='Uploading workflow')
            assistant._update(session_id,status='needs_review',stage=issue['error'])
            assistant._message(session_id,'assistant',issue['error'],error=True,error_details=issue.get('error_details',''))
        finally:
            with assistant.lock:pending.discard(session_id)
    threading.Thread(target=work,daemon=True,name='resume-owned-upload-workflow').start()
    return assistant.snapshot(session_id)


def resume_request(assistant, session_id, text, progress, message_id):
    """An explicit chat continuation reuses the exact saved plan and receipts."""
    import time
    if not re.fullmatch(r'\s*(?:please\s+)?(?:resume|continue|retry)\s+(?:(?:the|this|my)\s+)?(?:saved\s+)?(?:RCB\s+)?(?:uploading\s+|publishing\s+)?workflow(?:[.!]|\s*;\s*I deleted the long video\. Keep it deleted\.)?\s*',text,re.I):return False
    snapshot=assistant.snapshot(session_id);saved=snapshot.get('upload_workflow') or {}
    if not saved.get('id'):return False
    from .prepare_post_http import service,workflow_service
    from .user_messages import failure
    workflow=workflow_service(assistant.state,service(assistant.state,recover_delivery=False))
    flow=workflow.get(saved['id'],saved['profile']);owner=flow.get('assistant_plan') or {}
    if owner.get('session')!=session_id or owner.get('owner_port')!=assistant.state.port:
        raise ValueError('Resume this workflow from its original Storylens chat and service.')
    if flow['status']=='complete':
        assistant._message(session_id,'assistant','This workflow is already complete. Its existing uploads and buffer have been kept.')
        assistant._update(session_id,status='idle',stage=flow['message'])
        return True
    if flow['status'] in ('cancelled','stopped'):
        raise ValueError('This workflow was cancelled. Its saved posts were not rearmed.')
    if re.search(r'\bI deleted the long video\b',text,re.I):
        from hinglish_publish.prepare_post_workflow import completed_long_checkpoint
        if not completed_long_checkpoint(workflow.engine.publisher,flow):
            raise ValueError('The earlier Long step has no verified checkpoint. No replacement upload was started.')
        flow['owner_long_deleted']={'message_id':message_id,'time':time.time(),'source':'explicit_owner_confirmation'}
    with workflow.lock:
        if flow['id'] in workflow.running:return True
        workflow.running.add(flow['id'])
        owner.setdefault('original_message_id',owner.get('message_id'))
        owner['message_id']=message_id
        flow.setdefault('resumptions',[]).append({'message_id':message_id,'request':text,'time':time.time()})
        recovery=flow.setdefault('automatic_recovery',{})
        recovery.update(enabled=True,exhausted=False)
        # A new explicit owner continuation grants a fresh bounded retry budget;
        # the old failures remain in history and completed stages stay saved.
        recovery['step_attempts']={step:0 for step in set(recovery.get('step_attempts',{}))|
            {h['step'] for h in recovery.get('history',[]) if h.get('step')}|{flow.get('current_step','workflow')}}
        workflow.save(flow)
        assistant._update(session_id,status='running',stop=False,upload_workflow={**saved,'auto_resume':True},
                          stage='Continuing the unfinished saved stage; existing clips and uploads are reused.')
    try:
        execute(assistant,session_id,workflow,flow,progress)
    except Exception as error:
        issue=failure(error,feature='Uploading workflow');value=workflow.get(flow['id'],flow['profile'])
        value.update(status='failed',message=issue['error']);value.setdefault('errors',{})[value.get('current_step','workflow')]=issue
        workflow.save(value)
        assistant._update(session_id,status='needs_review',stage=issue['error'])
        assistant._message(session_id,'assistant',issue['error'],error=True,error_details=issue.get('error_details',''))
    finally:
        with workflow.lock:workflow.running.discard(flow['id'])
    return True


def execute(assistant, session_id, workflow, flow, progress):
    """Continue saved stages without rebuilding a model conversation or plan."""
    def checkpoint(message):
        if assistant._stopped(session_id):
            raise ValueError('Stopped. Completed stages and uploaded videos are saved.')
        progress(message)
    workflow.supervise(flow['id'], flow['profile'], checkpoint, should_stop=lambda: assistant._stopped(session_id))
    final = workflow.get(flow['id'], flow['profile'])
    saved = dict(assistant.snapshot(session_id)['upload_workflow'])
    saved.update(status=final['status'], auto_resume=False)
    assistant._update(session_id, status='idle', stage=final['message'], upload_workflow=saved)
    count = final['intent']['count']
    from hinglish_publish.prepare_post_workflow import completed_long_cancelled
    long_message = ('You deleted the earlier long video; it was not uploaded again. ' if final.get('owner_long_deleted') else
                    'The long schedule was cancelled and has been left cancelled. '
                    if completed_long_cancelled(workflow.engine.publisher,final) else
                    'Earlier long-video step reused from its verified checkpoint. ' if final.get('steps',{}).get('long_checkpoint_reused') else 'Long YouTube release verified. ')
    assistant._message(session_id, 'assistant', long_message+str(count)+' YouTube Shorts verified. '+str(count)+' Instagram Reels are queued locally; publication is verified at release time.')


def resume_tick(assistant, session_id, snapshot):
    """App-owned recovery of this exact authorized request, including after restart."""
    import threading
    saved = snapshot.get('upload_workflow') or {}
    if saved.get('status')=='complete' and not saved.get('auto_resume'):
        restore_buffer(assistant, session_id, saved)
        return False
    if (not saved.get('auto_resume') or snapshot.get('stop')
            or snapshot.get('status') in ('planning', 'running', 'transcribing')):
        return False
    from .prepare_post_http import service, workflow_service
    workflow = workflow_service(assistant.state, service(assistant.state, recover_delivery=False))
    with assistant.lock, workflow.lock:
        current = assistant.snapshot(session_id)
        if (current.get('stop') or current.get('upload_workflow') != saved
                or current.get('status') in ('planning', 'running', 'transcribing')
                or saved['id'] in workflow.running):
            return False
        flow = workflow.get(saved['id'], saved['profile'])
        owner = flow.get('assistant_plan') or {}
        recovery = flow.get('automatic_recovery') or {}
        if (owner.get('session') != session_id or owner.get('owner_port') != assistant.state.port
                or owner.get('message_id') != current.get('active_request_message_id')
                or not recovery.get('enabled') or recovery.get('exhausted')
                or flow['status'] in ('complete', 'cancelled', 'stopped', 'awaiting_instagram_cleanup')):
            return False
        workflow.running.add(flow['id'])
        assistant._update(session_id, status='running', stage='Continuing the saved uploading workflow; completed uploads are reused.')

    def work():
        try:
            execute(assistant, session_id, workflow, flow, lambda m: assistant._progress(session_id, m))
        except Exception as error:
            from .user_messages import failure
            issue = failure(error, feature='Uploading workflow')
            value = workflow.get(flow['id'], flow['profile'])
            value.update(status='failed', message=issue['error'])
            value.setdefault('errors', {})[value.get('current_step', 'workflow')] = issue
            workflow.save(value)
            assistant._update(session_id, status='needs_review', stage=issue['error'])
            assistant._message(session_id, 'assistant', issue['error'], error=True, error_details=issue.get('error_details', ''))
        finally:
            with workflow.lock:
                workflow.running.discard(flow['id'])
    threading.Thread(target=work, name='storylens-upload-workflow-resume', daemon=True).start()
    return True


def restore_buffer(assistant, session_id, saved):
    """Restart the authorized local buffer worker after app restart, without re-preparing."""
    from .prepare_post_http import service, workflow_service
    engine=service(assistant.state,recover_delivery=False)
    flow=workflow_service(assistant.state,engine).get(saved['id'],saved['profile'])
    owner=flow.get('assistant_plan') or {}
    if (flow['status']!='complete' or owner.get('session')!=session_id
            or owner.get('owner_port')!=assistant.state.port):return False
    for key in flow.get('jobs',{}).get('instagram',[]):
        job=engine.publisher.store.get(key)
        if (job['status']=='ready' and job.get('authorized_at')
                and job.get('profile')==flow['profile']
                and job.get('account_id')==flow['intent']['accounts']['instagram']
                and job.get('prepare_post_id')==flow['preparations']['shorts']):
            engine.start_delivery()
            return True
    return False
