"""Persistent small tool jobs, serialized; imported without starting workers."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy
import json
import os
import re
import subprocess
import threading
import time
import uuid
import hashlib
import math
import shutil
from hinglish_cinematic.curation import Store, digest, file_hash

from .user_messages import problem

def replace_retry(source,target):
    # Windows readers/AV can briefly hold the destination without DELETE sharing.
    # Keep the old committed file intact until replacement succeeds.
    for attempt in range(12):
        try:Path(source).replace(target);return
        except PermissionError:
            if attempt==11:raise
            time.sleep(min(.25,.025*2**attempt))

def atomic_json(path,value):
    path=Path(path);temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    replace_retry(temp,path)


class WorkbenchJobs:
    def __init__(self,root,engine_root=None):
        self.engine_root = Path(engine_root or root).resolve()
        self.root=Path(root).resolve();self.base=self.root/'output/workbench'
        self.lock=threading.RLock();self.rows={};self.stops={};self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='workbench')
    def _file(self,id):
        if not isinstance(id,str) or not re.fullmatch('[a-f0-9]{32}',id):raise ValueError('Choose a saved tool result.')
        return self.base/id/'job.json'
    def save(self,id,**values):
        with self.lock:
            self.rows[id].update(copy.deepcopy(values));file=self._file(id);file.parent.mkdir(parents=True,exist_ok=True)
            atomic_json(file,self.rows[id])
    def snapshot(self,id):
        with self.lock:
            if id not in self.rows:
                row=json.loads(self._file(id).read_text('utf-8'))
                if row['status'] in ('queued','running'):row.update(status='interrupted',stage='Stopped after app restart; completed files are kept.')
                self.rows[id]=row
            return copy.deepcopy(self.rows[id])
    def start(self,kind,value):
        if kind not in ('slow-motion-scan', 'slow-motion-render', 'footage','color-grade','intro','body','sound-mix','trials','visual-index','source-proxy','native-curation','intro-sound','sound-loop','match-cut','gaming-intro'):raise ValueError('Choose a supported workbench tool.')
        if not isinstance(value,dict):raise ValueError('Choose tool settings.')
        if kind=='footage':
            paths=value.get('paths',[]);folder=value.get('folder','')
            if not isinstance(paths,list) or any(not isinstance(p,str) for p in paths) or not isinstance(folder,str):raise ValueError('Choose video files or a folder.')
            count=value.get('best_count',20)
            if count is not None and (type(count) is not int or not 1<=count<=100):raise ValueError('Choose between 1 and 100 Best Shots, or all candidates.')
        if kind=='match-cut':
            from hinglish_cinematic.match_cut import settings
            settings(value)
        id=digest({'kind':kind,'key':value['idempotency_key']})[:32] if value.get('idempotency_key') else uuid.uuid4().hex
        with self.lock:
            if self._file(id).exists():
                previous=self.snapshot(id)
                if previous['kind']!=kind or digest(previous['request'])!=digest(value):raise ValueError('This render retry key belongs to different settings.')
                return previous
            if any(j['status'] in ('queued','running') for j in self.rows.values()):raise ValueError('Wait for the current footage or grade operation, or stop it first.')
            self.rows[id]={'id':id,'kind':kind,'status':'queued','stage':'Queued','progress':0,'request':value,'created':time.time()};self.stops[id]=threading.Event();self.save(id)
            self.pool.submit(self.run,id)
            return self.snapshot(id)
    def cancel(self,id):
        row=self.snapshot(id)
        if id in self.stops:self.stops[id].set()
        return row
    def resume(self,id):
        with self.lock:
            row=self.snapshot(id)
            if row['status'] not in ('failed','interrupted'):raise ValueError('Only failed or interrupted jobs can be resumed.')
            if row['kind'] not in ('slow-motion-scan', 'slow-motion-render', 'footage', 'visual-index', 'source-proxy', 'intro', 'body', 'trials', 'sound-mix', 'intro-sound', 'sound-loop', 'match-cut', 'gaming-intro'):
                raise ValueError('This job cannot be safely resumed. Check the saved result before starting another.')
            if any(j['status'] in ('queued','running') for j in self.rows.values()):raise ValueError('Wait for the active workbench operation.')
            attempts=row.get('resume_attempts',0)
            if attempts>=3:raise ValueError('Three recovery attempts failed. Review the recorded error before starting a new job.')
            self.stops[id]=threading.Event()
            self.save(id,status='queued',stage='Resuming saved work',resume_attempts=attempts+1,error=None)
            self.pool.submit(self.run,id)
            return self.snapshot(id)
    def run(self,id):
        try:
            self.save(id,status='running',stage='Reading tool settings')
            row=self.snapshot(id)
            if row['kind']=='footage':result=self.footage(id,row['request'])
            elif row['kind']=='gaming-intro':
                from .gaming_intro import run
                result=run(self.root,self.engine_root,row['request'],self.base/id,self.stops[id],
                           lambda stage,progress:self.save(id,stage=stage,progress=progress))
            elif row['kind']=='match-cut':
                from hinglish_cinematic.match_cut import run
                result=run(self.root,row['request'],self.base/id,self.stops[id],lambda stage,progress:self.save(id,stage=stage,progress=progress),gpu_root=self.engine_root)
            elif row['kind'] in ('slow-motion-scan', 'slow-motion-render'):
                from . import selective_slow_motion
                progress = lambda stage, percent: self.save(id, stage=stage, progress=percent)
                if row['kind'] == 'slow-motion-scan':
                    result = selective_slow_motion.analyze(row['request'], self.stops[id], progress, cache_root=self.root/'cache/slow-motion-analysis')
                else:
                    result = selective_slow_motion.render(self.root, row['request'], self.base/id, self.stops[id], progress, gpu_root=self.engine_root)
            elif row['kind']=='native-curation':
                from .native_curation import run
                result=run(self.root,row['request'],self.base/id,self.stops[id],lambda stage,progress:self.save(id,stage=stage,progress=progress))
            elif row['kind']=='source-proxy':
                from hinglish_cinematic.source_proxy import run_proxy
                result=run_proxy(self.root,row['request'],self.base/id,self.stops[id],lambda stage,progress:self.save(id,stage=stage,progress=progress))
            elif row['kind']=='visual-index':
                from hinglish_cinematic.visual_search import run_visual
                result=run_visual(self.root,row['request'],self.base/id,self.stops[id],lambda stage,progress:self.save(id,stage=stage,progress=progress))
            elif row['kind']=='sound-loop':
                from hinglish_cinematic.sound_loop import render_loop
                self.save(id,stage='Preparing the ambience loop for audition',progress=20)
                result=render_loop(self.root,row['request'],self.base/id,self.stops[id])
            elif row['kind']=='sound-mix':
                from hinglish_cinematic.sound_mix import mix
                from hinglish_cinematic.curation import resolve_sound,file_hash
                database=Store(self.root/'cache/curation/projects.sqlite3');saved=database.get(row['request']['plan_id'])
                if saved['kind']!='sound-plan' or saved['revision']!=row['request']['plan_revision']:raise ValueError('The mix plan changed while queued.')
                for event in saved['events']:resolve_sound(database.list('sound'),event['asset_id'],event['hash'])
                if file_hash(saved['original_audio'])!=saved['original_audio_hash']:raise ValueError('Original audio changed before mixing.')
                result=mix(saved,saved['original_audio'],saved['dialogue_activity'],self.base/id,self.stops[id])
            elif row['kind']=='body':
                from hinglish_cinematic.body_render import render_body
                result=render_body(self.root,row['request']['dataset_id'],row['request']['expected_revision'],self.base/id,self.stops[id])
            elif row['kind']=='trials':
                from .assembly_service import render_trials
                self.save(id,stage='Rendering body and verifying comparison trials',progress=10)
                result=render_trials(self.root,row['request'],self.base/id,self.stops[id],self)
            elif row['kind']=='intro-sound':
                from .intro_sound import run
                result=run(self.root,row['request'],self.base/id,self.stops[id],self)
            elif row['kind']=='intro':
                from hinglish_cinematic.intro_render import render_package
                saved=Store(self.root/'cache/curation/projects.sqlite3').get(row['request']['plan_id'])
                if saved['kind']!='intro':raise ValueError('Choose a saved intro plan.')
                body=Store(self.root/'cache/curation/projects.sqlite3').get(saved['dataset_id'])
                if saved['revision']!=row['request']['plan_revision'] or body['revision']!=row['request']['body_revision']:
                    raise ValueError('The body or intro plan changed while queued. Review the new revision before rendering.')
                from .intro_service import validate_saved
                validate_saved(self.root,saved['id'],row['request']['plan_revision'],row['request']['body_revision'])
                self.save(id,stage='Rendering and verifying intro frames',progress=10)
                reusable = []
                if saved.get('reuse_job_id'):
                    previous = self.snapshot(saved['reuse_job_id'])
                    if previous['kind'] == 'intro' and previous['status'] == 'complete':
                        reusable = previous['result']['intros']
                result = render_package(saved['plans'], saved['sources'], saved['body_revision'], saved['mode'],
                                        saved['category'], self.base/id, self.root, self.stops[id], reusable=reusable)
                validate_saved(self.root,saved['id'],row['request']['plan_revision'],row['request']['body_revision'])
            else:
                from .resolve_grade import apply_grade
                result=apply_grade(self.root,row['request'],self.base/id)
            if self.stops[id].is_set():raise InterruptedError('Stopped. Completed files are kept.')
            self.save(id,status='complete',stage='Ready',progress=100,result=result,finished=time.time())
        except Exception as error:
            self.save(id,status='cancelled' if self.stops[id].is_set() else 'failed',stage='Stopped',error=problem(error,feature={'footage':'Cinematic Footage','match-cut':'Match Cut Finder','color-grade':'Color Grade','intro':'Intro Create','gaming-intro':'Intro Create','body':'Story body','sound-mix':'Sound recipe','trials':'Intro trials'}.get(self.rows[id]['kind'],'Workbench')))
    def footage(self,id,value):
        from hinglish_cinematic.planner import VIDEO_EXTENSIONS,_content_fingerprint
        from hinglish_cinematic.footage import inspect,select_unique
        from hinglish_cinematic.footage_review import write_review
        from hinglish_cinematic.source_proxy import proxy_id
        from hinglish_cinematic.media_index import display_orientation, inspect_source
        from fractions import Fraction
        from hinglish_cut.gpu_lock import gpu_lock
        from hinglish_cut.compute_policy import ffmpeg_h264,heavy_device
        from .downloader import probe,export_timeline
        import imageio_ffmpeg
        stop=self.stops[id];paths=list(value.get('paths',[]))
        if value.get('folder'):
            folder=Path(value['folder']).resolve()
            if not folder.is_dir():raise ValueError('The footage folder is unavailable.')
            for p in folder.rglob('*'):
                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:
                    paths.append(str(p))
                    if len(set(paths))>100:raise ValueError('Choose a folder with up to 100 local videos.')
            paths.sort()
        paths=list(dict.fromkeys(str(Path(p).resolve()) for p in paths))
        if not 1<=len(paths)<=100:raise ValueError('Choose between 1 and 100 local videos.')
        output=self.base/id;hashes=set();rows=[];skipped=[];warnings=[];source_outcomes=[]
        store=Store(self.root/'cache/curation/projects.sqlite3')
        for n,path in enumerate(paths,1):
            if stop.is_set():raise InterruptedError('Footage collection stopped.')
            self.save(id,stage=f'Reading video {n} of {len(paths)}',progress=round(n/len(paths)*45))
            try:
                if not Path(path).is_file() or Path(path).suffix.lower() not in VIDEO_EXTENSIONS:raise ValueError('Missing file or unsupported video extension')
                content_hash=_content_fingerprint(path,stop)
                if content_hash in hashes:
                    skipped.append({'path':path,'reason':'Exact duplicate video'})
                    source_outcomes.append({'path':path,'hash':content_hash,'status':'duplicate'});continue
                hashes.add(content_hash)
                metadata_key=digest({'source_hash':content_hash,'analysis_version':'source-pts-v1'})
                source_record=store.cached(metadata_key)
                if source_record is None:
                    source_record=inspect_source(path,stop)
                    store.cached(metadata_key,source_record)
                source_record['original_uri']=path
                source_folder=output/'sources';source_folder.mkdir(exist_ok=True)
                (source_folder/(content_hash+'.json')).write_text(json.dumps(source_record),encoding='utf-8')
                cache_key=digest({'source_hash':content_hash,'analysis_version':'temporal-quality-v4-explanations','model':'none','settings':{'sample_seconds':.5,'duration':5}})
                regions=store.cached(cache_key)
                cache_hit=regions is not None
                if regions is None:
                    regions=inspect(path,stop,lambda message:None)
                    store.cached(cache_key,regions)
                orientation = display_orientation(source_record['width'], source_record['height'],
                                                  source_record['rotation'], Fraction(source_record.get('sample_aspect_ratio', '1')))
                for r in regions:
                    r['orientation'] = orientation
                    r['source']=path
                    r['source_sha256']=content_hash
                    r['id']=hashlib.sha256((content_hash+':'+str(r['start'])).encode()).hexdigest()[:20]
                    r.update(source_id=content_hash,proxy_id=proxy_id(content_hash),phase_tags=[],review_state='unreviewed',short=r['duration']<5,
                             analysis_cache_key=cache_key,semantic_status='needs_review')
                    tb=Fraction(source_record['timebase'])
                    r.update(in_pts=source_record['origin_pts']+round(Fraction(str(r['start']))/tb),
                             out_pts=source_record['origin_pts']+round(Fraction(str(r['start']+r['duration']))/tb),
                             timebase=source_record['timebase'],capture_time=source_record['capture_time'],
                             time_confidence=source_record['time_confidence'],
                             handles={'before_seconds':min(1,r['start']),'after_seconds':max(0,min(1,source_record['duration']-r['start']-r['duration']))})
                source_outcomes.append({'path':path,'hash':content_hash,'status':'analyzed','candidate_count':len(regions),'cache_hit':cache_hit})
            except InterruptedError:raise
            except Exception as e:
                if stop.is_set():raise InterruptedError('Footage collection stopped.')
                skipped.append({'path':path,'reason':str(e)});source_outcomes.append({'path':path,'status':'failed','error':str(e)});continue
            rows.extend(regions)
        (output/'source-outcomes.json').write_text(json.dumps(source_outcomes,indent=2),encoding='utf-8')
        duplicate_evidence=[]
        best,extras,duplicates=select_unique(rows,value.get('best_count',20),duplicate_evidence=duplicate_evidence)
        if not best:raise ValueError('No usable unique shots were found. Try better-exposed or different footage.')
        self.save(id,stage='Saving unique shots',progress=48)
        assets=[];selected=[('Best Shots',r) for r in best]+[('Extras',r) for r in extras]
        (output / 'Best Clip' / 'Review').mkdir(parents=True, exist_ok=True)
        for orientation in ('Horizontal', 'Vertical'):
            for folder in (output / 'Best Shots', output / 'Extras',
                           *(output / 'Best Clip' / bank for bank in ('All', 'Selected', 'Unused'))):
                (folder / orientation).mkdir(parents=True, exist_ok=True)
        # The GPU queue serializes encodes with the rest of Storylens. Decoding
        # and tiny visual descriptors are bounded I/O/analysis, not model calls.
        with gpu_lock(self.root):
            device=heavy_device(self.root)
            verified_sources=set()
            for n,(group,row) in enumerate(selected,1):
                if stop.is_set():raise InterruptedError('Footage collection stopped.')
                if row['source'] not in verified_sources:
                    if _content_fingerprint(row['source'],stop)!=row['source_sha256']:raise ValueError('A source video changed after analysis. Start a new scan; completed files are kept.')
                    verified_sources.add(row['source'])
                orientation = row['orientation']
                clip_folder = output / group / orientation
                clip_folder.mkdir(parents=True, exist_ok=True)
                dest = clip_folder / (row['id'] + '.mp4')
                partial = dest.with_suffix('.part.mp4')
                frame_count=max(1,math.floor(row['duration']*30)) if row['short'] else 150
                clip_receipt=dest.with_suffix('.verified.json')
                if dest.exists():
                    import av
                    with av.open(str(dest)) as verify:existing_frames=sum(1 for _ in verify.decode(video=0))
                    actual_hash=file_hash(dest)
                    prior=json.loads(clip_receipt.read_text('utf-8')) if clip_receipt.exists() else None
                    if existing_frames!=frame_count or prior and prior.get('sha256')!=actual_hash:
                        replace_retry(dest,dest.with_suffix('.invalid-'+uuid.uuid4().hex+'.mp4'))
                if not dest.exists():
                    args=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-y','-ss',str(row['start']),'-i',row['source'],'-t',str(row['duration']),'-map','0:v:0','-map','0:a:0?','-vf','fps=30:start_time=0:eof_action=pass','-frames:v',str(frame_count),*ffmpeg_h264(device,18),'-pix_fmt','yuv420p','-ar','48000','-c:a','aac','-b:a','256k','-threads','2','-movflags','+faststart',str(partial)]
                    proc=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    try:
                        while True:
                            try:_,error=proc.communicate(timeout=.5);break
                            except subprocess.TimeoutExpired:
                                if stop.is_set():raise InterruptedError('Footage collection stopped.')
                        if proc.returncode:raise RuntimeError(error.decode('utf-8',errors='replace')[-2500:])
                        info=probe(partial)
                        if abs(info['duration']-row['duration'])>.2:raise ValueError('A shot duration did not match its selected range.')
                        import av
                        with av.open(str(partial)) as verify:
                            actual_frames=sum(1 for _ in verify.decode(video=0))
                        if actual_frames!=frame_count:raise ValueError(f"Shot {row['id']} produced {actual_frames} frames; expected {frame_count}. Source: {row['source']} at {row['start']}s.")
                        replace_retry(partial,dest)
                    finally:
                        if proc.poll() is None:proc.kill();proc.communicate()
                        partial.unlink(missing_ok=True)
                atomic_json(clip_receipt,{'sha256':file_hash(dest),'frames':frame_count,'source_hash':row['source_sha256'],'start':row['start']})
                info=probe(dest);xml=export_timeline(dest,info,'video')
                # export_timeline's standard filename is per folder: save one
                # unique XML per clip so no preceding shot's timeline is lost.
                xml_target=dest.with_suffix('.xml');xml.replace(xml_target)
                poster=dest.with_suffix('.jpg')
                if not poster.is_file():
                    import av
                    with av.open(str(dest)) as container:
                        frame=next(container.decode(video=0));image=frame.to_image();image.thumbnail((320,240));image.save(poster,quality=82)
                assets.append({**{k:v for k,v in row.items() if k!='signature'},'group':group,'path':str(dest),'poster':str(poster),'xml':str(xml_target),'duration':info['duration']})
                filename=f"BC_{row['id']}__unclassified__{round(row['start']*1000):09d}-{round((row['start']+row['duration'])*1000):09d}.mp4"
                all_path = output / 'Best Clip' / 'All' / orientation / filename
                all_path.parent.mkdir(parents=True, exist_ok=True)
                if not all_path.exists():shutil.copy2(dest,all_path)
                unused_path = output / 'Best Clip' / 'Unused' / orientation / filename
                unused_path.parent.mkdir(parents=True, exist_ok=True)
                if not unused_path.exists():shutil.copy2(dest,unused_path)
                assets[-1].update(best_clip_path=str(all_path),filename=filename,output_frames=max(1,math.floor(row['duration']*30)) if row['short'] else 150,output_fps=30)
                manifest={'version':1,'assets':assets,'selection_method':'Measured detail, exposure and stability; temporal perceptual similarity, not semantic subject identity.', 'duplicate_windows':duplicates,'duplicate_evidence':duplicate_evidence,'skipped':skipped}
                atomic_json(output/'footage-bank.json',manifest)
                review=output/'Best Clip'/'Review'
                (review/'candidate_manifest.json').write_text(json.dumps({**manifest,'source_outcomes':source_outcomes,'approval_state':'candidate_review'},indent=2),encoding='utf-8')
                from html import escape
                cards=''.join('<article><video controls preload="none" width="240" src="../All/'+escape(a['orientation'] + '/' + a['filename'], quote=True)+'"></video><p>'+escape(a['source'])+' @ '+str(a['start'])+'s; quality '+str(a['score'])+'; semantic review pending</p></article>' for a in assets)
                (review/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Best Clip review</title><h1>Candidate review</h1><p>Unreviewed measured candidates. Selected remains empty until a body plan is approved.</p>'+cards,encoding='utf-8')
                self.save(id,stage=f'Saving shot {n} of {len(selected)}',progress=48+round(n/len(selected)*50),result={'folder':str(output),'assets':assets})
        review=write_review(output, {**manifest,'source_outcomes':source_outcomes,'approval_state':'candidate_review'}, stop)
        return {'folder':str(output),'review':review,'best_count':len(best),'extra_count':len(extras),'duplicate_count':duplicates,'skipped':skipped,'source_outcomes':source_outcomes,'assets':assets,'selection_method':'Visual quality and similarity filtering; semantic selection and human acceptance pending. Different viewpoints of the same subject can remain.'}


def service(state):
    with state.lock:
        if not hasattr(state,'workbench_jobs'):state.workbench_jobs=WorkbenchJobs(state.root,getattr(state,'engine_root',state.root))
        return state.workbench_jobs
