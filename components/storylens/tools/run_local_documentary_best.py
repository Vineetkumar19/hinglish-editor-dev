"""Bound the specific local director worker to 30 minutes without affecting other apps."""
import json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/reference-analysis/local-documentary-best';OUT.mkdir(parents=True,exist_ok=True)
budget=OUT/'budget-start.json'
resume=any(arg in sys.argv for arg in ['--reuse-first-answer','--repair-last-answer','--render-valid-plan'])
start=json.loads(budget.read_text())['started_unix'] if resume and budget.exists() else time.time()
budget.write_text(json.dumps({'started_unix':start}),encoding='utf8')
with (OUT/'worker.log').open('w',encoding='utf8') as log:
 process=subprocess.Popen([sys.executable,str(ROOT/'tools/local_documentary_best.py'),*sys.argv[1:]],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 (OUT/'process.json').write_text(json.dumps({'worker_pid':process.pid,'started_unix':start}),encoding='utf8')
 try:code=process.wait(timeout=max(1,1800-(time.time()-start)))
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
  path=OUT/'receipt.json';r=json.loads(path.read_text()) if path.exists() else {}
  r.update(status='time-limit',error='Stopped at approved 30-minute limit',elapsed_seconds=time.time()-start)
  path.write_text(json.dumps(r,indent=2),encoding='utf8');code=124
print('Local director exited',code,flush=True)
