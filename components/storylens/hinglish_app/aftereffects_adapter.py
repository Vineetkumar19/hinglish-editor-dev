"""Translate our generated FCP7 cuts into an AE composition import manifest.

Only plain cut timelines are reconstructed. Effects remain rendered media; AE
cannot interpret Premiere effects, nested sequences or transitions from XML.
"""
import math
from pathlib import Path
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET


def fps(node,default=30):
    if node is None:return default
    nominal=float(node.findtext('timebase','30'))
    return nominal*1000/1001 if node.findtext('ntsc','FALSE')=='TRUE' else nominal


def local_path(value):
    uri=urlparse(value)
    if uri.scheme!='file' or uri.netloc not in ('','localhost'):raise ValueError('AE import only accepts local media.')
    value=unquote(uri.path)
    if len(value)>2 and value[0]=='/' and value[2]==':':value=value[1:]
    return value


def cut_manifest(path):
    if Path(path).stat().st_size>20*1024**2:raise ValueError('This timeline is too large for AE import.')
    root=SafeET.parse(path).getroot();seq=root.find('sequence')
    if seq is None:raise ValueError('AE requires a generated, non-nested FCP7 timeline.')
    if seq.findall('.//transitionitem') or seq.findall('.//filter') or seq.findall('.//clipitem/sequence'):
        raise ValueError('Import the rendered result for timelines containing effects or transitions.')
    files={f.get('id'):f for f in seq.findall('.//file') if f.find('pathurl') is not None}
    rate=fps(seq.find('rate'));width=int(seq.findtext('media/video/format/samplecharacteristics/width','1920'))
    height=int(seq.findtext('media/video/format/samplecharacteristics/height','1080'));duration=int(seq.findtext('duration','0'))/rate
    if not (1<=width<=16384 and 1<=height<=16384 and math.isfinite(duration) and 0<duration<=86400):raise ValueError('Invalid composition dimensions or duration.')
    clips=[];seen_audio=set()
    for kind in ('video','audio'):
        for track in seq.findall('media/'+kind+'/track'):
            for clip in track.findall('clipitem'):
                file=clip.find('file')
                if file is None:raise ValueError('Missing timeline media.')
                source=file if file.find('pathurl') is not None else files.get(file.get('id'))
                if source is None:raise ValueError('Missing timeline media definition.')
                start=int(clip.findtext('start','-1'));end=int(clip.findtext('end','-1'));source_in=int(clip.findtext('in','-1'))
                if min(start,source_in)<0 or end<=start:raise ValueError('Invalid timeline trim.')
                item={'path':local_path(source.findtext('pathurl','')),'kind':kind,'start':start/rate,
                      'end':end/rate,'source_in':source_in/fps(clip.find('rate'),rate)}
                # FCP7 exports stereo as separate channel tracks. AE's footage
                # layer plays the full source audio, so do not double its volume.
                signature=(item['path'],item['start'],item['end'],item['source_in'])
                if kind=='audio' and signature in seen_audio:continue
                if kind=='audio':seen_audio.add(signature)
                clips.append(item)
    if not clips:raise ValueError('This timeline contains no usable clips.')
    return {'type':'cuts','name':seq.findtext('name','Hinglish Edit'),'width':width,'height':height,
            'fps':rate,'duration':duration,'clips':clips}


def result_manifest(job):
    if job['status']!='complete' or not job.get('result'):raise ValueError('Wait for the edit to complete first.')
    result=job['result']
    if job['mode'] in ('clean','script'):
        for path in result.get('xml_files',[]):
            try:return cut_manifest(path)
            except ValueError:continue
    preferred=result.get('previews',[])
    media=preferred or [p for p in result.get('media',[]) if Path(p).suffix.lower() in ('.mp4','.wav')]
    if job['mode']=='aiimage':media=[p for p in result.get('media',[]) if Path(p).suffix.lower() in ('.png','.jpg','.jpeg')]
    if not media:raise ValueError('Render the reviewed result before importing it into After Effects. Original layers were kept intact.')
    return {'type':'rendered','name':'Hinglish '+job['mode'],'paths':media,'note':'Rendered effects are imported as footage, not native editable AE effects.'}
