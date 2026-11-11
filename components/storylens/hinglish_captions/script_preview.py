"""Editable, silent caption projects from pasted text; no transcription."""
from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
from uuid import uuid4

from hinglish_cut.media import probe
from .core import CaptionWord, build_cues
from .project import write_project
from .report import write_report
from .styles import SELECTABLE_TEMPLATES, template
from .template_patterns import bind_patterns


FORMATS={'instagram_vertical':(720,1280),'square':(720,720),'youtube_horizontal':(1280,720)}


def script_cues(text, duration, style):
    if not isinstance(text,str) or not text.strip():raise ValueError('Paste captions to preview')
    if len(text)>6000:raise ValueError('Caption preview text is too long')
    tokens=text.split()
    if len(tokens)*.04>duration:raise ValueError('Caption preview needs more time')
    weights=[max(3,min(10,len(w))) for w in tokens];total=sum(weights)
    words=[];clock=0
    for index,(token,weight) in enumerate(zip(tokens,weights)):
        end=duration if index==len(tokens)-1 else clock+.04+(duration-.04*len(tokens))*weight/total
        words.append(CaptionWord(token,clock,end));clock=end
    # Each pasted line starts a new caption group. Long lines paginate using
    # the same template rules as ordinary projects.
    cues=[];cursor=0
    for line in text.splitlines():
        count=len(line.split())
        if count:
            cues.extend(build_cues(words[cursor:cursor+count],max_words=min(7,template(style).get('max_words',5)),max_chars=60,max_seconds=duration))
            cursor+=count
    cues=[replace(q,end=min(q.end,cues[i+1].start if i+1<len(cues) else duration)) for i,q in enumerate(cues)]
    return bind_patterns(cues)


def create_script_preview(root,payload, *, planned_cues=None, provenance=None):
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(root):
        return _create_script_preview(root,payload,planned_cues=planned_cues,provenance=provenance)


def _create_script_preview(root,payload, *, planned_cues=None, provenance=None):
    style=payload.get('style','caption_2')
    if not isinstance(style,str) or style not in SELECTABLE_TEMPLATES:raise ValueError('Choose a caption preview template')
    output_format=payload.get('format','instagram_vertical')
    if not isinstance(output_format,str) or output_format not in FORMATS:raise ValueError('Choose a caption preview format')
    try:duration=float(payload.get('duration',30))
    except (TypeError,ValueError):raise ValueError('Choose a caption preview duration') from None
    if isinstance(payload.get('duration'),bool) or not math.isfinite(duration) or not 3<=duration<=180:
        raise ValueError('Choose a caption preview duration')
    text=payload.get('text','');cues=script_cues(text,duration,style)
    if planned_cues is not None:
        if [w.text for q in planned_cues for w in q.words] != text.split():
            raise ValueError('The caption plan changed your words. Keep your script and generate again.')
        cues=planned_cues
    folder=Path(root).resolve()/'output/captions/script-previews'/uuid4().hex
    folder.mkdir(parents=True)
    source=folder/'source.mp4';width,height=FORMATS[output_format]
    color='white' if style in ('caption_3','caption_5') else 'black'
    if provenance:color='black'
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.compute_policy import ffmpeg_h264
    from hinglish_cut.compute_policy import heavy_device
    encoder=ffmpeg_h264(heavy_device(root),28)
    result=subprocess.run([get_ffmpeg_exe(),'-nostdin','-v','error','-y','-f','lavfi','-i',f'color=c={color}:s={width}x{height}:r=30',
        '-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',str(duration),*encoder,'-threads','2','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(source)],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Caption preview media could not be prepared: '+result.stderr[-1200:])
    project=write_project(folder/'caption-project.json',probe(source),cues,style,'source',source.name,reference_script=text)
    project.update(demo=True,demo_background=color,caption_content='speech',word_visibility='phrase',
                   script_preview=True,preview_stale=True,omit_source_video=True,project_path=str(folder/'caption-project.json'))
    if provenance:project['auto_caption_2']=provenance
    (folder/'caption-project.json').write_text(json.dumps(project,ensure_ascii=False,indent=2),'utf-8')
    (folder/'transcript.txt').write_text(text,'utf-8')
    write_report(folder/'report.html','Pasted captions',source.name,cues,style,[('Your script','transcript.txt')],project)
    return {'url':f'/caption-output/script-previews/{folder.name}/report.html','duration':duration,'words':sum(len(q.words) for q in cues)}
