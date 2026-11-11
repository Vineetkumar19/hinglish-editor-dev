"""Bounded device checks for the newly enabled CUDA paths; no downloads."""
import gc
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def warm_cutout():
    from PIL import Image
    from hinglish_motion.assets import Remover,has_alpha
    remover=Remover(ROOT)
    with Image.open(ROOT/'library/thumbnail-styles/mumbai-indians-2020/reference.jpg') as photo:
        photo.thumbnail((1024,1024));started=time.monotonic();result=remover(photo,'person')
    assert has_alpha(result)
    proof={**remover.last_receipt,'seconds':round(time.monotonic()-started,2),'alpha_verified':True}
    (ROOT/'output/validation/song-captions/rtx-cutout-warm-check.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print('WARM_CUDA_CUTOUT '+json.dumps(proof),flush=True)


def main():
    import numpy as np
    import torch
    from PIL import Image
    from hinglish_cut.model_storage import configure
    from hinglish_cut.model_preferences import release_ollama
    configure(ROOT);release_ollama(ROOT)
    assert torch.cuda.is_available()
    proof={'device':torch.cuda.get_device_name(0),'checks':{}}
    target=ROOT/'output/validation/song-captions/rtx-policy-check.json'
    def save():target.write_text(json.dumps(proof,indent=2),encoding='utf-8')
    def done(name,values):
        proof['checks'][name]=values;save();print(name+': '+json.dumps(values),flush=True)
    from hinglish_clean.detection import CleanSettings,SpeechDetector
    from hinglish_cut.media import read_audio
    detector=SpeechDetector(CleanSettings(device='cuda'))
    audio=read_audio(ROOT/'output/validation/song-captions/original-song.wav',0,15.4)
    found=detector(audio)
    assert not detector(np.zeros(16000,np.float32))
    devices=sorted({str(p.device) for p in detector.model.parameters()})
    assert devices and all(device.startswith('cuda') for device in devices)
    done('silero',{'passed':True,'parameter_devices':devices,'song_speech_regions':found,'silence_regions':0})
    del detector;gc.collect();torch.cuda.empty_cache()
    from hinglish_motion.assets import Remover,has_alpha
    remover=Remover(ROOT)
    with Image.open(ROOT/'library/thumbnail-styles/mumbai-indians-2020/reference.jpg') as photo:
        photo.thumbnail((1024,1024));started=time.monotonic();result=remover(photo,'person')
    assert has_alpha(result)
    result.save(ROOT/'output/validation/song-captions/cuda-cutout.png')
    done('birefnet',{**remover.last_receipt,'seconds':round(time.monotonic()-started,2),'alpha_verified':True})
    del remover,result;gc.collect();torch.cuda.empty_cache()
    from hinglish_sound.listen import Listener
    listener=Listener(ROOT,device='cuda')
    text=listener.texts(['A person singing with music','A car engine'])
    # Resampling is CPU preprocessing; the CLAP network must reside on CUDA.
    import scipy.signal
    waveform=scipy.signal.resample_poly(audio,3,1)
    sound=listener.audio([waveform])
    assert np.isfinite(text).all() and np.isfinite(sound).all()
    actual=str(next(listener.model.parameters()).device)
    assert actual.startswith('cuda')
    done('clap',{'passed':True,'parameter_device':actual,'text_shape':list(text.shape),'audio_shape':list(sound.shape)})
    proof['passed']=all(value['passed'] for value in proof['checks'].values());save()


if __name__=='__main__':
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):
        if '--warm-cutout' in sys.argv:warm_cutout()
        else:main()
