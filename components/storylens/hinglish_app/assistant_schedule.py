"""Upload-receipt-bound Studio scheduling. No uploads are selected from browser history."""
from datetime import datetime,timezone
import time


class UnavailableUploadError(ValueError):
    """A saved receipt does not establish that its remote video still exists."""


def continue_uploaded(assistant,session_id,text):
    """An explicit new scheduling command can reuse prior upload declarations.

    No new uploads, inferred declarations, platform changes, or draft-only
    requests qualify. The normal publisher still validates accounts and dates.
    """
    import re
    from .assistant_publishing_context import intent_text
    command=intent_text(text)
    if not re.search(r'\bschedul\w*\b',command,re.I) or re.search(
            r'\b(how|why|explain|cancel|never|do not|don.t|preview|draft|review only|without)\b',command,re.I):return False
    session=assistant.snapshot(session_id);review=session.get('publishing_review') or {}
    if not review.get('schedule') or review.get('state')!='review' or review.get('instagram_rows') or not review.get('ids'):return False
    jobs=[assistant.state.publisher.store.get(key) for key in review['ids']]
    if any(j['platform']!='youtube' or j['status'] not in ('uploaded_private','scheduled') or
           not j.get('remote',{}).get('id') or not j.get('authorized_at') or
           type(j.get('made_for_kids')) is not bool or type(j.get('synthetic_media')) is not bool for j in jobs):return False
    declarations={(j['made_for_kids'],j['synthetic_media']) for j in jobs}
    if len(declarations)!=1:return False
    kids,synthetic=declarations.pop()
    review.update(authorization_source='explicit_current_chat_schedule',authorization_text=command)
    assistant._update(session_id,publishing_review=review)
    assistant._message(session_id,'assistant',f'Applying your requested schedule to {len(jobs)} existing YouTube uploads. '
        'Your saved audience and synthetic-media declarations will be reused. Completion will be reported only after YouTube confirms each release time.')
    from .assistant_publish import start
    start(assistant,{'session':session_id,'review':review['id'],
                     'made_for_kids':kids,'synthetic_media':synthetic},internal=True)
    return True


def ready(assistant,review):
    if any(r.get('immediate') for r in review.get('rows',[])) and not assistant.state.local_browser.snapshot().get('youtube_publishing'):
        raise ValueError('Reload Storylens Local Publisher 0.4.32 and click Check now to enable immediate YouTube publication. The finished video is saved; nothing has uploaded.')
    if review.get('schedule') and review['ids'] and assistant.state.local_browser.snapshot().get('extension_version') in ('0.4.0','0.4.1','0.4.2','0.4.3','0.4.4','0.4.5','0.4.6'):
        raise ValueError('Reload Storylens Local Publisher to version 0.4.7, then click Check now. '
                         'This fixes the current Studio controls. Existing uploads are kept.')
    if review.get('schedule') and review['ids'] and not assistant.state.local_browser.snapshot().get('youtube_scheduling'):
        raise ValueError('Enable YouTube Studio in Storylens Local Publisher 0.4.0, then click Upload and schedule. '
                         'No upload was started. The reviewed exports and dates are saved.')
    if review.get('instagram_rows') and not assistant.state.local_browser.snapshot()['connected']:
        raise ValueError('Connect the local Chrome extension before arming Instagram slots. Nothing was queued.')
    for row in [*review['rows'],*review.get('instagram_rows',[])]:
        if row.get('private_only'):continue
        if row.get('browser_job_id'):continue
        if row.get('immediate') and not row.get('publish_at'):continue
        if review.get('schedule'):
            due=datetime.fromisoformat(row['publish_at'])
            lead=5 if row in review.get('instagram_rows',[]) else 60
            if due.tzinfo is None or due.timestamp()<=time.time()+lead:
                raise ValueError('A release time has passed. Choose new future dates before uploading.')


def verify(root,job,publish_at,allow_reschedule=False,private_only=False):
    """Read back exact channel, copy and instant; a browser click alone is not success."""
    from hinglish_publish.providers import youtube_client
    client,account=youtube_client(root,job['profile'])
    if account['channel_id']!=job['account_id']:
        raise ValueError('The reviewed YouTube channel changed.')
    data=client.videos().list(part='snippet,status',id=job['remote']['id']).execute().get('items',[])
    if len(data)!=1:raise UnavailableUploadError('YouTube cannot find the saved video '+job['remote']['id']+' on the reviewed channel. Its receipt is retained, but the video cannot be scheduled or assumed to exist.')
    item=data[0]
    if item['id']!=job['remote']['id'] or item['snippet']['channelId']!=job['account_id']:
        raise ValueError('YouTube returned a different video or channel.')
    if any(item['snippet'].get(k)!=job['metadata'][k] for k in ('title','description')):
        raise ValueError('The uploaded title or description does not match the reviewed copy.')
    status=item['status']
    if status.get('uploadStatus') in ('failed','rejected','deleted'):
        raise ValueError('YouTube rejected the uploaded video.')
    actual=status.get('publishAt')
    if private_only:
        if status.get('privacyStatus')!='private' or actual:
            raise ValueError('The full video must remain private with no scheduled release. Its existing visibility was not changed.')
        if status.get('uploadStatus')=='processed':
            return {**job['remote'],'privacy':'private','publish_at':'','private_verified_at':time.time()}
        return None
    if not publish_at:
        if status.get('privacyStatus')=='public' and status.get('uploadStatus')=='processed':
            return {**job['remote'],'privacy':'public','publish_at':'','publication_verified_at':time.time()}
        return None
    if status.get('privacyStatus')!='private' or not actual:
        return None
    expected=datetime.fromisoformat(publish_at.replace('Z','+00:00'))
    if datetime.fromisoformat(actual.replace('Z','+00:00'))!=expected:
        if allow_reschedule:return None
        raise ValueError('YouTube reports a different release time; no retry was sent.')
    return {**job['remote'],'privacy':'private','publish_at':actual,'schedule_verified_at':time.time()}


def run(assistant,session_id,review):
    publisher=assistant.state.publisher
    review['state']='scheduling'
    assistant._update(session_id,publishing_review=review,status='running',stage='Uploads complete; scheduling their new YouTube IDs in Chrome.')
    results=[];failures=[]
    # Validate the whole batch's identities before touching any remote schedule.
    for row in review['rows']:
        job=publisher.store.get(row['id'])
        if job.get('campaign')!=row.get('campaign',review['campaign']) or job['platform']!='youtube' or not job.get('remote',{}).get('id'):
            raise ValueError('Scheduling requires this campaign export’s private upload receipt.')
        if job['account_id']!=review['accounts'][job['profile']]['id']:
            raise ValueError('The uploaded video belongs to a different channel.')
    for row in review['rows']:
        if assistant._stopped(session_id):raise ValueError('Stopped; finished uploads and schedules are kept.')
        job=publisher.store.get(row['id'])
        try:
            remote=schedule_one(assistant,session_id,review,row,job)
        except (ValueError,RuntimeError,ConnectionError,TimeoutError) as error:
            if assistant._stopped(session_id):raise
            failures.append((row['id'],error))
            review['schedule_errors']=[{'id':key,'message':str(e)[:500]} for key,e in failures]
            assistant._update(session_id,publishing_review=review)
            if any(j['status'] in ('running','sharing') for j in assistant.state.local_browser.snapshot()['jobs']):
                break  # A live/uncertain browser action still owns the executor.
            # Each reviewed video is independent. A terminal failure for one
            # must not silently prevent trying the remaining authorized IDs.
            continue
        publisher.store.change(job['id'],status='uploaded_private' if row.get('private_only') else 'published' if row.get('immediate') else 'scheduled',remote=remote,
                               due=time.time() if row.get('immediate') or row.get('private_only') else datetime.fromisoformat(row['publish_at']).timestamp())
        results.append({'channel':row['channel'],'kind':row['kind']+' · '+row['publish_at'],'title':job['metadata']['title'],
                        'url':remote['url'],'visibility':'private' if row.get('private_only') else 'public' if row.get('immediate') else 'scheduled'})
        review['schedule_results']=list(results)
        assistant._update(session_id,publishing_review=review)
    if failures:
        raise failures[0][1]
    review['schedule_errors']=[]
    review['state']='complete'
    from .assistant_pipeline import change
    change(assistant,session_id,phase='waiting_instagram' if review.get('instagram_rows') else 'waiting_release',next_retry=0)
    with assistant.lock:
        published=sum(r['visibility']=='public' for r in results)
        private=sum(r['visibility']=='private' for r in results)
        scheduled=sum(r['visibility']=='scheduled' for r in results)
        assistant._message(session_id,'assistant',f'YouTube verified: {private} private, {published} public, {scheduled} scheduled.'+
            (' Instagram slots remain in the local Chrome queue; their individual receipts appear in the review.' if review.get('instagram_rows') else ''),publish_results=results)
        assistant._update(session_id,publishing_review=review,status='complete',stage='All uploads and exact YouTube release dates verified.')


def schedule_one(assistant,session_id,review,row,job):
    if row.get('private_only'):
        for _ in range(600):
            if assistant._stopped(session_id):raise ValueError('Stopped; the private upload is saved.')
            remote=verify(assistant.root,job,'',private_only=True)
            if remote:return remote
            assistant._progress(session_id,'YouTube is processing the private full video; keeping it private.')
            time.sleep(2)
        raise ValueError('YouTube is still processing the private full video. Resume will verify the saved upload without uploading again.')
    readback=lambda: verify(assistant.root,job,row['publish_at'],True) if review.get('allow_reschedule') else verify(assistant.root,job,row['publish_at'])
    remote=readback()
    if remote:return remote
    options={'allow_reschedule':True} if review.get('allow_reschedule') is True else {}
    task=assistant.state.local_browser.enqueue_youtube(job['account_id'],job['remote']['id'],
        row['publish_at'],session_id,authorized=True,channel_name=review['accounts'][job['profile']]['name'],switch_via=row.get('switch_via'),video_kind=job['kind'],publish_now=bool(row.get('immediate')),**options)
    assistant.state.publisher.store.change(job['id'],browser_schedule_id=task['id'])
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        state=assistant.state.local_browser.get(task['id'])
        assistant._progress(session_id,'Scheduling '+row['metadata']['title']+': '+state['message'])
        if assistant._stopped(session_id):
            assistant.state.local_browser.cancel(task['id'])
            raise ValueError('Stopped; check the saved schedule receipts before retrying.')
        if state['status'] in ('needs_review','blocked','cancelled'):raise ValueError(state['message'])
        if state['status']=='submitted':break
        time.sleep(1)
    else:raise ValueError('Chrome has not completed this schedule. Saved uploads will not be repeated.')
    for _ in range(120 if row.get('immediate') else 20):
        remote=readback()
        if remote:return remote
        time.sleep(1)
    raise ValueError('Studio submission is not confirmed by YouTube. No second submission was sent.')
