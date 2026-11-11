"""Finish the authorized C-drive model replacement only after real inference passes.

Resumable coordinator: never interrupts the independent model downloader. Old
weights stay available if downloads, validation, or index conversion fail.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
STORE=Path(r'C:\Ai Models')
STATE=ROOT/'downloads/model-upgrade-c-drive.json'
RECEIPT=STORE/'logs/model-upgrade-completion.json'
TAGS={'planner':'storylens-planner:9b-q6','meaning':'storylens-meaning:14b',
      'embedding':'storylens-embedding:8b-q6'}
ROLES=('planner','meaning','embedding','asr','independent_asr','broll_vision','cutout')
sys.path.insert(0,str(ROOT))


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.writing')
    temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def pending_speech_candidate(state):
    """Do not activate a rejected recognizer while its replacement is evaluated."""
    path=STORE/'logs/hinglish-asr-candidate.json'
    if not path.is_file(): return False
    candidate=read(path)
    selected=state['models'].get('asr',{})
    if candidate.get('path')==selected.get('path'): return False
    if candidate.get('status')=='needs_attention':
        raise RuntimeError('Native Hinglish replacement requires attention: '+str(candidate.get('error','unknown error')))
    return candidate.get('status') in ('downloading','downloaded','validating','adopted')


def ensure_ollama_store():
    source=Path.home()/'.ollama/models'
    if not source.is_junction() or source.resolve()!=(STORE/'ollama').resolve():
        return False
    return True


def import_model(session,name,row):
    files={}
    for weight in row['verified']:
        if not weight['file'].endswith('.gguf'): continue
        source=Path(row['path'])/weight['file']
        digest=weight['sha256']
        blob=STORE/'ollama/blobs'/('sha256-'+digest)
        blob.parent.mkdir(parents=True,exist_ok=True)
        if not blob.exists():
            # Both files are on C:. This registers verified bytes without a
            # second download or second physical copy of the weights.
            os.link(source,blob)
        if blob.stat().st_size!=source.stat().st_size:
            raise ValueError('Existing Ollama blob size mismatch')
        with blob.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:
                raise ValueError('Existing Ollama blob checksum mismatch')
        files[weight['file']]='sha256:'+digest
    options={'num_ctx':4096 if name=='embedding' else 8192}
    if name=='meaning': options.update(num_gpu=41,use_mmap=True)
    response=session.post('http://127.0.0.1:11434/api/create',json={
        'model':TAGS[name],'files':files,'parameters':options,'stream':False},timeout=1200)
    response.raise_for_status()
    if response.json().get('status')!='success':
        raise ValueError('Model import did not succeed: '+str(response.json()))
    response=session.post('http://127.0.0.1:11434/api/show',json={'model':TAGS[name]},timeout=30)
    response.raise_for_status()
    capabilities=response.json().get('capabilities',[])
    required={'planner':('completion','vision'),'meaning':('completion',),'embedding':('embedding',)}[name]
    if not set(required)<=set(capabilities):
        raise ValueError(f'{name} import is missing required capabilities: {capabilities}')
    print('IMPORTED '+TAGS[name],flush=True)


def selection(state):
    roles={key:dict(state['models'][key]) for key in ROLES}
    for key,tag in TAGS.items():
        roles[key]['ollama_model']=tag
        roles[key]['weight_file']=next(f for f in roles[key]['files'] if f.endswith('.gguf') and not f.startswith('mmproj'))
    return {'root':str(STORE),'active':True,'roles':roles,'aliases':{
        'Oriserve/Whisper-Hindi2Hinglish-Swift':roles['asr']['path'],
        'openai/clip-vit-base-patch32':roles['broll_vision']['path']}}


def _reindex(selection_file,receipt):
    import numpy as np
    from hinglish_cut.ollama_embeddings import OllamaEmbeddings
    from hinglish_cut.upgrade_embeddings import StagedEmbeddings
    path=ROOT/'library/creator-profiles/editing-dna.sqlite3'
    if not path.exists(): return
    model=TAGS['embedding']
    db=sqlite3.connect(path)
    try:
        rows=db.execute('SELECT id,text FROM records WHERE model=?',('intfloat/multilingual-e5-small',)).fetchall()
        if not rows: return
        backup=STORE/'backups/editing-dna-before-embedding-upgrade.sqlite3'
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():
            with sqlite3.connect(backup) as target: db.backup(target)
        selected=read(selection_file)['roles']['embedding']
        encoder=StagedEmbeddings(STORE/'cache/upgraded-style-embeddings.sqlite3',
            OllamaEmbeddings(ROOT,model),selected['revision'])
        from hinglish_cut.model_preferences import release_ollama
        release_ollama(ROOT)
        try:
            for start in range(0,len(rows),4):
                batch=rows[start:start+4]
                vectors=encoder.encode([text for _,text in batch])
                with db:
                    db.executemany('UPDATE records SET embedding=?,model=? WHERE id=?',
                        [(np.asarray(v,np.float32).tobytes(),model,key) for (key,_),v in zip(batch,vectors)])
                print(f'REINDEXED {min(start+4,len(rows))}/{len(rows)}',flush=True)
        finally: encoder.close()
        receipt['reindexed_records']=len(rows)
    finally: db.close()


def reindex(selection_file,receipt):
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):_reindex(selection_file,receipt)


def activate(data):
    backup=STORE/'backups/config-before-model-upgrade'
    backup.mkdir(parents=True,exist_ok=True)
    def update(relative,changes):
        path=ROOT/relative
        if path.exists() and not (backup/path.name).exists(): shutil.copy2(path,backup/path.name)
        current=read(path) if path.exists() else {}
        current.update(changes)
        write(path,current)
    update('config.models.local.json',{'planning_model':TAGS['planner'],'vision_model':TAGS['planner'],
        'meaning_model':TAGS['meaning'],'embedding_model':TAGS['embedding'],'context_limit':8192,
        'keep_alive':'30s','release_ollama_before_cuda':True,'device':'cuda'})
    update('config.phase2.json',{'embedding_model':TAGS['embedding'],'judge_model':TAGS['meaning']})
    update('config.broll.local.json',{'vision_model':data['roles']['broll_vision']['repo'],
                                    'device':'cuda','cpu_threads':8})
    update('config.sound.local.json',{'embed_model':TAGS['embedding']})
    meaning=data['roles']['meaning']; speech=data['roles']['independent_asr']
    for file in ('models/meaning-upgrade.json','models/meaning-models.json'):
        update(file,{'speech_path':speech['path'],'speech_revision':speech['revision'],
            'judge_path':str(Path(meaning['path'])/meaning['weight_file']),
            'judge_revision':meaning['revision'],'judge_repo':meaning['repo'],
            'backend':'ollama','ollama_model':TAGS['meaning'],'native_api':True})
    update('config.model_storage.local.json',data)


def main():
    import requests
    session=requests.Session();session.trust_env=False
    receipt=read(RECEIPT) if RECEIPT.exists() else {'status':'waiting_for_downloads','imported':[]}
    if receipt.get('status')=='complete':
        print('Model upgrade already completed.',flush=True);return
    receipt.pop('error',None)
    write(RECEIPT,receipt)
    while True:
        state=read(STATE) if STATE.exists() else {'models':{}}
        failures=[key for key,row in state['models'].items() if row.get('status')=='failed']
        if failures: raise RuntimeError('Download failed; old models retained: '+', '.join(failures))
        if ensure_ollama_store():
            for name in TAGS:
                row=state['models'].get(name,{})
                if row.get('status')=='downloaded' and name not in receipt['imported']:
                    import_model(session,name,row)
                    receipt['imported'].append(name);write(RECEIPT,receipt)
        runtime=STORE/'logs/speech-runtime-ready.json'
        if all(state['models'].get(key,{}).get('status')=='downloaded' for key in ROLES) and len(receipt['imported'])==3:
            if runtime.exists() and read(runtime).get('ready'):
                if not pending_speech_candidate(state): break
                receipt['status']='waiting_for_hinglish_validation'
            else:
                receipt['status']='waiting_for_speech_runtime'
            write(RECEIPT,receipt)
        time.sleep(20)
    data=selection(state)
    pending=STORE/'pending-model-selection.json'
    write(pending,data)
    os.environ.update(STORYLENS_MODEL_SELECTION=str(pending),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    from hinglish_cut.model_storage import configure
    configure(ROOT)
    receipt['status']='validating';write(RECEIPT,receipt)
    for check in ('meaning','planner','embedding','asr','independent_asr','broll_vision','cutout'):
        output=STORE/'logs'/('upgrade-validation-'+check+'.json')
        if output.exists():
            previous=read(output)
            selected=data['roles'][check]
            if previous.get('passed') and previous.get('model_path')==selected['path'] and previous.get('model_revision')==selected.get('revision'):
                continue
        subprocess.run([sys.executable,'-E','-X','utf8',str(ROOT/'tools/validate_model_upgrade.py'),
            '--check',check],cwd=ROOT,check=True,timeout=1800)
    edit_proof=ROOT/'output/validation/new-laptop/edit-pipeline-upgrade-inference.json'
    previous=read(edit_proof) if edit_proof.exists() else {}
    if not (previous.get('passed') and previous.get('asr_path')==data['roles']['asr']['path']
            and previous.get('asr_revision')==data['roles']['asr']['revision']):
        subprocess.run([sys.executable,'-E','-X','utf8',str(ROOT/'tools/validate_laptop_edit.py'),
            '--upgrade'],cwd=ROOT,check=True,timeout=900)
    reindex(pending,receipt)
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):
        activate(data)
        receipt['status']='activated_cleanup_pending';write(RECEIPT,receipt)
        subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'tools/retire_replaced_models.ps1')],
            cwd=ROOT,check=True,timeout=1200)
    receipt.update(status='complete',storage_root=str(STORE))
    write(RECEIPT,receipt)
    print('MODEL_UPGRADE_VALIDATED_ACTIVATED_AND_OLD_WEIGHTS_RETIRED',flush=True)


if __name__=='__main__':
    try: main()
    except Exception as error:
        data=read(RECEIPT) if RECEIPT.exists() else {}
        data.update(status='needs_attention',error=f'{type(error).__name__}: {error}')
        write(RECEIPT,data)
        raise
