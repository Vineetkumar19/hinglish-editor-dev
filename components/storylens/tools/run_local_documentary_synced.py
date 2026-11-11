"""Durable hidden runner for this one local trial; logs survive chat interruption."""
import json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/reference-analysis/local-documentary-synced'
OUT.mkdir(parents=True,exist_ok=True)
with (OUT/'worker.log').open('w',encoding='utf8') as log:
    worker=subprocess.Popen([sys.executable,str(ROOT/'tools/local_documentary_synced.py'),*sys.argv[1:]],cwd=ROOT,
        stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    (OUT/'process.json').write_text(json.dumps({'worker_pid':worker.pid,'started_unix':time.time()}),encoding='utf8')
    try:code=worker.wait(timeout=1800)
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill','/PID',str(worker.pid),'/T','/F'],capture_output=True)
        code=124
    (OUT/'worker-exit.json').write_text(json.dumps({'code':code,'ended_unix':time.time()}),encoding='utf8')
print('Local synchronized trial exited',code,flush=True)
sys.exit(code)
