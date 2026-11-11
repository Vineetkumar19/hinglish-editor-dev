"""Timing-only native AE captions: local speech evidence, exact script, no video render."""
import argparse
import gc
import hashlib
import json
import math
import re
from pathlib import Path

from .caption_persistence import save
from .template_text_model import align_script, normal
from .caption_speech_text import caption_tokens


class AudioAlignmentRequired(ValueError):
    """The script is valid, but recognition alone cannot time every word."""


def validate_capture(capture):
    if not isinstance(capture,dict) or capture.get('unsupported'):
        raise ValueError('Speech timing cannot read this narration edit. Use straight narration footage or choose Script duration. Existing layers are kept.')
    def number(value,lo,hi):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:
            raise ValueError('Reconnect the caption composition; its narration timing is invalid.')
        return value
    duration=number(capture.get('duration'),.1,3600)
    clips=capture.get('clips')
    if not isinstance(clips,list) or not 1<=len(clips)<=1000:raise ValueError('Enable the narration audio in the active composition, then retry Speech timing.')
    audio=[]
    for clip in clips:
        a=number(clip.get('start'),0,duration);b=number(clip.get('end'),0,duration)
        if b<=a or clip.get('stretch',100)!=100 or clip.get('time_remap'):
            raise ValueError('Speech timing does not support narration speed changes. Use straight narration footage or Script duration.')
        path=clip.get('path')
        if not isinstance(path,str) or len(path)>4096 or path.startswith(('\\\\','//')) or re.match(r'^[a-z]+://',path,re.I):raise ValueError('Relink the local narration file, then retry Speech timing.')
        audio.append({'path':path,'start':a,'end':b,'source_in':number(clip.get('source_in',0),0,86400),'rate':1,'gain':1})
    audio.sort(key=lambda a:a['start'])
    if any(a['start']<b['end']-.001 for b,a in zip(audio,audio[1:])):raise ValueError('Choose one narration track for Speech timing; overlapping narration is ambiguous. Your layers are kept.')
    return {'duration':duration,'audio':audio}


def align_words(script,observed,duration,normalizer=normal,*,allow_partial=False):
    if not isinstance(script,str) or not script.strip() or len(script)>6000 or len(script.split())>1000:raise ValueError('Paste the final spoken script (up to 6,000 characters) before generating captions.')
    if not isinstance(observed,list) or len(observed)>20000:raise ValueError('The saved speech evidence is invalid. Generate Speech timing again.')
    previous=-1
    for w in observed:
        a=w.get('start');b=w.get('end')
        if not isinstance(w.get('text'),str) or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (a,b)) or a<0 or b<=a or b>duration+.05 or a<previous:
            raise ValueError('The recognizer did not provide reliable word timing. Check the narration and retry Speech timing.')
        previous=a
    from .caption_native_match import reconcile
    decorated=caption_tokens(script)
    if not decorated:raise ValueError('Paste spoken words, rather than punctuation alone.')
    tokens=[w['spoken'] for w in decorated]
    matched=reconcile(' '.join(tokens),observed,normalizer,align_script)
    found={w['script_index'] for w in matched}
    missing_tokens=[t for i,t in enumerate(tokens) if i not in found]
    if missing_tokens and (not allow_partial or len(found)/len(tokens)<.9 or len(missing_tokens)>max(2,int(len(tokens)*.05)) or any(re.search(r'\d',t) for t in missing_tokens)):
        missing=' '.join(t for i,t in enumerate(tokens) if i not in found)
        raise AudioAlignmentRequired('The script does not match the recorded speech closely enough. Check these words: '+missing[:160]+'. Paste the final spoken script and retry; no estimated captions were added.')
    for before,after in zip(matched,matched[1:]):
        if after['start']<=before['start']+1e-5:
            raise AudioAlignmentRequired('The recognizer returned a shared phrase time instead of distinct word times. Retry Speech timing; no estimated captions were added.')
    return [{'text':decorated[w['script_index']]['text'],'start':w['start'],'end':min(duration,w['end']),'alignment':w['alignment'],'script_index':w['script_index']} for w in matched]


def recognize(factory,model_path,wav,duration,progress,model_options=None):
    model=None;segments=None;words=[]
    try:
        model=factory(model_path,**(model_options or {'device':'cpu','compute_type':'int8'}),cpu_threads=4,num_workers=1,local_files_only=True)
        from .caption_audio_alignment import guard_alignment
        guard_alignment(model)
        segments,info=model.transcribe(str(wav),beam_size=5,temperature=0,word_timestamps=True,vad_filter=True,condition_on_previous_text=False)
        for segment in segments:
            for word in segment.words or []:
                if word.probability<.20 or word.end<=word.start:continue
                parts=word.word.strip().split()
                if len(parts)!=1:raise ValueError('Speech timing could not separate a spoken word. Retry with a clearer narration track.')
                words.append({'text':parts[0],'start':max(0,float(word.start)),'end':min(duration,float(word.end)),'probability':float(word.probability)})
            progress('Matching words to the recorded speech',20+60*min(1,segment.end/duration))
        return words
    finally:
        if segments is not None and hasattr(segments,'close'):segments.close()
        segments=None;model=None;gc.collect()


def execute(root,key,*,work_lock=None):
    root=Path(root).resolve()
    if not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('Choose the saved caption timing request.')
    folder=root/'output/captions/ae-speech'/key
    request=json.loads((folder/'request.json').read_text('utf8'))
    scan=validate_capture(request['timing_context']);script=request['script']
    if not isinstance(script,str) or not script.strip() or len(script)>6000:raise ValueError('Paste the final spoken script (up to 6,000 characters).')
    def progress(stage,percent):save(folder/'status.json',{'id':key,'status':'running','stage':stage,'progress':percent})
    from hinglish_cut.model_storage import configure,role
    from hinglish_cut.gpu_lock import gpu_lock
    from .caption_compute import options_for,prepare_runtime
    compute=options_for(root);acquire=work_lock or gpu_lock;ran_model=False
    from .template_text_audio import cache_key,decode_map
    configure(root);speech=role(root,'independent_asr')
    if not speech or not Path(speech.get('path','')).is_dir():raise ValueError('The installed local speech model is unavailable. Check model settings; no caption layers were added.')
    audio_id=cache_key(scan)
    identity=hashlib.sha256(json.dumps({'audio':audio_id,'model':speech,'version':1,'backend':'faster-whisper-cpu-int8-words-no-prompt'},sort_keys=True).encode()).hexdigest()
    cache=root/'cache/caption-native-timing'/identity
    cache.mkdir(parents=True,exist_ok=True)
    wav=cache/'narration.wav';evidence=cache/'observed-words.json'
    reused_audio=evidence.is_file()
    if evidence.is_file():observed=json.loads(evidence.read_text('utf8'));progress('Reusing recorded word timing',82)
    else:
        progress('Waiting for the local speech queue',2)
        with acquire(root):
            if evidence.is_file():observed=json.loads(evidence.read_text('utf8'))
            else:
                if not wav.is_file():
                    progress('Reading narration audio only',8)
                    temporary=wav.with_suffix('.partial.wav');decode_map(scan,temporary);temporary.replace(wav)
                progress('Transcribing speech with the local word-timing model',18)
                from faster_whisper import WhisperModel
                prepare_runtime(root,compute);observed=recognize(WhisperModel,speech['path'],wav,scan['duration'],progress,model_options=compute);ran_model=True
                save(evidence,observed)
    progress('Aligning your exact script to the spoken words',85)
    from uroman import Uroman
    from .template_text_model import speech_normal
    romanizer=Uroman()
    normalizer=lambda t:speech_normal(romanizer.romanize_string(str(t),lcode='hin'))
    recovery_file=cache/'observed-window-recovery-v1.json'
    recognition_recovered=False
    try:align_words(script,observed,scan['duration'],normalizer)
    except AudioAlignmentRequired:
        from .caption_scope import scope_problem
        scope=scope_problem(script,observed,request['timing_context'],normalizer)
        if scope:raise ValueError(scope)
        if not recovery_file.is_file():
            progress('Rechecking incomplete speech recognition',24)
            with acquire(root):
                if not recovery_file.is_file():
                    if not wav.is_file():
                        temporary=wav.with_suffix('.partial.wav');decode_map(scan,temporary);temporary.replace(wav)
                    from faster_whisper import WhisperModel
                    from .caption_recognition_recovery import recognize_windows
                    prepare_runtime(root,compute)
                    retry=recognize_windows(WhisperModel,speech['path'],wav,scan['duration'],progress,compute);ran_model=True
                    save(recovery_file,retry)
        observed=json.loads(recovery_file.read_text('utf8'));recognition_recovered=True
    backend='faster-whisper'
    try:words=align_words(script,observed,scan['duration'],normalizer)
    except AudioAlignmentRequired:
        from .caption_scope import scope_problem
        scope=scope_problem(script,observed,request['timing_context'],normalizer)
        if scope:raise ValueError(scope)
        from .caption_audio_alignment import align_from_audio
        aligned_key=hashlib.sha256(json.dumps({'script':script,'audio':identity,'evidence':observed,'engine':'anchored-whisper-v4'},sort_keys=True).encode()).hexdigest()
        aligned_file=cache/'aligned'/('v4-'+aligned_key+'.json')
        if aligned_file.is_file():words=json.loads(aligned_file.read_text('utf8'))
        else:
            progress('Waiting for direct audio alignment',84)
            with acquire(root):
                if aligned_file.is_file():words=json.loads(aligned_file.read_text('utf8'))
                else:
                    if not wav.is_file():
                        temporary=wav.with_suffix('.partial.wav');decode_map(scan,temporary);temporary.replace(wav)
                    prepare_runtime(root,compute);words=align_from_audio(speech['path'],wav,script,observed,scan['duration'],normalizer,progress,model_options=compute);ran_model=True
                    save(aligned_file,words)
        backend='faster-whisper-direct-alignment'
    project={'version':1,'kind':'storylens-native-speech','media':{'duration':scan['duration']},'reference_script':script,'caption_script':' '.join(w['text'] for w in words),'cues':[{'start':w['start'],'end':w['end'],'words':[w]} for w in words],'transcription':{'timing_method':'speech','backend':backend,'model':speech.get('repo'),'device':'cpu','compute_type':'int8','audio_cache':identity,'script_words':len(words),'estimated_words':0,'omitted_script_words':[],'context_corrections':[w['text'] for w in words if w['alignment']=='context-corrected'],'acoustic_review_words':[w['text'] for w in words if w.get('review_reason')],'phrase_timed_words':[w['text'] for w in words if w['alignment']=='acoustic_phrase']}}
    project['transcription'].update({'requested_device':compute['device'],'device':compute['device'] if ran_model else 'cached','compute_type':compute['compute_type'] if ran_model else 'cached','reused_audio_evidence':reused_audio,'recognition_recovered':recognition_recovered})
    save(folder/'caption-project.json',project)
    save(folder/'status.json',{'id':key,'status':'complete','stage':'Speech timing ready','progress':100,'folder':str(folder),'words':len(words)})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--id',required=True);args=parser.parse_args()
    try:execute(args.root,args.id);return 0
    except Exception as error:
        from .user_messages import problem
        if re.fullmatch('[a-f0-9]{32}',args.id):save(args.root/'output/captions/ae-speech'/args.id/'status.json',{'id':args.id,'status':'failed','stage':'Speech timing stopped','error':problem(error,feature='Caption speech timing')})
        print(str(error),flush=True);return 1


if __name__=='__main__':raise SystemExit(main())
