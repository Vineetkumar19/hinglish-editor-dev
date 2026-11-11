"""Storylens-owned read-only reconciliation of one chat's actual pipeline."""
from datetime import datetime
from pathlib import Path
import re
import time

from .pipeline_ledger import Ledger,intent,canonical,outcome
from .assistant_upload_recovery import same_instant


def requested(text):
    return bool(re.match(r'^\s*(?:please\s+)?(?:check|verify|audit|inspect)\b',text,re.I)
        and re.search(r'\b(?:pipeline|workflow|whole batch|all deliveries)\b',text,re.I)
        and not re.search(r'\b(?:then|and)\s+(?:upload|post|publish|reschedule|extract)\b',text,re.I))


def media(path):
    """Objective container and sampled-decode checks, not a narrative quality claim."""
    import av
    with av.open(str(path)) as container:
        if len(container.streams.video)!=1 or not container.streams.audio:
            raise ValueError('The video needs a readable picture and audio stream.')
        stream=container.streams.video[0]
        duration=float(container.duration or 0)/av.time_base
        if duration<=0:raise ValueError('The video duration is unavailable.')
        result={'duration':round(duration,3),'width':stream.width,'height':stream.height,
                'video_codec':stream.codec_context.name,'audio_codec':container.streams.audio[0].codec_context.name}
        for second in (0,duration/2,max(0,duration-1)):
            container.seek(int(second*av.time_base))
            if next(container.decode(video=0),None) is None:raise ValueError('A sampled video frame could not be decoded.')
    with av.open(str(path)) as container:
        if next(container.decode(audio=0),None) is None:raise ValueError('The audio stream could not be decoded.')
    return result


def youtube(assistant,job,row,clients):
    from hinglish_publish.providers import youtube_client
    profile=job['profile']
    if profile not in clients:clients[profile]=youtube_client(assistant.root,profile)
    client,account=clients[profile]
    if account['channel_id']!=job['account_id']:raise ValueError('The connected YouTube channel differs from this saved upload.')
    remote=job.get('remote') or {}
    if not remote.get('id'):return {'state':'pending','detail':'No upload receipt yet.'}
    items=client.videos().list(part='snippet,status,processingDetails',id=remote['id']).execute().get('items',[])
    if len(items)!=1:raise ValueError('YouTube cannot find the saved video. Its receipt is retained; no replacement upload was sent.')
    item=items[0];snippet=item['snippet'];status=item['status']
    if item['id']!=remote['id'] or snippet['channelId']!=job['account_id']:raise ValueError('The returned video belongs to a different channel.')
    if any(snippet.get(k)!=job['metadata'].get(k) for k in ('title','description')):raise ValueError('The current YouTube title or description differs from the reviewed copy.')
    if status.get('uploadStatus') in ('failed','rejected','deleted'):raise ValueError('YouTube rejected or removed this upload.')
    privacy=status.get('privacyStatus');actual=status.get('publishAt','')
    proof={'external_id':remote['id'],'url':remote['url'],'account':snippet['channelId'],
           'observed_at':time.time(),'actual_publish_at':actual,'privacy':privacy,
           'processing':item.get('processingDetails',{}).get('processingStatus',status.get('uploadStatus',''))}
    if row.get('private_only'):
        if privacy!='private' or actual:raise ValueError('The full video is not private without a release date as requested.')
        return {**proof,'state':'private' if status.get('uploadStatus')=='processed' else 'pending','detail':'Private full-video upload verified.' if status.get('uploadStatus')=='processed' else 'Private upload still processing.'}
    if privacy=='public' and status.get('uploadStatus')=='processed':
        if row.get('publish_at') and datetime.fromisoformat(row['publish_at']).timestamp()>time.time()+60:
            raise ValueError('This video is already public before its requested release time.')
        return {**proof,'state':'published','detail':'Publication verified on the intended channel.'}
    if privacy=='private' and actual and same_instant(actual,row.get('publish_at','')):
        return {**proof,'state':'scheduled','detail':'YouTube confirmed the exact scheduled time; publication is still pending.'}
    if row.get('publish_at'):raise ValueError('YouTube does not currently confirm the requested release time.')
    return {**proof,'state':'uploaded','detail':'Uploaded privately; not public.'}


def run(assistant,session_id,progress=lambda _:None):
    snapshot=assistant.snapshot(session_id);review=snapshot.get('publishing_review')
    if not review:raise ValueError('This chat has no publishing batch to verify. Open the chat that owns the workflow.')
    ledger=Ledger(assistant.root);expected=intent(assistant,review)
    frozen={r['id']:r for r in ledger.inspect(review['id'])}
    # A Shorts-only date change leaves the private original outside its new
    # dispatch intent. A whole-workflow audit must still verify that original
    # from the same campaign's latest saved receipt, without dispatching it.
    private_rows={}
    campaigns={r.get('campaign') for r in review.get('rows',[])+review.get('instagram_rows',[]) if r.get('campaign')}
    selected={r['id'] for r in review.get('rows',[])}
    for saved in ledger.private_intents(session_id,campaigns):
        job_id=saved['id'].removeprefix('youtube:')
        if job_id in selected:continue
        row={'id':job_id,'private_only':True,'publish_at':''}
        private_rows[job_id]=row
        job=assistant.state.publisher.store.get(job_id)
        preserved={'rows':[row],'accounts':{job['profile']:{'id':saved['account']}},
            'made_for_kids':saved.get('made_for_kids'),'synthetic_media':saved.get('synthetic_media'),
            'youtube_check_only':saved.get('check_only',False)}
        expected.extend(intent(assistant,preserved))
        frozen[saved['id']]=saved
    report={'version':1,'review_id':review['id'],'checked_at':time.time(),
        'manifest':'frozen_intent' if frozen else 'legacy_receipts_checked_now',
        'deliveries':[],'artifacts':[],'warnings':[],
        'quality_scope':'File integrity and sampled decoding checked; narrative quality and factual spelling still require content review.'}
    files={};clients={};browser=assistant.state.local_browser
    for entry in expected:
        key=entry['id'];platform=entry['platform']
        result={'id':key,'platform':platform,'account':entry['account'],'publish_at':entry.get('publish_at','')}
        try:
            if frozen and canonical(frozen.get(key))!=canonical(entry):raise ValueError('The saved publishing intent changed after it was frozen.')
            path=entry['video'];progress('Checking the saved '+platform+' delivery: '+Path(path).name)
            if path not in files:
                from hinglish_publish.store import fingerprint
                before=Path(path).stat();digest=fingerprint(path);facts=media(path);after=Path(path).stat()
                if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('The video changed during validation.')
                files[path]={'path':path,'sha256':digest,**facts};report['artifacts'].append(files[path])
            if files[path]['sha256']!=entry['fingerprint']:raise ValueError('The export no longer matches the reviewed video checksum.')
            if platform=='youtube':
                row=next((r for r in review['rows'] if 'youtube:'+r['id']==key),None) or private_rows[key.removeprefix('youtube:')]
                job=assistant.state.publisher.store.get(row['id'])
                if job.get('account_id')!=entry['account']:raise ValueError('The upload and review target different YouTube channels.')
                result.update(title=job['metadata']['title'])
                if review.get('youtube_check_only'):result.update(state='checked',detail='Check-only request; no upload verified.')
                else:result.update(youtube(assistant,job,row,clients))
            else:
                row=next(r for r in review['instagram_rows'] if 'instagram:'+r['id']==key)
                result['title']=row.get('metadata',{}).get('title','Instagram Reel')
                if not row.get('browser_job_id'):
                    result.update(state='pending',detail='No local publishing job has been created.')
                else:
                    task=browser.get(row['browser_job_id'])
                    from .assistant_social import chrome_caption
                    if (task.get('reference')!=row['id'] or task.get('account')!=row['account'] or
                        str(Path(task['video']).resolve())!=entry['video'] or task.get('caption')!=chrome_caption(row.get('caption',''))):
                        raise ValueError('The Instagram job differs from the reviewed file, account or text.')
                    if not (not task.get('publish_at') and not entry.get('publish_at')) and not same_instant(task.get('publish_at',''),entry.get('publish_at','')):
                        raise ValueError('The Instagram queue has a different release time.')
                    result.update(job_id=task['id'],submission_started=bool(task.get('submission_started')))
                    if task['status']=='published' and task.get('url'):
                        result.update(state='published',url=task['url'],detail='Saved verified Instagram receipt; this check did not reopen the post.')
                    elif task['status']=='queued':
                        overdue=bool(task.get('not_before') and time.time()>task['not_before'])
                        result.update(state='queued',detail='Release is due; the saved Reel will post when Storylens and Chrome reconnect.' if overdue else 'Saved local job; publication has not happened yet.')
                    elif task.get('submission_started'):
                        raise ValueError('The submission outcome is unresolved. Verify the existing post before any retry.')
                    else:result.update(state='attention',detail=task.get('message') or 'Instagram needs attention.')
        except Exception as error:
            from .user_messages import problem
            issue=problem(error);result.update(state='attention',detail=issue['message'],error_code=issue['code'])
        report['deliveries'].append(result)
    state=browser.snapshot()
    if review.get('instagram_rows'):
        report['browser_connected']=state['connected']
        if not state['connected']:report['warnings'].append('Chrome Local Publisher is offline. Future Instagram posts need this connection.')
        report['warnings'].append('Instagram releases require this laptop awake, Storylens, Chrome, internet and signed-in accounts.')
    report['published_count']=sum(r['state']=='published' for r in report['deliveries'])
    report['complete']=bool(report['deliveries']) and all(r['state'] in ('published','private','checked') for r in report['deliveries'])
    report['attention_count']=sum(r['state']=='attention' for r in report['deliveries'])
    ledger.observe(session_id,review['id'],report)
    assistant._update(session_id,pipeline_audit=report)
    return report


def message(report):
    lines=['Workflow checked against the saved files and current YouTube results.']
    for platform,name in (('youtube','YouTube'),('instagram','Instagram')):
        rows=[r for r in report['deliveries'] if r['platform']==platform]
        counts=[]
        for state,label in (('published','published'),('private','private and verified'),('scheduled','scheduled and verified'),('queued','queued locally; not published'),('uploaded','uploaded privately'),('pending','unfinished'),('attention','need attention'),('checked','checked only')):
            n=sum(r['state']==state for r in rows)
            if n:counts.append(f'{n} {label}')
        if rows:lines.append(name+': '+', '.join(counts)+'.')
    for row in report['deliveries']:
        if row['state']=='attention':lines.append(row.get('title','Video')+': '+row['detail'])
    lines.append('All required publications are verified.' if report['complete'] else 'The workflow is still open until every required publication is verified.')
    lines.extend(report['warnings'])
    lines.append('Media checks cover file integrity and sampled decoding. They do not certify story quality or factual spelling.')
    return '\n\n'.join(lines)


def followup(assistant,session_id,text,snapshot):
    if not requested(text):return False
    assistant._update(session_id,status='running',stage='Checking the actual saved workflow')
    if re.search(r'\b(?:protect|lock)\b',text,re.I):
        from .pipeline_ledger import freeze
        review=snapshot.get('publishing_review')
        if not review:raise ValueError('Open the chat that owns the publishing workflow first.')
        freeze(assistant,session_id,review)
        assistant._update(session_id,publishing_review=review)
    report=run(assistant,session_id,lambda value:assistant._progress(session_id,value))
    assistant._message(session_id,'assistant',message(report))
    assistant._update(session_id,status='needs_review' if report['attention_count'] else 'idle',stage='Workflow verification finished.')
    return True


def reconcile_due(assistant,session_id,snapshot):
    """The existing supervisor checks due YouTube receipts; it never writes remotely."""
    from .assistant_request_status import pipeline_is_current
    if not pipeline_is_current(snapshot):return
    review=snapshot.get('publishing_review') or {}
    pipeline=snapshot.get('pipeline') or {}
    if not pipeline.get('automatic') or pipeline.get('authorized_review')!=review.get('id') or snapshot.get('stop'):
        return
    audit=snapshot.get('pipeline_audit') or {}
    if audit.get('checked_at',0)>time.time()-300:return
    due=[r for r in review.get('rows',[]) if r.get('publish_at') and
         datetime.fromisoformat(r['publish_at']).timestamp()<=time.time()]
    if not due or review.get('youtube_check_only'):return
    report=run(assistant,session_id)
    if report['complete']:
        from .assistant_pipeline import change
        with assistant.lock:
            current=assistant._get(session_id)
            if not pipeline_is_current(current):return
            if (current.get('publishing_review') or {}).get('id')!=report['review_id']:return
            change(assistant,session_id,phase='complete')
            assistant._message(session_id,'assistant','All required YouTube and Instagram publications have verified receipts.')
