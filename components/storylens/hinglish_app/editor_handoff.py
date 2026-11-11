"""Shared local editor exports for all Storylens feature results."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import threading
import uuid

from .user_messages import problem

_TASKS={};_LOCK=threading.RLock()
XML_TOOLS={'DOWNLOADED_SEQUENCE.xml':'downloader','EDITED_SEQUENCE.xml':'script','timeline.xml':'script','CAPTIONED_SEQUENCE.xml':'captions',
 'BROLL_SEQUENCE.xml':'broll','BROLL_OPTIONS.xml':'broll','VISUALS_SEQUENCE.xml':'visuals','ZOOMED_SEQUENCE.xml':'zoom',
 'SOUND_SEQUENCE.xml':'sound','MOTION_SEQUENCE.xml':'motion','MOTION_GRAPHICS_SEQUENCE.xml':'motion','AI_IMAGES_SEQUENCE.xml':'aiimage',
 'AI_VIDEO_SEQUENCE.xml':'aivideo','CINEMATIC_REEL.xml':'cinematic'}


def output_folder(root,value):
    folder=Path(value).resolve()
    if not folder.is_relative_to((Path(root)/'output').resolve()) or not folder.is_dir():
        raise ValueError('This finished edit is unavailable. Open its result again, then choose your editor.')
    return folder


def catalog(root,folder):
    folder=output_folder(root,folder);root=Path(root).resolve()
    xmls=sorted(p for p in folder.rglob('*.xml') if p.name in XML_TOOLS or p.name.startswith('SHORT_') or p.name.endswith('-SOURCE-TIMELINE.xml'))
    videos=[]
    if folder.is_relative_to(root/'output/workbench'):
        xmls=sorted(folder.rglob('*.xml'))
        videos=sorted(folder.rglob('*.mp4'))
    # Reuse the exact completed chat exports for this result, not an unrelated
    # recent edit or a short preview which may omit the rest of a long video.
    for file in (root/'cache/assistant').glob('*.json'):
        try:data=json.loads(file.read_text('utf-8'))
        except (ValueError,OSError):continue
        for message in data.get('messages',[]):
            result=message.get('result') or {}
            if result.get('folder') and Path(result['folder']).resolve()==folder:
                videos.extend(Path(p).resolve() for p in message.get('videos',[]))
                xmls.extend(Path(p).resolve() for p in result.get('xml_files',[]))
        if (data.get('last_result') or {}).get('folder') and Path(data['last_result']['folder']).resolve()==folder:
            videos.extend(Path(p).resolve() for p in data.get('last_paths',[]))
    if not videos:
        for project in folder.rglob('shorts-project.json'):
            data=json.loads(project.read_text('utf-8'))
            videos.extend((project.parent/s['mp4']).resolve() for s in data.get('shorts',[]) if s.get('mp4'))
        for name in ('cleaned.mp4','GAMING_HIGHLIGHTS.mp4','MOTION_GRAPHICS.mp4','captioned-preview.mp4','CINEMATIC_REEL.mp4','downloaded-video.mp4','extracted-audio.wav','extracted-audio.mp3'):
            videos.extend(p.resolve() for p in folder.rglob(name))
    videos=list(dict.fromkeys(p for p in videos if p.is_file() and p.is_relative_to(root/'output') and p.suffix.lower() in ('.mp4','.mov','.webm','.wav','.mp3')))
    # Caption Studio may have rebuilt this result after its chat export. Its
    # saved full render is authoritative; never send stale caption text/style.
    if folder.is_relative_to(root/'output/sound'):
        # The sound preview is the exact saved mix, not a fresh render.
        current=sorted(p.resolve() for p in folder.rglob('preview.mp4'))
        if current:videos=current
    if folder.is_relative_to(root/'output/captions'):
        current=sorted(p.resolve() for p in folder.rglob('captioned-preview.mp4'))
        if current:videos=current
        elif not videos:videos=sorted(p.resolve() for p in folder.rglob('caption-preview.mp4'))
    xmls=list(dict.fromkeys(p.resolve() for p in xmls if p.is_file() and p.resolve().is_relative_to(folder) and p.name!='source-timeline.xml'))
    restored=[p for p in xmls if p.name.endswith('-SOURCE-TIMELINE.xml')]
    if restored:xmls=restored
    return {'folder':str(folder),'xml_files':[str(p) for p in xmls],'videos':[str(p) for p in videos]}


def snapshot(task_id):
    with _LOCK:
        if task_id not in _TASKS:raise ValueError('This editor handoff is unavailable. Reopen the finished result and try again.')
        return json.loads(json.dumps(_TASKS[task_id]))


def start(root,payload):
    editor=payload.get('editor')
    if editor not in ('capcut','premiere','resolve','aftereffects'):raise ValueError('Choose Premiere Pro, After Effects, CapCut or DaVinci Resolve.')
    result=catalog(root,payload.get('folder',''))
    include_options=payload.get('broll_include_options',False)
    if type(include_options) is not bool:raise ValueError('Choose on or off for including the unused B-roll alternatives.')
    is_broll=Path(result['folder']).is_relative_to(Path(root).resolve()/'output/broll')
    is_visuals=Path(result['folder']).is_relative_to(Path(root).resolve()/'output/visuals')
    is_sound=Path(result['folder']).is_relative_to(Path(root).resolve()/'output/sound')
    caption_mode=payload.get('caption_mode','rendered')
    if caption_mode not in ('rendered','words'):raise ValueError('Choose finished video or editable word captions.')
    if caption_mode=='words' and editor=='resolve':raise ValueError('Editable word captions are available for CapCut and Premiere Pro. Choose the finished video for Resolve.')
    task_id=uuid.uuid4().hex
    with _LOCK:_TASKS[task_id]={'id':task_id,'status':'running','stage':'Preparing your editor files','editor':editor,'files':[]}
    def run():
        try:
            folder=Path(result['folder']);xmls=result['xml_files'];videos=result['videos']
            if is_sound and editor=='premiere':
                from hinglish_sound.keyword_folders import premiere_project
                prepared=[premiere_project(p) for p in sorted(folder.rglob('sound-plan.json'))]
                if prepared:xmls=prepared
            if is_broll and not include_options:xmls=[p for p in xmls if Path(p).name!='BROLL_OPTIONS.xml']
            from hinglish_cut.media import fingerprint
            signatures=[(p,fingerprint(p)) for p in dict.fromkeys(videos+xmls)]
            if is_sound:
                for p in sorted(folder.rglob('sound-plan.json')):
                    signatures.append((str(p),fingerprint(p)))
            caption_files=sorted(Path(result['folder']).rglob('caption-project.json')) if caption_mode=='words' else []
            signatures.extend((str(p),fingerprint(p)) for p in caption_files)
            if caption_mode=='words' and editor=='premiere':
                design_root=Path(__file__).resolve().parents[1]/'hinglish_captions'
                signatures.extend((str(p),fingerprint(p)) for p in sorted(design_root.glob('*reference.json')))
                signatures.extend((str(p),fingerprint(p)) for p in sorted(design_root.glob('*.py')))
                native_root=Path(__file__).with_name('templates')
                signatures.extend((str(p),fingerprint(p)) for p in sorted(native_root.glob('premiere-*')) if p.is_file())
                for p in (Path(__file__).with_name('premiere_captions.py'),design_root/'fonts/sources.json'):
                    signatures.append((str(p),fingerprint(p)))
            if folder.is_relative_to(Path(root).resolve()/'output/broll'):
                signatures.extend((str(p),fingerprint(p)) for p in sorted(folder.rglob('broll-project.json')))
                signatures.append(('broll-choice-bank',10,include_options))
            key=hashlib.sha256(json.dumps([9,editor,caption_mode,result,signatures],sort_keys=True).encode()).hexdigest()[:14]
            destination=Path(root)/'output/editor-handoffs'/key;destination.mkdir(parents=True,exist_ok=True)
            word_exports=[];premiere_projects=[];native_notes=[]
            if editor=='aftereffects':
                if is_sound:
                    from hinglish_sound.editors import aftereffects_script
                    scripts=[aftereffects_script(p,destination/f'SOUND-{i:03d}.jsx')
                             for i,p in enumerate(sorted(folder.rglob('sound-plan.json')),1)]
                    if not scripts:raise ValueError('Save your sound choices before preparing After Effects.')
                else:
                    from .aftereffects_handoff import prepare_scripts
                    scripts=prepare_scripts(result,destination,key)
                with _LOCK:_TASKS[task_id].update(status='complete',stage='Ready for After Effects',
                    files=[{'name':Path(p).name,'path':p} for p in scripts],projects=[],folder=str(destination),
                    scripts=scripts,notice=('Run the JSX in After Effects using File > Scripts > Run Script File. Video and each sound are separate layers with saved timing and mixed levels. Alternative recordings are in the Sound options project folder.' if is_sound else 'Supported timeline layers are prepared as separate editable After Effects compositions. Run the JSX or choose Open After Effects. Unsupported effects stop rather than silently changing the edit.'))
                return
            # Auto Caption 2 has a finished silent preview before a Studio
            # rebuild creates XML. Wrap that exact video without rerendering.
            if caption_mode=='rendered' and not xmls and videos and folder.is_relative_to(Path(root).resolve()/'output/captions'):
                import av
                import math
                from hinglish_cut.model import Media,Cut
                from hinglish_cut.xml_export import export_xml
                for i,video in enumerate(videos,1):
                    with av.open(video) as container:
                        stream=container.streams.video[0];fps=stream.average_rate
                        duration=float(stream.duration*stream.time_base) if stream.duration is not None else container.duration/av.time_base
                        audio=container.streams.audio[0] if container.streams.audio else None
                        media=Media(str(i),video,duration,str(fps),stream.width,stream.height,audio.channels if audio else 0,audio.sample_rate if audio else 48000)
                    path=destination/f'CAPTION-PREVIEW-{i:03d}.xml'
                    export_xml(path,[Cut(media.id,0,math.floor(duration*float(fps)+1e-6),0)],{media.id:media})
                    xmls.append(str(path.resolve()))
            if is_visuals:
                visual_files=sorted(folder.rglob('visuals-project.json'))
                if not any(any(s.get('clip') for s in json.loads(p.read_text('utf-8'))['slots']) for p in visual_files):
                    raise ValueError('Choose visual options and Save & rebuild before sending your selected layers to an editor.')
                if editor=='premiere':
                    from hinglish_broll.premiere import export as visual_export
                    for i,p in enumerate(visual_files,1):
                        path=visual_export(p,destination/f'VISUALS-{i:03d}.prproj',include_options=False,
                            visual_project=json.loads(p.read_text('utf-8')))
                        if path:premiere_projects.append(path)
            if editor=='premiere' and folder.is_relative_to(Path(root).resolve()/'output/broll'):
                from hinglish_broll.premiere import export as broll_export
                for i,project_file in enumerate(sorted(folder.rglob('broll-project.json')),1):
                    path=broll_export(project_file,destination/f'BROLL-{i:03d}.prproj',include_options=include_options)
                    if path:premiere_projects.append(path)
            if caption_mode=='words':
                from .word_captions import export
                word_exports=export(folder,destination)
                videos=[p['source'] for p in word_exports];xmls=[p['xml'] for p in word_exports]
                if editor=='premiere':
                    from .word_captions import load
                    from .premiere_captions import export as native_export
                    for i,((caption_path,project),word_export) in enumerate(zip(load(folder),word_exports),1):
                        project['media']['path']=word_export['source']
                        path=destination/f'CAPTIONS-{i:03d}.prproj'
                        if not path.exists():
                            _TASKS[task_id]['stage']=f'Preparing editable Premiere captions {i} of {len(word_exports)}'
                            native_export(Path(__file__).with_name('templates')/'premiere-caption-1.xml',project,path)
                        premiere_projects.append(str(path.resolve()))
                        if project.get('style')=='caption_3':
                            native_notes.append('Words stay editable on individual layers. The animated dotted frames are included on a separate transparent video layer.')
                        if project.get('style')=='kinetic_gold_draft':
                            native_notes.append('Words stay editable on individual layers. Animated shadows and brush strokes are included on a separate transparent video layer.')
                        if project.get('style')=='serif_circle_draft':
                            native_notes.append('Words stay editable on individual layers. Animated circles and underlines are included on a separate transparent video layer.')
                        if project.get('style')=='caption_2':
                            native_notes.append('Words stay editable. Soft glow, shadows and text-linked cross-outs are included on a separate transparent video layer.')
                        if project.get('style') in ('typography_1','typography_2'):
                            native_notes.append('Some decorative cards, strips, selection frames and wipe masks are not yet converted to native graphics. The word text, fonts and motion remain editable; use the finished video when those decorations must match exactly.')
            native_cuts=[]
            if editor=='capcut' and not word_exports:
                if is_sound:
                    from hinglish_sound.editors import capcut_spec as sound_spec
                    native_cuts=[sound_spec(p) for p in sorted(folder.rglob('sound-plan.json'))]
                    if native_cuts:videos=[s['clips'][0]['path'] for s in native_cuts]
                if is_visuals:
                    from hinglish_visuals.references import capcut_spec
                    native_cuts=[s for p in sorted(folder.rglob('visuals-project.json')) if (s:=capcut_spec(p))]
                    if native_cuts:videos=[s['clips'][0]['path'] for s in native_cuts]
                if folder.is_relative_to(Path(root).resolve()/'output/broll'):
                    from hinglish_broll.capcut import spec as broll_spec
                    native_cuts=[s for p in sorted(folder.rglob('broll-project.json')) if (s:=broll_spec(p,include_options=include_options))]
                    if native_cuts:videos=[s['clips'][0]['path'] for s in native_cuts]
                restored=[p for p in xmls if p.endswith('-SOURCE-TIMELINE.xml')]
                candidates=restored or [p for p in xmls if Path(p).name in ('timeline.xml','EDITED_SEQUENCE.xml','CINEMATIC_REEL.xml')]
                if candidates and not native_cuts:
                    from .capcut_adapter import timeline_spec
                    native_cuts=[timeline_spec(p) for p in candidates]
                    videos=[s['clips'][0]['path'] for s in native_cuts]
            if editor=='capcut' and not videos:
                from .assistant_media import outputs
                from hinglish_cut.gpu_lock import gpu_lock
                if xmls:
                    tool=XML_TOOLS.get(Path(xmls[0]).name,'shorts')
                    with gpu_lock(root):videos=outputs(root,{'tool':tool},result,destination,lambda text:_TASKS[task_id].update(stage=text))
                else:
                    # Script-only AI assets are ready media, not a whole movie.
                    videos=[str(p.resolve()) for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in ('.mp4','.mov','.png','.jpg') and not re.search('preview|sample|reference|source',p.name,re.I)]
            if editor=='capcut':
                if not videos:raise ValueError('No finished media is ready yet. Finish this feature’s export, then send it to CapCut. Your editable files are kept.')
                from .capcut_adapter import create_project
                projects=[]
                for i,path in enumerate(videos):
                    if Path(path).suffix.lower() not in ('.mp4','.mov','.mkv','.webm','.avi','.m4v','.png','.jpg','.jpeg','.webp','.wav','.mp3'):continue
                    _TASKS[task_id]['stage']=f'Creating CapCut project {i+1} of {len(videos)}'
                    feature=XML_TOOLS.get(Path(xmls[0]).name,'Media') if xmls else 'Media'
                    if word_exports:feature='captions'
                    elif native_cuts:feature='sound' if is_sound else 'visuals' if native_cuts[i].get('visuals') else 'broll' if native_cuts[i].get('broll') else ('clean' if 'phase1' in folder.parts else 'script')
                    label={'zoom':'Smart Zoom','captions':'Captions','clean':'Smart Clean','script':'Script Edit','broll':'B-roll','visuals':'Smart Visuals','sound':'Sound Design','motion':'Motion Graphics','aiimage':'AI Images','aivideo':'AI Video'}.get(feature,feature)
                    projects.append(create_project(root,path,'Storylens '+label+' '+str(i+1),key+'-'+str(i+1),word_rows=word_exports[i]['word_rows'] if word_exports else None,timeline=native_cuts[i] if native_cuts else None))
                if not projects:raise ValueError('No supported media was exported. Open the feature result and finish its export before retrying.')
                files=[{'name':Path(v).name,'path':v} for v in videos]
                files.extend({'name':p.name+' (editable subtitles)','path':str(p.resolve())} for p in folder.rglob('captions.srt'))
                notice='New CapCut projects are ready. Open them from CapCut Home. Captions, zooms and effects are kept in the finished video, not separate editable CapCut layers.'
                if folder.is_relative_to(Path(root).resolve()/'output/downloads'):
                    notice='Your downloaded media is ready as a new CapCut timeline. Open it from CapCut Home.'
                if word_exports:
                    files=[{'name':Path(p['srt']).name,'path':p['srt']} for p in word_exports]
                    notice='Clean video and a separate track of editable word blocks are ready in CapCut. Each word has its own text and timing. This editable mode uses basic text styling; choose Finished video for the exact Caption Studio design and animations. The SRT below is also available for manual import at timeline start.'
                elif native_cuts:
                    files=[{'name':Path(p).name,'path':p} for p in xmls]
                    notice='New CapCut timelines contain separate editable video cuts with linked camera audio. Open the named edited copy from CapCut Home; your source project is kept.'
                    if any(s.get('broll') for s in native_cuts):
                        notice='Your saved selected clips are on a separate editable B-roll track at their saved speech timestamps. Move, trim, resize or extend them within the available footage. The source video/audio stays separate.'
                        if include_options:notice+=' Additional choices are in a named section after the original video.'
                    if is_visuals:notice='Your selected animated visuals are separate editable clips at their saved spoken timestamps. The original source audio stays separate.'
                    if is_sound:notice='Your source video, dialogue, music and overlapping effects are separate editable tracks in a new CapCut project. Open it from CapCut Home.'
            else:
                if is_broll and not include_options:xmls=[p for p in xmls if Path(p).name!='BROLL_OPTIONS.xml']
                if not xmls:raise ValueError('This result has finished media but no XML timeline. Open its output folder and import the media in your editor.')
                projects=[];files=[{'name':Path(p).name,'path':p} for p in xmls]
                notice=('Open Premiere Pro, then use File > Import and choose the XML below.' if editor=='premiere' else 'Open a DaVinci Resolve project, then press Import timelines below.')
                if is_sound:notice+=' Sound Design keeps dialogue, music and overlapping effects on separate editable audio tracks. Projects also import Sound Design > keyword bins containing the full recommended recordings.'
                if premiere_projects and not word_exports:
                    files=[{'name':Path(p).name,'path':p} for p in premiere_projects]+files
                    notice='Your Premiere project has the original video and audio on V1/A1 and independently editable B-roll on V2. Trim or move each cutaway; extra footage handles are included where available.'
                    if include_options and any(json.loads(p.read_text('utf8')).get('review_options') for p in folder.rglob('broll-project.json')):
                        notice+=' All video choices are included as separate timestamp-named media in the Project panel; choose which to place on the timeline.'
                    if is_visuals:notice='Your Premiere project contains the original audio/video plus your selected animated visuals as separate editable clips. Move, trim or resize each visual in Premiere.'
                if word_exports:
                    files.extend({'name':Path(p['srt']).name,'path':p['srt']} for p in word_exports)
                    files=[{'name':Path(p).name,'path':p} for p in premiere_projects]+files
                    notice='Your Premiere project is ready with separate editable word graphics, saved fonts, colors and motion keyframes. Each word can be moved, retimed and edited. Quarter-resolution playback is requested; Premiere uses half resolution for 720p sequences.'
                    if native_notes:notice+=' '+native_notes[0]
            with _LOCK:_TASKS[task_id].update(status='complete',stage='Ready for '+{'capcut':'CapCut','premiere':'Premiere Pro','resolve':'DaVinci Resolve'}[editor],
                  files=files,projects=projects,premiere_projects=premiere_projects,notice=notice,folder=str(destination),xml_files=xmls)
        except Exception as error:
            with _LOCK:_TASKS[task_id].update(status='failed',stage='Your editor handoff stopped',error=problem(error))
    threading.Thread(target=run,daemon=True).start()
    return snapshot(task_id)


def act(root,payload):
    task=snapshot(payload.get('id',''))
    if task['status']!='complete':raise ValueError('The editor files are still being prepared. Wait for the completed result, then try again.')
    action=payload.get('action')
    if action=='open-folder':
        folder=Path(task['projects'][0]['folder']) if task.get('projects') else Path(task['files'][0]['path']).parent
        os.startfile(folder);return {'message':'Output folder opened.'}
    if action=='open-editor':
        if task['editor'] in ('aftereffects','premiere'):
            _single_adobe_editor(task['editor'])
        if task['editor']=='aftereffects':
            config=Path(root)/'config.editors.local.json'
            data=json.loads(config.read_text('utf-8')) if config.is_file() else {}
            configured=data.get('aftereffects_executable','')
            candidates=([Path(configured)] if configured else [])+sorted(Path('C:/Program Files/Adobe').glob('Adobe After Effects*/Support Files/AfterFX.exe'),reverse=True)
            exe=next((p for p in candidates if p.is_file()),None)
            if exe is None:raise ValueError('After Effects was not found. Download the JSX, then use File > Scripts > Run Script File in After Effects.')
            subprocess.Popen([str(exe),'-r',task['scripts'][0]])
            return {'message':'Opening the prepared Storylens compositions in After Effects.'}
        if task['editor']=='capcut':
            from .capcut_adapter import launch
            return {'message':launch(root)}
        if task['editor']=='resolve':
            from .resolve_adapter import import_timelines
            return {'message':'Imported '+str(len(import_timelines(task['xml_files'])))+' timelines into Resolve.'}
        data=json.loads((Path(root)/'config.editors.local.json').read_text('utf-8'))
        exe=Path(data.get('premiere_executable',''))
        if not exe.is_file():raise ValueError('Premiere Pro was not found at its saved location. Open Premiere Pro and import the XML below. Your timeline is kept.')
        projects=task.get('premiere_projects') or []
        if projects:
            # Open one project at a time: opening every caption project at once
            # needlessly consumes memory on the owner's laptop.
            path=Path(projects[0]).resolve()
            if not path.is_file() or not path.is_relative_to((Path(root)/'output').resolve()):
                raise ValueError('This Premiere project has moved. Prepare the caption handoff again; your saved captions are kept.')
            subprocess.Popen([str(exe),str(path)])
            return {'message':'Opening your editable Storylens project in Premiere Pro. Wait for the project to finish loading before playback.'}
        from .editor_link import import_into_premiere
        import psutil
        if not any((p.info.get('name') or '').lower()=='adobe premiere pro.exe' for p in psutil.process_iter(['name'])):
            subprocess.Popen([str(exe)])
            return {'message':'Premiere Pro is opening. Open the Storylens panel in your project, then select Open Premiere Pro here again.'}
        command_path = Path(task['folder'])/('premiere-command-'+task['id']+'.json')
        return import_into_premiere(root,'storylens-result-'+task['id'],task['xml_files'],
                                    'Storylens timeline',command_path)
    raise ValueError('Choose Open editor or Open folder.')


def _single_adobe_editor(editor):
    """Respect the owner's one-heavy-Adobe-app RAM policy without closing apps."""
    import psutil
    other='adobe premiere pro.exe' if editor=='aftereffects' else 'afterfx.exe'
    if any((p.info.get('name') or '').lower()==other for p in psutil.process_iter(['name'])):
        raise ValueError('Close '+('Premiere Pro' if editor=='aftereffects' else 'After Effects')+' after saving your work, then open this handoff. Both editors together use too much RAM. Your prepared files are kept.')


def download(root,task_id,index):
    task=snapshot(task_id)
    if task['status']!='complete':raise ValueError('This export is not ready yet. Wait for the completed handoff.')
    if not 0<=index<len(task['files']):raise ValueError('Choose one of this handoff’s exported files.')
    path=Path(task['files'][index]['path']).resolve()
    if not path.is_relative_to((Path(root)/'output').resolve()) or not path.is_file():raise ValueError('This exported file has moved. Reopen the feature result and prepare the handoff again.')
    return path
