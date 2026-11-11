"""Package a separately trained candidate; do not change serving configuration."""
import json,os,subprocess,sys,hashlib,re,shutil,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/sound-training/20261030-physical-sources'
def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--model',default='storylens-sound:14b-physical-candidate');args=parser.parse_args()
    OUT=args.output.resolve()
    if not OUT.is_relative_to((ROOT/'output/sound-training').resolve()):raise ValueError('Output must stay in sound-training')
    status=json.loads((OUT/'status.json').read_text())
    if status['stage']!='adapter_trained_awaiting_review':raise RuntimeError('Training must finish before packaging')
    from tools.sound_training import export_adapter
    export_adapter.OUT=OUT;export_adapter.main()
    base=Path('C:/Ai Models/ollama/blobs/sha256-500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0')
    scratch=Path('C:/Ai Models/training/sound-qwen3-14b')/('export-'+OUT.name)
    scratch.mkdir(exist_ok=True)
    merged=scratch/'sound-merged.gguf';quant=OUT/'sound-physical-Q4_K_M.gguf'
    if quant.exists():
        with quant.open('rb') as f:header=f.read(4)
        if header!=b'GGUF':quant.unlink() # only this run's incomplete derived file
    if shutil.disk_usage(scratch).free<15*1024**3 or shutil.disk_usage(OUT).free<10*1024**3:
        raise RuntimeError('Not enough free space for conversion; saved training weights are untouched')
    commands=[('merge',[str(ROOT/'tools/sound_training/export-build/bin/Release/llama-export-lora.exe'),'-m',str(base),'--lora',str(OUT/'adapter.gguf'),'-o',str(merged)]),
              ('quantize',[str(ROOT/'tools/llama/b11011/llama-quantize.exe'),'--allow-requantize',str(merged),str(quant),'Q4_K_M','2'])]
    for name,command in commands:
        print(name,flush=True)
        with (OUT/(name+'.log')).open('w',encoding='utf8') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        target=merged if name=='merge' else quant
        with target.open('rb') as f:header=f.read(4)
        if header!=b'GGUF' or target.stat().st_size<8*1024**3:raise RuntimeError('Incomplete model export; refusing registration')
    template=subprocess.check_output(['ollama','show','storylens-sound:14b-trained','--modelfile'],text=True,encoding='utf8')
    template=re.sub(r'^FROM .*$',f'FROM "{quant.as_posix()}"',template,flags=re.M)
    model=OUT/'Modelfile';model.write_text(template,encoding='utf8')
    with (OUT/'ollama-create.log').open('w',encoding='utf8') as log:
        subprocess.run(['ollama','create',args.model,'-f',str(model)],stdout=log,stderr=subprocess.STDOUT,check=True)
    with quant.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    (OUT/'packaging.json').write_text(json.dumps({'model':args.model,'path':str(quant),'sha256':digest,'serving_config_changed':False},indent=2),encoding='utf8')
    merged.unlink() # disposable conversion intermediate; adapter and quantized result retained
    print('Candidate registered separately; no live model replaced.',flush=True)
if __name__=='__main__':main()
