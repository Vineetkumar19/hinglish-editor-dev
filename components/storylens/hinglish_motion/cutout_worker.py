"""Isolated CUDA ONNX cutouts using the already installed GPU runtime."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();sys.path.insert(0,str(args.root))
    from hinglish_cut.model_storage import configure,role
    configure(args.root)
    selected=role(args.root,'cutout');assert selected and Path(selected['path']).is_file()
    import onnxruntime as ort
    if 'CUDAExecutionProvider' not in ort.get_available_providers():raise RuntimeError('The isolated cutout runtime has no CUDA provider')
    torch_lib=Path(importlib.util.find_spec('torch').origin).parent/'lib'
    dll_directory=os.add_dll_directory(str(torch_lib)) if hasattr(os,'add_dll_directory') else None
    ort.preload_dlls(directory=str(torch_lib))
    from PIL import Image
    from rembg import new_session,remove
    options=ort.SessionOptions();options.enable_profiling=True
    options.profile_file_prefix=str(args.output.parent/'cuda-profile')
    options.intra_op_num_threads=4;options.inter_op_num_threads=1
    session=new_session('birefnet-general',sess_opts=options,providers=[
        ('CUDAExecutionProvider',{'cudnn_conv_algo_search':'HEURISTIC','cudnn_conv_use_max_workspace':'0'}),
        'CPUExecutionProvider'])
    if 'CUDAExecutionProvider' not in session.inner_session.get_providers():raise RuntimeError('CUDA cutout initialization failed; CPU fallback is disabled by policy')
    with Image.open(args.input) as image:result=remove(image.convert('RGB'),session=session)
    result.save(args.output)
    profile=Path(session.inner_session.end_profiling());events=json.loads(profile.read_text())
    gpu=[event for event in events if event.get('args',{}).get('provider')=='CUDAExecutionProvider']
    neural=[event for event in gpu if any(op in event.get('args',{}).get('op_name','') for op in ('Conv','MatMul','Gemm'))]
    if not neural:raise RuntimeError('No neural cutout operations ran on CUDA')
    receipt={'providers':session.inner_session.get_providers(),'cuda_events':len(gpu),
        'cuda_neural_events':len(neural),'model_path':selected['path'],'profile':str(profile),'passed':True}
    args.output.with_suffix('.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
