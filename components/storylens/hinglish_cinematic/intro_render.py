"""Render validated source spans using Storylens's existing CUDA shot executor."""
from pathlib import Path
import json
from .curation import digest, file_hash, validate_intros


def render_intro(plan, sources, folder, root, stop):
    import av
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.compute_policy import heavy_device
    from .render import render_cuda_shot, run_ffmpeg
    from hinglish_app.workbench_jobs import atomic_json
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    width,height=plan.get('canvas',[720,1280])
    if type(width) is not int or type(height) is not int or min(width,height)<128 or max(width,height)>3840 or width%2 or height%2:
        raise ValueError('Use even canvas dimensions between 128 and 3840 pixels.')
    fps=plan['fps'];cursor=0;files=[];segments=[]
    plan_hash = digest(plan)
    if stop.is_set():
        raise InterruptedError('Intro rendering stopped.')
    for source_id in {span['source_id'] for span in plan['source_spans']}:
        source = sources[source_id]
        if file_hash(source['path']) != source['hash']:
            raise ValueError('A source changed after planning.')
    artifact_receipt = folder / 'artifact.json'
    target = folder / 'intro.mp4'
    try:
        saved = json.loads(artifact_receipt.read_text(encoding='utf-8'))
        if (saved.get('plan_hash') == plan_hash and saved.get('frame_count') == plan['frame_count']
                and saved.get('path') == str(target) and saved.get('checksum') == file_hash(target)):
            return saved
    except (OSError, ValueError):
        pass
    with gpu_lock(root):
        if heavy_device(root)!='cuda':raise ValueError('This intro executor requires the configured CUDA render path.')
        for i,span in enumerate(plan['source_spans']):
            source=sources[span['source_id']]
            if file_hash(source['path'])!=source['hash']:raise ValueError('A source changed after planning.')
            shot={'path':source['path'],'source_in':span['start'],'source_out':span['end'],'speed':1,
                  'duration_frames':span['frames'],'start_frame':cursor,'end_frame':cursor+span['frames']}
            target=folder/f'shot-{i:03d}.mp4';signature=digest({'shot':shot,'source_hash':source['hash'],'canvas':[width,height],'fps':fps})
            receipt=target.with_suffix('.json')
            valid=False
            if target.is_file() and receipt.is_file():
                try:
                    prior = json.loads(receipt.read_text('utf-8'))
                    valid = prior.get('signature') == signature and prior.get('hash') == file_hash(target)
                except (OSError, ValueError):
                    pass
            if not valid:
                silent=folder/f'shot-{i:03d}.silent.mp4';partial=folder/f'shot-{i:03d}.partial.mp4'
                render_cuda_shot({'fps':str(fps),'beat_frames':[]},shot,silent,width,height,'fit',[],0,stop)
                seconds=span['frames']/float(fps)
                with av.open(source['path']) as media:has_audio=bool(media.streams.audio)
                audio_input=['-ss',str(span['start']),'-i',source['path']] if has_audio else ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
                run_ffmpeg(['-i',silent,*audio_input,'-map','0:v:0','-map','1:a:0','-c:v','copy',
                            '-af',f'apad,atrim=duration={seconds},asetpts=PTS-STARTPTS','-ar','48000','-ac','2',
                            '-c:a','aac','-b:a','192k','-t',str(seconds),'-movflags','+faststart',partial],folder,stop)
                with av.open(str(partial)) as verify:actual=sum(1 for _ in verify.decode(video=0))
                if actual!=span['frames']:raise ValueError('An intro shot failed exact frame verification.')
                partial.replace(target)
                atomic_json(receipt, {'signature': signature, 'hash': file_hash(target), 'frames': actual})
            files.append(target);segments.append({**span,'timeline_start_frame':cursor});cursor+=span['frames']
        listing=folder/'join.txt';listing.write_text('\n'.join("file '"+p.name+"'" for p in files),encoding='utf-8')
        partial=folder/'intro.partial.mp4';target=folder/'intro.mp4'
        run_ffmpeg(['-f','concat','-safe','1','-i',listing,'-c:v','copy','-c:a','aac','-ar','48000','-ac','2',
                    '-t',str(cursor/float(fps)),'-movflags','+faststart',partial],folder,stop)
        with av.open(str(partial)) as check:frames=sum(1 for _ in check.decode(video=0))
        if frames!=plan['frame_count']:raise ValueError('The intro failed its complete frame-count gate.')
        partial.replace(target)
        result={'path':str(target),'checksum':file_hash(target),'frame_count':frames,'fps':fps,
                'plan_hash':digest(plan),'body_revision':plan['body_revision'],'segments':segments,
                'approval_state':'preview','sound_recipe_status':'not_applied','native_editable_status':'not_created'}
        atomic_json(artifact_receipt, result)
        return result


def render_package(plans, sources, body_revision, mode, category, folder, root, stop, reusable=()):
    qa=validate_intros(plans,sources,body_revision,mode,category)
    results=[]
    from hinglish_app.workbench_jobs import atomic_json
    import shutil
    for index, plan in enumerate(plans):
        if stop.is_set():
            raise InterruptedError('Intro rendering stopped.')
        variant_dir = Path(folder) / f'variant-{index+1}'
        previous = reusable[index] if index < len(reusable) else None
        if previous and previous.get('plan_hash') == digest(plan):
            source = Path(previous['path']).resolve()
            if (source.is_relative_to((Path(root) / 'output/workbench').resolve()) and source.is_file()
                    and file_hash(source) == previous['checksum'] and previous['frame_count'] == plan['frame_count']):
                variant_dir.mkdir(parents=True, exist_ok=True)
                target = variant_dir / 'intro.mp4'
                partial = variant_dir / 'reuse.partial.mp4'
                shutil.copy2(source, partial)
                if file_hash(partial) != previous['checksum']:
                    raise ValueError('An existing intro changed during reuse.')
                partial.replace(target)
                reused = {**previous, 'path': str(target), 'reused_from': str(source)}
                atomic_json(variant_dir / 'artifact.json', reused)
                results.append(reused)
                continue
        results.append(render_intro(plan, sources, variant_dir, root, stop))
    result={'mode':mode,'body_revision':body_revision,'qa':qa,'intros':results,'approval_state':'preview'}
    from hinglish_app.workbench_jobs import atomic_json
    atomic_json(Path(folder) / 'variant-manifest.json', result)
    return result
