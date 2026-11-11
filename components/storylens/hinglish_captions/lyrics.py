"""Full-context song recognition and exact-reference lyric timing, without speech VAD gates."""
from dataclasses import replace
from difflib import SequenceMatcher
import gc
import math
import re
from pathlib import Path

from .core import CaptionCue,CaptionWord,build_cues


def reference_cues(lines,words,duration):
    expected=[token for line in lines for token in line.split()]
    if [word.text for word in words]!=expected:
        raise ValueError('Lyric timing changed the supplied words')
    cues=[];cursor=0
    for line in lines:
        count=len(line.split());group=tuple(words[cursor:cursor+count]);cursor+=count
        if count>5 or len(line)>34:
            cues.extend(build_cues(group,max_words=5,max_chars=28,max_seconds=5.5))
        else:
            cues.append(CaptionCue(group,group[0].start,min(duration,group[-1].end+.08)))
    return [replace(cue,end=min(cue.end,cues[i+1].start) if i+1<len(cues) else cue.end)
            for i,cue in enumerate(cues)]


def mapped_reference_words(lines,heard,romanize):
    """Only transfer word attention when the complete ordered phrase agrees.

    The reference supplies spelling; it is never fed to the recognizer as a prompt.
    Unsupported words stay reviewable rather than being called independent ASR.
    """
    expected=[token for line in lines for token in line.split()]
    normal=lambda text:re.sub('[^a-z]','',romanize(text).casefold())
    if len(expected)!=len(heard):return None,[]
    matches=[SequenceMatcher(None,normal(a),normal(b['text'])).ratio()>=.70 for a,b in zip(expected,heard)]
    if not matches or sum(matches)/len(matches)<.75:return None,[]
    words=[CaptionWord(text,float(row['start']),float(row['end'])) for text,row in zip(expected,heard)]
    changes=[{'reference':text,'recognized':row['text'],'start':row['start']}
             for text,row,match in zip(expected,heard,matches) if not match]
    return words,changes


def transcribe_song(root,media,reference='',device='cuda',progress=print,analysis_audio=None):
    import numpy as np
    import torch
    from faster_whisper import WhisperModel
    from uroman import Uroman
    from hinglish_cut.media import extract_audio,read_audio,fingerprint
    from hinglish_cut.model_storage import role,configure
    from hinglish_cut.model_preferences import release_ollama
    from hinglish_cut.recognition_quality import checked_transcript
    configure(root);release_ollama(root)
    selected=role(root,'independent_asr')
    if not selected:raise ValueError('Install and select the independent speech model for song lyrics first.')
    cache=Path(root)/'cache/captions/lyrics'/fingerprint(Path(media.path));cache.mkdir(parents=True,exist_ok=True)
    wav=Path(analysis_audio).resolve() if analysis_audio is not None else cache/'full-song.wav'
    if analysis_audio is None:extract_audio(media,wav)
    audio=read_audio(wav)
    if not np.isfinite(audio).all():raise ValueError('The audio contains invalid samples')
    if device!='cuda':raise ValueError('Song lyric inference is configured for NVIDIA RTX. Select NVIDIA RTX.')
    if not torch.cuda.is_available():raise RuntimeError('NVIDIA CUDA is unavailable; song inference will not silently switch to CPU.')
    torch.set_num_threads(8)
    # Loading through Torch exposes the installed CUDA/cuBLAS DLLs to native
    # CTranslate2 on Windows. The previous speech backend did this in its base
    # constructor; this direct full-song path needs the same initialization.
    (torch.ones((8,8),device='cuda')@torch.ones((8,8),device='cuda')).sum().item()
    progress('  Recognizing the whole song excerpt on NVIDIA RTX (no speech-only cuts)')
    model=WhisperModel(selected['path'],device='cuda',compute_type='float16',cpu_threads=8,local_files_only=True)
    try:
        # Roman Hinglish output implies Hindi transcription, not language auto-
        # detection from a music-heavy intro (which can select English incorrectly).
        segments,info=model.transcribe(audio,language='hi',task='transcribe',beam_size=5,
            condition_on_previous_text=False,vad_filter=False,temperature=0,word_timestamps=True)
        rows=list(segments)
        recognized=checked_transcript(' '.join(row.text.strip() for row in rows))
        heard=[{'text':word.word.strip(),'start':word.start,'end':word.end,
                'probability':word.probability} for row in rows for word in row.words or []]
        if not heard:raise ValueError('No lyrics could be recognized. Supply the exact lyric lines for review.')
        backend_device=str(model.model.device)
    finally:del model;gc.collect()
    romanizer=Uroman();romanize=lambda text:romanizer.romanize_string(text,lcode='hin')
    lines=[line.strip() for line in reference.splitlines() if line.strip()]
    warnings=[]
    if lines:
        words,changes=mapped_reference_words(lines,heard,romanize)
        if words is None:
            from hinglish_cut.backends import LocalSpeech
            from hinglish_cut.model import Settings
            engine=LocalSpeech(Settings(device=device,offline=True,cpu_threads=8),Path(root)/'models')
            try:
                aligned=engine.align(audio,' '.join(lines))
                if not aligned or sum(word.score>=.1 for word in aligned)/len(aligned)<.6:
                    raise ValueError('The supplied lyric lines do not align confidently to this song excerpt.')
                words=[CaptionWord(word.text,word.start,word.end) for word in aligned]
            finally:engine.close()
            warnings.append('reference_alignment_needs_timing_review')
            method='MMS forced alignment of user-supplied lyrics'
        else:
            method='Independent Whisper word attention mapped to ordered user-supplied lyrics'
            # Whisper sometimes stretches the first word across the musical
            # intro. Refine that onset against the supplied text rather than
            # displaying the word from frame zero.
            if words and words[0].start <= .02 and words[0].end > 1:
                from hinglish_cut.backends import LocalSpeech
                from hinglish_cut.model import Settings
                engine=LocalSpeech(Settings(device=device,offline=True,cpu_threads=8),Path(root)/'models')
                try:
                    aligned=engine.align(audio,' '.join(lines))
                    if aligned and aligned[0].text==words[0].text and aligned[0].score>=.1 and words[0].start<aligned[0].start<words[0].end-.02:
                        words[0]=replace(words[0],start=aligned[0].start)
                        method+='; leading word onset refined with MMS alignment'
                finally:engine.close()
        if changes:warnings.append('reference_corrected_recognition: '+', '.join(change['reference'] for change in changes))
        cues=reference_cues(lines,words,media.duration)
    else:
        words=[CaptionWord(romanize(row['text']),float(row['start']),float(row['end'])) for row in heard]
        cues=build_cues(words,max_words=5,max_chars=28,max_seconds=5.5)
        method='Independent Whisper full-context Hindi transcription and Roman transliteration'
        warnings.append('automatic_song_transcript_needs_lyric_review')
    if any(not (math.isfinite(word.start) and math.isfinite(word.end) and 0<=word.start<word.end<=media.duration+.05) for word in words):
        raise ValueError('The song model returned invalid word timing')
    metadata={'mode':'lyrics','device':device,'backend_device':backend_device,'model_path':selected['path'],
        'model_revision':selected['revision'],'vad_filter':False,'language':'hi','timing_method':method,
        'reference_authoritative':bool(lines),'recognized_text':recognized,'warnings':warnings,
        'accuracy_scope':'Reference wording is supplied by the user. Timing is model-aligned and reviewable; automatic transcription accuracy is not certified.'}
    return cues,metadata
