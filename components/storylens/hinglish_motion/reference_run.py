"""One reference, one locally authored editable composition and soundtrack."""
from datetime import datetime
from fractions import Fraction
import json
import shutil
import subprocess
from pathlib import Path
import uuid
import wave
import re
import hashlib

import numpy as np

from .reference_composer import ask,arr,obj,string,number,save,author,layers,sound_catalogue,resolve_sound
from .reference_finish import frame_media,finish as finish_saved


def soundtrack(brain,root,folder,plan,catalogue,progress):
    from hinglish_sound.library import decode
    rate=48000;seconds=sum(s['duration'] for s in plan['scenes'])
    mix=np.zeros((2,round(seconds*rate)),np.float32);rows=[];clock=0.
    for i,scene in enumerate(plan['scenes']):
        for j,cue in enumerate(scene['sound_intents']):
            words=set(__import__('re').findall(r'[a-z]+',cue['query'].lower()))
            scored=sorted(catalogue,key=lambda r:sum(w in r['name'].lower() for w in words),reverse=True)
            offered=[r for r in scored[:14] if any(w in r['name'].lower() for w in words)]
            if not offered:raise ValueError('Motion reference sound unavailable: no library match for '+cue['query'])
            choose=obj({'id':{'enum':[r['id'] for r in offered]}})
            selected=ask(brain,folder,f'local-sound-{i+1}-{j+1}',
              'Choose ONE exact library ID for the intended animation sound. Source titles are evidence; avoid unrelated nature, voices or footstep sounds. Do not invent an ID. Choose a useful audible excerpt, not silence.',
              {'intent':cue,'choices':[{k:v for k,v in r.items() if k!='path'} for r in offered]},choose,200)
            path=resolve_sound(offered,selected['id'])
            from hinglish_sound.library import exact_peak_time
            peak_time=exact_peak_time(str(path))
            if peak_time is None:raise ValueError('Motion reference sound unavailable: unreadable audio excerpt.')
            source_in=max(0,peak_time-.25);excerpt_seconds=2.5
            audio=decode(path,rate,limit=source_in+excerpt_seconds)
            audio=audio[:,round(source_in*rate):][:,:round(excerpt_seconds*rate)]
            if not audio.size or np.max(np.abs(audio))<1e-5:raise ValueError('Motion reference sound unavailable: selected excerpt is silent. Choose another excerpt.')
            # Normalize short cues against their loudest 50ms, then apply the local model's mix choice.
            block=2400;power=[np.mean(audio[:,a:a+block]**2) for a in range(0,audio.shape[1],block)]
            audio*=10**(cue['gain_db']/20)/max(np.sqrt(max(power)),1e-6)
            fade=min(480,audio.shape[1]//4)
            audio[:,:fade]*=np.linspace(0,1,fade);audio[:,-fade:]*=np.linspace(1,0,fade)
            desired=clock+cue['time'];start=desired-(peak_time-source_in)
            if start<0:
                crop=round(-start*rate);audio=audio[:,crop:];source_in+=crop/rate;start=0.
            at=round(start*rate);n=min(audio.shape[1],mix.shape[1]-at)
            if n>0:mix[:,at:at+n]+=audio[:,:n]
            rows.append({'scene':i+1,'time':start,'peak_anchor':desired,'path':str(path),'query':cue['query'],
                         'gain_db':cue['gain_db'],'source_in':source_in,'seconds':n/rate})
        clock+=scene['duration']
        progress(f'Sound Design: placed accents for scene {i+1}')
    music=sound_catalogue([root/'library/music'])
    if music:
        chosen=ask(brain,folder,'local-music','Choose a suitable instrumental background bed for this ORIGINAL story, using only one offered library ID. Keep it below the short effects.',
          {'story':plan['title'],'choices':[{k:v for k,v in r.items() if k!='path'} for r in music]},obj({'id':{'enum':[r['id'] for r in music]}}),150)
        path=resolve_sound(music,chosen['id']);bed=decode(path,rate,limit=seconds)
        if bed.size:
            rms=max(float(np.sqrt(np.mean(bed**2))),1e-6);bed*=.045/rms
            n=min(bed.shape[1],mix.shape[1]);mix[:,:n]+=bed[:,:n]
            rows.append({'role':'music','path':str(path),'time':0.,'seconds':n/rate})
    fade=min(rate,mix.shape[1]//4);mix[:,:fade]*=np.linspace(0,1,fade);mix[:,-fade:]*=np.linspace(1,0,fade)
    peak=float(np.max(np.abs(mix)))
    if peak<1e-5:raise ValueError('Motion reference sound unavailable: output mix is silent.')
    if peak>.94:mix*=.94/peak
    target=folder/'soundtrack.wav'
    with wave.open(str(target),'wb') as out:
        out.setparams((2,2,rate,0,'NONE','not compressed'));out.writeframes((mix.T*32767).astype('<i2').tobytes())
    save(folder/'sound-events.json',{'events':rows,'peak_before_safety':peak,'source_reference_audio_used':False})
    return target


def run(root,source,brief,sounds,quality='preview',progress=print):
    root,source=Path(root).resolve(),Path(source).resolve()
    if not source.is_file() or source.suffix.lower() not in ('.mp4','.mov','.mkv','.webm'):
        raise ValueError('Motion reference unavailable: select one local reference video.')
    from .student_demo import knowledge_package,run as render_student
    student_knowledge=knowledge_package(root,source,brief)
    if student_knowledge:return render_student(root,source,student_knowledge,brief,progress)
    from .teacher_demo import teacher_package,run as render_teacher
    supplied_teacher=teacher_package(root,source,brief)
    if supplied_teacher:return render_teacher(root,source,supplied_teacher,progress)
    if re.search(r'^Local model reference:\s*automatic',brief,re.M|re.I):
        from .autonomous_reference import run as autonomous
        return autonomous(root,source,brief,progress)
    resume=re.search(r'^Continue project:\s*([^\r\n]+)$',brief,re.M|re.I)
    if resume and (Path(resume[1].strip())/'MOTION_GRAPHICS.mp4').is_file() and (Path(resume[1].strip())/'reference-motion-project.json').is_file():
        from .reference_composer import load_checkpoint
        load_checkpoint(resume[1].strip(),hashlib.sha256(source.read_bytes()).hexdigest(),root)
        if re.search(r'^Text animation repair:\s*reference',brief,re.M|re.I):
            from .native_text_repair import run as repair_text
            return repair_text(root,source,resume[1].strip(),progress)
        progress('Finalizing the existing local-model video; no new model calls or renders')
        return finish_saved(resume[1].strip(),progress)
    folder=root/'output/motion'/('reference-'+datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True);(folder/'scenes').mkdir()
    # The app parent already owns the shared GPU queue; no nested lock in this worker.
    resume=re.search(r'^Continue project:\s*([^\r\n]+)$',brief,re.M|re.I)
    prior={}
    if resume:
        from .reference_composer import inspect_reference,load_checkpoint
        from hinglish_visuals.brain import open_brain
        story,prior=load_checkpoint(resume[1].strip(),hashlib.sha256(source.read_bytes()).hexdigest(),root)
        evidence=inspect_reference(root,source,folder,progress)
        brain=open_brain(root,'auto',progress=progress)
        total=min(18,evidence['duration']);weight=sum(b['weight'] for b in story['scenes'])
        for beat in story['scenes']:beat['duration']=total*beat['weight']/weight
        save(folder/'local-storyboard-resumed.json',{'answer':story,'source_checkpoint':resume[1].strip(),'model':brain.name})
        progress('Continuing the saved local storyboard and prepared cutouts; no new image searches')
    else:brain,evidence,story=author(root,source,folder,brief,progress)
    from .assets import AssetFinder,Asset
    assets={};receipts=[]
    for i,beat in enumerate(story['scenes']):
        requested=beat['assets']; finder=AssetFinder(root,progress,use_ai=False,check=True,require_vision=True,prefer_web=True)
        try:
            for spec in requested:
                if spec['id'] in assets:continue  # same-ID subject reuse was checked before sourcing
                if spec['id'] in prior:
                    row=dict(prior[spec['id']]);original=Path(row.pop('_path'))
                    dest=folder/'assets'/f'resumed-{len(assets)+1}{original.suffix}'
                    dest.parent.mkdir(exist_ok=True);shutil.copyfile(original,dest)
                    row.update(file=dest.relative_to(folder).as_posix(),src=dest.as_uri(),resumed_from=str(original))
                    assets[spec['id']]=row;receipts.append(row);continue
                progress(f'Finding independent asset for scene {i+1}: '+spec['query'])
                asset=Asset(spec['kind'],spec['query'])
                finder.find(asset,folder,f'asset-{i+1}-{len(assets)+1}',spec['cutout'],beat['duration'],
                            'portrait' if evidence['height']>evidence['width'] else 'landscape',(720,1280))
                if not asset.file:raise ValueError('Motion reference asset missing: '+spec['query']+'; '+asset.error)
                actual=(folder/asset.file).resolve()
                if actual==source:raise ValueError('Motion reference asset missing: reference footage is not production media.')
                row={**spec,**asset.to_dict(),'id':spec['id'],'src':actual.as_uri(),'independent_from_reference':True}
                assets[spec['id']]=row;receipts.append(row)
        finally:finder.close()
    save(folder/'asset-receipts.json',receipts)
    authored=[]
    for i,beat in enumerate(story['scenes']):
        selected={s['id']:assets[s['id']] for s in beat['assets']}
        authored.append(layers(brain,folder,i,beat,evidence,selected,progress))
    plan={'title':story['title'],'scenes':authored,'reference':str(source),'analysis_only':True,'author':brain.name}
    save(folder/'reference-motion-project.json',plan)
    catalogue=sound_catalogue([root/'library/sfx',root/'library/sfx-pro',root/'library/sound-online',Path(sounds)] if sounds else [root/'library/sfx',root/'library/sfx-pro',root/'library/sound-online'])
    save(folder/'sound-catalogue.json',{'count':len(catalogue),'files':catalogue})
    progress(f'Local LLM choosing effects from {len(catalogue)} library files')
    track=soundtrack(brain,root,folder,plan,catalogue,progress)
    brain.close()
    from .creative_export import render_hyperframes
    from imageio_ffmpeg import get_ffmpeg_exe
    portrait=evidence['height']>evidence['width'];width,height=((360,640) if portrait else (640,360)) if quality=='preview' else ((720,1280) if portrait else (1280,720))
    files=[];clock=0.;cuts=[];media={}
    from hinglish_cut.model import Media,Cut
    from hinglish_cut.xml_export import export_xml
    for i,scene in enumerate(authored):
        progress(f'Hyperframes rendering locally authored scene {i+1}/{len(authored)}')
        file=folder/'scenes'/f'{i+1:02d}.mp4'
        payload={'template':'reference_layers','mode':'full','duration':scene['duration'],'quality':quality,
                 'data':{'reference_scene':scene,'assets':[{'id':k,'src':v['src']} for k,v in assets.items()]}}
        render_hyperframes(payload,file,30,width,height,progress)
        files.append(file)
        count=round(scene['duration']*30);key=str(i+1)
        media[key]=Media(key,str(file),count/30,'30',width,height,0,48000);cuts.append(Cut(key,0,count,i))
        clock+=scene['duration']
    listing=folder/'concat.txt';listing.write_text(''.join("file '"+f.resolve().as_posix().replace("'","'\\''")+"'\n" for f in files),'utf-8')
    target=folder/'MOTION_GRAPHICS.mp4'
    result=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(track),
              '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(target)],capture_output=True,timeout=180)
    if result.returncode:raise RuntimeError('Motion reference render stopped: '+result.stderr.decode(errors='replace')[-800:])
    return finish_saved(folder,progress)
