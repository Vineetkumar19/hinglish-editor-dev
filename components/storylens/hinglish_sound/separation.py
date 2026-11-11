"""Optional real source separation; never substitute attenuation for isolation."""
import hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np


def isolate(root,voice,folder,progress=print,device='cpu'):
    from hinglish_cut.compute_policy import heavy_device
    device=heavy_device(root,device)
    import soundfile as sf
    root=Path(root);folder=Path(folder)
    runtime=root/'tools/sound-separation-runtime/separate.py'
    if not runtime.is_file() or not (runtime.parent/'packages/demucs').is_dir():
        raise RuntimeError('Source music removal unavailable: install the local voice separator or uncheck Remove existing music.')
    voice=np.asarray(voice,dtype=np.float32)
    digest=hashlib.sha256(b'htdemucs-v1-48000'+voice.tobytes()).hexdigest()
    cache=root/'cache/sound-separation'/digest;cache.mkdir(parents=True,exist_ok=True)
    target=cache/'dialogue.wav'
    if not target.is_file():
        progress('Separating your voice from existing music (the original video is kept)')
        source=cache/'source.wav';sf.write(source,np.stack([voice,voice],axis=1),48000,subtype='FLOAT')
        partial=cache/'dialogue-partial.wav'
        with (folder/'voice-separation.log').open('w',encoding='utf-8') as log:
            try:
                r=subprocess.run([sys.executable,str(runtime),'--input',str(source),'--output',str(partial),'--device',device],
                    cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=1800,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            except subprocess.TimeoutExpired as error:
                raise RuntimeError('Source music removal stopped: try a shorter clip or uncheck Remove existing music. Your original video is kept.') from error
        if r.returncode or not partial.is_file():
            raise RuntimeError('Source music removal stopped: check Technical details and retry, or uncheck Remove existing music. Your original video is kept.')
        audio,sr=sf.read(partial,always_2d=True,dtype='float32')
        if sr!=48000 or len(audio)!=len(voice) or not np.isfinite(audio).all():
            raise RuntimeError('Source music removal stopped: the separated voice has invalid timing. Keep the source and retry.')
        partial.replace(target)
    audio,sr=sf.read(target,always_2d=True,dtype='float32')
    if sr!=48000 or len(audio)!=len(voice) or not np.isfinite(audio).all():
        raise RuntimeError('Source music removal stopped: the saved voice has invalid timing. Keep the source and retry.')
    receipt=dict(engine='Demucs 4.0.1 · htdemucs',path=str(target.resolve()),samples=len(audio),sample_rate=sr,
      source_sha256=digest,original_preserved=True,notice='Existing music/effects are reduced by source separation. Some may remain, and voice artefacts are possible.')
    (folder/'voice-separation.json').write_text(json.dumps(receipt,indent=2),'utf-8')
    return audio.mean(axis=1),receipt
