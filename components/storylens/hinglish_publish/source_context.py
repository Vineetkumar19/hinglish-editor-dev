"""Recover recorded speech for an exact saved export, never from its filename."""
from pathlib import Path
import json
from .store import fingerprint

def preserve_transcript(root, source, target):
    """Carry measured export speech to an identical renamed delivery copy.

    Publishing copies lose the source library's filename lookup. Recover only
    hash-verified export words, never a title or a neighbouring video's script.
    Existing owner transcripts always win; originals are never written.
    """
    source, target = Path(source), Path(target)
    sidecar = target.with_suffix('.txt')
    if sidecar.is_file():return False
    digest = fingerprint(target)
    if fingerprint(source) != digest:
        raise ValueError('The selected publishing copy changed. No transcript or upload was prepared.')
    text, receipt = saved_transcript(root, source)
    if not text:return False
    if receipt.get('sha256') != digest or fingerprint(target) != digest:
        raise ValueError('The selected publishing copy changed. No transcript or upload was prepared.')
    from hinglish_app.durable_json import write
    write(target.with_suffix('.transcript-source.json'), receipt)
    # Exclusive creation also preserves a transcript saved while lookup ran.
    try:
        with sidecar.open('x', encoding='utf-8') as stream:stream.write(text)
    except FileExistsError:return False
    return True


def spoken_context(root,video,transcript,progress):
    """Prefer the owner's script, then exact export evidence, before fresh ASR."""
    if transcript is not None:return transcript,None
    path=Path(video);sidecar=path.with_suffix('.txt')
    if sidecar.is_file():return sidecar.read_text('utf-8-sig'),{'method':'creator_transcript','path':str(sidecar)}
    text,receipt=saved_transcript(root,path)
    if text:return text,receipt
    from hinglish_shorts.source import open_video,transcribe
    from hinglish_cut.model_preferences import preferred_device
    words=transcribe(root,open_video(path),device=preferred_device(root),progress=progress,retry_unreadable=True)
    return ' '.join(w.text for w in words),{'method':'speech_recognition'}

def saved_transcript(root,video):
    root=Path(root).resolve();video=Path(video).resolve();candidates=[];digest=None
    if (video.parent/'shorts-project.json').is_file():candidates.append(video)
    for library in dict.fromkeys([video.parent/'library.json',root/'All Shorts/library.json']):
        if not library.is_file() or library.stat().st_size>8*1024**2:continue
        try:rows=json.loads(library.read_text('utf-8-sig')).get('shorts',[])
        except (ValueError,OSError):continue
        matching=[r for r in rows if r.get('file')==video.name]
        if not matching:continue
        digest=digest or fingerprint(video)
        for row in matching:
            if row.get('sha256')!=digest:continue
            for value in row.get('original_paths',[]):
                original=Path(value).resolve()
                if original.is_relative_to(root/'output') and original.is_file() and fingerprint(original)==digest:candidates.append(original)
    found={}
    for original in dict.fromkeys(candidates):
        project=original.parent/'shorts-project.json'
        if not project.is_file() or project.stat().st_size>32*1024**2:continue
        try:
            data=json.loads(project.read_text('utf-8-sig'))
            entries=[s for s in data.get('shorts',[]) if (project.parent/s.get('mp4','')).resolve()==original]
            if len(entries)!=1:continue
            pieces=entries[0]['pieces'];words=data['words']
            if not isinstance(pieces,list) or not pieces or any(len(p)!=2 or not 0<=p[0]<p[1] for p in pieces):continue
            text=' '.join(str(w[0]) for w in words if any(a<=(float(w[1])+float(w[2]))/2<b for a,b in pieces)).strip()
            if text:found[text]={'method':'saved_export_word_timings','project':str(project),'original':str(original),'sha256':digest or fingerprint(video),'pieces':pieces}
        except (ValueError,OSError,TypeError,KeyError,IndexError):continue
    return next(iter(found.items())) if len(found)==1 else ('',None)
