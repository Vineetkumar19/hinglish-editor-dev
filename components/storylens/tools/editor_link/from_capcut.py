"""Export basic saved CapCut video/audio cuts to FCP 7 XML without rendering.

Unsupported processing stops conversion instead of silently dropping appearance.
The original CapCut draft is read-only. Generated XML can go to Premiere/Resolve.
"""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from hinglish_cut.xml_export import add,rate,video_format_dimensions,premiere_pathurl
from hinglish_app.capcut_adapter import media_path


def export(draft, output):
    import av
    data=json.loads((draft/'draft_content.json').read_text('utf8'))
    fps=Fraction(str(data['fps'])).limit_denominator(1001)
    canvas=data['canvas_config']
    materials={m['id']:m for k in ('videos','audios') for m in data['materials'].get(k,[])}
    infos={}
    def info(mid):
        if mid in infos:return infos[mid]
        m=materials[mid]; path=media_path(draft,m['path'])
        if not path.is_file():raise ValueError('Missing CapCut media: '+str(path))
        with av.open(str(path)) as c:
            v=c.streams.video[0] if c.streams.video else None
            a=c.streams.audio[0] if c.streams.audio else None
            result={'path':path,'width':v.width if v else 0,'height':v.height if v else 0,
                    'channels':a.codec_context.channels if a else 0,'sample_rate':a.rate if a else 48000,
                    'duration':round(float(c.duration or m.get('duration',0))/1e6*float(fps))}
        infos[mid]=result;return result
    root=ET.Element('xmeml',version='5');seq=add(root,'sequence',id='capcut-sequence')
    add(seq,'name',data.get('name') or draft.name);add(seq,'duration',round(data['duration']/1e6*float(fps)));rate(seq,fps)
    tc=add(seq,'timecode');rate(tc,fps);add(tc,'string','00:00:00:00');add(tc,'frame',0);add(tc,'displayformat','NDF')
    media=add(seq,'media');video=add(media,'video');audio=add(media,'audio')
    video_format_dimensions(add(add(video,'format'),'samplecharacteristics'),canvas['width'],canvas['height'],fps)
    add(audio,'numOutputChannels',2)
    af=add(add(audio,'format'),'samplecharacteristics');add(af,'depth',16);add(af,'samplerate',48000)
    seen=set();clip_number=0;omissions=[]
    # Generated neutral helper materials are harmless; any referenced processing
    # other than a unity speed is deliberately not guessed.
    by_id={m['id']:(kind,m) for kind,rows in data['materials'].items() if isinstance(rows,list) for m in rows if isinstance(m,dict) and m.get('id')}
    def validate(s):
        clip=s.get('clip') or {}
        nonneutral=(s.get('speed',1)!=1 or s.get('reverse') or s.get('common_keyframes') or s.get('keyframe_refs') or
                    any(float(v)!=1 for v in (clip.get('scale') or {}).values()) or
                    any(float(v)!=0 for v in (clip.get('transform') or {}).values()) or
                    clip.get('rotation',0)!=0 or clip.get('alpha',1)!=1 or any((clip.get('flip') or {}).values()))
        if nonneutral:raise ValueError('CapCut transforms, animation or retimes require appearance conversion; original draft preserved.')
        for ref in s.get('extra_material_refs',[]):
            kind,m=by_id.get(ref,('',{}))
            neutral=(kind=='speeds' and m.get('speed',1)==1 and not m.get('curve_speed')) or (kind=='placeholder_infos' and m.get('meta_type')=='none') or (kind=='sound_channel_mappings' and m.get('audio_channel_mapping',0)==0)
            neutral=neutral or (kind=='canvases' and not any(m.get(k) for k in ('color','blur','image','album_image')))
            neutral=neutral or (kind=='material_colors' and not any(m.get(k) for k in ('is_color_clip','is_gradient','solid_color')))
            neutral=neutral or (kind=='vocal_separations' and m.get('choice',0)==0 and not m.get('removed_sounds'))
            if not neutral:raise ValueError('CapCut processing material needs appearance conversion: '+kind)
    def emit(parent,s,kind,channel=1):
        nonlocal clip_number
        m=info(s['material_id']);clip_number+=1
        target=s['target_timerange'];source=s['source_timerange']
        if abs(source['duration']-target['duration'])>2000:raise ValueError('A CapCut speed/duration change needs separate conversion.')
        ci=add(parent,'clipitem',id='capcut-'+str(clip_number));add(ci,'name',materials[s['material_id']].get('material_name') or materials[s['material_id']].get('name') or m['path'].stem)
        add(ci,'enabled','TRUE' if s.get('visible',True) else 'FALSE');add(ci,'duration',m['duration']);rate(ci,fps)
        for tag,value in [('start',target['start']),('end',target['start']+target['duration']),('in',source['start']),('out',source['start']+source['duration'])]:add(ci,tag,round(value/1e6*float(fps)))
        fid='file-'+s['material_id'];f=add(ci,'file',id=fid)
        if fid not in seen:
            seen.add(fid);add(f,'name',m['path'].name);add(f,'pathurl',premiere_pathurl(m['path']));rate(f,fps);add(f,'duration',m['duration'])
            fm=add(f,'media')
            if m['width']:video_format_dimensions(add(add(fm,'video'),'samplecharacteristics'),m['width'],m['height'],fps)
            if m['channels']:
                a=add(fm,'audio');asc=add(a,'samplecharacteristics');add(asc,'depth',16);add(asc,'samplerate',m['sample_rate']);add(a,'channelcount',m['channels'])
        if kind=='audio':
            st=add(ci,'sourcetrack');add(st,'mediatype','audio');add(st,'trackindex',channel)
            eff=add(add(ci,'filter'),'effect')
            for k,v in [('name','Audio Levels'),('effectid','audiolevels'),('effectcategory','audiolevels'),('effecttype','audiolevels'),('mediatype','audio')]:add(eff,k,v)
            par=add(eff,'parameter');add(par,'parameterid','level');add(par,'name','Level');add(par,'value',s.get('volume',1))
    for track in data['tracks']:
        segments=track.get('segments') or []
        if not segments:continue
        if track['type'] not in ('video','audio'):raise ValueError('CapCut '+track['type']+' layers require appearance conversion.')
        for s in segments:validate(s)
        if track['type']=='video':
            vt=add(video,'track')
            for s in segments:emit(vt,s,'video')
            if any(info(s['material_id'])['channels'] and s.get('volume',1)>0 for s in segments):
                ats=[add(audio,'track') for _ in range(2)]
                for s in segments:
                    if not info(s['material_id'])['channels'] or s.get('volume',1)<=0:continue
                    for ch in range(min(2,info(s['material_id'])['channels'])):emit(ats[ch],s,'audio',ch+1)
        else:
            channels=max(min(2,info(s['material_id'])['channels']) for s in segments)
            ats=[add(audio,'track') for _ in range(channels)]
            for s in segments:
                for ch in range(min(channels,info(s['material_id'])['channels'])):emit(ats[ch],s,'audio',ch+1)
    output.parent.mkdir(parents=True,exist_ok=True);ET.indent(root,space='  ')
    ET.ElementTree(root).write(output,encoding='utf8',xml_declaration=True)
    report={'status':'basic_edit_xml_prepared','source_draft':str(draft.resolve()),'xml':str(output.resolve()),'entries':clip_number,'rendered':False,'full_appearance_verified':False}
    output.with_suffix('.receipt.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--draft',type=Path,required=True);p.add_argument('--xml',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(export(a.draft,a.xml)))
    except Exception as e:print(json.dumps({'status':'needs_review','error':str(e)}));sys.exit(1)
