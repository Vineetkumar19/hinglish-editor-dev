"""Shared project/script context and typed native-editor round trips."""
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import math
import os
import re
import threading
import time
import uuid

HOSTS=('premiere','aftereffects','capcut')
TOOLS=('clean','script','captions','broll','visuals','zoom','sound','beats','cinematic','downloader','photos')


class PanelContexts:
    def __init__(self,root):
        self.root=Path(root).resolve();self.base=self.root/'cache/editor-panel';self.lock=threading.RLock()

    def save(self,value):
        host=value.get('host');script=value.get('script','');form=value.get('content_format','short')
        if host not in HOSTS:raise ValueError('Choose Premiere Pro, After Effects or the CapCut companion.')
        if not isinstance(script,str) or len(script)>20000:raise ValueError('Paste one script of up to 20,000 characters.')
        if form not in ('short','long'):raise ValueError('Choose Short form or Long form.')
        project=str(value.get('project_id','')).strip();sequence=str(value.get('sequence_id','')).strip()
        if not project or not sequence or len(project+sequence)>4096:raise ValueError('Open a project and select its timeline or composition first.')
        if value.get('timeline_xml'):
            import shutil
            from defusedxml import ElementTree as SafeET
            source=Path(str(value['timeline_xml'])).resolve()
            if not source.is_file() or source.suffix.lower()!='.xml' or source.stat().st_size>20*1024**2:raise ValueError('Capture the current timeline again.')
            if SafeET.parse(source).getroot().tag!='xmeml':raise ValueError('Capture a supported Final Cut XML timeline.')
            if not source.is_relative_to((self.root/'cache').resolve()):
                destination=self.base/'exports';destination.mkdir(parents=True,exist_ok=True)
                copied=destination/(hashlib.sha256(source.read_bytes()).hexdigest()[:24]+'.xml')
                if not copied.exists():shutil.copy2(source,copied)
                value={**value,'timeline_xml':str(copied)}
        key=hashlib.sha256(json.dumps([host,project,sequence]).encode()).hexdigest()[:24]
        context={**value,'id':key,'host':host,'script':script,'content_format':form}
        self.base.mkdir(parents=True,exist_ok=True)
        with self.lock:
            dest=self.base/(key+'.json');temp=dest.with_suffix('.tmp')
            temp.write_text(json.dumps(context,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8');os.replace(temp,dest)
        return context

    def load(self,key):
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{24}',key):raise ValueError('Connect the current timeline again.')
        file=self.base/(key+'.json')
        if not file.is_file():raise ValueError('Connect the current timeline again; its shared script has not been saved.')
        return json.loads(file.read_text(encoding='utf-8'))


def snapshot_xml(root,context):
    """Preserve native straight footage cuts and source trims; never flatten silently."""
    from hinglish_cut.media import probe
    from hinglish_cut.model import Cut
    from hinglish_cut.xml_export import export_xml
    message='This composition contains unsupported layers, gaps, speed changes or effects. Use a copy with straight footage cuts and linked audio. Your original composition is kept.'
    if context.get('unsupported'):raise ValueError(message)
    try:
        fps=Fraction(str(context.get('fps',30)));duration=float(context['duration'])
        width=int(context['width']);height=int(context['height'])
        if fps<=0 or fps>240 or not math.isfinite(duration) or not 0<duration<=86400 or not 1<=width<=16384 or not 1<=height<=16384:raise ValueError()
    except (ValueError,KeyError,TypeError,ZeroDivisionError):raise ValueError('Check the composition dimensions, duration and frame rate.') from None
    clips=context.get('clips',[])
    if not isinstance(clips,list) or not 1<=len(clips)<=5000:raise ValueError('Put footage in the active timeline or composition first.')
    videos=[c for c in clips if c.get('kind','video')=='video'];videos.sort(key=lambda c:float(c.get('start',0)))
    if not videos:raise ValueError('Choose a composition with video footage to edit.')
    if any(c.get('kind')=='audio' for c in clips):raise ValueError(message)
    media={};cuts=[];position=0
    for i,clip in enumerate(videos):
        try:
            path=Path(str(clip['path'])).resolve();a=float(clip['start']);b=float(clip['end']);source_in=float(clip.get('source_in',0))
            if not all(math.isfinite(v) for v in (a,b,source_in)) or a<0 or source_in<0 or b<=a or b>duration+.001:raise ValueError()
            if clip.get('stretch',100)!=100 or clip.get('track',0)!=0 or abs(a-position)>.5/float(fps):raise ValueError(message)
            if not path.is_file() or path.suffix.lower() not in ('.mp4','.mov','.mxf','.mkv','.avi','.webm','.m4v'):raise ValueError('Relink the missing footage, then try again.')
            m=probe(path)
            if abs(float(m.rate-fps))>.01 or source_in+b-a>m.duration+.5/float(fps):raise ValueError(message)
            if m.width!=width or m.height!=height:raise ValueError(message)
            media[m.id]=m;cuts.append(Cut(m.id,round(source_in*fps),round((source_in+b-a)*fps),i));position=b
        except (KeyError,TypeError,OverflowError):raise ValueError('Check the footage trims before running this tool.') from None
    if abs(position-duration)>.5/float(fps):raise ValueError(message)
    folder=Path(root)/'cache/editor-panel/timelines';folder.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(json.dumps(context,sort_keys=True,allow_nan=False).encode()).hexdigest()[:24]
    target=folder/(key+'.xml');export_xml(target,cuts,media)
    return target


def job_payload(root,context,mode,settings):
    if mode not in TOOLS[:7]:raise ValueError('Choose a supported editing tool from the panel.')
    script=context.get('script','').strip()
    if mode!='clean' and not script:raise ValueError('Paste your script once at the top of the panel. All editing tools will share it.')
    timeline=context.get('timeline_xml')
    if timeline:
        timeline=Path(timeline).resolve()
        if not timeline.is_relative_to((Path(root)/'cache').resolve()) or not timeline.is_file():raise ValueError('Capture the current timeline again.')
    else:timeline=snapshot_xml(root,context)
    count=2 if context.get('content_format')=='long' else 5
    payload={'mode':mode,'host':context['host'],'timeline_xml':str(timeline),'script':script,'caption_reference':script,
             'preview':False,'panel_context':context['id'],'panel_auto_import':mode not in ('broll','visuals'),
             'caption_style':settings.get('caption_style','caption_2'),'format':settings.get('format','original'),
             'density':settings.get('density','medium')}
    if mode=='broll':payload.update(broll_review_options=True,broll_options_per_moment=count)
    if mode=='visuals':payload.update(visuals_review_options=True,visuals_options_per_moment=count,visuals_popups=False)
    if mode=='zoom':payload.update(zoom_jump_cuts=True,zoom_style=settings.get('zoom_style','mixed'))
    if mode=='sound':
        action=settings.get('sound_action','recommend')
        if action not in ('recommend','auto'):raise ValueError('Choose sound suggestions or automatic sound design.')
        payload.update(panel_auto_import=action=='auto' or context.get('content_format')=='long',sound_remove_music=False,sound_music=True,sound_effects=True,
                       panel_sound_action='auto',sound_content_form=context.get('content_format','short'))
    return payload


def caption_manifest(project):
    from .caption_scene import build
    from .premiere_captions import font_name
    words=[{**word,'font_name':font_name(word['font_path'])} for word in build(project)]
    return {'type':'captions','name':'Storylens '+project.get('style','Captions'),'style':project.get('style'),
            'width':int(project['width']),'height':int(project['height']),'duration':float(project['media']['duration']),
            'fps':float(Fraction(str(project['media'].get('fps',30)))),'source':project['media']['path'],'words':words}


def asset_choices(root,folder,count):
    folder=Path(folder).resolve();output=(Path(root)/'output').resolve()
    if not folder.is_relative_to(output) or not folder.is_dir():raise ValueError('Choose a finished Storylens result.')
    if count not in (2,5):raise ValueError('Choose Long form or Short form.')
    rows=[]
    for pattern in ('broll-project.json','visuals-project.json'):
        for file in folder.rglob(pattern):
            project=json.loads(file.read_text(encoding='utf-8'))
            for slot in project.get('slots',[]):
                for i,option in enumerate(slot.get('options',[])[:count]):
                    raw=option.get('original') or option.get('image') or option.get('asset') or option.get('clip') or option.get('path')
                    if not raw:continue
                    path=(file.parent/raw).resolve()
                    if not path.is_relative_to(folder) or not path.is_file():continue
                    if pattern=='visuals-project.json' and path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):continue
                    rows.append({'id':f'{file.parent.name}-{slot.get("index",0)}-{i}','path':str(path),'keyword':slot.get('label') or slot.get('text',''),
                                 'start':slot.get('start',0),'end':slot.get('end',0),'name':path.name,'kind':'image' if pattern.startswith('visuals') else 'video'})
    return rows


def layer_manifest(xml):
    """Import ordinary file layers; recognize basic scale/position and volume only."""
    from defusedxml import ElementTree as SafeET
    from .aftereffects_adapter import fps,local_path
    tree=SafeET.parse(xml);seq=tree.getroot().find('sequence')
    if seq is None or seq.findall('.//transitionitem') or seq.findall('.//clipitem/sequence'):
        raise ValueError('This timeline uses a nested sequence or transition that this After Effects import cannot preserve.')
    rate=fps(seq.find('rate'));files={f.get('id'):f for f in seq.findall('.//file') if f.find('pathurl') is not None}
    result={'type':'layers','name':seq.findtext('name','Storylens timeline'),'fps':rate,
            'width':int(seq.findtext('media/video/format/samplecharacteristics/width','1920')),
            'height':int(seq.findtext('media/video/format/samplecharacteristics/height','1080')),
            'duration':int(seq.findtext('duration','0'))/rate,'clips':[]}
    seen=set()
    for kind in ('video','audio'):
        for lane,track in enumerate(seq.findall('media/'+kind+'/track')):
            for ci in track.findall('clipitem'):
                f=ci.find('file');f=f if f is not None and f.find('pathurl') is not None else files.get(f.get('id') if f is not None else '')
                if f is None:raise ValueError('Relink the timeline media before importing it.')
                path=local_path(f.findtext('pathurl',''));start=int(ci.findtext('start','-1'))/rate;end=int(ci.findtext('end','-1'))/rate
                source=int(ci.findtext('in','-1'))/fps(ci.find('rate'),rate)
                key=(path,start,end,source)
                if min(start,source)<0 or end<=start or not Path(path).is_file():raise ValueError('Check the generated timeline trims and media paths.')
                if kind=='audio' and key in seen:continue
                if kind=='audio':seen.add(key)
                item={'path':path,'kind':kind,'start':start,'end':end,'source_in':source,'track':lane,'motion':{}}
                for effect in ci.findall('./filter/effect'):
                    name=(effect.findtext('effectid') or '').lower()
                    if name not in ('basic','motion','volume','audiolevels','audio levels','opacity'):
                        raise ValueError('This generated effect needs a rendered layer for After Effects. Your original timeline is unchanged.')
                    for param in effect.findall('parameter'):
                        prop=(param.findtext('parameterid') or param.findtext('name') or '').lower()
                        if prop not in ('scale','center','rotation','opacity','level'):
                            raise ValueError('This timeline includes an effect parameter that After Effects cannot preserve yet. Your original timeline is unchanged.')
                        def numeric(node):
                            if node is None:raise ValueError('The generated motion value is missing.')
                            result=[float(node.findtext('horiz')),float(node.findtext('vert'))] if prop=='center' else float(node.text)
                            if not all(math.isfinite(v) for v in (result if isinstance(result,list) else [result])):raise ValueError('The generated motion value is invalid.')
                            return result
                        value=numeric(param.find('value'));keys=[]
                        if param.findall('keyframe'):
                            raise ValueError('This timeline has unsampled effect keyframes. Use the frame-sampled Storylens result for After Effects.')
                        item['motion'][prop]={'value':value,'keys':keys}
                result['clips'].append(item)
    if not result['clips']:raise ValueError('The generated timeline has no importable layers.')
    return result


def prepare_import(root,host,folder,*,mode='',context=None,asset=None):
    root=Path(root).resolve();folder=Path(folder).resolve()
    if host not in HOSTS or not folder.is_relative_to(root/'output') or not folder.is_dir():raise ValueError('Choose a finished result for the connected editor.')
    expected={'project_id':context.get('project_id'),'sequence_id':context.get('sequence_id')} if context else {}
    if folder.is_relative_to(root/'output/broll'):
        from .panel_broll_choices import load_bank,handoff
        if asset:raise ValueError('Choose a checked B-roll card so its exact source window and keyword timing are kept.')
        projects=list(folder.rglob('broll-project.json'))
        if len(projects)!=1:raise ValueError('Open one B-roll collection and choose its checked video options first.')
        bank=load_bank(root,folder,projects[0],(context or {}).get('content_format','short'))
        return handoff(root,bank,host,expected)
    if folder.is_relative_to(root/'output/visuals'):
        raise ValueError('Choose a checked source image in the visual review before importing it. Saved renders remain available in Storylens.')
    if folder.is_relative_to(root/'output/sound-recommendations'):
        raise ValueError('Choose a checked sound candidate to import its original recording. Auditions are listening previews.')
    if asset:
        path=Path(asset).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or path.suffix.lower() not in ('.mp4','.mov','.mkv','.webm','.wav','.mp3','.png','.jpg','.jpeg','.webp'):
            raise ValueError('Choose one of this result’s saved media files.')
        return {'type':'assets','name':'Storylens assets','paths':[str(path)],'expected':expected,'insert':True}
    if folder.is_relative_to(root/'output/photo-collector'):
        raise ValueError('Use Photo Collector’s import button so previews, originals and screenshot folders keep their identities.')
    if mode=='captions' and host=='aftereffects':
        from .word_captions import load
        project=load(folder)[0][1];manifest=caption_manifest(project);manifest['expected']=expected
        if project.get('style') in ('caption_2','caption_3','kinetic_gold_draft','serif_circle_draft') and project.get('word_visibility','phrase')!='spoken':
            from .premiere_decorations import render
            destination=root/'output/editor-handoffs/aftereffects'/uuid.uuid4().hex;destination.mkdir(parents=True)
            manifest['decorations']=str(render(project,destination/'captions.aep'))
        return manifest
    if host in ('premiere','capcut'):
        from . import editor_handoff
        task=editor_handoff.start(root,{'editor':host,'folder':str(folder),'caption_mode':'words' if mode=='captions' else 'rendered'})
        while task['status']=='running':time.sleep(.2);task=editor_handoff.snapshot(task['id'])
        if task['status']!='complete':raise ValueError(task['error']['message'])
        if host=='capcut':return {'type':'capcut','task_id':task['id'],'notice':task['notice'],'projects':task.get('projects',[])}
        files=task.get('premiere_projects') or task.get('xml_files')
        if mode=='sound':
            from hinglish_sound.keyword_folders import package
            plans=list(folder.rglob('sound-plan.json'))
            if plans:
                bank=package(plans[0])
                if bank:return {'type':'files','paths':[str(plans[0].parent/'SOUND_SEQUENCE.xml')],
                    'name':'Storylens sound draft','keyword_folders':bank['folders'],'expected':expected,'activate':True}
        return {'type':'files','paths':files,'name':'Storylens '+mode,'expected':expected,'activate':True}
    xmls=sorted(folder.rglob('*.xml'))
    preferred=[p for p in xmls if p.name in ('DOWNLOADED_SEQUENCE.xml','CINEMATIC_REEL.xml','SOUND_SEQUENCE.xml','ZOOMED_SEQUENCE.xml','EDITED_SEQUENCE.xml','timeline.xml') or p.name.endswith('-SOURCE-TIMELINE.xml')]
    if preferred:
        manifest=layer_manifest(preferred[0]);manifest['expected']=expected
        if folder.is_relative_to(root/'output/sound'):
            from hinglish_sound.keyword_folders import package
            plans=list(folder.rglob('sound-plan.json'))
            if plans:
                bank=package(plans[0])
                if bank:manifest['keyword_folders']=bank['folders']
        return manifest
    files=[str(p.resolve()) for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.mp4','.mov','.wav','.mp3') and not re.search('preview|thumb|reference',p.name,re.I)]
    if not files:raise ValueError('This result has no finished media to import. Finish its download or export first.')
    return {'type':'assets','paths':files,'name':folder.name,'expected':expected,'insert':True}


class PanelService:
    def __init__(self,state):
        self.state=state;self.contexts=PanelContexts(state.root);self.jobs={};self.lock=threading.RLock()

    def snapshot(self,key):
        with self.lock:
            if key not in self.jobs:raise ValueError('This panel task is unavailable. Reconnect and use the saved result.')
            return json.loads(json.dumps(self.jobs[key]))

    def update(self,key,**changes):
        with self.lock:self.jobs[key].update(changes)

    def start(self,value):
        context=self.contexts.load(value.get('context_id',''))
        ensure_license(self.state,context['host'])
        if 'script' in value:context=self.contexts.save({**context,'script':value['script'],'content_format':value.get('content_format',context['content_format'])})
        settings=value.get('settings') or {}
        if not isinstance(settings,dict):raise ValueError('Choose this tool’s settings again.')
        payload=job_payload(self.state.root,context,value.get('mode'),settings)
        key=uuid.uuid4().hex
        with self.lock:
            if any(j['status'] in ('queued','running') and j['context_id']==context['id'] for j in self.jobs.values()):raise ValueError('Wait for this timeline’s current panel task to finish.')
            self.jobs[key]={'id':key,'context_id':context['id'],'mode':payload['mode'],'status':'queued','stage':'Waiting for the local editor','progress':0,'auto_import':payload['panel_auto_import']}
        def run():
            try:
                self.update(key,status='running',stage='Reading the current timeline')
                if payload['mode']=='captions':
                    from .timeline_cut import prepare
                    work=Path(self.state.root)/'cache/editor-panel/analysis'/key;work.mkdir(parents=True)
                    video=prepare(payload.pop('timeline_xml'),work,lambda m:self.update(key,stage=m))
                    payload.update(source_paths=[str(video)])
                job=self.state.create_job(payload)
                self.update(key,engine_id=job['id'])
                while job['status'] in ('queued','running'):
                    self.update(key,stage=job.get('stage','Editing'),progress=job.get('progress',0));time.sleep(.7);job=self.state.snapshot(job['id'])
                if job['status']!='complete':raise ValueError(job.get('stage') or 'The editing step stopped. Check its saved progress.')
                result=job['result'];count=2 if context['content_format']=='long' else 5
                visual_sources=None;sound_review=None
                if payload['mode']=='broll':
                    from .panel_broll_choices import cards
                    choices=cards(self.state.root,result['folder'],context['content_format'])
                elif payload['mode']=='visuals':
                    from .visual_source_transport import VisualSourceTransport
                    visual_sources=VisualSourceTransport(self.state).describe(job['id'])
                    choices=[]
                elif payload['mode']=='sound' and result.get('sound_recommendations'):
                    from .panel_sound_review import describe
                    sound_review=describe(self.state,job['id']);choices=[]
                elif payload['mode']=='sound' and list(Path(result['folder']).rglob('sound-plan.json')):
                    from .panel_sound_review import describe
                    from hinglish_sound.human_review import register
                    saved=next(Path(result['folder']).rglob('sound-plan.json'))
                    if json.loads(saved.read_text('utf-8')).get('human_review'):
                        sound_review=describe(self.state,register(saved))
                    choices=[]
                else:
                    choices=sound_choices(self.state.root,result['folder']) if payload['mode']=='sound' and not payload['panel_auto_import'] else []
                # A technical quality score is not semantic approval. Script
                # assembly produces a review draft, even when its XML is valid.
                review_required=payload['mode']=='script' or bool(result.get('review_required'))
                auto_import=payload['panel_auto_import'] and not review_required and payload['mode'] not in ('broll','visuals')
                self.update(key,result=result,choices=choices,stage='Preparing editor layers',
                            review_required=review_required,auto_import=auto_import,visual_sources=visual_sources,sound_review=sound_review)
                manifest=prepare_import(self.state.root,context['host'],result['folder'],mode=payload['mode'],context=context) if auto_import else None
                stage='Review draft ready. Check the edit, then add the draft when you choose.' if review_required else 'Ready in the panel'
                self.update(key,status='complete',stage=stage,progress=100,manifest=manifest)
            except Exception as error:
                from .user_messages import failure
                self.update(key,status='failed',stage='The panel task stopped',**failure(error,feature='Editor panel'))
        threading.Thread(target=run,daemon=True,name='storylens-editor-panel').start()
        return self.snapshot(key)


def panel_service(state):
    with state.lock:
        if not hasattr(state,'_editor_panel'):state._editor_panel=PanelService(state)
        return state._editor_panel


def ensure_license(state,host):
    if state.license_client is not None:
        state.license_for('plugins' if host in ('premiere','aftereffects') else 'desktop').ensure(host if host in ('premiere','aftereffects') else 'standalone')


def sound_choices(root,folder):
    """Offer the actual AI-selected source sounds with their planned timestamps."""
    import shutil
    import xml.etree.ElementTree as ET
    from .aftereffects_adapter import local_path,fps
    folder=Path(folder).resolve()
    if not folder.is_relative_to((Path(root)/'output').resolve()):raise ValueError('Choose a finished sound result.')
    rows=[];seen=set();destination=folder/'panel-sound-options'
    for xml in folder.rglob('SOUND_SEQUENCE.xml'):
        tree=ET.parse(xml);seq=tree.getroot().find('sequence');rate=fps(seq.find('rate'))
        files={f.get('id'):f for f in seq.findall('.//file') if f.find('pathurl') is not None}
        for ci in seq.findall('./media/audio/track/clipitem'):
            node=ci.find('file');node=node if node is not None and node.find('pathurl') is not None else files.get(node.get('id') if node is not None else '')
            if node is None:continue
            source=Path(local_path(node.findtext('pathurl','')))
            if source.suffix.lower() not in ('.wav','.mp3','.m4a','.flac','.ogg') or not source.is_file() or str(source) in seen:continue
            seen.add(str(source));destination.mkdir(exist_ok=True)
            target=destination/(hashlib.sha256(str(source).encode()).hexdigest()[:10]+'-'+source.name)
            if not target.exists():shutil.copy2(source,target)
            rows.append({'id':str(len(rows)),'path':str(target),'name':source.name,'keyword':ci.findtext('name',source.stem),
                         'start':int(ci.findtext('start','0'))/rate,'end':int(ci.findtext('end','0'))/rate,'kind':'audio'})
    if destination.exists():(destination/'source-credits.json').write_text(json.dumps({'sources':list(seen),'note':'Keep the source library licences and credits with these files.'},indent=2),encoding='utf-8')
    return rows
