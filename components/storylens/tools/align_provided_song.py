"""Test exact user-provided lyrics against the uploaded song on CUDA."""
import gc
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
LYRICS='Haan tujhe dekhta raha\nKissi khwab ki tarah\nJo ab samne hai tu\nHo kaise yakeen bhala'


def main():
    import numpy as np
    import torch
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.model_storage import configure,role
    from hinglish_cut.model_preferences import release_ollama
    from hinglish_cut.media import read_audio
    from hinglish_cut.backends import LocalSpeech
    from hinglish_cut.model import Settings
    configure(ROOT);release_ollama(ROOT);torch.set_num_threads(8)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUDA_CACHE_PATH=r'C:\Ai Models\cache\cuda')
    folder=ROOT/'output/validation/song-captions';(folder/'provided-lyrics.txt').write_text(LYRICS,encoding='utf-8')
    audio=read_audio(folder/'original-song.wav')
    from faster_whisper import WhisperModel
    model=WhisperModel(role(ROOT,'independent_asr')['path'],device='cuda',compute_type='float16',cpu_threads=8,local_files_only=True)
    segments,info=model.transcribe(audio,language='hi',task='transcribe',beam_size=5,
        condition_on_previous_text=False,vad_filter=False,temperature=0,word_timestamps=True)
    data={'user_lyrics':LYRICS,'inference_device':'cuda','gpu':torch.cuda.get_device_name(0),
        'forced_hindi_segments':[{'text':s.text,'start':s.start,'end':s.end,'avg_logprob':s.avg_logprob,
            'words':[{'text':w.word,'start':w.start,'end':w.end,'probability':w.probability} for w in s.words or []]} for s in segments]}
    del model;gc.collect();torch.cuda.empty_cache()
    print(json.dumps(data,ensure_ascii=False),flush=True)
    engine=LocalSpeech(Settings(device='cuda',offline=True,cpu_threads=8),ROOT/'models')
    try:
        words=engine.align(audio,' '.join(LYRICS.splitlines()))
        data['aligned_words']=[vars(w) for w in words]
        data['aligner_device']=str(next(engine.aligner.parameters()).device)
        data['torch_peak_GiB']=torch.cuda.max_memory_allocated()/2**30
        assert data['aligner_device'].startswith('cuda')
    finally:engine.close()
    (folder/'provided-lyrics-alignment.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(data,indent=2,ensure_ascii=False),flush=True)


if __name__=='__main__':
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):main()
