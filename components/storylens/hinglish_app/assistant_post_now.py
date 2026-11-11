"""An explicit immediate follow-up keeps the current Reel files and receipts."""
import copy
import re
import time
import uuid


def followup(assistant,session_id,text,snapshot):
    from .distribution_schedule import normalize
    from .assistant_publish_intent import instruction,positive,platforms
    value=instruction(normalize(text))
    # Rejecting scheduling does not reject the following affirmative upload,
    # even when it is spoken in one clause: "don't schedule, post now".
    action_text=re.sub(r"\b(?:do not|don't)\s+(?:(?:want|wish)\s+to\s+)?schedul\w*\b",'',value,flags=re.I)
    command=positive(action_text)
    command=re.sub(r'\breview first\b','review only',command,flags=re.I)
    if not re.search(r'\b(?:post|publish|upload)\b[^.!?\n]{0,90}\b(?:now|immediately|right away)\b',command,re.I):return False
    if re.match(r'^\s*(?:how|why|what|where|explain|can i)\b',command,re.I):return False
    if re.search(r'[A-Za-z]:[\\/]|\b(?:extract|create|make|new|different|another|tomorrow|later|first|second|gap|apart|rewrite|rename|retitle|change|replace|edit|update|switch)\b',command,re.I):return False
    if re.search(r'\b(?:only|just)\s+(?:one|\d+)\b|\b(?:one|\d+)\s+of\b',command,re.I):return False
    from .assistant_sources import literal_locations
    if literal_locations(text)[0]:return False
    previous=snapshot.get('publishing_review') or {}
    if not previous.get('instagram_rows'):return False
    from .assistant_saved_reels import clip_count
    count=clip_count(command)
    if count and count!=len(previous['instagram_rows']):return False
    scope=platforms(text)
    if 'youtube' in scope or (previous.get('rows') and scope!=['instagram']):return False
    from .delivery_request import profiles
    from .assistant_distribution import context
    destinations=profiles(command,context(assistant.root))
    if destinations and set(destinations)!={r['profile'] for r in previous['instagram_rows']}:return False
    # A stated new count is a fresh selection request, unless the owner clearly
    # refers to this existing batch. Do not silently truncate or enlarge it.
    if re.search(r'\b(?:\d+|one|two|three|four|five|six|seven)\s+(?:reels?|videos?|clips?)\b',command,re.I) and not re.search(r'\b(?:these|those|same|them|both|all)\b',command,re.I):return False
    from .assistant_upload_recovery import present
    review=copy.deepcopy(present(assistant,{**snapshot,'publishing_review':previous}))
    remaining=[];preserved=0
    bridge=assistant.state.local_browser
    for row in review['instagram_rows']:
        job=bridge.get(row['browser_job_id']) if row.get('browser_job_id') else None
        if job and (job.get('reference')!=row['id'] or job.get('account')!=row['account'] or job.get('video')!=row['video']):
            raise ValueError('The saved Instagram receipt does not match these Reels. Check the existing task before retrying.')
        if row.get('status')=='published' or job and job.get('status')=='published':
            preserved+=1
            continue
        if job:
            safe=job.get('status')=='queued' or job.get('status')=='needs_review' and job.get('last_phase') in ('queued','running')
            if not safe or job.get('submission_started') is not False or job.get('stop'):
                assistant._message(session_id,'assistant','One of these Reels is already posting or has an uncertain result. Check its saved receipt before changing the time. I have kept the existing posts and queue unchanged.',question=True)
                assistant._update(session_id,status='needs_review',stage='Check the Reel already in progress.')
                return True
        row.update(immediate=True,publish_at='',status='draft',message='Ready to post now; the existing queue time changes only after this request is confirmed.')
        remaining.append(row)
    if not remaining:
        assistant._message(session_id,'assistant','These Reels were already posted. No new upload was started.')
        assistant._update(session_id,status='complete',stage='Existing publication receipts retained.')
        return True
    review.update(id=uuid.uuid4().hex,ids=[],rows=[],accounts={},state='review',created=time.time(),
                  request_message_id=snapshot.get('active_request_message_id'),allow_reschedule=True,
                  random_window=None,upload_requested=True,schedule=True,distribution=True)
    preview=bool(re.search(r'\b(?:draft|preview|review first|review only|ask me first|do not publish|don.t publish|do not queue|don.t queue)\b',value,re.I))
    review['automatic']=not preview
    history=list(snapshot.get('publishing_review_history',[]))+[previous]
    assistant._update(session_id,publishing_review=review,publishing_review_history=history[-10:],
        status='needs_review',selected='publish',stage='Ready to post the saved Reels now.',
        pipeline={'version':1,'request':text,'request_message_id':snapshot.get('active_request_message_id'),
                  'automatic':not preview,'phase':'review','review_id':review['id'],'attempts':0,'next_retry':0,'created':time.time()})
    accounts=', '.join('@'+v for v in dict.fromkeys(r['account'] for r in remaining))
    assistant._message(session_id,'assistant',f'{len(remaining)} saved Reel'+('s are' if len(remaining)!=1 else ' is')+
        f' ready to post now to {accounts}. The same files, titles, hashtags and queue identities will be reused.'+
        (f' {preserved} already posted Reel'+('s are' if preserved!=1 else ' is')+' kept; no duplicate upload will be sent.' if preserved else ''),
        publishing_review=review)
    if not preview:
        from .assistant_preferences import declarations
        from .assistant_publish import start
        defaults=declarations(assistant.root)
        start(assistant,{'session':session_id,'review':review['id'],**defaults},internal=True)
    return True
