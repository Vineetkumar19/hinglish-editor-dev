"""One bounded shared GPU queue for music-led reels. No publishing or documentary jobs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy
import json
import threading
import uuid
import re
from hinglish_beats.detect import number
from .planner import inspect_shot, assemble, VIDEO_EXTENSIONS
from .render import render


class CinematicService:
    def __init__(self, root, beats, work_lock=None):
        self.root=Path(root);self.folder=self.root/'output/cinematic-reels'
        self.beats=beats;self.work_lock=work_lock or threading.Lock()
        self.lock=threading.RLock();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='cinematic-reels')
        self.jobs={};self.stops={};self.latest_id=None

    def upload(self,name,stream,length):
        name=Path(str(name or '').replace('\\','/')).name
        if not name or Path(name).suffix.lower() not in VIDEO_EXTENSIONS or not 0<length<=4*1024**3:
            raise ValueError('Choose a supported performance video up to 4 GB')
        folder=self.folder/'performance-shots';folder.mkdir(parents=True,exist_ok=True)
        target=folder/(uuid.uuid4().hex[:12]+'-'+name);partial=target.with_suffix(target.suffix+'.partial')
        try:
            with partial.open('wb') as file:
                while length:
                    block=stream.read(min(1024**2,length))
                    if not block:raise ValueError('Video upload stopped early')
                    file.write(block);length-=len(block)
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True);raise
        return {'path':str(target.resolve()),'name':name}

    def start(self,payload,effects=False,verify_license=None):
        with self.lock:
            if any(j['status'] in ('queued','running') for j in self.jobs.values()):
                raise ValueError('A cinematic reel is already processing; wait or cancel it first')
            if effects:
                parent=self.snapshot(payload.get('id',''))
                if parent['status']!='complete':raise ValueError('Assemble the reel before applying effects')
                # Always render effects from the clean assembly, avoiding effect stacking.
                base_id=parent.get('base_id') or parent['id']
                base=self.snapshot(base_id)
                data=copy.deepcopy(base['result']['plan']);base_folder=base['result']['folder']
            else:
                beat=self.beats.snapshot(payload.get('beat_id',''))
                if beat['status']!='complete':raise ValueError('Detect the music beats first')
                data=beat['plan'];base_folder=None;base_id=None
            key=uuid.uuid4().hex
            if len(self.jobs)>=30:
                # Keep base assemblies needed by effect results; otherwise ask for restart.
                disposable=next((k for k,j in self.jobs.items() if j['status'] in ('failed','cancelled')),None)
                if disposable:self.jobs.pop(disposable);self.stops.pop(disposable,None)
                else:raise ValueError('This session has 30 reels. Restart the local editor for a new session; rendered files stay on disk.')
            self.jobs[key]={'id':key,'status':'queued','stage':'Waiting for the current local edit','progress':0,'base_id':base_id}
            self.stops[key]=threading.Event()
            self.pool.submit(self._run,key,dict(payload),data,base_folder,verify_license)
            return self.snapshot(key)

    def _progress(self,key,message,percent):
        with self.lock:self.jobs[key].update(status='running',stage=message,progress=percent)

    def _run(self,key,payload,data,base_folder,verify_license):
        finished=threading.Event()
        try:
            from hinglish_cut.gpu_lock import gpu_lock
            from hinglish_cut.compute_policy import heavy_device
            with self.work_lock,gpu_lock(self.root):
                payload['device']=heavy_device(self.root)
                stop=self.stops[key]
                if stop.is_set():raise RuntimeError('Cinematic reel cancelled')
                if verify_license:verify_license()
                if verify_license:
                    def watch_license():
                        while not finished.wait(30):
                            try:verify_license()
                            except Exception:
                                with self.lock:self.jobs[key]['license_error']='Editing stopped because this computer could not verify its subscription.'
                                stop.set();return
                    threading.Thread(target=watch_license,name='cinematic-license-watchdog',daemon=True).start()
                if not base_folder:
                    paths=payload.get('source_paths',[])
                    if not isinstance(paths,list) or any(not isinstance(p,str) for p in paths):raise ValueError('Choose performance video files')
                    paths=list(paths)
                    folder=payload.get('performance_folder')
                    if folder:
                        path=Path(folder).resolve()
                        if not path.is_dir():raise ValueError('The performance-shots folder is unavailable')
                        paths+= [str(p.resolve()) for p in sorted(path.iterdir()) if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
                    paths=list(dict.fromkeys(str(Path(p).resolve()) for p in paths))
                    if not 1<=len(paths)<=100:raise ValueError('Choose between 1 and 100 performance shots')
                    if any(not Path(p).is_file() or Path(p).suffix.lower() not in VIDEO_EXTENSIONS for p in paths):
                        raise ValueError('One or more performance videos are unavailable')
                    shots=[];skipped=[]
                    for i,path in enumerate(paths,1):
                        if stop.is_set():raise RuntimeError('Cinematic reel cancelled')
                        self._progress(key,f'Comparing usable sections: shot {i}/{len(paths)}',min(8,i*8//len(paths)))
                        try:shots.append(inspect_shot(path,cancel=stop))
                        except ValueError as error:
                            skipped.append(Path(path).name+': '+str(error));continue
                        if sum(s['duration'] for s in shots)>3600:raise ValueError('Limit performance footage to one hour per reel')
                    if not shots:raise ValueError('None of the selected performance shots has a usable visible section')
                    from hinglish_cut.reelmimic import context as reference_context
                    reference = reference_context(self.root, 'cinematic')
                    if reference:
                        mean = reference.get('measured',{}).get('pacing',{}).get('mean_shot_s')
                        if isinstance(mean,(float,int)) and .25 <= mean <= 30:
                            payload.setdefault('min_shot', max(.25,min(15,mean*.6)))
                            payload.setdefault('max_shot', max(1,min(30,mean*1.6)))
                    data=assemble(data,shots,payload);data['warnings'].extend(skipped)
                    if reference:data['reelmimic_reference']=reference
                    payload['effects']=[]   # assembly never silently applies the second step
                def progress(message,percent):
                    self._progress(key,message,percent)
                target=self.folder/key
                result=render(data,target,payload,progress,stop,base_folder)
                with self.lock:
                    if stop.is_set():raise RuntimeError('Cinematic reel cancelled')
                    self.jobs[key].update(status='complete',stage='Ready to review',progress=100,result=result)
                    receipt=target/'completed-reel.json';partial=target/'completed-reel.partial.json'
                    partial.write_text(json.dumps(self.jobs[key],indent=2),encoding='utf-8');partial.replace(receipt)
                    latest=self.folder/'latest.partial.json';latest.write_text(json.dumps({'id':key}),encoding='utf-8');latest.replace(self.folder/'latest.json')
                    self.latest_id=key
        except Exception as error:
            from hinglish_app.user_messages import failure
            with self.lock:
                cancelled=self.stops[key].is_set() and not self.jobs[key].get('license_error')
                issue=failure(self.jobs[key].get('license_error') or error,feature='Cinematic editing')
                self.jobs[key].update(status='cancelled' if cancelled else 'failed',
                    stage='Stopped at your request. Completed files are kept.' if cancelled else issue['error'],progress=100,**issue)
        finally:finished.set()

    def close(self):
        with self.lock:
            for stop in self.stops.values():stop.set()
        self.pool.shutdown(wait=True,cancel_futures=True)

    def snapshot(self,key):
        with self.lock:
            if key not in self.jobs:
                if not isinstance(key,str) or not re.fullmatch(r'[a-f0-9]{32}',key):raise ValueError('Reel unavailable')
                folder=(self.folder/key).resolve()
                if not folder.is_relative_to(self.folder.resolve()):raise ValueError('Invalid saved reel folder')
                try:
                    saved=json.loads((folder/'completed-reel.json').read_text(encoding='utf-8'))
                    result=saved['result']
                    if saved['id']!=key or saved['status']!='complete' or Path(result['preview']).resolve()!=folder/'CINEMATIC_REEL.mp4' or [Path(p).resolve() for p in result['xml_files']]!=[folder/'CINEMATIC_REEL.xml'] or Path(result['folder']).resolve()!=folder:
                        raise ValueError('Invalid saved reel')
                    if not Path(result['preview']).is_file() or not Path(result['xml_files'][0]).is_file():raise ValueError('Saved reel media is missing')
                    return saved
                except (OSError,KeyError,TypeError,json.JSONDecodeError) as error:raise ValueError('Reel unavailable') from error
            return copy.deepcopy(self.jobs[key])

    def latest(self):
        if not self.latest_id:
            try:self.latest_id=json.loads((self.folder/'latest.json').read_text(encoding='utf-8'))['id']
            except (OSError,KeyError,TypeError,json.JSONDecodeError):raise ValueError('No completed cinematic reel yet. Open Cinematic Reels and assemble your shots first.') from None
        return self.snapshot(self.latest_id)

    def cancel(self,key):
        with self.lock:
            job=self.snapshot(key)
            if job['status'] not in ('queued','running'):raise ValueError('This reel is not processing')
            self.stops[key].set()
        return {'ok':True}

    def video(self,key):
        job=self.snapshot(key)
        if job['status']!='complete':raise ValueError('The reel is not finished')
        return Path(job['result']['preview'])
