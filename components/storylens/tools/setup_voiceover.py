"""Install VoiceStudio's inference code into a private runtime. Never replace Storylens CUDA."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('D:/Repository Vault/2026-10-23/voicestudio/source')
TARGET = ROOT/'tools/voicestudio-runtime'


def main():
    os.environ['TEMP'] = os.environ['TMP'] = str(ROOT/'work')
    TARGET.mkdir(exist_ok=True)
    dest = TARGET/'source'
    dest.mkdir(exist_ok=True)
    shutil.copytree(SOURCE/'omnivoice', dest/'omnivoice', dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('LICENSE','LICENSE-NOTICE.md'):
        shutil.copy2(SOURCE/name, dest/name)
    receipt = dict(repository='https://github.com/debpalash/VoiceStudio', source=str(SOURCE), copied_files={})
    for file in (dest/'omnivoice').rglob('*.py'):
        receipt['copied_files'][str(file.relative_to(dest))] = hashlib.sha256(file.read_bytes()).hexdigest()
    (TARGET/'provenance.json').write_text(json.dumps(receipt,indent=2),'utf-8')
    python = TARGET/'venv/Scripts/python.exe'
    if not python.is_file(): subprocess.run([sys.executable,'-m','venv','--without-pip',str(TARGET/'venv')],check=True)
    # Reuse the installed CUDA wheel and audio libraries by path; private packages
    # always resolve first. pip cannot change Storylens's packages through this path.
    site = TARGET/'venv/Lib/site-packages'
    (site/'storylens_dependencies.pth').write_text(str(ROOT/'.venv/Lib/site-packages')+'\n','utf-8')
    subprocess.run([sys.executable,'-m','pip','--python',str(python),'install','transformers>=5.10.0,<6','huggingface-hub>=1.7,<2','pydub','soundfile','accelerate'],check=True)
    subprocess.run([str(python),'-c',"import sys;sys.path.insert(0,sys.argv[1]);from omnivoice import OmniVoice;from transformers import HiggsAudioV2TokenizerModel;print('Voice runtime imports verified')",str(dest)],check=True)
    from huggingface_hub import snapshot_download
    snapshot_download('k2-fsa/OmniVoice',local_dir=ROOT/'models/voicestudio/OmniVoice',ignore_patterns=['*.bin','*.pt','*.pth','*.onnx','*.png','*.jpg','*.mp4'])
    print('VoiceStudio runtime and local model installed. Restart Storylens when your work is safe.')


if __name__ == '__main__': main()
