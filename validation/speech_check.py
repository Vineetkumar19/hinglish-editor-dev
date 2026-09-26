r"""Reproducible local checks against a short public model-provider speech sample.

Run from project root: .venv\Scripts\python.exe validation\speech_check.py
The sample was downloaded from Oriserve's Swift model card. Not user footage.
"""
from pathlib import Path
import sys
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import av
import numpy as np
from hinglish_cut.backends import LocalSpeech, LocalJudge
from hinglish_cut.model import Settings

root=Path(__file__).resolve().parents[1]
container=av.open(str(root/'validation'/'provider-hindi-sample.wav'))
resampler=av.AudioResampler(format='fltp',layout='mono',rate=16000)
parts=[x.to_ndarray().flatten() for frame in container.decode(audio=0) for x in resampler.resample(frame)]
parts.extend(x.to_ndarray().flatten() for x in resampler.resample(None))
container.close()
audio=np.concatenate(parts)
settings=Settings(offline=True)
speech=LocalSpeech(settings,root/'models')
result={'sample_source':'https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Swift/blob/main/audios/f89b6428-c58a-4355-ad63-0752b69f2d30.wav',
        'reference':'Vah bas din mein kitni baar chalti hai?', 'duration':len(audio)/16000}
result['vad_silence']=speech.detect(np.zeros(16000,dtype=np.float32))
result['speech_regions']=speech.detect(audio)
result['transcript']=speech.recognize(audio)
print('Recognized:',result['transcript'],flush=True)
try:
    from dataclasses import asdict
    result['alignment']=[asdict(w) for w in speech.align(audio,result['transcript'])]
    print('Aligned words:',len(result['alignment']),flush=True)
except Exception as error:
    result['alignment_error']=str(error)
speech.close()
try:
    settings.judge_model='Qwen/Qwen2.5-1.5B-Instruct'
    judge=LocalJudge(settings,root/'models')
    result['semantic_same']=judge.judge(result['reference'],result['transcript'])
    result['semantic_negation']=judge.judge('Aap ye kaam nahi kar sakte.','Aap ye kaam kar sakte.')
except Exception as error:
    result['judge_error']=str(error)
(root/'validation'/'speech-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True,indent=2))
