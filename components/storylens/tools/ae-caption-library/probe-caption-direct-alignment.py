"""Local research probe; never imports or edits an Adobe project."""
from pathlib import Path
import json,sys,time,wave
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
out=root/'output/caption-one-general-speech-20261029';out.mkdir(parents=True,exist_ok=True)
from hinglish_cut.gpu_lock import gpu_lock
from hinglish_cut.model_storage import role
print('Waiting for the shared processing slot',flush=True)
with gpu_lock(root):
    print('Loading existing speech model for direct alignment',flush=True)
    from faster_whisper import WhisperModel
    from faster_whisper.tokenizer import Tokenizer
    from faster_whisper.audio import pad_or_trim
    import numpy as np
    began=time.monotonic();model=WhisperModel(role(root,'independent_asr')['path'],device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,local_files_only=True)
    request=json.loads((root/'output/captions/ae-speech/24034e757ca82b6a313606ff77a00cdb/request.json').read_text('utf8'))
    words=request['script'].split()[:19]
    wav=root/'cache/caption-native-timing/447fb02f763e6fb4914dfed024cba6e8455a87259f048059e6c0e57a01075c5e/narration.wav'
    with wave.open(str(wav)) as f:audio=np.frombuffer(f.readframes(round(6.2*16000)),dtype='<i2').astype(np.float32)/32768
    features=model.feature_extractor(audio);frames=min(features.shape[-1]-1,3000);encoded=model.encode(pad_or_trim(features))
    results=[]
    for language in ('hi','en'):
        print('Aligning reference words',language,flush=True)
        tokenizer=Tokenizer(model.hf_tokenizer,model.model.is_multilingual,task='transcribe',language=language)
        ids=[];bounds=[0]
        for word in words:ids.extend(tokenizer.encode(' '+word));bounds.append(len(ids))
        result=model.model.align(encoded,tokenizer.sot_sequence,[ids],frames)[0]
        pairs=np.asarray(result.alignments);jumps=np.pad(np.diff(pairs[:,0]),(1,0),constant_values=1).astype(bool);times=pairs[:,1][jumps]/model.tokens_per_second
        aligned=[]
        for i,word in enumerate(words):aligned.append({'text':word,'start':float(times[bounds[i]]),'end':float(times[bounds[i+1]]),'probability':float(np.mean(result.text_token_probs[bounds[i]:bounds[i+1]]))})
        results.append({'language':language,'words':aligned})
    (out/'direct-alignment-probe.json').write_text(json.dumps({'seconds':time.monotonic()-began,'results':results},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Saved direct-alignment-probe.json',round(time.monotonic()-began,2),'seconds',flush=True)
