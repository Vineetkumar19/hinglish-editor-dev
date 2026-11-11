"""Playable human-choice banks shared by the review and editor adapters."""
from pathlib import Path


def rows(project,folder):
    folder=Path(folder)
    result=[]
    for slot in project.get('slots',[]):
        for index,option in enumerate(slot.get('options',[]),1):
            path=(folder/option['clip']).resolve()
            if not path.is_file():continue
            label=f'{slot["start"]:05.2f}s | {slot["text"][:65]} | option {index}'
            result.append({'path':str(path),'name':label,'start':slot['start'],'end':slot['end'],
                           'source_in':option.get('source_in',0),
                           'source_duration':option.get('source_duration',slot['end']-slot['start']),
                           'slot':slot['index'],'id':option['id']})
    return result


def export_xml(project,folder):
    import xml.etree.ElementTree as ET
    from fractions import Fraction
    from hinglish_cut.xml_export import add,rate,video_format_dimensions
    from .xml_export import build_track
    t=project['timeline'];fps=Fraction(t['fps']);placements=[];position=0
    for item in rows(project,folder):
        length=min(round(4*fps),round(item['source_duration']*fps)-round(item['source_in']*fps))
        if length<=0:continue
        placements.append({**item,'start':float(position/fps),'end':float((position+length)/fps)})
        position+=length+round(float(fps)*.25)
    if not placements:return
    root=ET.Element('xmeml',version='5');seq=add(root,'sequence',id='broll-human-options')
    add(seq,'name',t['name']+' - B-roll keyword options');add(seq,'duration',position);rate(seq,str(fps))
    video=add(add(seq,'media'),'video')
    video_format_dimensions(add(add(video,'format'),'samplecharacteristics'),t['width'],t['height'],str(fps))
    video.append(build_track(placements,fps,t['width'],t['height'],'option'))
    ET.indent(root,space='  ')
    Path(folder,'BROLL_OPTIONS.xml').write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True))
