"""Completed-job-bound manual sound choices; never a mix or automatic placement."""
import hashlib
import json
from pathlib import Path
import re


def _bound(state,job_id):
    if not isinstance(job_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',job_id):raise ValueError('Choose a completed sound review.')
    job=state.snapshot(job_id)
    if not job or job.get('id')!=job_id or job.get('mode')!='sound' or job.get('status')!='complete':
        raise ValueError('Finish the sound suggestions before choosing an alternative.')
    root=Path(state.root).resolve();result=job['result'];folder=Path(result['folder']).resolve(strict=True)
    info=result['sound_recommendations'];path=Path(info['manifest_path']).resolve(strict=True)
    if (not folder.is_relative_to(root/'output/sound-recommendations') or path.parent!=folder
            or path.name!='manifest.json' or path.stat().st_size>16*1024**2):
        raise ValueError('Choose a sound recommendation saved by this application.')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=info['manifest_sha256']:
        raise ValueError('This sound review changed. Refresh its saved alternatives first.')
    manifest=json.loads(raw)
    if (manifest.get('schema')!='storylens.sound-recommendations' or manifest.get('version')!=1
            or manifest.get('status') not in ('ready','no_match') or manifest['status']!=info['status']):
        raise ValueError('The saved sound recommendations are not ready for review.')
    return path,info['manifest_sha256'],manifest


def _candidate(manifest,key):
    from hinglish_sound.recommendations import _candidate_id
    rows=[(g,c) for g in manifest['groups'] for c in g['candidates'] if c.get('id')==key]
    if len(rows)!=1:raise ValueError('Choose one offered sound candidate; no automatic winner was selected.')
    group,row=rows[0]
    if (group.get('decision')==-1 or group.get('status')!='candidates' or row.get('group_id')!=group['id']
            or key!=_candidate_id(manifest['fingerprint'],group['id'],row['source'],row['timeline'])):
        raise ValueError('This sound candidate is no longer available. Refresh the review.')
    return row


def _roots(root):
    from hinglish_sound.settings import load_settings
    settings=load_settings(root)
    return [settings.music_folder,settings.sfx_folder,settings.pro_folder or root/'library/sfx-pro',
            root/'library/sound-online',root/'library/owner-sound-packs/music',root/'library/owner-sound-packs/sfx']


def describe(state,job_id):
    if str(job_id).startswith('mix-'):
        from hinglish_sound.human_review import registered
        path,plan=registered(state.root,job_id)
        from hinglish_sound.keyword_folders import organize
        folders=organize(plan['human_review'])
        groups=[]
        for event in plan['human_review']['events']:
            timeline={'start':event['time'],'end':min(plan['seconds'],event['time']+event['duration'])}
            rows=[{'id':event['id']+'/'+c['id'],'name':c['asset']['name'],'kind':'sfx','rank':i+1,
                   'reason':c['recommendation'],'timeline':timeline,'source_in':0,
                   'source_out':min(c['asset']['duration'],event['duration']),'proposed_level_db':event['level_db']}
                  for i,c in enumerate(event['candidates']) if c.get('folder_approved') is not False]
            groups.append({'id':event['id'],'kind':'sfx','role':event['category'],'status':'candidates',
                           'timeline':timeline,'intent':event['intent'],'keyword':event.get('keyword'),'candidates':rows})
        return {'job_id':job_id,'status':'ready','groups':groups,'folders':folders,'folder':str(path.parent),
                'auto_insert':False,'human_review':True}
    path,sha,manifest=_bound(state,job_id)
    groups=[]
    for group in manifest['groups']:
        choices=[]
        for row in group['candidates']:
            _candidate(manifest,row['id'])
            choices.append({k:row.get(k) for k in ('id','name','kind','rank','reason','timeline','proposed_level_db','coverage')}
                           | {'source_in':row['source']['in'],'source_out':row['source']['out']})
        groups.append({k:group.get(k) for k in ('id','kind','role','status','timeline','intent')} | {'candidates':choices})
    return {'job_id':job_id,'status':manifest['status'],'groups':groups,'auto_insert':False}


def saved_results(state,jobs):
    rows=[];seen=set()
    for job in jobs:
        if job.get('mode')!='sound' or job.get('status')!='complete' or job.get('id') in seen:continue
        try:
            path,sha,manifest=_bound(state,job['id'])
            rows.append({'job_id':job['id'],'name':path.parent.name,'created':float(job.get('created') or 0)})
            seen.add(job['id'])
        except (ValueError,KeyError,TypeError,OSError):continue
    from hinglish_sound.human_review import registered
    for record in (Path(state.root)/'cache/app/human-sound-reviews').glob('mix-*.json'):
        try:
            path,plan=registered(state.root,record.stem)
            rows.append({'job_id':record.stem,'name':plan.get('name',path.parent.name)+' · sound choices','created':path.stat().st_mtime})
        except (ValueError,OSError,KeyError):continue
    return sorted(rows,key=lambda row:row['created'],reverse=True)[:80]


def audition(state,job_id,candidate_id):
    if str(job_id).startswith('mix-'):
        from hinglish_sound.human_review import registered,audition as listen
        path,plan=registered(state.root,job_id)
        parts=str(candidate_id).split('/')
        if len(parts)!=2:raise ValueError('Choose a sound from this event.')
        return {'status':'ready',**listen(path,*parts)}
    from hinglish_sound.audition import prepare
    path,sha,manifest=_bound(state,job_id);_candidate(manifest,candidate_id)
    return prepare(state.root,path,sha,candidate_id,allowed_roots=_roots(Path(state.root).resolve()))


def original(state,job_id,candidate_id,context,insert=False):
    if type(insert) is not bool:raise ValueError('Choose import or add at playhead.')
    if str(job_id).startswith('mix-'):
        from hinglish_sound.human_review import registered,_candidate
        path,plan=registered(state.root,job_id)
        parts=str(candidate_id).split('/')
        if len(parts)!=2:raise ValueError('Choose a sound from this event.')
        event,row=_candidate(plan,*parts)
        source=Path(row['asset']['path']).resolve()
        if not any(source.is_relative_to(Path(p).resolve()) for p in _roots(Path(state.root).resolve())):
            raise ValueError('Choose a sound from your configured library.')
        # Audio-only WAV also handles OGG/FLAC uniformly in the native host adapters.
        import soundfile as sf
        from hinglish_sound.library import decode
        key=hashlib.sha256((str(source)+str(source.stat().st_mtime_ns)+str(insert)+str(event['duration'])).encode()).hexdigest()[:20]
        destination=path.parent/'review-audio'/(key+'-import.wav');destination.parent.mkdir(exist_ok=True)
        if not destination.exists():sf.write(destination,decode(source,limit=event['duration'] if insert else None).T,48000,subtype='PCM_24')
        return {'manifest':{'type':'assets','paths':[str(destination)],'source_assets':True,'insert':insert,'sound_review':True,
                 'name':'Storylens sound choices','expected':{k:context.get(k) for k in ('project_id','sequence_id')}},
                'notice':'Sound excerpt ready at the playhead; use a spare audio track.' if insert else 'Original sound ready for the project bin.'}
    from hinglish_sound.recommendations import verify_candidate_source
    path,sha,manifest=_bound(state,job_id);row=_candidate(manifest,candidate_id)
    verified=verify_candidate_source(state.root,row,allowed_roots=_roots(Path(state.root).resolve()))
    return {'manifest':{'type':'assets','paths':[verified['path']],'source_assets':True,'insert':insert,
            'name':'Storylens sound sources','expected':{k:context.get(k) for k in ('project_id','sequence_id')}},
            'source_window':{'in':verified['source_in'],'out':verified['source_out']},'proposed_timeline':row['timeline'],
            'notice':'Original sound is ready for the project bin. Use the displayed source window and suggested timing when placing it.'}


def preview(state,job_id,audition_id):
    manifest,sha,data=_bound(state,job_id)
    if not isinstance(audition_id,str) or not re.fullmatch(r'audition-[a-f0-9]{32}',audition_id):raise ValueError('Choose a prepared sound audition.')
    folder=manifest.parent/'auditions';receipt=folder/(audition_id+'.json');path=folder/(audition_id+'.wav')
    if not receipt.is_file() or receipt.stat().st_size>1024**2:raise ValueError('Prepare this sound audition before listening.')
    saved=json.loads(receipt.read_text('utf-8'));facts=saved['preview']
    _candidate(data,saved['candidate_id'])
    if (saved.get('status')!='ready' or saved.get('id')!=audition_id or saved.get('manifest_sha256')!=sha
            or Path(facts['path']).resolve()!=path.resolve() or not path.is_file()
            or path.stat().st_size>7*1024**2 or path.stat().st_size!=facts['bytes']
            or hashlib.sha256(path.read_bytes()).hexdigest()!=facts['sha256']):
        raise ValueError('This prepared audition changed. Refresh the sound review before listening.')
    return {'path':str(path),'mime':'audio/wav','sha256':facts['sha256'],'bytes':facts['bytes']}
