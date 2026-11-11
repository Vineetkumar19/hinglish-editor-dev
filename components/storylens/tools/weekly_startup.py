"""Windows-login launcher for explicitly enabled weekly plans only.

Never enables a plan, edits a video, retries an upload or changes credentials.
The existing extension heartbeat handles internet/Studio readiness after login.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def active_plans(root):
    path=Path(root)/'cache/publisher/weekly-seo.sqlite3'
    if not path.is_file():return False
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        rows=db.execute('SELECT data FROM plans').fetchall()
    return any(p.get('enabled') and p.get('status') not in ('complete','paused','cancelled','needs_review')
        for p in (json.loads(row[0]) for row in rows))


def validate_config(root,config):
    command=config.get('command',[])
    if (not isinstance(command,list) or not all(isinstance(a,str) for a in command) or
        '-m' not in command or command[command.index('-m')+1]!='hinglish_app' or
        '--root' not in command or Path(command[command.index('--root')+1]).resolve()!=Path(root).resolve() or
        '--port' not in command or command[command.index('--port')+1]!='8765' or
        not Path(command[0]).is_file() or Path(config.get('cwd','')).resolve()!=Path(root).resolve()):
        raise ValueError('The saved Storylens startup command does not match this workspace.')


def hidden_launch(command,cwd,log):
    options={}
    if sys.platform=='win32':
        startup=subprocess.STARTUPINFO()
        startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow=0
        options={'startupinfo':startup,'creationflags':subprocess.CREATE_NO_WINDOW}
    return subprocess.Popen(command,cwd=cwd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,**options)


def run(root=ROOT,check_only=False):
    root=Path(root)
    # No enabled plan means no application/browser startup or network request.
    if not active_plans(root):return {'status':'no_enabled_plans','apps_started':[]}
    config=json.loads((root/'work/weekly-startup-config.json').read_text(encoding='utf-8'))
    validate_config(root,config)
    if check_only:return {'status':'configured','apps_started':[],'enabled_plans':True}
    import requests
    session=requests.Session();session.trust_env=False
    base='http://127.0.0.1:8765'
    def healthy():
        try:return 'weekly_seo_browser_v1' in session.get(base+'/api/health',timeout=3).json().get('capabilities',[])
        except (requests.RequestException,ValueError):return False
    started=[];folder=root/'cache/publisher';folder.mkdir(parents=True,exist_ok=True)
    with (folder/'weekly-startup.log').open('ab') as log:
        if not healthy():
            with socket.socket() as probe:
                probe.settimeout(2)
                occupied=probe.connect_ex(('127.0.0.1',8765))==0
            if occupied:
                return {'status':'needs_review','message':'Port8765 is occupied by a service without weekly support. Nothing was stopped.','apps_started':[]}
            hidden_launch(config['command'],config['cwd'],log);started.append('Storylens')
            for _ in range(40):
                if healthy():break
                time.sleep(.5)
            else:raise RuntimeError('Storylens did not become ready. Check weekly-startup.log.')
        token=session.get(base+'/api/bridge',timeout=5).json()['token']
        connected=session.get(base+'/api/local-browser',headers={'X-Hinglish-Token':token},timeout=5).json().get('connected')
    return {'status':'waiting_for_normal_extension_heartbeat','apps_started':started,
        'message':('Due weekly sets resume through the existing connector after internet and Studio are ready.'
                   if connected else 'Open Chrome manually to connect Storylens and resume due weekly sets.')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    folder=ROOT/'cache/publisher';folder.mkdir(parents=True,exist_ok=True)
    import msvcrt
    with (folder/'weekly-startup.lock').open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
        try:
            try:result=run(check_only=args.check)
            except Exception as error:
                result={'status':'needs_review','message':'Weekly startup could not finish. Open Storylens and check the startup details. Your saved plans are kept.',
                    'technical_details':str(error),'apps_started':[]}
            result['checked']=time.time()
            (folder/'weekly-startup-status.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result))
            if result['status']=='needs_review':raise SystemExit(1)
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


if __name__=='__main__':main()
