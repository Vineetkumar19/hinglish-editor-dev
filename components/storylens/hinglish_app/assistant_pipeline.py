"""Supervise new chat-owned workflows using durable tool receipts.

Only workflows created by begin() participate. Legacy reviews never become
authorized merely by upgrading/restarting Storylens.
"""
import copy
import re
import threading
import time


def begin(assistant, session_id, text, steps, sources):
    from .assistant_edit_workflow import requested
    if not steps or steps[-1]['tool'] != 'distribute':
        return
    # Tool plans cannot confer permission: require the user's execution command.
    auto = requested(text) and not re.search(
        r'\b(?:draft|preview|review first|ask me first|do not publish|don.t publish)\b', text, re.I)
    previous=assistant.snapshot(session_id)
    reviews=list(previous.get('publishing_review_history',[]))
    if previous.get('publishing_review'):
        reviews.append(previous['publishing_review'])
    assistant._update(session_id, publishing_review=None, publishing_review_history=reviews[-10:],
        campaign=None, shorts_paths=[], edit_publish_checkpoint=None, pipeline={
        'version': 1, 'request': text, 'sources': list(sources), 'steps': copy.deepcopy(steps),
        'request_message_id':previous.get('active_request_message_id'),
        'automatic': bool(auto), 'phase': 'editing', 'attempts': 0,
        'next_retry': 0, 'authorized_review': '', 'created': time.time()})


def change(assistant, session_id, **values):
    with assistant.lock:
        pipeline = assistant._get(session_id).get('pipeline')
        if pipeline:
            pipeline.update(values)
            assistant._update(session_id, pipeline=pipeline)


def resume_saved(assistant,session_id,text,snapshot):
    """Resume this chat's authorized receipt, without selecting a batch again."""
    if not re.match(r'^\s*(?:please\s+)?(?:resume|retry|continue|finish|complete)\b',text,re.I):return False
    if re.search(r'\b(?:cancel|stop|different|instead)\b',text,re.I):return False
    review=snapshot.get('publishing_review') or {};pipeline=snapshot.get('pipeline') or {}
    if (review.get('id')!=pipeline.get('authorized_review') or not review.get('declarations_confirmed')
        or not review.get('retryable')):return False
    from .assistant_publishing_context import schedule_literals
    explicit=schedule_literals(text)
    from datetime import datetime
    for row in review.get('rows',[]):
        due=datetime.fromisoformat(row['publish_at']) if row.get('publish_at') else None
        if due and (explicit.get('first_date') and due.date().isoformat()!=explicit['first_date'] or
                    explicit.get('clock') and due.strftime('%H:%M')!=explicit['clock']):return False
    if re.search(r'\bno new\b[^.!?]*\bupload',text,re.I) and review.get('uploaded_count',0)<len(review.get('ids',[])):
        return False
    incomplete=any(not (r.get('private_verified') or r.get('publication_verified') or r.get('schedule_verified')) if review.get('schedule') else not r.get('url') for r in review.get('rows',[]))
    incomplete=incomplete or any(r.get('status')!='published' for r in review.get('instagram_rows',[]))
    if not incomplete:return False
    # Stop applies to that browser attempt. A new explicit resume authorizes
    # a fresh pre-submission attempt, not a new upload or replay of Schedule.
    for row in review.get('rows',[]):
        if not row.get('id'):continue
        job=assistant.state.publisher.store.get(row['id'])
        if job.get('browser_schedule_id'):
            assistant.state.local_browser.retire_stopped_youtube(job['browser_schedule_id'],session_id)
    review['state']='needs_review'
    assistant._update(session_id,publishing_review=review)
    assistant._message(session_id,'assistant','Resuming the unfinished steps. Completed uploads and posts will be reused.')
    if not assistant.state.local_browser.snapshot().get('connected'):
        change(assistant,session_id,phase='waiting_executor')
        assistant._update(session_id,status='needs_review',stage='Waiting for Chrome to reconnect; the saved workflow will resume automatically.')
        return True
    from .assistant_publish import start
    start(assistant,{'session':session_id,'review':review['id'],
        'made_for_kids':review['made_for_kids'],'synthetic_media':review['synthetic_media']},internal=True)
    return True


def checkpoint(assistant, session_id):
    """Finished media is the boundary from which preparation can safely resume."""
    snapshot = assistant.snapshot(session_id)
    pipeline = snapshot.get('pipeline')
    if not pipeline:
        return
    assistant._update(session_id, edit_publish_checkpoint={
        'steps': pipeline['steps'], 'result': snapshot.get('last_result'),
        'profile': snapshot.get('profile')})
    change(assistant, session_id, phase='preparing')


def prepared(assistant, session_id, review):
    snapshot = assistant.snapshot(session_id)
    pipeline = snapshot.get('pipeline')
    if not pipeline:
        return
    change(assistant, session_id, phase='review', review_id=review['id'])
    if not pipeline.get('automatic') or assistant._stopped(session_id):
        return
    from .assistant_publish import confirmation, start
    # Never infer children's-content/synthetic-media declarations from the topic
    # or from another batch. They can be supplied in the original prompt.
    payload = confirmation(pipeline['request'], review, assistant.root, execution=True)
    if not review['ids']:
        payload = {'review': review['id'], 'made_for_kids': False, 'synthetic_media': False}
    if payload:
        review.update(made_for_kids=payload['made_for_kids'],synthetic_media=payload['synthetic_media'],
                      declarations_confirmed=True)
        assistant._update(session_id,publishing_review=review)
        change(assistant,session_id,phase='waiting_executor',authorized_review=review['id'])
        if not assistant.state.local_browser.snapshot().get('connected'):
            assistant._update(session_id,status='needs_review',stage='Waiting for Chrome to reconnect; this workflow is saved.')
            assistant._message(session_id,'assistant',
                'Your publishing request is saved. I will continue when Chrome and Storylens Local Publisher '
                'reconnect; you do not need to repeat the request. The original release times are retained.')
            return
        start(assistant, {'session': session_id, **payload}, internal=True)
    else:
        assistant._message(session_id, 'assistant',
            'The clips, descriptions and daily slots are ready. For this batch, tell me whether it is '
            'made for kids and whether it contains realistic synthetic media. You can give these '
            'two declarations in your original request next time. After approval I will continue '
            'the saved workflow; Instagram needs no daily reminder.', question=True)


def authorized(assistant, session_id, review):
    snapshot = assistant._get(session_id)
    pipeline = snapshot.get('pipeline') or {}
    if pipeline.get('review_id') != review['id']:
        return
    change(assistant, session_id, phase='publishing', authorized_review=review['id'],
           request_message_id=snapshot.get('active_request_message_id'),next_retry=0)


def failed(assistant, session_id, error):
    """Bounded automatic recovery; unknown remote outcomes remain paused."""
    snapshot = assistant.snapshot(session_id)
    from .assistant_request_status import pipeline_is_current
    if not pipeline_is_current(snapshot):return
    pipeline = snapshot.get('pipeline') or {}
    if not pipeline.get('automatic') or snapshot.get('stop'):
        return
    review = snapshot.get('publishing_review') or {}
    if review and (pipeline.get('authorized_review') != review.get('id') or not review.get('retryable')):
        return
    message = str(error)
    transient = isinstance(error, (TimeoutError, ConnectionError, PermissionError)) or bool(re.search(
        r'timed out|timeout|temporarily unavailable|connection (?:refused|reset|aborted)|'
        r'Chrome has not completed|Studio submission is not confirmed|'
        r'Studio did not finish loading|HTTP (?:429|502|503|504)\b', message, re.I))
    attempt = pipeline.get('attempts', 0)
    if not transient or attempt >= 3:
        change(assistant, session_id, phase='attention', last_error=message[:500], next_retry=0)
        return
    if not review and not snapshot.get('shorts_paths'):
        return  # Never launch another render when the renderer's outcome is unknown.
    delay = (30, 120, 300)[attempt]
    change(assistant, session_id, phase='waiting_retry', attempts=attempt + 1,
           last_error=message[:500], next_retry=time.time() + delay)
    assistant._message(session_id, 'assistant',
        f'A temporary failure interrupted this workflow. I saved its progress and will check again '
        f'in {delay} seconds. Finished exports and upload receipts will be reused.')


def tick(assistant, session_id):
    """One supervisor tick; claim under the chat lock before starting any worker."""
    from .assistant import ACTIVE
    with assistant.lock:
        snapshot = assistant.snapshot(session_id)
        from .assistant_request_status import pipeline_is_current
        if not pipeline_is_current(snapshot):return False
        pipeline = snapshot.get('pipeline') or {}
        if not pipeline.get('automatic') or snapshot.get('stop') or snapshot['status'] in ACTIVE:
            return False
        if pipeline.get('phase') in ('waiting_instagram','attention'):
            review = snapshot.get('publishing_review') or {}
            if review.get('id') != pipeline.get('authorized_review'):
                return False
            rows = review.get('instagram_rows', [])
            # Only retry failures proven to precede Share. Neither an uncertain
            # submission nor a login/identity failure can be replayed here.
            retries=dict(pipeline.get('instagram_retries',{}))
            browser=assistant.state.local_browser
            version=browser.snapshot().get('extension_version','')
            def version_at_least(required):
                try:return tuple(map(int,version.split('.')))>=required
                except (TypeError,ValueError):return False
            for row in rows:
                if row.get('status')!='needs_review' or not row.get('browser_job_id'):continue
                job=browser.get(row['browser_job_id']);message=job.get('message','')
                attempt=retries.get(job['id'],0)
                if (review.get('account_switch_retry') and attempt<3 and job.get('preflight_id')
                    and job.get('submission_started') is False and not job.get('stop')
                    and message.startswith('The scheduled account readiness check failed. ')):
                    check=browser.get(job['preflight_id'])
                    if (check.get('message') in (
                        'Instagram did not confirm the alternate account; no upload was started.',
                        'Instagram could not confirm the requested account after switching. No post was shared.')
                        and time.time()>=check.get('finished',time.time())+(5,20,60)[attempt]):
                        browser.retry_account_readiness(job['id'])
                        retries[job['id']]=attempt+1
                        change(assistant,session_id,phase='waiting_instagram',instagram_retries=retries)
                        assistant._update(session_id,status='complete',stage='Rechecking the Instagram account before uploading the saved Reel.')
                        assistant._message(session_id,'assistant','The account switch took too long. Rechecking the same account before uploading; no post was submitted.')
                        return False
                transient=bool(re.search(r'receiving end does not exist|message port closed|frame was removed|'
                    r'Cannot access contents of the page|'
                    r'did not load the selected video|has not finished decoding|has not finished loading|'
                    r'Keep one Instagram working tab|Instagram has not opened the destination profile|'
                    r'storylens-safe-retry:empty-composer',message,re.I))
                # A slow account-switch navigation may finish after the
                # executor's bounded identity wait. A new reviewed workflow
                # can recheck from that actual account, before any media or
                # Share. Each attempt still verifies the exact destination.
                if review.get('account_switch_retry') and message in (
                    'Instagram did not confirm the alternate account; no upload was started.',
                    'Instagram could not confirm the requested account after switching. No post was shared.'):
                    transient=True
                if 'Keep one Instagram working tab' in message and not version_at_least((0,4,13)):continue
                if 'Instagram has not opened the destination profile' in message and not version_at_least((0,4,15)):continue
                attempt=retries.get(job['id'],0)
                if (transient and attempt<3 and job.get('submission_started') is False and not job.get('stop')
                    and job.get('last_phase') in ('queued','running')
                    and time.time()>=job.get('finished',time.time())+(5,20,60)[attempt]
                    and browser.snapshot().get('connected')):
                    from hinglish_publish.features import instagram_text_mode
                    title=(row.get('metadata') or {}).get('title','')
                    if instagram_text_mode(assistant.root,pipeline.get('request',''))=='title' and title and job.get('caption')!=title:
                        # Reapply the creator's original title-only instruction.
                        # The queue preserves the same media/job identity and
                        # refuses metadata changes after the Share boundary.
                        browser.enqueue('reel',job['account'],row['video'],title,session_id,authorized=True,
                                        publish_at=row.get('publish_at',''),reference=row['id'])
                        row['caption']=title
                        row['metadata']={**row['metadata'],'instagram_caption':title}
                        assistant._update(session_id,publishing_review=review)
                    else:browser.retry_before_share(job['id'])
                    retries[job['id']]=attempt+1
                    change(assistant,session_id,phase='waiting_instagram',instagram_retries=retries)
                    assistant._update(session_id,status='complete',stage='Resuming the saved Instagram upload automatically.')
                    assistant._message(session_id,'assistant',
                        'Retrying the saved Instagram upload after a temporary browser failure. '
                        'Share had not started; the same video and destination are being reused.')
                    return False
            if rows and all(row.get('status') == 'published' for row in rows):
                if review.get('schedule') and not review.get('youtube_check_only') and any(
                    not (row.get('private_verified') or row.get('publication_verified') or row.get('schedule_verified')) for row in review.get('rows',[])):
                    if pipeline.get('phase')!='attention':
                        change(assistant,session_id,phase='attention')
                        assistant._update(session_id,status='needs_review',stage='Instagram posted. YouTube scheduling is unfinished; resume the saved workflow.')
                    return False
                from .user_messages import publication_result
                from .pipeline_ledger import outcome
                settled=outcome(review,snapshot.get('pipeline_audit'))
                change(assistant, session_id, phase='complete' if settled['complete'] else 'waiting_release')
                assistant._update(session_id,status='complete',publishing_review=review,stage='Instagram publication receipts verified.')
                assistant._message(session_id, 'assistant',
                    publication_result(review))
            elif any(row.get('status') in ('needs_review','blocked','cancelled') for row in rows):
                parents={row.get('browser_job_id') for row in rows}
                if any(j.get('action')=='verify_reel' and j.get('verification_parent') in parents
                       and j.get('status') in ('queued','running')
                       for j in assistant.state.local_browser.snapshot()['jobs']):
                    return False
                if pipeline.get('phase')=='attention':return False
                change(assistant, session_id, phase='attention')
                assistant._update(session_id,status='needs_review',stage='Instagram task needs attention; check its saved receipt.')
                assistant._message(session_id, 'assistant',
                    'Instagram posting stopped: '+next((r.get('message') or 'The upload needs checking.'
                        for r in rows if r.get('status') in ('needs_review','blocked','cancelled')),'The upload needs checking.'),
                    publishing_review=review, error=True)
            return False
        interrupted = snapshot['status'] == 'interrupted'
        if not interrupted and pipeline.get('phase')!='waiting_executor' and (pipeline.get('phase') != 'waiting_retry'
                                or pipeline.get('next_retry', 0) > time.time()):
            return False
        review = snapshot.get('publishing_review') or {}
        if review:
            if (pipeline.get('authorized_review') != review.get('id')
                    or not review.get('declarations_confirmed') or not review.get('retryable')):
                return False
            # On process restart the old thread cannot own "uploading/scheduling".
            # Recover only rows whose saved upload outcomes permit safe reuse.
            if review['state'] in ('uploading', 'scheduling'):
                review['state'] = 'needs_review'
                assistant._update(session_id, publishing_review=review)
            if review['state'] not in ('review','needs_review'):
                return False
            # Wait for the executor, rather than spending retries while offline.
            if not assistant.state.local_browser.snapshot().get('connected'):
                return False
            assistant._update(session_id, status='running', stage='Recovering the saved publishing workflow')
            mode = 'publish'
        else:
            if pipeline.get('phase') not in ('preparing', 'waiting_retry') or not snapshot.get('shorts_paths'):
                return False
            assistant._update(session_id, status='running', stage='Resuming saved caption and description preparation')
            mode = 'prepare'
        change(assistant, session_id, next_retry=0, phase='publishing' if review else 'preparing')

    def work():
        try:
            if mode == 'publish':
                from .assistant_publish import start
                start(assistant, {'session': session_id, 'review': review['id'],
                    'made_for_kids': review['made_for_kids'],
                    'synthetic_media': review['synthetic_media']}, internal=True)
            else:
                from .assistant_distribution import from_outputs
                from_outputs(assistant, session_id, pipeline['steps'][-1]['options'],
                             pipeline['request'], lambda m: assistant._progress(session_id, m))
        except Exception as error:
            with assistant.lock:
                from .user_messages import problem
                issue=problem(error)
                assistant._update(session_id,status='needs_review',stage=issue['message'],error_details=issue['details'],error_code=issue['code'])
                failed(assistant, session_id, error)
    threading.Thread(target=work, name='storylens-workflow-resume', daemon=True).start()
    return True


def supervise(assistant, stop):
    """Started by the app, not Codex; only new explicitly owned workflows qualify."""
    while not stop.wait(5):
        from .assistant_upload_workflow import recover_delivery
        recover_delivery(assistant)
        for path in assistant.folder.glob('*.json'):
            if not re.fullmatch(r'[a-f0-9]{16}', path.stem):
                continue
            try:
                tick(assistant, path.stem)
                snapshot=assistant.snapshot(path.stem)
                from .assistant_upload_workflow import resume_tick
                resume_tick(assistant, path.stem, snapshot)
                if snapshot.get('status') not in ('planning','running','transcribing') and (snapshot.get('pipeline') or {}).get('phase') in ('waiting_instagram','waiting_release'):
                    from .pipeline_audit import reconcile_due
                    reconcile_due(assistant,path.stem,snapshot)
            except Exception:
                # One unreadable chat cannot prevent other independent queues.
                import logging
                logging.getLogger(__name__).exception('Workflow recovery failed for %s', path.stem)
