"""Final Cut Pro 7 XML (xmeml v5), not modern Apple FCPXML."""
from pathlib import Path
from fractions import Fraction
import math
import xml.etree.ElementTree as ET
from urllib.parse import quote

OUTPUT_FORMATS={
    'instagram_vertical':(1080,1920),
    'square':(1080,1080),
    'youtube_horizontal':(1920,1080),
}


def add(parent,name,value=None,**attrs):
    e=ET.SubElement(parent,name,attrs)
    if value is not None:
        e.text=str(value)
    return e


def rate(parent,fps):
    value=Fraction(fps)
    r=add(parent,'rate')
    nominal=round(float(value))
    if value not in (Fraction(nominal),Fraction(nominal*1000,1001)):
        raise ValueError(f'Unsupported XML frame rate: {fps}')
    add(r,'timebase',nominal)
    add(r,'ntsc','TRUE' if value.denominator==1001 else 'FALSE')


def video_format(parent,m):
    video_format_dimensions(parent,m.width,m.height,m.fps)


def video_format_dimensions(parent,width,height,fps):
    rate(parent,fps)
    add(parent,'width',width)
    add(parent,'height',height)
    add(parent,'anamorphic','FALSE')
    add(parent,'pixelaspectratio','square')
    add(parent,'fielddominance','none')


def premiere_pathurl(media_path):
    """Use Premiere's Windows-compatible FCP 7 file URI form.

    Premiere Pro treats ``file:///E:/...`` as a network/UNC location on some
    Windows builds. Giving it an explicit localhost host makes it resolve to
    the local E: drive instead.
    """
    absolute=Path(media_path).resolve().as_posix()
    return 'file://localhost/' + quote(absolute,safe='/:')


def canvas_for(output_format,source):
    if output_format is None:
        return source.width,source.height
    try:
        return OUTPUT_FORMATS[output_format]
    except KeyError as error:
        raise ValueError(f'Unknown output format: {output_format}') from error


def add_fit_motion(clip_item,source,canvas_width,canvas_height):
    """Keep the entire rotated source visible; never create an automatic crop."""
    scale=min(canvas_width/source.width,canvas_height/source.height)*100
    filter_node=add(clip_item,'filter')
    effect=add(filter_node,'effect')
    add(effect,'name','Basic Motion')
    add(effect,'effectid','basic')
    add(effect,'effecttype','motion')
    add(effect,'mediatype','video')
    parameter=add(effect,'parameter')
    add(parameter,'parameterid','scale')
    add(parameter,'name','Scale')
    add(parameter,'value',f'{scale:.6f}'.rstrip('0').rstrip('.'))


def export_xml(path,cuts,media,output_format=None):
    if not cuts:
        raise ValueError('No matched cuts to export')
    used=[media[c.media_id] for c in cuts]
    if len({m.rate for m in used})!=1:
        raise ValueError('Mixed frame rates: conform source files to one constant frame rate first')
    for c in cuts:
        m=media[c.media_id]
        if c.start_frame<0 or c.end_frame<=c.start_frame or c.end_frame>math.floor(m.duration*float(m.rate)+1e-6):
            raise ValueError(f'Invalid source bounds: {c}')
    root=ET.Element('xmeml',version='5')
    seq=add(root,'sequence',id='sequence-1')
    add(seq,'name',Path(path).stem)
    add(seq,'duration',sum(c.duration for c in cuts))
    rate(seq,used[0].fps)
    tc=add(seq,'timecode'); rate(tc,used[0].fps)
    add(tc,'string','00:00:00:00'); add(tc,'frame',0); add(tc,'displayformat','NDF')
    med=add(seq,'media'); video=add(med,'video')
    canvas_width,canvas_height=canvas_for(output_format,used[0])
    video_format_dimensions(add(add(video,'format'),'samplecharacteristics'),canvas_width,canvas_height,used[0].fps)
    vt=add(video,'track')
    max_channels=max(m.channels for m in used)
    ats=[]
    if max_channels:
        audio=add(med,'audio')
        add(audio,'numOutputChannels',max_channels)
        af=add(add(audio,'format'),'samplecharacteristics')
        add(af,'depth',16); add(af,'samplerate',48000)
        ats=[add(audio,'track') for _ in range(max_channels)]
    file_ids={m.id:f'file-{i+1}' for i,m in enumerate({m.id:m for m in used}.values())}
    seen=set(); position=0
    audio_counts=[0]*max_channels
    for i,c in enumerate(cuts,1):
        m=media[c.media_id]
        ids=[f'v-{i}']+[f'a-{i}-{ch+1}' for ch in range(m.channels)]
        for ch in range(m.channels):
            audio_counts[ch]+=1
        for kind,channel,parent,clip_id in [('video',0,vt,ids[0])]+[('audio',ch+1,ats[ch],ids[ch+1]) for ch in range(m.channels)]:
            ci=add(parent,'clipitem',id=clip_id)
            add(ci,'name',f'{Path(m.path).name} | script {c.line_index+1}')
            add(ci,'enabled','TRUE'); add(ci,'duration',math.floor(m.duration*float(m.rate)+1e-6))
            rate(ci,m.fps)
            for tag,value in [('start',position),('end',position+c.duration),('in',c.start_frame),('out',c.end_frame)]:
                add(ci,tag,value)
            if kind=='video' and output_format is not None:
                add_fit_motion(ci,m,canvas_width,canvas_height)
            f=add(ci,'file',id=file_ids[m.id])
            if m.id not in seen:
                seen.add(m.id)
                add(f,'name',Path(m.path).name); add(f,'pathurl',premiere_pathurl(m.path))
                rate(f,m.fps); add(f,'duration',math.floor(m.duration*float(m.rate)+1e-6))
                ft=add(f,'timecode'); rate(ft,m.fps)
                add(ft,'string','00:00:00:00'); add(ft,'frame',0); add(ft,'displayformat','NDF')
                fm=add(f,'media'); fv=add(fm,'video')
                video_format(add(fv,'samplecharacteristics'),m)
                if m.channels:
                    fa=add(fm,'audio'); asc=add(fa,'samplecharacteristics')
                    add(asc,'depth',16); add(asc,'samplerate',m.sample_rate)
                    add(fa,'channelcount',m.channels)
            if kind=='audio':
                source=add(ci,'sourcetrack'); add(source,'mediatype','audio'); add(source,'trackindex',channel)
            for li,lid in enumerate(ids):
                link=add(ci,'link'); add(link,'linkclipref',lid)
                add(link,'mediatype','video' if li==0 else 'audio')
                add(link,'trackindex',1 if li==0 else li)
                add(link,'clipindex',i if li==0 else audio_counts[li-1])
                if li:
                    add(link,'groupindex',1)
        position+=c.duration
    ET.indent(root,space='  ')
    data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    Path(path).write_bytes(data.replace(b'?>',b'?>\n<!DOCTYPE xmeml>',1))
