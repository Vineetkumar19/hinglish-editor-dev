"""Validated native curation requests over the existing installed Adobe bridge."""
from pathlib import Path
import json,time,shutil
from hinglish_cinematic.curation import Store,file_hash
from .editor_link import _bridge

def prepare(state,value):
    action=value.get('action')
    if action not in ('catalog','inspect','populate','render','intro_variants'):raise ValueError('Choose a supported native curation step.')
    request={'action':action,'idempotency_key':value['idempotency_key']}
    if action=='catalog':return request
    if action=='inspect':
        if not str(value.get('composition_id','')).isdigit():raise ValueError('Choose a composition from the connected project.')
        request.update(composition_id=str(value['composition_id']),project_path=value['project_path'])
        return request
    from .workbench_jobs import service
    prior=service(state).snapshot(value['inspection_id'] if action=='populate' else value.get('comparison_id') or value['population_id'])
    if prior['kind']!='native-curation' or prior['status']!='complete':raise ValueError('Finish the preceding native step first.')
    if action=='intro_variants':
        if prior['request']['action']!='populate':raise ValueError('Choose a populated native body.')
        intro=service(state).snapshot(value['intro_job_id'])
        if intro['kind']!='intro' or intro['status']!='complete':raise ValueError('Render and review the three cinematic previews first.')
        database=Store(state.root/'cache/curation/projects.sqlite3');plan=database.get(intro['request']['plan_id']);bank=database.get(plan['dataset_id'])
        if plan['mode']!='cinematic' or len(plan['plans'])!=3:raise ValueError('Choose the three cinematic introductions.')
        if plan['dataset_id']!=prior['request']['dataset_id'] or bank['revision']!=plan['body_revision'] or bank['revision']!=prior['request']['expected_revision']:
            raise ValueError('The native body and intro plan must use the same current footage revision.')
        from hinglish_cinematic.curation import validate_intros
        validate_intros(plan['plans'],plan['sources'],bank['revision'],'cinematic',plan['category'])
        native=prior['result'];request.update(population_id=prior['id'],intro_job_id=intro['id'],plan_id=plan['id'],plan_revision=plan['revision'],dataset_id=bank['id'],expected_revision=bank['revision'],composition_id=native['composition_id'],project_path=native['project_path'],plans=plan['plans'],sources=plan['sources'],canvas=native['canvas'])
        return request
    if action=='render' and value.get('comparison_id'):
        if prior['request']['action']!='intro_variants':raise ValueError('Choose the saved native comparison project.')
        part=value.get('comparison_part');variants=prior['result']['variants']
        if not isinstance(part,str) or part not in ('intro_A','intro_B','intro_C','trial_A','trial_B','trial_C'):raise ValueError('Choose one of the native intro or trial compositions.')
        kind,label=part.split('_');variant=next(v for v in variants if v['variant']==label)
        request.update(comparison_id=prior['id'],comparison_part=part,population_id=prior['request']['population_id'],composition_id=variant[kind+'_comp_id'],project_path=prior['result']['project_path'],frame_count=variant[kind+'_frames'],canvas=prior['request']['canvas'],discard_lossless_after_preview=True)
        if kind=='trial':
            baseline=None
            for saved in sorted((state.root/'output/workbench').glob('*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True):
                try:record=json.loads(saved.read_text('utf-8'))
                except (ValueError,OSError):continue
                old=record.get('request',{})
                if record.get('kind')=='native-curation' and record.get('status')=='complete' and old.get('action')=='render' and old.get('population_id')==prior['request']['population_id'] and not old.get('comparison_id'):
                    baseline=record;break
            if not baseline:raise ValueError('Render the native body before comparing its trials.')
            reference_skip=variant['intro_frames'] if variant.get('assembly_mode')=='dedicated_slot' else 0
            request.update(body_reference_path=baseline['result']['path'],body_reference_hash=baseline['result']['checksum'],body_reference_job=baseline['id'],intro_frames=variant['intro_frames'],body_reference_skip=reference_skip)
        return request
    if action=='render':
        if prior['request']['action']!='populate':raise ValueError('Choose a populated native project.')
        native=prior['result']
        request.update(population_id=prior['id'],composition_id=native['composition_id'],project_path=native['project_path'],frame_count=native['frame_count'],canvas=native['canvas'])
        return request
    if prior['request']['action']!='inspect':raise ValueError('Choose an inspected template.')
    manifest=Path(prior['result']['manifest_path'])
    manifest_hash=file_hash(manifest)
    if manifest_hash!=prior['result']['manifest_hash']:raise ValueError('The inspected template manifest changed. Inspect it again.')
    saved=json.loads(manifest.read_text('utf-8-sig'))
    if not saved['supported']:raise ValueError('Resolve the template’s missing dependencies or unsupported features first.')
    bank=Store(state.root/'cache/curation/projects.sqlite3').get(value['dataset_id'])
    if bank['revision']!=value['expected_revision']:raise ValueError('Reload the current footage review.')
    rows={r['id']:r for r in bank['candidates']};mapping=value.get('assignments',[])
    if len(mapping)!=len(saved['slots']) or len({r['slot_id'] for r in mapping})!=len(mapping):raise ValueError('Assign each native slot exactly once.')
    selected={r['slot_id']:r for r in mapping};assignments=[];used=set()
    banned=set((bank.get('body') or {}).get('banned',[]))
    for slot in saved['slots']:
        choice=selected.get(slot['slot_id'],{});row=rows.get(choice.get('candidate_id'))
        if not row or row.get('review_state')!='approved' or row['id'] in banned:raise ValueError('Choose approved, unbanned candidates for all native slots.')
        if row['id'] in used:raise ValueError('Use a distinct source candidate for each native slot.')
        used.add(row['id'])
        if row['duration']*slot['fps']+.01<slot['duration_frames']:raise ValueError('A selected candidate is shorter than its native slot.')
        if file_hash(row['source'])!=row['source_sha256']:raise ValueError('An original source changed after review.')
        assignments.append({'slot_id':slot['slot_id'],'candidate_id':row['id'],'path':row['best_clip_path'],'source_hash':file_hash(row['best_clip_path']),'duration':row['duration'],'fit':'contain'})
    request.update(inspection_id=prior['id'],manifest_path=str(manifest),manifest_hash=manifest_hash,project_path=saved['project_path'],composition_id=saved['root_comp_id'],dataset_id=bank['id'],expected_revision=bank['revision'],assignments=assignments)
    return request

def run(root,request,folder,stop,progress):
    from hinglish_cut.gpu_lock import gpu_lock
    from .workbench_jobs import atomic_json
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);action=request['action']
    payload={'type':'reel_recreate','curation_action':action}
    if action!='catalog':payload.update(root_comp_id=request['composition_id'],project_path=request['project_path'])
    if action=='inspect':payload['manifest_path']=str(folder/'template-manifest.json')
    elif action=='populate':
        if file_hash(request['manifest_path'])!=request['manifest_hash']:raise ValueError('The inspected manifest changed.')
        bank=Store(Path(root)/'cache/curation/projects.sqlite3').get(request['dataset_id'])
        if bank['revision']!=request['expected_revision']:raise ValueError('The footage review changed before native population.')
        for row in request['assignments']:
            if file_hash(row['path'])!=row['source_hash']:raise ValueError('Candidate media changed before native population.')
        payload.update(template_path=request['project_path'],expected_manifest_path=request['manifest_path'],assignments=request['assignments'],revision_id=folder.name,output_path=str(folder/'Populated.aep'))
    elif action=='intro_variants':
        database=Store(Path(root)/'cache/curation/projects.sqlite3')
        if database.get(request['dataset_id'])['revision']!=request['expected_revision'] or database.get(request['plan_id'])['revision']!=request['plan_revision']:
            raise ValueError('The body or intro plan changed before native creation.')
        for source in request['sources'].values():
            if file_hash(source['path'])!=source['hash']:raise ValueError('Intro source media changed.')
        payload.update(output_path=str(folder/'Intro_comparisons.aep'),revision_id=folder.name,plans=request['plans'],sources=request['sources'])
    elif action=='render':
        needed=request['canvas'][0]*request['canvas'][1]*request['frame_count']*4+512*1024**2
        if shutil.disk_usage(folder).free<needed:raise ValueError('There is not enough free space for this native lossless preview. Keep the editable project and free space before rendering.')
        payload['output_path']=str(folder/'Native_preview.avi')
    receipt=folder/'native-command.json'
    # All native work is serialized with Storylens GPU/editor work. No second scheduler.
    with gpu_lock(root):
        if stop.is_set():raise InterruptedError('Stopped before native submission.')
        if receipt.exists():row=_bridge(root,'status?id='+json.loads(receipt.read_text())['id'])
        else:
            row=_bridge(root,'command',{'host':'aftereffects','action':'import','payload':payload,'request_id':'curation-workbench-'+folder.name})
            atomic_json(receipt,row)
        progress('Waiting for After Effects confirmation',10)
        while row['status'] in ('queued','sent'):
            # An already-sent native mutation must settle before releasing its lease.
            time.sleep(1);row=_bridge(root,'status?id='+row['id'])
        atomic_json(folder/'native-result.json',row)
        if row['status']!='confirmed':raise ValueError(row.get('error') or 'Native action remains unconfirmed. Check the exact project; it was not replayed.')
    result=row['result']
    if result.get('error'):raise ValueError(result['error'])
    if action=='inspect':
        manifest=json.loads(Path(result['manifest_path']).read_text('utf-8-sig'))
        result.update(slots=manifest['slots'],manifest_hash=file_hash(result['manifest_path']))
    if action=='render':
        rendered=json.loads(result['render_json'])
        if rendered.get('error'):raise ValueError(rendered['error'])
        import av
        with av.open(rendered['path']) as media:count=sum(1 for _ in media.decode(video=0))
        if count!=result['frame_count']:raise ValueError('Native preview frame count did not verify.')
        if request.get('body_reference_path'):
            import hashlib
            reference=request['body_reference_path']
            if file_hash(reference)!=request['body_reference_hash']:raise ValueError('The body reference changed before trial comparison.')
            def pixels(path,skip=0):
                with av.open(path) as media:
                    return [hashlib.sha256(frame.to_ndarray(format='rgb24').tobytes()).hexdigest() for i,frame in enumerate(media.decode(video=0)) if i>=skip]
            expected=pixels(reference,request.get('body_reference_skip',0));actual=pixels(rendered['path'],request['intro_frames'])
            if expected!=actual:raise ValueError('The native trial changed one or more decoded body frames.')
            result.update(body_frames_identical=True,body_frames_compared=len(expected),body_reference_job=request['body_reference_job'])

        from hinglish_cinematic.render import run_ffmpeg
        from hinglish_cut.compute_policy import ffmpeg_h264,heavy_device
        progress('Preparing the browser preview from the native render',90)
        preview=folder/'Native_preview.mp4';temporary=folder/'Native_preview.partial.mp4'
        with gpu_lock(root):
            run_ffmpeg(['-i',rendered['path'],'-map','0:v:0','-map','0:a:0?',*ffmpeg_h264(heavy_device(root),18),'-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-movflags','+faststart',temporary],folder,stop)
        with av.open(str(temporary)) as media:preview_frames=sum(1 for _ in media.decode(video=0))
        if preview_frames!=count:raise ValueError('Browser preview frames differ from the native render.')
        temporary.replace(preview)
        result.update(path=rendered['path'],checksum=file_hash(rendered['path']),decoded_frames=count,preview_path=str(preview),preview_sha256=file_hash(preview))
        if request.get('discard_lossless_after_preview'):
            lossless=Path(rendered['path']).resolve()
            if lossless.parent!=folder.resolve() or lossless.name!='Native_preview.avi':raise ValueError('Unexpected native intermediate path; preserved for review.')
            result.update(native_lossless_sha256=result['checksum'],native_lossless_frames=count,path=str(preview),checksum=result['preview_sha256'],lossless_intermediate_retained=False)
            lossless.unlink()

    return {**result,'native_command_id':row['id'],'approval_state':'preview'}
