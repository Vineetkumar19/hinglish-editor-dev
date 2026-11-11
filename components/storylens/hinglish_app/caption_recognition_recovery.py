"""Independent bounded ASR retry; never feed the desired script into recognition."""
import gc
import math
import wave
from .template_text_model import normal


def word_rows(word,offset,duration):
    a=offset+float(word.start);b=min(duration,offset+float(word.end));p=float(word.probability)
    if not all(math.isfinite(v) for v in (a,b,p)) or b<=a or p<.2:return []
    # An ASR token can contain whitespace. Keep its measured span; the acoustic
    # stage, not fabricated equal subdivision, will separate these words later.
    return [{'text':t,'start':max(0.,a),'end':b,'probability':p} for t in word.word.split()]


def stitch(left,right,seam):
    if not left:return right
    pairs=[]
    for i,a in enumerate(left):
        if abs(a['start']-seam)>1.5:continue
        for j,b in enumerate(right):
            if normal(a['text'])==normal(b['text']) and abs(a['start']-b['start'])<.45:
                pairs.append((abs((a['start']+b['start'])/2-seam),i,j))
    if pairs:
        _,i,j=min(pairs)
        return left[:i]+right[j:]
    return [w for w in left if (w['start']+w['end'])/2<seam]+[w for w in right if (w['start']+w['end'])/2>=seam]


def recognize_windows(factory,model_path,wav,duration,progress,options):
    import numpy as np
    from .caption_audio_alignment import guard_alignment
    model=None;segments=None;words=[]
    try:
        with wave.open(str(wav)) as source:
            if (source.getframerate(),source.getnchannels(),source.getsampwidth())!=(16000,1,2):
                raise ValueError('The saved narration needs to be decoded again before retrying speech timing.')
            model=factory(model_path,**options,cpu_threads=4,num_workers=1,local_files_only=True)
            guard_alignment(model)
            count=math.ceil(duration/12)
            for index in range(count):
                core=index*12.;begin=max(0.,core-1);end=min(duration,core+13)
                source.setpos(min(source.getnframes(),round(begin*16000)))
                audio=np.frombuffer(source.readframes(round((end-begin)*16000)),dtype='<i2').astype(np.float32)/32768
                if len(audio)<320:continue
                progress('Rechecking narration section '+str(index+1)+' of '+str(count),30+50*index/count)
                # Retry without the silence skipper that can drop quiet/code-switched
                # speech. Bounded independent windows also prevent a decoder seek
                # error from consuming the rest of the recording.
                segments,_=model.transcribe(audio,beam_size=5,temperature=0,word_timestamps=True,
                    vad_filter=False,no_speech_threshold=None,condition_on_previous_text=False)
                current=[]
                try:
                    for segment in segments:
                        for word in segment.words or []:current.extend(word_rows(word,begin,duration))
                finally:
                    if hasattr(segments,'close'):segments.close()
                    segments=None
                words=stitch(words,current,core)
        if not words:raise ValueError('No clear spoken words were recovered. Check the narration audio; your script is kept.')
        return words
    finally:
        if segments is not None and hasattr(segments,'close'):segments.close()
        segments=None;model=None;gc.collect()
