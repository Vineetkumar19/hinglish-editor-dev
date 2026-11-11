"""Validate finished models sequentially while other weights continue downloading."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
STORE=Path(r'C:\Ai Models')
TAGS={'planner':'storylens-planner:9b-q6','embedding':'storylens-embedding:8b-q6','meaning':'storylens-meaning:14b'}


def main():
    state=json.loads((ROOT/'downloads/model-upgrade-c-drive.json').read_text())
    receipt=json.loads((STORE/'logs/model-upgrade-completion.json').read_text(encoding='utf-8-sig'))
    roles={key:dict(row) for key,row in state['models'].items() if row.get('status')=='downloaded'}
    for key,tag in TAGS.items():
        if key in roles:
            roles[key]['ollama_model']=tag
            roles[key]['weight_file']=next(name for name in roles[key]['files']
                if name.endswith('.gguf') and not name.startswith('mmproj'))
    pending=STORE/'early-validation-selection.json'
    aliases={}
    for name,key in [('Oriserve/Whisper-Hindi2Hinglish-Swift','asr'),
                     ('openai/clip-vit-base-patch32','broll_vision')]:
        if key in roles: aliases[name]=roles[key]['path']
    temporary=pending.with_suffix('.writing')
    temporary.write_text(json.dumps(dict(root=str(STORE),active=True,roles=roles,aliases=aliases)),encoding='utf-8')
    temporary.replace(pending)
    os.environ.update(STORYLENS_MODEL_SELECTION=str(pending),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    for key in ('planner','embedding','meaning','asr','independent_asr','broll_vision','cutout'):
        if key not in roles or (key in TAGS and key not in receipt.get('imported',[])):continue
        proof=STORE/'logs'/('upgrade-validation-'+key+'.json')
        if proof.exists():
            previous=json.loads(proof.read_text())
            if previous.get('passed') and previous.get('model_revision')==roles[key].get('revision'):continue
        subprocess.run([sys.executable,'-E','-X','utf8',str(ROOT/'tools/validate_model_upgrade.py'),'--check',key],
                       cwd=ROOT,check=True,timeout=1800)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    while True:
        receipt=json.loads((STORE/'logs/model-upgrade-completion.json').read_text(encoding='utf-8-sig'))
        if args.watch and receipt.get('status') not in ('waiting_for_downloads','waiting_for_speech_runtime'):
            break
        main()
        if not args.watch: break
        time.sleep(20)
