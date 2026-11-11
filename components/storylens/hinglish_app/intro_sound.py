"""Attach a source-bound recipe mix to one intro without duplicating original audio."""
from pathlib import Path
import copy,json
from hinglish_cinematic.curation import Store,file_hash,resolve_sound

def validate_chain(root,job,jobs):
    import threading
    from types import SimpleNamespace
    state=SimpleNamespace(root=Path(root),lock=threading.RLock(),workbench_jobs=jobs)
    seen=set()
    while job['kind']=='intro-sound':
        if job['id'] in seen or len(seen)>=50:raise ValueError('The sound revision chain needs review.')
        seen.add(job['id'])
        if prepare(state,job['request'])!=job['request']:raise ValueError('A sound revision changed; rebuild its mix.')
        job=jobs.snapshot(job['request']['intro_job_id'])
    return True

def prepare(state,value):
    from .workbench_jobs import service
    jobs=service(state);intro=jobs.snapshot(value['intro_job_id']);mix=jobs.snapshot(value['mix_job_id'])
    if intro['kind'] not in ('intro','intro-sound') or intro['status']!='complete':raise ValueError('Choose a completed intro set.')
    if mix['kind']!='sound-mix' or mix['status']!='complete':raise ValueError('Finish the approved sound recipe mix first.')
    variant=value.get('variant')
    if type(variant) is not int or variant not in range(len(intro['result']['intros'])):raise ValueError('Choose an intro in this set.')
    database=Store(state.root/'cache/curation/projects.sqlite3');plan=database.get(intro['request']['plan_id']);body=database.get(plan['dataset_id'])
    sound=database.get(mix['request']['plan_id']);artifact=intro['result']['intros'][variant]
    if plan['revision']!=intro['request']['plan_revision'] or body['revision']!=plan['body_revision']:raise ValueError('The body or intro plan changed; use the current previews.')
    if sound['revision']!=mix['request']['plan_revision']:raise ValueError('The recipe mix is obsolete.')
    if sound['original_audio_hash']!=artifact['checksum'] or mix['result']['original_audio_hash']!=artifact['checksum']:
        raise ValueError('Create the mix using this exact intro as its original audio; do not combine a different soundtrack.')
    if abs(sound['duration']-artifact['frame_count']/artifact['fps'])>.001:raise ValueError('The recipe mix must fill this intro exactly.')
    for event in sound['events']:resolve_sound(database.list('sound'),event['asset_id'],event['hash'])
    return {'intro_job_id':intro['id'],'mix_job_id':mix['id'],'variant':variant,'plan_id':plan['id'],'plan_revision':plan['revision'],'body_revision':body['revision'],'sound_plan_id':sound['id'],'sound_plan_revision':sound['revision'],'idempotency_key':value['idempotency_key']}

def run(root,request,folder,stop,jobs):
    import av,hashlib
    from hinglish_cinematic.render import run_ffmpeg
    from hinglish_cut.gpu_lock import gpu_lock
    import threading
    from types import SimpleNamespace
    state=SimpleNamespace(root=Path(root),lock=threading.RLock(),workbench_jobs=jobs)
    # Recheck all saved approvals, versions, hashes and lineage at execution.
    checked=prepare(state,request)
    if checked!=request:raise ValueError('Intro or sound bindings changed before execution.')
    intro=jobs.snapshot(request['intro_job_id']);mix=jobs.snapshot(request['mix_job_id']);index=request['variant'];artifact=intro['result']['intros'][index]
    if file_hash(artifact['path'])!=artifact['checksum'] or file_hash(mix['result']['path'])!=mix['result']['hash']:raise ValueError('A chosen intro or mix changed.')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);partial=folder/'intro.partial.mp4';final=folder/'intro.mp4'
    with gpu_lock(root):
        run_ffmpeg(['-i',artifact['path'],'-i',mix['result']['path'],'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','256k','-ar','48000','-ac','2','-t',str(artifact['frame_count']/artifact['fps']),'-movflags','+faststart',partial],folder,stop)
    def pixels(path):
        with av.open(str(path)) as media:return [hashlib.sha256(f.to_ndarray(format='rgb24').tobytes()).hexdigest() for f in media.decode(video=0)]
    before=pixels(artifact['path']);after=pixels(partial)
    if len(after)!=artifact['frame_count'] or before!=after:raise ValueError('Applying the mix changed intro video frames.')
    with av.open(str(partial)) as media:
        if len(media.streams.audio)!=1 or media.streams.audio[0].sample_rate!=48000:raise ValueError('Expected one 48kHz mixed soundtrack.')
        for frame in media.decode(audio=0):pass
    # Changes during the mux must not promote an obsolete result.
    if prepare(state,request)!=request:raise ValueError('The edit changed during mix attachment.')
    partial.replace(final);result=copy.deepcopy(intro['result'])
    result['intros'][index]={**artifact,'path':str(final),'checksum':file_hash(final),'sound_recipe_status':'applied','sound_mix_job_id':mix['id'],'sound_recipe_id':mix['result']['recipe_id'],'sound_mix_hash':mix['result']['hash'],'video_frames_unchanged':True,'audition_state':'pending'}
    result.update(parent_intro_job_id=intro['id'],changed_variant=index,approval_state='preview')
    (folder/'variant-manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result
