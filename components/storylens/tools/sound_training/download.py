"""Bounded resumable public-model download. No model execution or live changes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import shutil
import time
import urllib.request

BASE=Path('C:/Ai Models/training/sound-qwen3-14b/base')
OUT=Path(__file__).resolve().parents[2]/'output/sound-training/20261030-qwen3-14b'
REPO='https://huggingface.co/unsloth/Qwen3-14B-bnb-4bit/resolve/b455922269e4678c84f854fe38a6993d73614a1e/'
FILES=[('model-00001-of-00002.safetensors',4996841286,'bfe83ea0507e41dc677f2886304125ed43d2408af1ae4ee8b759a86d48a82c5f'),
       ('model-00002-of-00002.safetensors',4931923327,'7fc7e11e126568f258d2d0c113477b481323b455a01ad248a55eb693a9c96c12')]

def ranges(size,start,chunk):
    if size<0 or start<0 or start>size or chunk<=0:raise ValueError('Invalid range parameters')
    return [(a,min(size-1,a+chunk-1)) for a in range(start,size,chunk)]

def check_range(status,header,start,end,size,length):
    if status!=206 or header!=f'bytes {start}-{end}/{size}' or length!=end-start+1:
        raise ValueError(f'Incorrect range response: {status}, {header}, length {length}')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(8*1024*1024):h.update(chunk)
    return h.hexdigest()

def atomic(path,value):
    t=path.with_suffix(path.suffix+'.tmp');t.write_text(json.dumps(value,indent=2),encoding='utf-8');t.replace(path)

def main():
    OUT.mkdir(parents=True,exist_ok=True);BASE.mkdir(parents=True,exist_ok=True)
    state_path=BASE/'range-download-state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {}
    tasks=[]
    for name,size,checksum in FILES:
        dest=BASE/name
        if dest.exists():
            if dest.stat().st_size!=size or sha(dest)!=checksum:raise ValueError('Existing final weight file failed its pinned checksum')
            state[name]={'size':size,'checksum':checksum,'verified':True,'prefix':size,'done':[]};continue
        partial=BASE/(name+'.ranged-partial')
        if name not in state:
            prefix=0
            previous=list((BASE/'.cache/huggingface/download').glob('*.'+checksum+'.incomplete'))
            if previous and 0<previous[0].stat().st_size<size:
                shutil.copyfile(previous[0],partial);prefix=previous[0].stat().st_size
            elif partial.exists():raise ValueError('Untracked partial file; refusing to overwrite')
            else:partial.touch()
            state[name]={'size':size,'checksum':checksum,'verified':False,'prefix':prefix,'done':[]}
        s=state[name]
        if s['size']!=size or s['checksum']!=checksum:raise ValueError('Download revision mismatch')
        done={tuple(x) for x in s['done']}
        for a,b in ranges(size,s['prefix'],32*1024*1024):
            if (a,b) not in done:tasks.append((name,a,b,size))
    atomic(state_path,state)
    start=time.monotonic();last=0
    def fetch(task):
        name,a,b,size=task
        if (OUT/'STOP_DOWNLOAD').exists():raise RuntimeError('Owner stopped download')
        req=urllib.request.Request(REPO+name+f'?download=true&range_id={a}',headers={'Range':f'bytes={a}-{b}'})
        failure=None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req,timeout=45) as r:
                    data=r.read(b-a+2)
                    check_range(r.status,r.headers.get('Content-Range'),a,b,size,len(data))
                with (BASE/(name+'.ranged-partial')).open('r+b') as f:
                    f.seek(a);f.write(data);f.flush()
                return name,a,b
            except Exception as e:failure=e
        raise RuntimeError(f'{name} range {a}-{b}: {failure}')
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fetch,t) for t in tasks]
        try:
            for future in as_completed(futures):
                name,a,b=future.result();state[name]['done'].append([a,b]);atomic(state_path,state)
                completed=sum(x['prefix']+sum(b-a+1 for a,b in x['done']) for x in state.values())
                receipt=dict(stage='downloading_training_weights',verified_bytes=0,downloaded_bytes=completed,
                             total_bytes=sum(x[1] for x in FILES),elapsed_seconds=round(time.monotonic()-start,1))
                atomic(OUT/'download-progress.json',receipt)
                if time.monotonic()-last>15:print(json.dumps(receipt),flush=True);last=time.monotonic()
        except BaseException:
            for future in futures:future.cancel()
            raise
    for name,size,checksum in FILES:
        if state[name]['verified']:continue
        partial=BASE/(name+'.ranged-partial')
        actual=sha(partial)
        if partial.stat().st_size!=size or actual!=checksum:
            atomic(OUT/'download-checksum-failure.json',dict(file=name,expected=checksum,actual=actual))
            raise ValueError('Downloaded weight checksum mismatch; preserved partial, training must not start')
        partial.replace(BASE/name);state[name]['verified']=True;atomic(state_path,state)
    receipt=dict(stage='training_weights_verified',files=FILES,sha256_verified=True)
    atomic(OUT/'download-receipt.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
