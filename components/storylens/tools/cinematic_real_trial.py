"""Owner-requested local trial. Never uploads media or posts anything online."""
from pathlib import Path
import json
import time
import wave
from urllib.request import Request,urlopen
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/cinematic-real-trial'


def instrumental(path,seconds=20):
    sr=44100;n=round(sr*seconds);sound=np.zeros((n,2),dtype=np.float64);rng=np.random.default_rng(428)
    def note(start,length,freq,volume,kind='pad'):
        left=round(start*sr);count=min(round(length*sr),n-left)
        if count<=0:return
        t=np.arange(count)/sr
        if kind=='pad':env=np.minimum(1,t/.12)*np.minimum(1,(length-t)/.25);tone=np.sin(2*np.pi*freq*t)+.22*np.sin(4*np.pi*freq*t)
        else:env=np.exp(-t*6)*np.minimum(1,t/.008);tone=np.sin(2*np.pi*freq*t)+.15*np.sin(6*np.pi*freq*t)
        values=volume*env*tone
        sound[left:left+count,0]+=values;sound[left:left+count,1]+=values*.96
    chords=[(220,261.626,329.628),(174.614,220,261.626),(130.813,164.814,195.998),(195.998,246.942,293.665)]
    for bar,start in enumerate(np.arange(0,seconds,2)):
        chord=chords[bar%4]
        for freq in chord:note(float(start),2.1,freq,.045)
        for beat in range(4):note(float(start+beat*.5),.45,chord[0]/2,.1,'pluck')
        for step in range(8):note(float(start+step*.25),.32,chord[step%3]*2,.035,'pluck')
    for beat,start in enumerate(np.arange(0,seconds,.5)):
        left=round(start*sr);count=min(round(.22*sr),n-left);t=np.arange(count)/sr
        kick=np.sin(2*np.pi*(42*t+90*.025*(1-np.exp(-t/.025))))*np.exp(-t*23)*.65
        sound[left:left+count]+=kick[:,None]
        if beat%2:
            noise=rng.normal(size=count);noise=np.diff(noise,prepend=0)
            clap=noise*np.exp(-t*35)*.08;sound[left:left+count]+=clap[:,None]
    for start in np.arange(.25,seconds,.25):
        left=round(start*sr);count=min(round(.06*sr),n-left);t=np.arange(count)/sr
        noise=rng.normal(size=count);hat=np.diff(noise,prepend=0)*np.exp(-t*100)*.025
        sound[left:left+count]+=hat[:,None]
    fade=np.minimum(1,np.arange(n)/(.03*sr))*np.minimum(1,(n-1-np.arange(n))/(.3*sr))
    sound*=fade[:,None];sound*=.88/max(.88,float(np.max(np.abs(sound))))
    with wave.open(str(path),'wb') as file:
        file.setparams((2,2,sr,0,'NONE','not compressed'));file.writeframes((sound*32767).astype('<i2').tobytes())


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    song=OUT/'original-preview-instrumental.wav';instrumental(song)
    (OUT/'MUSIC-NOTE.txt').write_text('Original procedural instrumental created locally for this private editing trial. No creator-reference audio or downloaded song samples were used.\n',encoding='utf-8')
    inventory=json.loads((ROOT/'output/cinematic-trial-inventory.json').read_text(encoding='utf-8'))
    eligible=[row for row in inventory if 'path' in row and 6<=row['duration']<=20]
    indices=np.linspace(0,len(eligible)-1,min(12,len(eligible))).round().astype(int)
    sources=[eligible[i]['path'] for i in sorted(set(indices))]
    token=json.loads((ROOT/'cache/app/bridge.json').read_text(encoding='utf-8'))['token']
    def api(path,body=None):
        request=Request('http://127.0.0.1:8769'+path,data=json.dumps(body).encode() if body is not None else None,
                        headers={'Content-Type':'application/json','X-Hinglish-Token':token})
        with urlopen(request,timeout=20) as response:return json.load(response)
    def wait(job,route):
        last='';deadline=time.monotonic()+1200
        while job['status'] in ('queued','running'):
            if time.monotonic()>deadline:
                if route=='cinematic':api('/api/cinematic/cancel',{'id':job['id']})
                raise RuntimeError('Trial exceeded the time allowance and was cancelled')
            stage=job.get('stage',job['status'])
            if stage!=last:print(stage,flush=True);last=stage
            time.sleep(1);job=api('/api/'+route+'/jobs/'+job['id'])
        if job['status']!='complete':raise RuntimeError(job.get('error',job.get('stage','Failed')))
        return job
    print(f'Using {len(sources)} owner-provided 4K/5K shots, one at a time. Original 20s instrumental.',flush=True)
    started=time.perf_counter()
    beat=wait(api('/api/beats/analyze',{'path':str(song),'density':'medium','fps':24}),'beats')
    base=wait(api('/api/cinematic/assemble',{'beat_id':beat['id'],'source_paths':sources,'pace':'cinematic',
        'fps':24,'max_shots':12,'max_shot':5,'aspect':'16:9','resolution':'1080','framing':'fit',
        'allow_slow':True,'allow_fast':True,'allow_reuse':False,'split_music':True}),'cinematic')
    print('Clean assembly complete. Rendering a separate light punch + flash version.',flush=True)
    effects=wait(api('/api/cinematic/effects',{'id':base['id'],'effects':['punch','flash'],'effect_amount':4}),'cinematic')
    receipt={'source_folder':r'E:\Danghar with sneha\Videos','source_files':sources,
             'music':str(song),'music_origin':'Original procedural instrumental; no third-party reference audio',
             'elapsed_seconds':round(time.perf_counter()-started,2),'clean':base,'effects':effects,
             'view_url':'http://127.0.0.1:8769/cinematic.html?reel='+effects['id']}
    (OUT/'trial-results.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'elapsed_seconds':receipt['elapsed_seconds'],'shot_count':base['result']['shot_count'],
                      'clean':base['result']['preview'],'effects':effects['result']['preview'],'view_url':receipt['view_url']}),flush=True)


if __name__=='__main__':main()
