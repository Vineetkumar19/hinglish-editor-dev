"""Chat-owned, receipt-bound copy repair; never re-upload an existing video."""
import copy
import json
import re
import time
import uuid
from pathlib import Path


def read_remote(assistant,job):
    from hinglish_publish.providers import youtube_client
    client,account=youtube_client(assistant.root,job['profile'])
    if account['channel_id']!=job['account_id']:raise ValueError('The saved upload belongs to a different connected channel.')
    items=client.videos().list(part='snippet,status',id=job['remote']['id']).execute().get('items',[])
    if len(items)!=1 or items[0]['snippet']['channelId']!=job['account_id']:
        raise ValueError('The exact saved video cannot be verified on this channel.')
    item=items[0]
    if item['status'].get('privacyStatus')!='private' or item['status'].get('publishAt'):
        raise ValueError('This repair is limited to an unscheduled private upload. Its visibility was not changed.')
    return item


def repair_remote(assistant,session_id,review,job,old,new):
    def matches(item,value):return all(item['snippet'].get(k)==value[k] for k in ('title','description'))
    current=read_remote(assistant,job)
    if matches(current,new):return
    if not matches(current,old):raise ValueError('The saved video copy was changed outside this repair. No text was overwritten.')
    task=assistant.state.local_browser.enqueue_youtube(job['account_id'],job['remote']['id'],'',session_id,
        authorized=True,channel_name=review['accounts'][job['profile']]['name'],video_kind=job['kind'],
        metadata={k:new[k] for k in ('title','description')},expected_metadata={k:old[k] for k in ('title','description')})
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        state=assistant.state.local_browser.get(task['id'])
        assistant._progress(session_id,'Correcting the existing YouTube copy: '+state['message'])
        if assistant._stopped(session_id):
            assistant.state.local_browser.cancel(task['id']);raise ValueError('Stopped. The saved video ID is retained.')
        if state['status']=='submitted':break
        if state['status'] in ('needs_review','blocked','cancelled'):raise ValueError(state['message'])
        time.sleep(1)
    else:raise ValueError('The copy repair is still waiting for Chrome. No replacement upload was sent.')
    for _ in range(30):
        if matches(read_remote(assistant,job),new):return
        time.sleep(1)
    raise ValueError('YouTube has not verified the new copy. The saved video will not be uploaded again.')


def followup(assistant,session_id,text,snapshot,progress):
    if not re.match(r'^\s*(?:please\s+)?(?:repair|rewrite|correct)\b',text,re.I) or not re.search(r'\b(?:publishing copy|metadata|descriptions?)\b',text,re.I):return False
    if re.search(r'\b(?:do not|don.t|never)\b',text,re.I):return False
    review=snapshot.get('publishing_review')
    if not review or not review.get('rows'):raise ValueError('Open the chat containing the videos whose publishing copy needs repair.')
    from .durable_json import write
    journal=assistant.folder/('copy-repair-'+session_id+'.json')
    saved=json.loads(journal.read_text('utf-8')) if journal.exists() else None
    if saved and review['id'] not in (saved['original_review'],saved['review']['id']):saved=None
    # Re-check an interrupted journal after the copy policy changes. Restore
    # only unapplied local draft text, and only after reading the exact remote
    # video. Never overwrite an external edit or discard an uncertain outcome.
    if saved and saved.get('copy_policy_version')!=2:
        restore=[]
        for job_id,revision in saved['revisions'].items():
            job=assistant.state.publisher.store.get(job_id)
            if job['metadata'] not in (revision['old'],revision['new']):
                raise ValueError('Publishing text changed outside the saved repair. Review it before continuing.')
            if job.get('remote',{}).get('id'):
                actual=read_remote(assistant,job)['snippet']
                same=lambda value:all(actual.get(k)==value[k] for k in ('title','description'))
                if same(revision['old']):restore.append((job_id,revision['old']))
                elif not same(revision['new']):raise ValueError('The video text changed outside Storylens. It was preserved.')
            else:restore.append((job_id,revision['old']))
        for job_id,metadata in restore:assistant.state.publisher.store.change(job_id,metadata=metadata)
        write(journal.with_name(journal.stem+'-previous.json'),saved)
        saved=None
    if not saved:
        for row in review.get('instagram_rows',[]):
            if row.get('browser_job_id'):
                task=assistant.state.local_browser.get(row['browser_job_id'])
                if task['status']!='queued' or task.get('submission_started'):
                    raise ValueError('A Reel has already started or finished. This repair only changes unposted queue entries.')
        revisions={}
        from hinglish_visuals.brain import open_brain
        from hinglish_publish.metadata import concise_youtube
        from hinglish_publish.features import title_hashtags
        with assistant.state.work_lock:
            brain=open_brain(assistant.root,'ollama',progress=progress)
            try:
                for row in review['rows']:
                    job=assistant.state.publisher.store.get(row['id'])
                    if job.get('remote',{}).get('id'):read_remote(assistant,job)
                    elif job['status']!='draft':raise ValueError('An upload has an unresolved outcome. Verify it before changing copy.')
                    transcript=Path(job['video']).with_suffix('.txt').read_text('utf-8-sig')
                    progress('Local AI is rewriting and checking '+job['kind']+' publishing copy')
                    events=[]
                    def record(stage,draft,error=''):
                        events.append({'stage':stage,'draft':draft,'error':error})
                        write(assistant.folder/('copy-review-'+session_id+'-'+job['id']+'.json'),{'events':events})
                    new=concise_youtube(brain,transcript,progress,record=record)
                    # Browser editing changes only title/description; keep the
                    # already-uploaded tags instead of pretending to edit them.
                    if job.get('remote',{}).get('id'):new['tags']=job['metadata']['tags']
                    new['instagram_caption']=title_hashtags(new)
                    revisions[job['id']]={'old':job['metadata'],'new':new}
            finally:brain.close()
        revised=copy.deepcopy(review);revised.update(id=uuid.uuid4().hex,state='review',created=time.time())
        for row in revised['rows']:row['metadata']=revisions[row['id']]['new']
        for reel in revised.get('instagram_rows',[]):
            paired=next(r for r in revised['rows'] if r['fingerprint']==reel['fingerprint'] and r['profile']==reel['profile'])
            reel.update(metadata=paired['metadata'],caption=paired['metadata']['instagram_caption'])
        saved={'copy_policy_version':2,'original_review':review['id'],'review':revised,'revisions':revisions,'complete':False}
        write(journal,saved)
    revised=saved['review'];publisher=assistant.state.publisher
    for row in revised['rows']:
        job=publisher.store.get(row['id']);revision=saved['revisions'][row['id']]
        if job['metadata'] not in (revision['old'],revision['new']):raise ValueError('Publishing copy changed outside the saved repair.')
        publisher.store.change(row['id'],metadata=revision['new'])
    history=list(snapshot.get('publishing_review_history',[]))
    if review['id']!=revised['id']:history.append(review)
    from .pipeline_ledger import freeze
    freeze(assistant,session_id,revised)
    pipeline={**(snapshot.get('pipeline') or {}),'automatic':True,'phase':'copy_repair','request':text,
              'review_id':revised['id'],'authorized_review':revised['id']}
    assistant._update(session_id,publishing_review=revised,publishing_review_history=history[-10:],pipeline=pipeline,
        status='running',stage='Repairing publishing copy on the saved videos')
    for row in revised['rows']:
        job=publisher.store.get(row['id'])
        if job.get('remote',{}).get('id'):
            repair_remote(assistant,session_id,revised,job,**saved['revisions'][row['id']])
    from .assistant_social import chrome_caption
    for row in revised.get('instagram_rows',[]):
        task=assistant.state.local_browser.enqueue('reel',row['account'],row['video'],chrome_caption(row['caption']),session_id,
            authorized=True,publish_at=row['publish_at'],reference=row['id'],switch_via=row.get('instagram_switch_via',''))
        row.update(browser_job_id=task['id'],status=task['status'])
    # Keep the reusable campaign and preparation cache in sync for date changes.
    folder=Path(revised['campaign']);manifest=folder/'campaign.json'
    campaign=json.loads(manifest.read_text('utf-8'))
    for clip in campaign.get('clips',[])+campaign.get('long_videos',[]):
        paired=next(r for r in revised['rows'] if r['fingerprint']==clip['fingerprint'])
        clip['metadata']=paired['metadata']
    write(manifest,campaign)
    checkpoint=folder/'preparation.json'
    if checkpoint.exists():
        prepared_copy=json.loads(checkpoint.read_text('utf-8'))
        for cached in prepared_copy.get('clips',{}).values():
            paired=next((r for r in revised['rows'] if r['fingerprint']==cached['fingerprint']),None)
            if paired:cached['metadata']=paired['metadata']
        write(checkpoint,prepared_copy)
    saved.update(review=revised,complete=True);write(journal,saved)
    assistant._update(session_id,publishing_review=revised)
    assistant._message(session_id,'assistant','Publishing copy corrected from the speech. The existing video ID and finished Shorts were reused.')
    if re.search(r'\b(?:resume|continue|finish)\b',text,re.I):
        from .assistant_pipeline import prepared
        prepared(assistant,session_id,revised)
    else:assistant._update(session_id,status='idle',stage='Copy repair verified; publishing is paused.')
    return True
