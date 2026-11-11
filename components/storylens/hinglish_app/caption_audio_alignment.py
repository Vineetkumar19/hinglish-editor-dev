"""Bounded direct Whisper text/audio alignment; no duration-distributed timings."""
import math
import re
import wave
from .caption_speech_text import caption_tokens
from .template_text_model import FUNCTION_WORDS,align_script
from .caption_native_match import reconcile


def guard_alignment(model):
    original=getattr(model,'find_alignment',None)
    if not callable(original):return
    def guarded(tokenizer,text_tokens,encoder_output,num_frames,*args,**kwargs):
        # Older CTranslate2 builds can terminate natively on a one-frame tail.
        if isinstance(num_frames,(int,float)) and num_frames<2:return [[] for _ in text_tokens]
        return original(tokenizer,text_tokens,encoder_output,num_frames,*args,**kwargs)
    model.find_alignment=guarded


def check_relation(tokens,anchors,observed,normalizer):
    trusted={w['script_index'] for w in anchors if w.get('alignment')!='context-corrected'}
    content=[i for i,t in enumerate(tokens) if normalizer(t) not in FUNCTION_WORDS]
    if not tokens or len(trusted)/len(tokens)<.5 or content and sum(i in trusted for i in content)/len(content)<.35:
        raise ValueError('This script appears to belong to different speech. Paste the script for this recording; its saved audio is kept.')
    from .caption_numbers import numeric_parts,number_stream
    wanted=[n for t in tokens if any(c.isdigit() for c in t) for n in numeric_parts(t,normalizer)]
    heard=number_stream([w['text'] for w in observed],normalizer)
    if wanted and heard:
        cursor=0
        for value in wanted:
            while cursor<len(heard) and heard[cursor]!=value:cursor+=1
            if cursor==len(heard):raise ValueError('A script number conflicts with the recorded words. Check '+value+' before generating captions.')
            cursor+=1


def plan_windows(tokens,anchors,duration):
    if not tokens or not math.isfinite(duration) or duration<.2:raise ValueError('Choose at least a short spoken phrase for audio alignment.')
    strong=[w for w in anchors if w.get('alignment')=='matched']
    boundaries=[(0,0.)];first=0;start=0.
    while duration-start>14 or len(tokens)-first>60:
        choices=[w for w in strong if first+2<=w['script_index']<=first+60 and start+.2<=w['start']<=min(duration-.2,start+14)]
        if not choices:
            choices=[w for w in anchors if w.get('alignment')!='context-corrected' and first+2<=w['script_index']<=first+60 and start+.2<=w['start']<=min(duration-.2,start+14)]
        if not choices:raise ValueError('A long section could not be tied to this recording. Check that script section; saved speech analysis is kept.')
        chosen=max(choices,key=lambda w:w['start']);first=chosen['script_index'];start=float(chosen['start']);boundaries.append((first,start))
    boundaries.append((len(tokens),duration))
    return [{'first':a[0],'last':b[0],'start':a[1],'end':b[1]} for a,b in zip(boundaries,boundaries[1:])]


def validate_aligned(tokens,raw,duration):
    if len(tokens)!=len(raw):raise ValueError('The speech aligner did not return every script word. Saved analysis is kept.')
    for w in raw:
        if any(not isinstance(w.get(k),(float,int)) or not math.isfinite(w[k]) for k in ('start','end','probability')) or w['start']<0 or w['end']<w['start'] or w['end']>duration+.04:
            raise ValueError('The speech aligner returned an invalid audio interval. Saved analysis is kept.')
    result=[]
    for i,(text,w) in enumerate(zip(tokens,raw)):
        start=float(w['start']);end=min(duration,float(w['end']));reason='';kind=w.get('source_alignment','acoustic_word')
        if end-start<.015:
            after=next((v for v in raw[i+1:] if v['end']-v['start']>=.015 and v['start']>=start-.04),None)
            before=next((v for v in reversed(raw[:i]) if v['end']-v['start']>=.015),None)
            neighbour=after if after and after['start']-start<=.5 else before
            if neighbour is None:raise ValueError('This spoken phrase could not be timed reliably. Saved speech analysis is kept.')
            start=float(neighbour['start']);end=min(duration,float(neighbour['end']));kind='acoustic_phrase';reason='Shared phrase timing; check this script wording against the audio'
        elif w['probability']<.2:reason='Low-confidence script/audio match; review this word'
        if result and start<result[-1]['start']-.04:raise ValueError('The aligned script words changed order. Saved speech analysis is kept.')
        if result and start<result[-1]['start']:start=result[-1]['start']
        if end<=start:raise ValueError('This spoken word could not be timed reliably. Saved speech analysis is kept.')
        if any(c.isdigit() for c in text) and w['probability']<.2:raise ValueError('The recording could not verify the script number '+text+'. Check it before generating captions.')
        result.append({'text':text,'start':start,'end':end,'alignment':kind,'script_index':i,'confidence':float(w['probability']),**({'review_reason':reason} if reason else {})})
    return result


def plan_audio_sections(tokens,anchors,duration):
    fixed=[]
    for a in anchors:
        i=a['script_index']
        if a.get('alignment') not in ('matched','compound','phonetic') or a.get('probability',0)<.2:continue
        if any(c.isdigit() for c in tokens[i]) and re.findall(r'\d+',tokens[i])!=re.findall(r'\d+',a['text']):continue
        fixed.append(a)
    sections=[];first=0;begin=0.;left=None
    for a in fixed+[{'script_index':len(tokens),'start':duration,'end':duration}]:
        last=a['script_index'];end=float(a['start'])
        if last>first:
            if end-begin>14 or last-first>60:raise ValueError('This long script section has no reliable speech anchor. Check its wording against the recording; saved analysis is kept.')
            sections.append({'first':first,'last':last,'start':begin,'end':end,'left':left,'right':a if last<len(tokens) else None})
        if last<len(tokens):sections.append({'first':last,'last':last+1,'start':a['start'],'end':a['end'],'anchor':a})
        first=last+1;begin=float(a['end']);left=a
    return sections


class WhisperScriptAligner:
    def __init__(self,path,language='en',device='cpu',compute_type='int8'):
        from faster_whisper import WhisperModel
        from faster_whisper.tokenizer import Tokenizer
        self.model=WhisperModel(path,device=device,compute_type=compute_type,cpu_threads=4,num_workers=1,local_files_only=True)
        self.tokenizer=Tokenizer(self.model.hf_tokenizer,self.model.model.is_multilingual,task='transcribe',language=language)

    def align(self,audio,words):
        import numpy as np
        from faster_whisper.audio import pad_or_trim
        tokens=[];boundaries=[0]
        for word in words:tokens.extend(self.tokenizer.encode(' '+word));boundaries.append(len(tokens))
        if not tokens or len(tokens)>400:raise ValueError('This script phrase is too dense for reliable audio timing. Break it into shorter spoken phrases.')
        features=self.model.feature_extractor(audio);frames=features.shape[-1]-1
        if not 20<=frames<=2800:raise ValueError('This audio-alignment window is too short or too long.')
        encoded=self.model.encode(pad_or_trim(features))
        aligned=self.model.model.align(encoded,self.tokenizer.sot_sequence,[tokens],frames)[0]
        pairs=np.asarray(aligned.alignments)
        if pairs.ndim!=2 or pairs.shape[1]!=2 or not len(pairs):raise ValueError('The speech aligner returned no acoustic path.')
        jumps=np.pad(np.diff(pairs[:,0]),(1,0),constant_values=1).astype(bool);times=pairs[:,1][jumps]/self.model.tokens_per_second
        if len(times)<=boundaries[-1]:raise ValueError('The speech aligner returned an incomplete acoustic path.')
        return [{'start':float(times[a]),'end':float(times[b]),'probability':float(np.mean(aligned.text_token_probs[a:b]))} for a,b in zip(boundaries,boundaries[1:])]


def align_from_audio(model_path,wav,script,observed,duration,normalizer,progress,factory=WhisperScriptAligner,model_options=None):
    tokens=caption_tokens(script);spoken=[w['spoken'] for w in tokens]
    anchors=reconcile(' '.join(spoken),observed,normalizer,align_script)
    check_relation(spoken,anchors,observed,normalizer);windows=plan_audio_sections(spoken,anchors,duration)
    language='hi' if any('\u0900'<=c<='\u097f' for c in script) else 'en'
    model=None;raw=[]
    import numpy as np
    with wave.open(str(wav)) as source:
        if source.getframerate()!=16000 or source.getnchannels()!=1 or source.getsampwidth()!=2:raise ValueError('The saved narration audio needs to be decoded again.')
        for i,window in enumerate(windows):
            progress('Aligning script directly to the recorded audio ('+str(i+1)+'/'+str(len(windows))+')',85+10*i/len(windows))
            if 'anchor' in window:
                a=window['anchor'];raw.append({'start':a['start'],'end':a['end'],'probability':a['probability'],'source_alignment':a['alignment']});continue
            if window['end']-window['start']<.04:
                neighbour=window['right'] or window['left'];raw.extend({'start':neighbour['start'],'end':neighbour['start'],'probability':0.} for _ in range(window['last']-window['first']));continue
            first=window['first']-(1 if window['left'] else 0);last=window['last']+(1 if window['right'] else 0)
            begin=max(0.,(window['left']['start']-.1) if window['left'] else window['start']);end=min(duration,(window['right']['end']+.1) if window['right'] else window['end'])
            if end-begin<.22:begin=max(0.,begin-.12);end=min(duration,end+.12)
            source.setpos(round(begin*16000));samples=source.readframes(round((end-begin)*16000));audio=np.frombuffer(samples,dtype='<i2').astype(np.float32)/32768
            if model is None:model=factory(model_path,language=language,**(model_options or {}))
            result=model.align(audio,spoken[first:last])
            if len(result)!=last-first:raise ValueError('The speech aligner did not return every script word.')
            for w in result[window['first']-first:window['last']-first]:
                start=min(window['end'],max(window['start'],begin+w['start']));end=min(window['end'],max(start,begin+w['end']));raw.append({**w,'start':start,'end':end})
    return validate_aligned([w['text'] for w in tokens],raw,duration)
