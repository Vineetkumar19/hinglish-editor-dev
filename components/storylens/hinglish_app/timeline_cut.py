"""Local cut analysis with a reversible mapping back to original timeline media."""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET
import math

from hinglish_zoom.xml_apply import Sequence
from hinglish_broll.timeline import read_rate


def unchanged_audio(item):
    """Premiere exports its default unity-gain control even on untouched clips."""
    for node in item.findall('filter'):
        effect=node.find('effect')
        if effect is None or (effect.findtext('effectid') or '').lower()!='audiolevels':return False
        params=effect.findall('parameter')
        if not params:return False
        for parameter in params:
            if parameter.findtext('parameterid')!='level' or parameter.findall('.//keyframe'):return False
            try:value=float(parameter.findtext('value',''))
            except (TypeError,ValueError):return False
            if not math.isfinite(value) or abs(value-1)>1e-9:return False
    return True


def validate(path):
    seq=Sequence(path)
    message='This timeline has layers, gaps, transitions or effects that this cut round trip cannot preserve yet. Export a video for analysis, or use a copy containing straight cuts and linked camera audio. Your original timeline is kept.'
    if not seq.clips or any(t.findall('clipitem') for t in seq.upper):raise ValueError(message)
    position=0
    for c in sorted(seq.clips,key=lambda c:c.start):
        if c.start!=position or not c.zoomable or not Path(c.path).is_file():raise ValueError(message)
        if any((e.findtext('effectid') or '').lower()!='basic' for e in c.item.findall('./filter/effect')):raise ValueError(message)
        position=c.end
    if position!=seq.frames or seq.sequence.findall('.//transitionitem'):raise ValueError(message)
    # Analysis uses linked camera audio only. Reject music/voiceovers instead of
    # silently removing them or analysing audio that differs from the timeline.
    for track in seq.sequence.findall('./media/audio/track'):
        if (track.findtext('enabled') or 'TRUE').upper()=='FALSE':raise ValueError(message)
        if len(track.findall('clipitem'))!=len(seq.clips):raise ValueError(message)
        for item in track.findall('clipitem'):
            file=item.find('file');source=seq.files.get(file.get('id')) if file is not None else None
            a=int(item.findtext('start','-1'));b=int(item.findtext('end','-1'))
            match=next((c for c in seq.clips if c.start==a and c.end==b and c.path==source),None)
            if match is None or int(item.findtext('in','0'))!=match.source_in or not unchanged_audio(item) or (item.findtext('enabled') or 'TRUE').upper()=='FALSE':raise ValueError(message)
    return seq


def prepare(path,work,progress):
    validate(path)
    from .assistant_media import render_xml
    target=Path(work)/'timeline-analysis.mp4'
    progress('Reading the saved timeline, including its existing trims')
    return Path(render_xml(path,target,progress))


def remap(original,analysed,edited,target):
    """Project kept intervals from the analysed movie back onto source clips."""
    seq=validate(original);out=Sequence(edited)
    if any(Path(c.path).resolve()!=Path(analysed).resolve() for c in out.clips):
        # The clean tool links/copies the conformed source into its output.
        from hinglish_cut.media import fingerprint
        digest=fingerprint(analysed)
        if any(fingerprint(c.path)!=digest for c in out.clips):
            raise ValueError('The cut result uses a changed analysis video. Keep the original timeline and review the result before importing it.')
    ranges=[]
    for c in sorted(out.clips,key=lambda c:c.start):
        a,b=c.source_seconds(out.fps)
        a=round(a*float(seq.fps));b=round(b*float(seq.fps))
        if a<0 or b>seq.frames or b<=a:raise ValueError('The cut result exceeds the saved timeline. Keep the original and review the cut details.')
        ranges.append((a,b))
    files={f.get('id'):deepcopy(f) for f in seq.root.iter('file') if f.findtext('pathurl')}
    for track in seq.sequence.findall('./media/video/track')+seq.sequence.findall('./media/audio/track'):
        original_items=list(track.findall('clipitem'))
        for item in original_items:track.remove(item)
        offset=0;piece=0
        for a,b in ranges:
            for item in original_items:
                start=int(item.findtext('start'));end=int(item.findtext('end'))
                left=max(a,start);right=min(b,end)
                if right<=left:continue
                clone=deepcopy(item);piece+=1;clone.set('id',f'{item.get("id")}-storylens-{piece}')
                rate=read_rate(item,seq.fps);source_in=int(item.findtext('in','0'))+round(Fraction(left-start)*rate/seq.fps)
                for name,value in [('start',offset+left-a),('end',offset+right-a),('in',source_in),('out',source_in+round(Fraction(right-left)*rate/seq.fps))]:clone.find(name).text=str(value)
                for node in list(clone):
                    if node.tag in ('pproTicksIn','pproTicksOut'):clone.remove(node)
                for link in clone.findall('link'):
                    ref=link.find('linkclipref')
                    if ref is not None:ref.text=f'{ref.text}-storylens-{piece}'
                    index=link.find('clipindex')
                    if index is not None:index.text=str(piece)
                f=clone.find('file')
                if f is not None and f.get('id') in files:
                    clone.remove(f);clone.append(deepcopy(files[f.get('id')]))
                track.append(clone)
            offset+=b-a
    seq.sequence.find('duration').text=str(sum(b-a for a,b in ranges))
    seq.sequence.find('name').text=(seq.sequence.findtext('name') or 'Timeline')+' - Storylens edited copy'
    ET.indent(seq.tree,space='  ');seq.tree.write(target,encoding='utf-8',xml_declaration=True)
    return str(Path(target).resolve())
