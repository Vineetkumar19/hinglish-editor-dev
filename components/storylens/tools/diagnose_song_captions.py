"""Compare installed recognizers on the user's complete song excerpt, without speech VAD cuts."""
import gc
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import numpy as np
    import torch
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.model_storage import configure,role
    from hinglish_cut.model_preferences import release_ollama
    from hinglish_cut.media import read_audio
    from hinglish_cut.backends import LocalSpeech
    from hinglish_cut.model import Settings
    configure(ROOT);release_ollama(ROOT)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUDA_CACHE_PATH=r'C:\Ai Models\cache\cuda')
    torch.set_num_threads(8)
    folder=ROOT/'output/validation/song-captions';folder.mkdir(parents=True,exist_ok=True)
    source=ROOT/'cache/app/jobs/c5bb5a966d94/media/0000-6c06e15c-Rog Music.mp4'
    wav=folder/'original-song.wav'
    subprocess.run([get_ffmpeg_exe(),'-nostdin','-y','-v','error','-i',str(source),'-vn','-ac','1','-ar','16000',str(wav)],check=True)
    subprocess.run([get_ffmpeg_exe(),'-nostdin','-y','-v','error','-ss','5','-i',str(source),'-frames:v','1','-vf','scale=360:-2',str(folder/'source-frame.jpg')],check=True)
    audio=read_audio(wav,0,15.4)
    assert np.isfinite(audio).all()
    data={'source':str(source),'audio_finite':True,'seconds':len(audio)/16000,
          'peak':float(abs(audio).max()),'rms':float(np.sqrt(np.mean(audio**2)))}
    proof=folder/'recognizer-comparison.json'
    def save():proof.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    save()
    engine=LocalSpeech(Settings(device='cuda',offline=True,cpu_threads=8),ROOT/'models')
    try:
        data['speech_vad_intervals']=engine.detect(audio)
        data['prime_full_audio']=engine.recognize(audio)
        save();print('PRIME_FULL_AUDIO',data['prime_full_audio'],flush=True)
    finally:engine.close();del engine;gc.collect();torch.cuda.empty_cache()
    from faster_whisper import WhisperModel
    model=WhisperModel(role(ROOT,'independent_asr')['path'],device='cuda',compute_type='float16',cpu_threads=8,local_files_only=True)
    segments,info=model.transcribe(audio,language=None,task='transcribe',beam_size=5,
        condition_on_previous_text=False,vad_filter=False,temperature=0,word_timestamps=True)
    data['independent_language']=info.language;data['independent_language_probability']=info.language_probability
    data['independent_segments']=[{'start':s.start,'end':s.end,'text':s.text,
        'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,
        'words':[{'text':w.word,'start':w.start,'end':w.end,'probability':w.probability} for w in s.words or []]} for s in segments]
    save();print(json.dumps(data,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):main()
