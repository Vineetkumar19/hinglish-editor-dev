"""Evaluate the larger native-Hinglish specialist after Qwen failed script editing.

Downloads run independently. Do not alter the original download state until that
downloader has finished and this candidate passes both inference and real editing.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
STORE=Path(r'C:\Ai Models')
STATE=ROOT/'downloads/model-upgrade-c-drive.json'
PROOF=STORE/'logs/hinglish-asr-candidate.json'
sys.path.insert(0,str(ROOT))


def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.writing')
    temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)


def main():
    from tools.upgrade_laptop_models import configure
    from tools.ranged_download import patch_huggingface
    from huggingface_hub import HfApi,snapshot_download
    configure();patch_huggingface(STORE)
    row=read(PROOF) if PROOF.exists() else {}
    if row.get('status')=='adopted': return
    row.pop('error',None)
    repo='Oriserve/Whisper-Hindi2Hinglish-Prime'
    for attempt in range(5):
        try:
            info=HfApi().model_info(repo,revision=row.get('revision') or 'main',files_metadata=True)
            break
        except Exception:
            if attempt==4: raise
            time.sleep(2**attempt)
    files=sorted(f.rfilename for f in info.siblings if '/' not in f.rfilename
                 and f.rfilename.endswith(('.safetensors','.json','.txt','.model')))
    assert any(name.endswith('.safetensors') for name in files)
    metadata={f.rfilename:f for f in info.siblings}
    path=STORE/'huggingface'/repo.replace('/','--')
    row.update(repo=repo,revision=info.sha,path=str(path),files=files,
        selected_bytes=sum(metadata[name].size for name in files),status='downloading',
        reason='Native Roman-Hinglish output required; Qwen ASR passed transcription but failed actual script matching.')
    write(PROOF,row)
    for attempt in range(5):
        try:
            snapshot_download(repo,revision=info.sha,allow_patterns=files,local_dir=str(path),max_workers=2)
            assert all((path/name).is_file() and (path/name).stat().st_size==metadata[name].size for name in files)
            break
        except Exception:
            if attempt==4: raise
            time.sleep(2**attempt)
    verified=[]
    for name in files:
        meta=metadata[name].lfs
        digest=meta.get('sha256') if isinstance(meta,dict) else getattr(meta,'sha256',None)
        if digest:
            with (path/name).open('rb') as stream:
                assert hashlib.file_digest(stream,'sha256').hexdigest()==digest,'Candidate checksum mismatch'
            verified.append(dict(file=name,sha256=digest))
    row.update(status='downloaded',verified=verified);write(PROOF,row)
    print('HINGLISH_SPECIALIST_DOWNLOAD_AND_SHA256_COMPLETE',flush=True)
    # The other downloader owns its manifest until its final atomic save.
    while True:
        state=read(STATE)
        if (state.get('status')=='downloads_verified_integration_pending'
                and all(state['models'].get(key,{}).get('status')=='downloaded'
                        for key in ('planner','meaning','embedding','asr','independent_asr','broll_vision','cutout'))): break
        time.sleep(20)
    from tools.finish_model_upgrade import selection
    data=selection(state)
    data['roles']['asr']=dict(row)
    data['aliases']['Oriserve/Whisper-Hindi2Hinglish-Swift']=str(path)
    pending=STORE/'native-hinglish-candidate-selection.json';write(pending,data)
    os.environ.update(STORYLENS_MODEL_SELECTION=str(pending),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    inference=STORE/'logs/native-hinglish-candidate-inference.json'
    edit=STORE/'logs/native-hinglish-candidate-edit.json'
    row['status']='validating';write(PROOF,row)
    subprocess.run([sys.executable,'-E','-X','utf8',str(ROOT/'tools/validate_model_upgrade.py'),
        '--check','asr','--output',str(inference)],cwd=ROOT,check=True,timeout=1800)
    subprocess.run([sys.executable,'-E','-X','utf8',str(ROOT/'tools/validate_laptop_edit.py'),
        '--upgrade','--output',str(edit)],cwd=ROOT,check=True,timeout=1800)
    assert read(inference)['passed'] and read(edit)['passed']
    state=read(STATE)
    assert state.get('status')=='downloads_verified_integration_pending'
    if state['models']['asr'].get('repo')!=repo:
        write(STORE/'logs/rejected-qwen-asr-selection.json',state['models']['asr'])
    selected=dict(row,status='downloaded')
    state['models']['asr']=selected
    write(STATE,state)
    shutil.copy2(inference,STORE/'logs/upgrade-validation-asr.json')
    shutil.copy2(edit,ROOT/'output/validation/new-laptop/edit-pipeline-upgrade-inference.json')
    row['status']='adopted';write(PROOF,row)
    print('NATIVE_HINGLISH_SPECIALIST_PASSED_AND_SELECTED',flush=True)
    completion=STORE/'logs/model-upgrade-completion.json'
    # A failed Qwen end-to-end control leaves the old configuration intact.
    # Resume that coordinator only after this different recognizer has passed.
    if read(completion).get('status')=='needs_attention':
        os.environ.pop('STORYLENS_MODEL_SELECTION',None)
        with (STORE/'logs/upgrade-completion-native-hinglish.log').open('a',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-E','-X','utf8','-u',str(ROOT/'tools/finish_model_upgrade.py')],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=36000)


if __name__=='__main__':
    try: main()
    except Exception as error:
        row=read(PROOF) if PROOF.exists() else {}
        row.update(status='needs_attention',error=f'{type(error).__name__}: {error}')
        write(PROOF,row)
        raise
