"""Explicit native-caption compute choice and existing portable CUDA runtime."""
import json,os
from pathlib import Path
_dll_handles=[]

def priority_gpu_ready(free_mb,utilization):
    return free_mb>=7000 and 0<=utilization<=10

def options_for(root):
    path=Path(root)/'config.caption-native.local.json'
    from hinglish_cut.compute_policy import speech_options
    value=json.loads(path.read_text('utf8')) if path.is_file() else speech_options(root)
    device=value.get('device');kind=value.get('compute_type','int8_float16' if device=='cuda' else 'int8')
    from hinglish_cut.compute_policy import heavy_device
    selected=heavy_device(root,device)
    if selected!=device:device=selected;kind='int8_float16'
    if device not in ('cpu','cuda') or kind not in (('int8_float16','float16') if device=='cuda' else ('int8','float32')):raise ValueError('Choose CUDA or CPU in native-caption compute settings.')
    return {'device':device,'compute_type':kind}

def prepare_runtime(root,options):
    if options['device']!='cuda':return
    if os.name=='nt':
        folder=Path(root)/'tools/cuda-reference-runtime/bin'
        if not all((folder/name).is_file() for name in ('cublas64_12.dll','cudnn64_9.dll')):raise ValueError('Restore the existing portable CUDA libraries for caption GPU timing.')
        os.environ['PATH']=str(folder)+os.pathsep+os.environ.get('PATH','')
        if hasattr(os,'add_dll_directory'):_dll_handles.append(os.add_dll_directory(str(folder)))
    import ctranslate2
    if ctranslate2.get_cuda_device_count()<1:raise ValueError('The selected caption GPU is unavailable. Saved speech analysis is kept; CPU fallback was not started.')
