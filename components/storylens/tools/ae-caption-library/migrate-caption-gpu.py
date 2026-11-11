"""Owner-authorized migration of ONE waiting caption job onto an idle GPU.

Preserve the request/ASR cache and original insertion identity. Suspend only the
verified waiting worker, finish real GPU inference, then retire that old waiter.
No AE control, service restart, other-job termination, or project save.
"""
import argparse,json,re,subprocess,sys,time
from contextlib import contextmanager
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import psutil
from hinglish_app.caption_compute import priority_gpu_ready
from hinglish_app.caption_native_timing import execute
from hinglish_app.caption_persistence import save
from hinglish_cut.gpu_lock import gpu_lock
parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);args=parser.parse_args()
if not re.fullmatch('[a-f0-9]{32}',args.id):raise ValueError('Choose one saved caption job.')
folder=root/'output/captions/ae-speech'/args.id;status=json.loads((folder/'status.json').read_text('utf8'));lease=json.loads((folder/'worker.json').read_text('utf8'))
if status.get('stage')!='Waiting for direct audio alignment' or status.get('status')!='running':raise ValueError('This job is no longer waiting. No worker was interrupted.')
parent=psutil.Process(lease['pid'])
if abs(parent.create_time()-lease['started']/1000)>2:raise ValueError('The saved caption process identity changed.')
workers=[]
for p in [parent]+parent.children(recursive=True):
    if p.name().lower()!='python.exe':continue
    cmd=p.cmdline()
    if 'hinglish_app.caption_native_timing' in cmd and args.id in cmd and p.memory_info().rss<256*1024*1024:workers.append(p)
if not workers:raise ValueError('No matching waiting caption process was found.')
# The venv launcher is not an inference process. Suspend the actual child first.
workers.sort(key=lambda p:p.pid==parent.pid)
receipt={'id':args.id,'old_waiters':[p.pid for p in workers],'started':time.time(),'mode':'Owner-requested idle-GPU priority admission','other_jobs_changed':False}
@contextmanager
def admission(project):
    with gpu_lock(root/'cache/caption-priority-cuda'):
        while True:
            line=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True,creationflags=subprocess.CREATE_NO_WINDOW).splitlines()[0]
            free,util=[float(x.strip()) for x in line.split(',')]
            if priority_gpu_ready(free,util):
                receipt['admitted_gpu']={'free_mb':free,'utilization':util};print('GPU admitted with '+str(free)+' MiB free',flush=True);break
            save(folder/'status.json',{'id':args.id,'status':'running','stage':'Priority caption waiting for GPU memory','progress':84});time.sleep(1)
        yield
suspended=[];success=False;begin=time.monotonic()
try:
    for p in workers:p.suspend();suspended.append(p)
    print('Preserved original waiting job; starting its cached-audio CUDA alignment',flush=True)
    execute(root,args.id,work_lock=admission)
    result=json.loads((folder/'caption-project.json').read_text('utf8'));final=json.loads((folder/'status.json').read_text('utf8'))
    if final.get('status')!='complete' or result['transcription'].get('device')!='cuda':raise RuntimeError('The GPU result was not confirmed; original waiting job is preserved.')
    success=True;receipt.update({'ok':True,'seconds':time.monotonic()-begin,'transcription':result['transcription']})
    # Existing CEP exit handler leaves a genuinely complete result intact.
    for p in reversed(suspended):
        try:p.terminate()
        except psutil.NoSuchProcess:pass
    print(json.dumps({'ok':True,'seconds':receipt['seconds'],'device':result['transcription']['device'],'words':final['words']}),flush=True)
except Exception as error:
    receipt.update({'ok':False,'error':str(error),'seconds':time.monotonic()-begin});print(str(error),flush=True)
    save(folder/'status.json',status)
    raise
finally:
    if not success:
        for p in reversed(suspended):
            try:p.resume()
            except psutil.NoSuchProcess:pass
    save(folder/'gpu-migration.json',receipt)
