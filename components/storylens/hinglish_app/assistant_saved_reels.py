"""Explicit saved-library delivery, without extraction or changing older tasks."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import time


def requested(text):
    from .assistant_publishing_context import intent_text
    text=intent_text(text)
    folders=False
    if re.search(r'[A-Za-z]:[\\/]',text):
        from .assistant_sources import literal_locations
        try:
            locations,text=literal_locations(text)
            folders=any(path.is_dir() for path in locations)
        except ValueError:pass
    positive=re.sub(r'\b(?:do not|don.t|never|without|no)\b[^.!?\n]*',' ',text,flags=re.I)
    if re.match(r'^\s*(?:how|why|what|where|explain|can i)\b',positive,re.I):return False
    saved_reference=bool(folders or re.search(r'\b(?:saved|existing|old|already.created|already.rendered|finished|completed|memory)\b',positive,re.I)
        or re.search(r'\b(?:any|choose|pick|select)\b',positive,re.I) and clip_count(positive))
    return bool(saved_reference
        and re.search(r'\b(?:reels?|shorts?|clips?|videos?)\b',positive,re.I)
        and re.search(r'\b(?:queue|post|upload|publish|schedule)\b',positive,re.I)
        and not re.search(r'\b(?:extract|render|cut|trim|crop|zoom|subtitles?|overlay|watermark)\b',positive,re.I)
        and not re.search(r'\b(?:make|create)\s+(?:\d+\s+)?(?:new\s+)?(?:reels?|shorts?|clips?)\b',positive,re.I))


def clip_count(text):
    words={'one':1,'two':2,'both':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twelve':12}
    match=re.search(r'\b(\d+|'+'|'.join(words)+r')\s+(?:(?:already.created|already.rendered|saved|existing|old|finished|completed)\s*[, ]*\s*)*(?:reels?|shorts?|clips?|videos?)\b',text,re.I)
    return (int(match[1]) if match[1].isdigit() else words[match[1].lower()]) if match else 0


def supplied_locations(text):
    """Resolve only literal owner-supplied paths; keep folder selection plural."""
    from .assistant_sources import literal_locations
    locations,_=literal_locations(text)
    return locations


def export_context(path,digest):
    """Restore subject evidence after exports receive simple numbered names."""
    title=path.stem
    index=path.parent/'library.json'
    if index.is_file():
        try:
            entry=next((c for c in json.loads(index.read_text('utf-8')).get('shorts',[])
                if c.get('file')==path.name and c.get('sha256')==digest),{})
            title=entry.get('title') or title
        except (ValueError,OSError,TypeError):pass
    text_file=path.with_suffix('.txt')
    excerpt=text_file.read_text('utf-8-sig')[:1600] if text_file.is_file() else ''
    return title,excerpt


def library(assistant, repost, locations=()):
    from .campaign_memory import catalog,resolve
    from hinglish_publish.store import fingerprint
    from hinglish_publish.features import title_hashtags
    # Reading manifests is explicitly authorized for a saved-library request;
    # this does not retrieve another chat's instructions or authorization.
    cards=catalog(assistant)
    cards.sort(key=lambda c:(assistant.root/'output/campaigns'/c['id']/'campaign.json').stat().st_mtime,reverse=True)
    with assistant.state.local_browser.lock:
        jobs=copy.deepcopy(assistant.state.local_browser.data['jobs'])
    used={str(Path(j['video']).resolve()) for j in jobs if j.get('action')=='reel' and
          j['status']!='cancelled' and j.get('video') and
          not (j.get('stop') and j.get('submission_started') is False) and
          (not repost or j['status']!='published')}
    blocked_fingerprints={fingerprint(p) for p in used if Path(p).is_file()}
    items=[];seen=set()
    for card in cards:
        if not card['available_for_upload']:continue
        _,campaign,_=resolve(assistant,card['id'])
        for clip in campaign['clips']:
            path=Path(clip['video']).resolve();digest=clip['fingerprint']
            if locations and not any(path==base or base.is_dir() and path.is_relative_to(base) for base in locations):continue
            if str(path) in used or digest in blocked_fingerprints or digest in seen:continue
            if fingerprint(path)!=digest:continue
            seen.add(digest)
            meta=clip.get('metadata',{})
            _,excerpt=export_context(path,digest)
            items.append({'id':hashlib.sha256((card['id']+':'+str(clip['index'])).encode()).hexdigest()[:16],
                'campaign_id':card['id'],'source':card['source'],'video':str(path),
                'fingerprint':digest,'duration':clip['duration'],'metadata':meta,
                'title':meta.get('title',path.stem),'content_excerpt':excerpt,
                'caption':title_hashtags(meta) if meta.get('title') else ''})
            if len(items)>=40:return items
    # Extraction outputs exist before a publishing campaign is prepared. They
    # are saved media too; assets/backgrounds are never candidate Reels.
    roots=list(locations) or [assistant.root/'output/shorts']
    from hinglish_shorts.source import open_video
    for base in roots:
        if not base.exists():continue
        paths=[base] if base.is_file() else sorted(base.rglob('*.mp4'),key=lambda p:p.stat().st_mtime,reverse=True)[:2000]
        for path in paths:
            path=path.resolve()
            if any(part.lower()=='assets' for part in path.parts) or path.suffix.lower()!='.mp4' or not path.is_file():continue
            if base.is_dir() and not path.is_relative_to(base):continue
            digest=fingerprint(path)
            if str(path) in used or digest in blocked_fingerprints or digest in seen:continue
            try:facts=open_video(path)
            except (ValueError,OSError):continue
            if facts.width>=facts.height or not 2<=facts.duration<=50.1:continue
            seen.add(digest)
            title,excerpt=export_context(path,digest)
            title=re.sub(r'^\d+\s*[-_]\s*','',title).replace('-',' ').strip()
            items.append({'id':hashlib.sha256(str(path).encode()).hexdigest()[:16],
                'campaign_id':'','source':path.parent.name,'video':str(path),'fingerprint':digest,
                'duration':facts.duration,'metadata':{'title':title,'description':'','tags':[]},
                'title':title,'content_excerpt':excerpt,'caption':''})
            if len(items)>=40:return items
    return items


def followup(assistant,session_id,text,progress):
    from .assistant_publish_intent import platforms
    if requested(text) and set(platforms(text))=={'youtube','instagram'}:
        from hinglish_cut.model_preferences import publishing_memory_budget
        with publishing_memory_budget():
            return _followup(assistant,session_id,text,progress)
    return _followup(assistant,session_id,text,progress)


def _followup(assistant,session_id,text,progress):
    if not requested(text):return False
    from .assistant_publishing_context import intent_text
    text=intent_text(text)
    from .assistant_publish_intent import instruction,positive,platforms
    scope=platforms(text)
    paired=set(scope)=={'youtube','instagram'}
    # YouTube-only requests retain their own handler. Paired saved exports use
    # this bounded selector instead of the full editing-tool planning schema.
    if not paired and re.search(r'\b(?:youtube|yt)\b',positive(instruction(text)),re.I):return False
    from .assistant_distribution import context,stage,prepare_copy
    from .distribution_schedule import contract
    from .assistant_edit_workflow import destination_profile
    from .durable_json import write
    from .delivery_request import account_order
    workflow=context(assistant.root)
    if paired:
        from .delivery_request import profiles as named_profiles
        destinations=named_profiles(instruction(text),workflow)
        if len(destinations)!=1:
            raise ValueError('Choose one channel profile for this paired saved-video request. No upload started.')
        expected_profiles=destinations*clip_count(instruction(text))
    else:
        expected_profiles=account_order(text,workflow=workflow)
    count=len(expected_profiles) or clip_count(text)
    if not 1<=count<=40:raise ValueError('Tell me how many saved Reels to queue (1–40). No new videos were extracted.')
    # A separate delivery must be explicitly requested. Ordinary retries keep
    # the original immutable receipt and cannot silently repost old videos.
    repost=bool(re.search(r'\b(?:repost|posted again|post again|new test publications|new test posts)\b',text,re.I))
    cycle=list(dict.fromkeys(expected_profiles))
    if not cycle or any(p not in ('cricket','gaming') for p in cycle):
        raise ValueError('Choose the cricket or gaming Instagram account, or name the accounts in alternating order.')
    schedule=contract(text,context(assistant.root))
    request_key=hashlib.sha256(text.encode()).hexdigest()[:16]
    folder=assistant.root/'output/campaigns'/f'reused-{session_id}-{request_key}'
    journal=folder/'selection.json'
    if not journal.exists():
        for older in (assistant.root/'output/campaigns').glob(f'reused-{session_id}-*/selection.json'):
            record=json.loads(older.read_text('utf-8'))
            if intent_text(record.get('request',''))==text:folder=older.parent;journal=older;break
    prefix=[];prefix_profiles=[]
    if journal.exists():
        saved=json.loads(journal.read_text('utf-8'))
        if intent_text(saved['request'])!=text:raise ValueError('The saved delivery belongs to a different request.')
        chosen=saved['clips'];model=saved['model'];profiles=saved.get('profiles',expected_profiles)
        if profiles!=expected_profiles:
            from .delivery_request import remaining_order
            remaining=remaining_order(expected_profiles,profiles)
            if len(chosen)!=len(profiles):raise ValueError('The saved account order differs from this request. No post was queued.')
            if not remaining:
                if re.search(r'\b(?:alternat\w*|round.robin|taking turns)\b',text,re.I):raise ValueError('The saved alternating order differs. Existing posts are preserved.')
                expected_profiles=profiles
            else:
                prefix=chosen;prefix_profiles=profiles;expected_profiles=profiles+remaining
    if not journal.exists() or prefix:
        select_count=count-len(prefix)
        select_profiles=expected_profiles[len(prefix):]
        items=library(assistant,repost,supplied_locations(text))
        if paired:
            # Do not turn a new test into edits/replays of another queue item.
            reserved={j.get('fingerprint') for j in assistant.state.publisher.store.list()
                      if j.get('profile','general')==cycle[0] and j.get('platform')=='youtube'}
            items=[item for item in items if item['fingerprint'] not in reserved]
        prefix_hashes={clip['fingerprint'] for clip in prefix}
        items=[clip for clip in items if clip['fingerprint'] not in prefix_hashes]
        if len(items)<select_count:raise ValueError(f'I found {len(items)} eligible saved Reels, but {select_count} more are needed. Earlier posts are preserved; no new posts were queued.')
        from hinglish_visuals.brain import open_brain
        from hinglish_cut.gpu_lock import gpu_lock
        from hinglish_niche.profiles import use
        schema={'type':'object','additionalProperties':False,'properties':{
            'clip_ids':{'type':'array','uniqueItems':True,'minItems':select_count,'maxItems':select_count,
                'items':{'type':'string','enum':[c['id'] for c in items]}},
            'profiles':{'type':'array','minItems':select_count,'maxItems':select_count,
                'items':{'type':'string','enum':list(dict.fromkeys(cycle))}}},'required':['clip_ids','profiles']}
        data={'request':text,'count':select_count,'required_account_order':select_profiles,
            'candidates':[{k:c[k] for k in ('id','source','title','duration','content_excerpt')} for c in items]}
        creator={'profile':'general'}
        if paired:
            from hinglish_niche.profiles import Profiles
            creator=Profiles(assistant.root).context(cycle[0])
        with assistant.state.work_lock,gpu_lock(assistant.root),use(creator):
            brain=open_brain(assistant.root,'ollama',progress=progress)
            try:
                selector=brain
                if paired:
                    from hinglish_publish.campaign import RecordedBrain
                    folder.mkdir(parents=True,exist_ok=True)
                    selector=RecordedBrain(brain,folder)
                for attempt in range(2):
                    answer=selector.json('You are Storylens\'s saved-media selector. Choose exactly count DIFFERENT finished Reel IDs from candidates in publication order. '
                        'Honor an explicitly named source. When the user leaves the choice open, prefer actual gaming clips for a gaming destination and actual cricket clips for cricket. '
                        'Use title and content_excerpt to identify the real subject, not the numbered filename or account name. These are real completed files. '
                        'Return one destination profile for each clip in the exact required_account_order. This is one post per clip, not every clip on every account. '
                        'Do not extract, render or invent files. Only return supplied IDs. The application handles account verification, metadata and exact release times.',
                        data,schema,max_tokens=1000,think=False)
                    ids=answer.get('clip_ids',[])
                    if (len(ids)==select_count and len(set(ids))==select_count and all(i in {c['id'] for c in items} for i in ids)
                        and answer.get('profiles')==select_profiles):break
                    data['validation_error']='Choose exactly the requested number of distinct supplied IDs and preserve required_account_order.'
                else:raise ValueError('The local model could not select the requested saved Reels. No uploads started.')
                chosen=prefix+[next(c for c in items if c['id']==i) for i in ids];profiles=prefix_profiles+answer['profiles'];model=brain.name
            finally:brain.close()
        folder.mkdir(parents=True,exist_ok=True)
        if prefix and not (folder/'selection-before-scope-repair.json').exists():write(folder/'selection-before-scope-repair.json',saved)
        write(journal,{'request':text,'clips':chosen,'profiles':profiles,'model':model,'repost_authorized':repost})
    previous=assistant.snapshot(session_id)
    reviews=list(previous.get('publishing_review_history',[]))
    if previous.get('publishing_review'):reviews.append(previous['publishing_review'])
    assistant._update(session_id,status='running',stage=f'Reusing {count} finished Reels; no extraction',brain=model,
        publishing_review=None,publishing_review_history=reviews[-10:],edit_publish_checkpoint=None,campaign_pending=None,
        pipeline={'version':1,'request':text,'automatic':not bool(re.search(r'\b(?:draft|preview|review first|ask me first|do not publish|don.t publish|do not queue)\b',text,re.I)),
                  'request_message_id':previous.get('active_request_message_id'),
                  'phase':'preparing','attempts':0,'next_retry':0,'authorized_review':'','created':time.time()})
    assistant._message(session_id,'assistant',f'I found {count} finished video'+('s' if count!=1 else '')+'. I will reuse the selected files and verify each requested platform after uploading.')
    from hinglish_publish.store import fingerprint
    from hinglish_publish.features import title_hashtags
    from .assistant_publishing_context import IST
    from datetime import datetime
    clips=[]
    for index,item in enumerate(chosen,1):
        profile=profiles[index-1]
        if assistant._stopped(session_id):raise ValueError('Stopped. Saved Reels and existing uploads are preserved.')
        source=Path(item['video']);path=folder/f'short-{index:02}.mp4'
        if fingerprint(source)!=item['fingerprint']:raise ValueError('A selected saved Reel changed. No other file was substituted.')
        if not path.exists():
            partial=path.with_suffix('.copying');shutil.copy2(source,partial);partial.replace(path)
        if fingerprint(path)!=item['fingerprint']:raise ValueError('The saved delivery file changed. No upload started.')
        for suffix in ('.txt','.publish.json'):
            if source.with_suffix(suffix).is_file() and not path.with_suffix(suffix).exists():shutil.copy2(source.with_suffix(suffix),path.with_suffix(suffix))
        from hinglish_publish.source_context import preserve_transcript
        preserve_transcript(assistant.root,source,path)
        copy_file=folder/f'short-{index:02}.metadata.json'
        meta=json.loads(copy_file.read_text('utf-8')) if copy_file.exists() else copy.deepcopy(item['metadata'])
        caption=title_hashtags(meta) if meta.get('title') else ''
        refresh_copy=not copy_file.exists() and bool(re.search(r'\b(?:seo|rewrite|correct|improve)\b',text,re.I))
        if refresh_copy or not (meta.get('title') and 3<=len(re.findall(r'(?<!\w)#[A-Za-z][A-Za-z0-9_]*',caption))<=5 and len(caption)<=2200):
            from .publishing_speech import cancellation
            with assistant.state.work_lock,cancellation(lambda:assistant._stopped(session_id)):
                meta,_=prepare_copy(assistant.root,path,profile,text,progress,instagram=True,youtube=paired,source_title=item['title'])
        meta['instagram_caption']=title_hashtags(meta)
        write(copy_file,meta)
        clips.append({'index':index,'video':str(path.resolve()),'fingerprint':item['fingerprint'],
            'duration':item['duration'],'metadata':meta,'publish_at':datetime.now(IST).isoformat(),
            'destination_profile':profile,'reused_from':{'campaign_id':item['campaign_id'],'video':item['video']}})
    targets=[]
    for profile in dict.fromkeys(profiles):
        account=assistant.state.publisher.accounts(profile)['youtube']
        targets.append({'profile':profile,'id':account.get('id',''),'name':account.get('name',profile)})
    write(folder/'campaign.json',{'status':'reviewed','source':chosen[0]['source'],
        'targets':targets,
        'clips':clips,'long_videos':[],'model':model,'saved_library_delivery':True})
    assistant._update(session_id,campaign=str(folder),last_paths=[c['video'] for c in clips],shorts_paths=[c['video'] for c in clips])
    spec={**schedule,'campaign_ids':[folder.name],'platforms':['instagram'],'destination_profiles':list(dict.fromkeys(profiles)),
        'clip_destinations':{str(i):profile for i,profile in enumerate(profiles,1)},
        'clip_indices':[],'include_longform':False,'request':text}
    if paired:
        # The fresh manifest already binds the exact YouTube account ID and
        # paired Instagram profile. No cross-channel destination override.
        spec.update(platforms=['youtube','instagram'],destination_profiles=[])
        spec.pop('clip_destinations')
    stage(assistant,session_id,spec)
    from .assistant_pipeline import prepared
    prepared(assistant,session_id,assistant.snapshot(session_id)['publishing_review'])
    return True
