"""Independent LOCAL speech evidence for malformed numerical captions only."""
import hashlib
import json
from pathlib import Path
import re


def suspicious(text):
    token=text.strip('.,!?;:()[]')
    if re.fullmatch(r'(?:T20I?|U19|IPL\d{4})',token,re.I):return False
    return bool(re.fullmatch(r'0\d{2,}',token) or re.fullmatch(r'\d+[A-Za-z]\d+',token))


def clip_audio(video,start,end):
    """Seek/decode only the requested source interval; do not create another video."""
    import av
    import numpy as np
    rate=16000;audio=np.zeros(round((end-start)*rate),dtype=np.float32)
    with av.open(str(video.path)) as container:
        stream=container.streams.audio[0]
        container.seek(max(0,int((start+video.video_start)*av.time_base)))
        resampler=av.AudioResampler(format='s16',layout='mono',rate=rate)
        for frame in container.decode(stream):
            if frame.pts is not None and float(frame.pts*frame.time_base)-video.video_start>end+.2:break
            for chunk in resampler.resample(frame):
                if chunk.pts is None:continue
                position=round((float(chunk.pts*chunk.time_base)-video.video_start-start)*rate)
                data=chunk.to_ndarray().reshape(-1).astype(np.float32)/32768
                a=max(0,position);b=min(len(audio),position+len(data))
                if b>a:audio[a:b]=data[a-position:b-position]
    return audio


def collect(root,video,words,pieces,progress=print,device_override=None):
    targets=[w for w in words if suspicious(w.text) and any(s<=(w.start+w.end)/2<e for s,e in pieces)]
    if not targets:return []
    from hinglish_cut.model_storage import role
    selected=role(root,'independent_asr')
    if not selected:raise ValueError('A malformed score needs the installed independent local speech model before captions can be exported.')
    from hinglish_shorts.source import quick_fingerprint
    spec={'v':1,'source':quick_fingerprint(video.path),'model':selected['path'],'revision':selected.get('revision',''),
          'windows':[(max(0,w.start-2.5),min(video.duration,w.end+2.5)) for w in targets]}
    folder=Path(root)/'cache/captions/numeric-evidence';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()+'.json')
    if path.exists():
        try:
            cached=json.loads(path.read_text('utf-8'))
            if isinstance(cached,list) and len(cached)==len(spec['windows']) and all(isinstance(w,dict) and all(k in w for k in ('start','end','transcript','supported_digits')) for w in cached):return cached
        except (ValueError,OSError):pass
    from hinglish_cut.model_preferences import release_ollama,preferred_device
    from hinglish_cut.model_storage import configure
    from faster_whisper import WhisperModel
    import gc
    configure(root);release_ollama(root)
    if device_override not in (None,'cpu','cuda'):
        raise ValueError('Choose CPU or NVIDIA CUDA for score verification.')
    device=device_override or preferred_device(root)
    if device=='cuda':
        import torch
        if not torch.cuda.is_available():raise RuntimeError('NVIDIA CUDA is required for the selected local score-verification model.')
        (torch.ones((2,2),device='cuda')@torch.ones((2,2),device='cuda')).sum().item()
    progress('Checking unclear scores against the original audio with the independent local speech model')
    model=WhisperModel(selected['path'],device=device,compute_type='float16' if device=='cuda' else 'int8',cpu_threads=8,local_files_only=True)
    windows=[]
    try:
        for start,end in spec['windows']:
            segments,_=model.transcribe(clip_audio(video,start,end),language='hi',task='transcribe',
                beam_size=5,temperature=0,vad_filter=False,condition_on_previous_text=False)
            text=' '.join(s.text.strip() for s in segments)
            from hinglish_cut.model import Word
            from .numbers import digits
            normalized=' '.join(w.text for w in digits([Word(t,i*.1,i*.1+.09) for i,t in enumerate(text.split())]))
            windows.append({'start':start,'end':end,'transcript':text,
                            'supported_digits':re.findall(r'\b\d+\b',normalized),'model':selected['repo']})
    finally:del model;gc.collect()
    partial=path.with_suffix('.partial');partial.write_text(json.dumps(windows,ensure_ascii=False,indent=2),'utf-8');partial.replace(path)
    return windows
