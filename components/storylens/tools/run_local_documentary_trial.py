"""Run the local-only trial with an independent hard 30-minute process deadline."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/reference-analysis/local-documentary-trial';OUT.mkdir(parents=True,exist_ok=True)
receipt_path=OUT/'receipt.json'
prior=json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.exists() else {}
start_unix=prior.get('started_unix',time.time())
budget_path=OUT/'budget-start.json'
if not budget_path.exists():budget_path.write_text(json.dumps({'started_unix':start_unix}),encoding='utf-8')
start=time.monotonic()-(time.time()-start_unix)
with (OUT/'worker.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen([sys.executable,str(ROOT/'tools/local_documentary_trial.py'),*sys.argv[1:]],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (OUT/'process.json').write_text(json.dumps({'worker_pid':process.pid,'started_unix':time.time(),'budget_seconds':1800}),encoding='utf-8')
    try:code=process.wait(timeout=max(1,1800-(time.monotonic()-start)))
    except subprocess.TimeoutExpired:
        # Only terminate this specific trial's process tree. Do not stop unrelated editor/model services.
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
        receipt=json.loads((OUT/'receipt.json').read_text(encoding='utf-8')) if (OUT/'receipt.json').exists() else {}
        receipt.update(status='time-limit',elapsed_seconds=time.monotonic()-start,error='Stopped at the approved 30-minute limit')
        (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');code=124
print('Local trial exited with code',code,flush=True)
