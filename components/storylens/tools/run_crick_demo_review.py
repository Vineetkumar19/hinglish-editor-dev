"""Sequential, light-memory final pass after the main demo render completes."""
import subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/reference-analysis/crick-edit-editing-style/demo'
deadline=time.time()+1800
while time.time()<deadline:
    log=(OUT/'render.log').read_text(encoding='utf-8',errors='replace')
    if 'Complete:' in log and (OUT/'CRICK_EDIT_60S.mp4').exists():break
    error=(OUT/'render-error.log').read_text(encoding='utf-8',errors='replace')
    if 'Traceback' in error:raise RuntimeError(error)
    time.sleep(3)
else:raise TimeoutError('Main demo export did not complete')
for chapter in [1,6]:
    print(f'Review correction: chapter {chapter}',flush=True)
    subprocess.run([sys.executable,str(ROOT/'tools/render_crick_edit_demo.py'),'--chapter',str(chapter)],cwd=ROOT,check=True)
print('Balancing audio and checking final encoded frames',flush=True)
subprocess.run([sys.executable,str(ROOT/'tools/finish_crick_edit_demo.py')],cwd=ROOT,check=True)
print('REVIEW COMPLETE',flush=True)
