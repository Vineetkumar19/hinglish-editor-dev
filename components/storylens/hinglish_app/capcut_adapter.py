"""Local CapCut 9.6 handoff. Existing projects are read, never rewritten."""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid

_LOCK=threading.RLock()
EXTENSIONS={'.mp4','.mov','.mkv','.webm','.avi','.m4v'}
IMAGES={'.png','.jpg','.jpeg','.webp'}
AUDIO={'.wav','.mp3'}


def signature(video,words=None,timeline=None):
    from hinglish_cut.media import fingerprint
    digest=fingerprint(video)
    if words is None and not timeline:return digest
    sources=[(c['path'],fingerprint(c['path'])) for name in ('clips','overlays','options','audio_layers') for c in timeline.get(name,[])] if timeline else []
    return hashlib.sha256(json.dumps([digest,words,timeline,sources],sort_keys=True).encode()).hexdigest()


def media_path(folder,value):
    raw=str(value or '')
    match=re.match(r'^##_draftpath_placeholder_[^/\\]+_##[/\\](.*)$',raw)
    if match:
        path=(Path(folder)/match[1]).resolve()
        if not path.is_relative_to(Path(folder).resolve()):raise ValueError('The CapCut media location is invalid. Relink the footage in CapCut and save again.')
        return path
    return Path(raw)


def settings(root):
    file=Path(root)/'config.editors.local.json'
    data=json.loads(file.read_text('utf-8')) if file.is_file() else {}
    home=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData/Local')/'CapCut'
    base=Path(data.get('capcut_home') or home)
    return base,base/'User Data/Projects/com.lveditor.draft'


def executable(root):
    base,_=settings(root)
    choices=list((base/'Apps').glob('*/CapCut.exe'))
    if not choices:raise ValueError('CapCut was not found. Install CapCut Desktop, then reopen Storylens and try again. Your output is kept.')
    return max(choices,key=lambda p:p.stat().st_mtime)


def projects(root):
    _,base=settings(root)
    rows=[]
    for folder in sorted(base.glob('*'),key=lambda p:p.stat().st_mtime,reverse=True):
        file=folder/'draft_content.json'
        if not folder.is_dir() or folder.name.startswith('.') or not file.is_file():continue
        try:
            data=json.loads(file.read_text('utf-8'))
            meta=json.loads((folder/'draft_meta_info.json').read_text('utf-8'))
        except (ValueError,OSError):continue
        media=[];seen=set()
        for v in data.get('materials',{}).get('videos',[]):
            p=media_path(folder,v.get('path'))
            if not v.get('path') or p.suffix.lower() not in EXTENSIONS or str(p) in seen:continue
            seen.add(str(p));media.append({'id':v['id'],'name':p.name,'path':str(p),'available':p.is_file()})
        rows.append({'id':folder.name,'name':meta.get('draft_name') or folder.name,'media':media})
        if len(rows)>=40:break
    return {'projects':rows,'installed':bool((settings(root)[0]/'Apps').is_dir()),
            'note':'Save your CapCut project first. Use saved timeline for Smart Clean or Script Edit on straight cuts and linked camera audio; the result opens as a new editable project. For layered edits, export MP4 from CapCut first. Choose source footage to start from an original recording.'}


def source(root,project_id,media_id):
    row=next((p for p in projects(root)['projects'] if p['id']==project_id),None)
    media=next((m for m in row['media'] if m['id']==media_id),None) if row else None
    if not media or not media['available']:
        raise ValueError('This CapCut source video is missing or moved. Relink it in CapCut, or choose the video file in Storylens.')
    return media['path']


def _write(path,value):
    temp=path.with_name(path.name+'.storylens-tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,path)


def _layout(folder,content):
    """CapCut 9.6 requires its multi-timeline project manifest as well as media."""
    timelines=folder/'Timelines';timelines.mkdir(exist_ok=True)
    manifest=timelines/'project.json'
    if manifest.exists():return
    timeline_id=content['id'];now=time.time_ns()//1000
    _write(manifest,{'config':{'color_space':-1,'hdr_vivid':False,'mixed_track_mode_on':False,
        'render_index_track_mode_on':False,'use_float_render':False},'create_time':now,'update_time':now,
        'id':str(uuid.uuid4()).upper(),'main_timeline_id':timeline_id,'version':0,
        'timelines':[{'create_time':now,'update_time':now,'id':timeline_id,'is_marked_delete':False,'name':'Timeline 01'}]})
    _write(folder/'timeline_layout.json',{'dockItems':[{'dockIndex':0,'ratio':1,'timelineIds':[timeline_id],
         'timelineNames':['Timeline 01']}],'layoutOrientation':1})
    _write(folder/'draft_biz_config.json',{'timeline_settings':{timeline_id:{}}})
    (folder/'draft_settings').write_text(f'[General]\ndraft_create_time={now//1000000}\ndraft_last_edit_time={now//1000000}\nreal_edit_seconds=0\nreal_edit_keys=0\n')


def create_project(root,video,title,key,*,word_rows=None,timeline=None):
    import av
    root=Path(root);video=Path(video).resolve()
    if not video.is_file() or video.suffix.lower() not in EXTENSIONS|IMAGES|AUDIO:raise ValueError('Choose finished video or image media before sending it to CapCut.')
    _,base=settings(root);base.mkdir(parents=True,exist_ok=True)
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','-',title)[:90]+' - '+key
    folder=base/name
    with _LOCK:
        receipt=folder/'storylens-handoff.json'
        if receipt.is_file():
            saved=json.loads(receipt.read_text('utf-8'))
            if saved.get('source_sha256')!=signature(video,word_rows,timeline):
                raise ValueError('This saved CapCut handoff belongs to a different video. Prepare a new handoff; the existing project is kept.')
            _layout(folder,json.loads((folder/'draft_content.json').read_text('utf-8')))
            return saved
        if folder.exists():raise ValueError('A CapCut project already uses this handoff name. Keep that project and prepare a new handoff.')
        template=json.loads(Path(__file__).with_name('capcut_template.json').read_text('utf-8'))
        still=video.suffix.lower() in IMAGES
        audio_only=video.suffix.lower() in AUDIO
        if audio_only:
            with av.open(str(video)) as c:
                a=c.streams.audio[0];duration=round(float(a.duration*a.time_base if a.duration is not None else c.duration/1e6)*1e6)
            fps=30;width=1920;height=1080;has_audio=True
        elif still:
            from PIL import Image
            with Image.open(video) as image:width,height=image.size
            duration=5_000_000;fps=30;has_audio=False
        else:
            with av.open(str(video)) as c:
                v=c.streams.video[0];fps=float(v.average_rate or 30)
                duration=round(float(v.duration*v.time_base if v.duration else c.duration/1e6)*1e6)
                width,height=v.width,v.height;has_audio=bool(c.streams.audio)
        if duration<=0:raise ValueError('The finished video has no usable duration. Reopen its review and export it again.')
        content=copy.deepcopy(template['content']);meta=copy.deepcopy(template['meta'])
        uid=lambda:str(uuid.uuid4()).upper()
        project_id=uid();timeline_id=uid();material_id=uid();now=time.time_ns()//1000
        folder.mkdir();asset=folder/video.name;shutil.copy2(video,asset)
        video_data=copy.deepcopy(template['video']);video_data.update(id=material_id,type='photo' if still else 'video',path=asset.as_posix(),material_name=video.name,
             width=width,height=height,duration=duration,has_audio=has_audio)
        segment=copy.deepcopy(template['segment']);segment.update(id=uid(),material_id=material_id,
             source_timerange={'start':0,'duration':duration},target_timerange={'start':0,'duration':duration})
        for k in content['materials']:content['materials'][k]=[]
        content.update(id=timeline_id,name=title,duration=duration,create_time=now,update_time=now,fps=fps,
             canvas_config={'width':width,'height':height,'ratio':'original','background':None},
             tracks=[{'id':uid(),'type':'video','segments':[segment],'flag':0,'attribute':0,'name':'Storylens finished video','is_default_name':False}])
        content['materials']['videos']=[video_data]
        if audio_only:
            content['materials']['videos']=[]
            content['materials']['audios']=[{'id':material_id,'type':'extract_music','path':asset.as_posix(),
                'name':video.name,'duration':duration,'category_id':'','category_name':'local','check_flag':1,
                'music_id':'','app_id':0,'source_platform':0,'wave_points':[],'local_material_id':uid()}]
            segment['clip']=None
            content['tracks'][0].update(type='audio',name='Storylens extracted audio')
        if timeline:
            content['tracks'][0]['segments']=[];content['materials']['videos']=[];assets={}
            for cut in timeline['clips']:
                path=Path(cut['path']);mid=assets.get(str(path))
                if mid is None:
                    mid=uid();assets[str(path)]=mid
                    copied=asset if path.resolve()==video else folder/(str(len(assets))+'-'+path.name)
                    if copied!=asset:shutil.copy2(path,copied)
                    with av.open(str(path)) as c:
                        v=c.streams.video[0];vd=copy.deepcopy(template['video'])
                        vd.update(id=mid,type='video',path=copied.as_posix(),material_name=path.name,width=v.width,height=v.height,
                            duration=round(float(v.duration*v.time_base if v.duration else c.duration/1e6)*1e6),has_audio=bool(c.streams.audio))
                    content['materials']['videos'].append(vd)
                seg=copy.deepcopy(template['segment']);seg.update(id=uid(),material_id=mid,
                    source_timerange={'start':cut['source_in'],'duration':cut['duration']},
                    target_timerange={'start':cut['start'],'duration':cut['duration']})
                content['tracks'][0]['segments'].append(seg)
                if timeline.get('mute_source_audio'):seg['volume']=0
            duration=timeline['duration'];content.update(duration=duration,fps=timeline['fps'])
            content['canvas_config'].update(width=timeline['width'],height=timeline['height'])
            content['tracks'][0]['name']='Storylens editable cuts'
            for field,label in (('overlays','B-roll suggestions'),('options','B-roll choices — after original video')):
                if field=='overlays' and timeline.get('selected_only'):label='Selected B-roll'
                if field=='overlays' and timeline.get('visuals'):label='Selected Smart Visuals'
                extra=[]
                for cut in timeline.get(field,[]):
                    path=Path(cut['path']);mid=assets.get(str(path))
                    if mid is None:
                        mid=uid();assets[str(path)]=mid
                        copied=folder/(str(len(assets))+'-'+path.name);shutil.copy2(path,copied)
                        with av.open(str(path)) as media:
                            v=media.streams.video[0];vd=copy.deepcopy(template['video'])
                            vd.update(id=mid,type='video',path=copied.as_posix(),material_name=cut.get('name',path.name),
                                width=v.width,height=v.height,duration=round(float(v.duration*v.time_base if v.duration else media.duration/1e6)*1e6),has_audio=False)
                        content['materials']['videos'].append(vd)
                    if field=='options':
                        next(v for v in content['materials']['videos'] if v['id']==mid)['material_name']=cut.get('name',path.name)
                    seg=copy.deepcopy(template['segment']);seg.update(id=uid(),material_id=mid,volume=0,
                        track_render_index=1 if field=='overlays' else 2,
                        source_timerange={'start':cut['source_in'],'duration':cut['duration']},
                        target_timerange={'start':cut['start'],'duration':cut['duration']})
                    extra.append(seg)
                if extra:content['tracks'].append({'id':uid(),'type':'video','segments':extra,'flag':0,'attribute':0,
                    'name':label,'is_default_name':False})
        if timeline and timeline.get('audio_layers'):
            audio_tracks={}
            for layer in timeline['audio_layers']:
                path=Path(layer['path']);mid=uid()
                copied=folder/(mid+'-'+path.name);shutil.copy2(path,copied)
                with av.open(str(path)) as c:
                    a=c.streams.audio[0]
                    length=round(float(a.duration*a.time_base if a.duration is not None else c.duration/1e6)*1e6)
                content['materials']['audios'].append({'id':mid,'type':'extract_music','path':copied.as_posix(),
                    'name':layer['name'],'duration':length,'category_id':'','category_name':'local',
                    'check_flag':1,'music_id':'','app_id':0,'source_platform':0,'wave_points':[],'local_material_id':uid()})
                seg=copy.deepcopy(template['segment']);seg.update(id=uid(),material_id=mid,clip=None,volume=1.,
                    source_timerange={'start':layer['source_in'],'duration':layer['duration']},
                    target_timerange={'start':layer['start'],'duration':layer['duration']})
                audio_tracks.setdefault(layer['lane'],[]).append(seg)
            for lane,segments in audio_tracks.items():
                content['tracks'].append({'id':uid(),'type':'audio','segments':segments,'flag':0,'attribute':0,
                    'name':'Sound Design '+lane,'is_default_name':False})
        if word_rows:
            font=executable(root).parent/'Resources/Font/SystemFont/en.ttf'
            texts=[];segments=[];word_tracks={}
            for row in word_rows:
                selected_font=Path(row.get('font_path') or font)
                if not selected_font.is_file():raise ValueError('The saved caption font is missing. Open Caption Studio and select an available font, then save and export again.')
                font_folder=folder/'fonts';font_folder.mkdir(exist_ok=True)
                copied_font=font_folder/selected_font.name
                if not copied_font.exists():shutil.copy2(selected_font,copied_font)
                from PIL import ImageFont
                family,_=ImageFont.truetype(str(copied_font),20).getname()
                render_font=copied_font
                installed=root/'output/editor-handoffs/caption-font-installation.json'
                if row.get('design') and installed.is_file():
                    for face in json.loads(installed.read_text('utf-8')).get('fonts',[]):
                        candidate=Path(face['path'])
                        if Path(face['source']).resolve()==selected_font.resolve() and candidate.is_file() and hashlib.sha256(candidate.read_bytes()).hexdigest()==face['sha256']:
                            render_font=candidate
                            break
                text=copy.deepcopy(template['text']);tid=uid();size=float(row.get('size_px',60))*1080/(height*4)
                color=row.get('color') or '#FFFFFF';rgb=[int(color.lstrip('#')[i:i+2],16)/255 for i in (0,2,4)]
                selected_font=render_font
                text.update(id=tid,font_path=font.as_posix(),font_size=size,group_id='')
                text.update(font_path=selected_font.as_posix(),font_name=family,font_title=family,text_color=color)
                text['content']=json.dumps({'text':row['text'],'styles':[{'range':[0,len(row['text'].encode('utf-16-le'))//2],
                    'size':size,'font':{'id':'','path':selected_font.as_posix()},'fill':{'alpha':1,'content':{'render_type':'solid','solid':{'alpha':1,'color':rgb}}}}]},ensure_ascii=False)
                seg=copy.deepcopy(template['text_segment']);seg.update(id=uid(),material_id=tid,
                    target_timerange={'start':round(row['start']*1e6),'duration':max(1,round((row['end']-row['start'])*1e6))})
                layout=row.get('layout') or {'x':.5,'y':.7}
                seg['clip']['transform']={'x':2*(float(layout['x'])-.5),'y':2*(.5-float(layout['y']))}
                if row.get('design'):
                    # Normal text clips stay independent of CapCut's shared
                    # subtitle styling and can overlap on separate layers.
                    text.update(type='text',add_type=0,is_rich_text=True,
                        use_effect_default_color=False,letter_spacing=float(row.get('tracking',0)))
                    lane=int(row.get('slot',0));seg['track_render_index']=lane+1
                    seg['render_index']=14000+lane
                    animation=row.get('animation') or []
                    for prop,field,convert in (
                        ('KFTypePositionX','x',lambda v:2*(v/width-.5)),
                        ('KFTypePositionY','y',lambda v:2*(.5-v/height)),
                        ('KFTypeAlpha','alpha',lambda v:v)):
                        if len(animation)>1:
                            seg['common_keyframes'].append({'id':uid(),'property_type':prop,'material_id':'','keyframe_list':[
                                {'id':uid(),'time_offset':round(k['time']*1e6),'values':[convert(k[field])],
                                 'curveType':'Line','graphID':'','left_control':{'x':0.,'y':0.},'right_control':{'x':0.,'y':0.}}
                                for k in animation]})
                    word_tracks.setdefault(lane,[]).append(seg)
                texts.append(text);segments.append(seg)
            content['materials']['texts']=texts
            for lane,clips in sorted((word_tracks or {0:segments}).items()):
                content['tracks'].append({'id':uid(),'type':'text','segments':clips,'flag':0,'attribute':0,
                    'name':f'Storylens words {lane+1}','is_default_name':False})
        meta.update(draft_id=project_id,draft_name=title,draft_fold_path=folder.as_posix(),draft_root_path=base.as_posix(),
             tm_draft_create=now,tm_draft_modified=now,tm_duration=duration,draft_timeline_materials_size_=asset.stat().st_size)
        _write(folder/'draft_content.json',content);_write(folder/'draft_meta_info.json',meta)
        (folder/'Timelines').mkdir();timeline_folder=folder/'Timelines'/timeline_id;timeline_folder.mkdir()
        _write(timeline_folder/'draft_content.json',content)
        _layout(folder,content)
        # Only append our fresh entry. Back up the original index before every
        # atomic update; never replace the owner's existing draft records.
        index=base/'root_meta_info.json'
        existing=json.loads(index.read_text('utf-8')) if index.is_file() else {'all_draft_store':[],'draft_ids':[],'root_path':base.as_posix()}
        if index.is_file():
            backups=root/'output/editor-handoffs/capcut-index-backups';backups.mkdir(parents=True,exist_ok=True)
            shutil.copy2(index,backups/f'{time.time_ns()}.json')
        entry={k:v for k,v in meta.items() if k!='draft_materials'}
        entry.update(draft_json_file=(folder/'draft_content.json').as_posix(),draft_cover='',draft_timeline_materials_size=asset.stat().st_size,streaming_edit_draft_ready=True)
        existing['all_draft_store'].insert(0,entry)
        _write(index,existing)
        saved={'project':title,'folder':str(folder),'video':str(asset),'duration':duration/1e6,
             'source_sha256':signature(video,word_rows,timeline),
             'notice':'Finished video in a new CapCut timeline. Existing captions and effects are baked into the video; they are not separate editable CapCut layers.'}
        if timeline and timeline.get('sound'):
            saved['notice']='Source picture, dialogue, music and effects remain separate editable clips on sound lanes.'
        _write(receipt,saved)
        return saved


def launch(root):
    subprocess.Popen([str(executable(root))],cwd=str(executable(root).parent))
    return 'CapCut opened. On its Home page, open the named Storylens project. If it was already open, return to Home to refresh the project list.'


def timeline_spec(xml):
    from .timeline_cut import validate
    seq=validate(xml)
    if any(c.base_scale!=1 or c.base_center!=(0.,0.) for c in seq.clips):
        raise ValueError('This timeline has framing changes. Use the finished-video handoff to retain them exactly; editable CapCut cuts currently need original framing.')
    return {'fps':float(seq.fps),'width':seq.width,'height':seq.height,'duration':round(seq.frames/float(seq.fps)*1e6),
        'clips':[{'path':c.path,'source_in':round(c.source_in/float(c.rate)*1e6),'start':round(c.start/float(seq.fps)*1e6),
                  'duration':round((c.end-c.start)/float(seq.fps)*1e6)} for c in sorted(seq.clips,key=lambda c:c.start)]}


def export_timeline(root,project_id):
    """Snapshot a saved straight-cut project. Never mutate the open project."""
    row=next((p for p in projects(root)['projects'] if p['id']==project_id),None)
    if not row:raise ValueError('This CapCut project is unavailable. Save it in CapCut, then refresh the project list.')
    folder=settings(root)[1]/project_id
    data=json.loads((folder/'draft_content.json').read_text('utf-8'))
    tracks=[t for t in data.get('tracks',[]) if t.get('segments')]
    message='This saved CapCut timeline contains extra layers, effects, speed changes or framing that cannot be preserved in this cut round trip yet. Use a straight-cut copy, or export MP4 from CapCut and choose that video. Your CapCut project is kept.'
    if len(tracks)!=1 or tracks[0].get('type')!='video':raise ValueError(message)
    materials={m['id']:m for m in data['materials']['videos']}
    from hinglish_cut.media import probe
    from hinglish_cut.model import Cut
    from hinglish_cut.xml_export import export_xml
    media={};cuts=[];position=0
    for segment in sorted(tracks[0]['segments'],key=lambda s:s['target_timerange']['start']):
        target=segment['target_timerange'];source_range=segment.get('source_timerange');clip=segment.get('clip') or {}
        if (target['start']!=position or not source_range or segment.get('speed',1)!=1 or segment.get('reverse') or segment.get('common_keyframes') or segment.get('keyframe_refs') or segment.get('volume',1)!=1 or
            any(float(v)!=1 for v in (clip.get('scale') or {}).values()) or any(float(v)!=0 for v in (clip.get('transform') or {}).values()) or clip.get('rotation',0)!=0 or clip.get('alpha',1)!=1 or any((clip.get('flip') or {}).values())):raise ValueError(message)
        # Any referenced processing material could change picture or sound.
        # Neutral speed/canvas entries are safe; reject everything else.
        refs=set(segment.get('extra_material_refs') or [])
        for kind,values in data.get('materials',{}).items():
            for value in values if isinstance(values,list) else []:
                if not isinstance(value,dict) or value.get('id') not in refs:continue
                neutral=(kind=='speeds' and value.get('speed',1)==1 and not value.get('curve_speed')) or (kind=='canvases' and value.get('type')=='canvas_color' and not any(value.get(k) for k in ('color','blur','image','album_image')))
                neutral=neutral or (kind=='placeholder_infos' and value.get('meta_type')=='none')
                neutral=neutral or (kind=='sound_channel_mappings' and value.get('audio_channel_mapping')==0)
                neutral=neutral or (kind=='material_colors' and not value.get('is_color_clip') and not value.get('is_gradient') and not value.get('solid_color'))
                neutral=neutral or (kind=='vocal_separations' and value.get('choice')==0 and not value.get('removed_sounds'))
                if not neutral:raise ValueError(message)
        material=materials.get(segment.get('material_id'))
        if not material or not media_path(folder,material.get('path')).is_file():raise ValueError('A CapCut timeline video is missing. Relink it in CapCut and save, then select the timeline again.')
        default_crop={'upper_left_x':0,'upper_left_y':0,'upper_right_x':1,'upper_right_y':0,'lower_left_x':0,'lower_left_y':1,'lower_right_x':1,'lower_right_y':1}
        if material.get('crop',default_crop)!=default_crop or material.get('crop_scale',1)!=1 or material.get('audio_fade') or (material.get('matting') or {}).get('flag',0) or (material.get('stable') or {}).get('stable_level',0):raise ValueError(message)
        algorithm=material.get('video_algorithm') or {}
        if any(algorithm.get(k) for k in ('algorithms','path','motion_blur_config','noise_reduction','quality_enhance','super_resolution','ai_background_configs')):raise ValueError(message)
        m=probe(media_path(folder,material['path']));media[m.id]=m
        canvas=data.get('canvas_config') or {}
        if canvas.get('width',m.width)!=m.width or canvas.get('height',m.height)!=m.height:raise ValueError(message)
        if abs(float(m.rate)-float(data['fps']))>.001:raise ValueError('This timeline mixes video frame rates. Export it as MP4 in CapCut and select that file before cutting.')
        a=round(source_range['start']/1e6*float(m.rate));b=a+round(target['duration']/1e6*float(m.rate))
        if abs(source_range['duration']-target['duration'])>2000:raise ValueError(message)
        cuts.append(Cut(m.id,a,b,len(cuts)));position+=target['duration']
    if not cuts:raise ValueError('This CapCut timeline is empty. Add your video, save the project, then select it again.')
    key=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()[:16]
    destination=Path(root)/'output/editor-handoffs/capcut-sources'/key;destination.mkdir(parents=True,exist_ok=True)
    target=destination/'CAPCUT_SOURCE.xml';export_xml(target,cuts,media)
    _write(destination/'saved-capcut-project.json',data)
    return str(target.resolve())
