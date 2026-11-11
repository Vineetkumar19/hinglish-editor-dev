import argparse
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import importlib
import json
import os
import sys


def doctor(device='cpu'):
    checks={}; failed=False
    for name in ('numpy','av','torch','torchaudio','transformers','silero_vad','uroman'):
        try:
            module=importlib.import_module(name)
            checks[name]={'ok':True,'version':getattr(module,'__version__','installed')}
        except Exception as error:
            failed=True; checks[name]={'ok':False,'error':str(error)}
    if checks['torch']['ok']:
        import torch
        checks['cuda_available']=torch.cuda.is_available()
        if torch.cuda.is_available():
            checks['gpu']=torch.cuda.get_device_name(0)
            checks['cuda_build']=torch.version.cuda
        if device=='cuda':
            try:
                checks['gpu_kernel_test']=float((torch.ones((8,8),device='cuda')@torch.ones((8,8),device='cuda')).sum().item())
            except Exception as error:
                failed=True; checks['gpu_kernel_error']=str(error)
    print(json.dumps(checks,indent=2))
    return 1 if failed else 0


def prepare(root,settings):
    from .model_storage import configure, selected_path, role
    configure(root)
    from huggingface_hub import snapshot_download, HfApi
    models=Path(root)/'models'; models.mkdir(parents=True,exist_ok=True)
    ids=[settings.asr_model,settings.align_model]
    if settings.judge_model: ids.append(settings.judge_model)
    for model in ids:
        if role(root,'meaning') and model in ('Qwen/Qwen2.5-1.5B-Instruct',role(root,'meaning')['ollama_model']):
            from hinglish_semantic.setup_meaning import require
            require(root)
            continue
        model=selected_path(root,model)
        if Path(model).is_dir(): continue
        print(f'Downloading model for local use: {model}',flush=True)
        files=[] if settings.offline else HfApi().list_repo_files(model)
        weights=['*.safetensors'] if settings.offline or any(f.endswith('.safetensors') and '/' not in f for f in files) else ['pytorch_model*.bin']
        snapshot_download(model,cache_dir=str(models),local_files_only=settings.offline,
                          allow_patterns=['*.json','*.txt','*.model','*.tiktoken']+weights,
                          ignore_patterns=['onnx/*','coreml/*'])
    print('Model files prepared. Use --offline for subsequent runs.')


def demo(root):
    from .demo import create_demo_media
    from .media import probe,extract_audio
    from .model import Transcript,Word,Settings
    from .pipeline import finish_project
    root=Path(root)/'output'/('demo-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    (root/'media').mkdir(parents=True)
    lines=['Aaj hum video editing seekhenge.','Ab hum timeline export karenge.']
    transcripts=[]; wavs={}
    for index,(name,text,color) in enumerate([('take-02.mp4',lines[1],(46,70,85)),('take-01.mp4',lines[0],(90,59,42))]):
        video=root/'media'/name
        create_demo_media(video,6,440+index*220,color)
        m=probe(video); wav=root/'media'/(name+'.wav'); extract_audio(m,wav); wavs[m.id]=wav
        words=[Word(word,.35+i*.7,.75+i*.7,.99) for i,word in enumerate(text.split())]
        # Insert a pause after the second word to test real split assembly.
        for word in words[2:]: word.start+=.7; word.end+=.7
        transcripts.append(Transcript(m,words,[(w.start,w.end) for w in words],[]))
    def fixture_transcript(wav):
        return lines[0] if '0001' in Path(wav).stem else lines[1]
    finish_project(lines,transcripts,wavs,root/'edit',Settings(),fixture_transcript,demo=True)
    print(f'Demo report: {root / "edit" / "report.html"}')
    return root/'edit'


def main(argv=None):
    parser=argparse.ArgumentParser(description='Local Hinglish video assembly for Premiere Pro (FCP 7 XML).')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('run','prepare','doctor','demo'):
        p=sub.add_parser(name)
        p.add_argument('--root',type=Path,default=Path.cwd())
        p.add_argument('--config',type=Path)
        p.add_argument('--device',choices=['cpu','cuda'])
        p.add_argument('--offline',action='store_true',default=None)
    args=parser.parse_args(argv)
    try:
        if args.command=='doctor': return doctor(args.device or 'cpu')
        if args.command=='demo': demo(args.root); return 0
        from .pipeline import load_settings,run_project
        config=args.config or args.root/'config.cpu.json'
        settings=load_settings(config if config.exists() else None,args.device,args.offline)
        if settings.offline:
            os.environ['HF_HUB_OFFLINE']='1'; os.environ['TRANSFORMERS_OFFLINE']='1'
        if args.command=='prepare': prepare(args.root,settings); return 0
        _,report=run_project(args.root,settings,lambda message:print(message,flush=True))
        return 0 if report['status']=='CHECKS_PASSED_REVIEW_RECOMMENDED' else 2
    except KeyboardInterrupt:
        print('Interrupted. Completed source analysis is cached for the next run.',file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Could not complete: {error}',file=sys.stderr)
        print('Run the doctor command to check dependencies. Source videos are unchanged.',file=sys.stderr)
        return 1


if __name__=='__main__':
    sys.exit(main())
