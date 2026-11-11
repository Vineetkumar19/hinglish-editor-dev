"""Isolated workbench UI/real-media fixture. No models or native app launches."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hinglish_app.server import serve
from hinglish_cut.gpu_lock import gpu_lock
import imageio_ffmpeg

BASE=ROOT/'output/workbench-20261103';BASE.mkdir(parents=True,exist_ok=True)
APP=BASE/'fixture-app';APP.mkdir(exist_ok=True)
(APP/'config.models.local.json').write_text(json.dumps({'device':'cuda','heavy_workloads_gpu_only':True}),encoding='utf-8')
SHOTS=BASE/'Source videos';SHOTS.mkdir(exist_ok=True)
source=SHOTS/'three-distinct-scenes.mp4'
if not source.exists():
    args=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y']
    for color in ('red','green','blue'):args+=['-f','lavfi','-i',f'color=c={color}:s=480x270:r=30:d=5']
    args+=['-filter_complex','[0:v][1:v][2:v]concat=n=3:v=1:a=0,drawgrid=w=60:h=54:t=2:c=white[v]',
           '-map','[v]','-c:v','h264_nvenc','-preset','p4','-pix_fmt','yuv420p',str(source)]
    with gpu_lock(ROOT):subprocess.run(args,check=True,capture_output=True)
    shutil.copy2(source,SHOTS/'exact-duplicate.mp4')
server,state=serve(APP,0,publish_bridge=False)
receipt={'url':f'http://127.0.0.1:{state.port}/','root':str(APP),'source_folder':str(SHOTS),'pid':os.getpid(),
         'scope':'Actual isolated application, real generated footage and CUDA exports. No native editor or local reasoning model.'}
(BASE/'preview.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt),flush=True)
try:server.serve_forever()
finally:
    if hasattr(state,'workbench_jobs'):
        for stop in state.workbench_jobs.stops.values():stop.set()
        state.workbench_jobs.pool.shutdown(wait=True,cancel_futures=True)
    server.server_close()
