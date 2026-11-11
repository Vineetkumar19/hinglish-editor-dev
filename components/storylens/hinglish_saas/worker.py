"""One private sequential worker. No incoming HTTP or client supplied paths."""
import argparse
import json
import shutil
import os
import subprocess
import signal
import sys
import time
import uuid
from pathlib import Path
from .config import Settings
from .store import Store

ENGINE=Path(__file__).resolve().parents[1]
EXPORT_TYPES={'.mp4','.png','.jpg','.srt','.ass','.txt'}


def worker_environment():
    allowed={'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE','APPDATA','LOCALAPPDATA',
             'PYTHONPATH','PYTHONIOENCODING','HF_HOME','HF_HUB_CACHE','HUGGINGFACE_HUB_CACHE','TORCH_HOME',
             'XDG_CACHE_HOME','CUDA_PATH','CUDA_VISIBLE_DEVICES','CUDA_MODULE_LOADING','OMP_NUM_THREADS','MKL_NUM_THREADS'}
    return {key:value for key,value in os.environ.items() if key.upper() in allowed}


def claim(store):
    with store.connect(immediate=True) as db:
        # This starter intentionally uses one rendering worker, not a fake
        # multi-GPU scheduler. Never claim another job while one is running.
        if db.execute("SELECT id FROM jobs WHERE state='running'").fetchone():return None
        row=db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
        if not row:return None
        db.execute("UPDATE jobs SET state='running',message='Preparing your edit',updated=? WHERE id=?",(time.time(),row['id']))
        return dict(row)


def process_job(store,settings,row):
    if not store.entitlement(row['user_id'])['active']:
        store.execute("UPDATE jobs SET state='failed',message='Subscription expired before processing started',updated=? WHERE id=?",(time.time(),row['id']));return
    if row['tool'] not in settings.enabled_tools:raise ValueError('Tool is disabled on this worker.')
    job_root=settings.data_dir/'work'/row['user_id']/row['id'];job_root.mkdir(parents=True,exist_ok=True)
    source=job_root/'input'/'uploads';source.mkdir(parents=True,exist_ok=True)
    data=json.loads(row['payload']);paths=[]
    for index,upload_id in enumerate(data['upload_ids']):
        upload=store.one('SELECT * FROM uploads WHERE id=? AND user_id=?',(upload_id,row['user_id']))
        if not upload:raise ValueError('Your source upload is no longer available.')
        original=Path(upload['path']).resolve()
        if not original.is_relative_to((settings.data_dir/'uploads'/row['user_id']).resolve()):raise ValueError('Source is outside your upload folder.')
        target=source/(str(index)+original.suffix);shutil.copyfile(original,target);paths.append(str(target))
    # Share no local publishing accounts, learned personal memories, private
    # media or secrets. Explicitly provision licensed production libraries
    # and model paths in this job root before enabling their tools.
    (job_root/'config.cpu.json').write_text(json.dumps({'device':'cpu','asr_model':'Oriserve/Whisper-Hindi2Hinglish-Swift',
        'align_model':'MahmoudAshraf/mms-300m-1130-forced-aligner','judge_model':None,'offline':False}),encoding='utf-8')
    from hinglish_app.server import AppState
    state=AppState(job_root,python_executable=sys.executable,engine_root=ENGINE)
    payload={'mode':row['tool'],'profile':'general','device':'cpu','quality_check':False,
             'script':data['script'],**data['options']}
    engine_id=uuid.uuid4().hex[:12]
    state.jobs[engine_id]={'id':engine_id,'mode':row['tool'],'status':'queued','progress':0,'stage':'Waiting','logs':[],'created':time.time(),'result':None}
    # Execute synchronously; the public request never launches subprocesses.
    state._run_job(engine_id,payload,[],source if paths else None,data['script'])
    result=state.snapshot(engine_id)
    (job_root/'worker-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if result['status']!='complete':raise RuntimeError('The editing engine could not complete this video. Support can inspect the private worker log.')
    found=set()
    for path in (job_root/'output').rglob('*'):
        if not path.is_file() or path.suffix.lower() not in EXPORT_TYPES:continue
        resolved=path.resolve()
        if not resolved.is_relative_to(job_root.resolve()):continue
        if path.name.startswith(('source','conformed')) or '.partial' in path.name:continue
        found.add(resolved)
    if not found:
        raise RuntimeError('No downloadable output was created. The source may contain no detected speech.')
    for path in sorted(found):
        store.execute('INSERT INTO exports VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,row['user_id'],row['id'],path.name,str(path),time.time()))
    store.execute("UPDATE jobs SET state='complete',message='Your edit is ready',updated=? WHERE id=?",(time.time(),row['id']))
    # Original upload stays available; private per-job staging is discarded.
    for path in source.glob('*'):path.unlink(missing_ok=True)


def run_once(settings):
    if not settings.worker_enabled:raise RuntimeError('Explicitly enable the private worker before starting it.')
    store=Store(settings.data_dir,settings.database_url);row=claim(store)
    if not row:return False
    try:
        clean_env=worker_environment()
        if settings.database_url:clean_env['HINGLISH_SAAS_DATABASE_URL']=settings.database_url
        command=[sys.executable,'-m','hinglish_saas.worker','--job',row['id'],'--data-dir',str(settings.data_dir),'--tools',','.join(settings.enabled_tools)]
        with (settings.data_dir/'worker-private.log').open('ab') as log:
            process=subprocess.Popen(command,cwd=ENGINE,env=clean_env,stdout=log,stderr=log,
                start_new_session=os.name!='nt',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:code=process.wait(timeout=settings.job_timeout)
            except subprocess.TimeoutExpired:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
                else:os.killpg(process.pid,signal.SIGKILL)
                process.wait();raise RuntimeError('The edit exceeded the processing time limit.')
            if code:raise RuntimeError('Private rendering process failed.')
    except Exception:
        store.execute("UPDATE jobs SET state='failed',message='This edit could not complete. Contact support with the edit ID.',updated=? WHERE id=?",(time.time(),row['id']))
        raise
    return True


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--job');parser.add_argument('--data-dir',type=Path);parser.add_argument('--tools');args=parser.parse_args()
    if args.job:
        if not args.data_dir or not args.tools:raise ValueError('Private job configuration is missing.')
        settings=Settings(data_dir=args.data_dir,worker_enabled=True,enabled_tools=tuple(args.tools.split(',')),database_url=os.environ.get('HINGLISH_SAAS_DATABASE_URL',''))
        store=Store(settings.data_dir,settings.database_url);row=store.one("SELECT * FROM jobs WHERE id=? AND state='running'",(args.job,))
        if not row:raise ValueError('Private job was not claimed.')
        process_job(store,settings,row);return
    settings=Settings.from_env()
    if args.once:run_once(settings);return
    while True:
        try:worked=run_once(settings)
        except Exception as error:print(type(error).__name__+': worker stopped this edit',flush=True);worked=False
        if not worked:time.sleep(3)


if __name__=='__main__':main()
