"""Explicit one-reference Motion Graphics requests use the ordinary queued job path."""
import re
import time
from pathlib import Path


def request(text):
    script=re.search(r'^SCRIPT:\s*\n?([\s\S]+)$',text,re.M|re.I)
    if script:
        header=text[:script.start()]
        if re.search(r'\bmotion\s+graphics\b',header,re.I) and re.search(r'theme:elements|\belement animation\b',header,re.I) and re.search(r'\b(?:create|make|render)\b',header,re.I):
            return {'script':script[1].strip(),'aspect':'9:16' if re.search(r'9:16|vertical',header,re.I) else '16:9','quality':'preview' if re.search(r'preview',header,re.I) else 'full'}
    if not re.search(r'\bmotion\s+graphics?\b',text,re.I) or re.search(r'\b(?:do not|don.t|never)\s+(?:create|render|make|recreate)\b',text,re.I):return None
    if not re.search(r'\b(?:create|render|make|recreate)\b',text,re.I):return None
    source=re.search(r'^Reference:\s*([^\r\n]+)$',text,re.M|re.I)
    sounds=re.search(r'^Sounds folder:\s*([^\r\n]+)$',text,re.M|re.I)
    if not source and re.search(r'\b(?:reference|recreate|copy|match)\b',text,re.I):
        files=re.findall(r'[A-Za-z]:[/\\][^\r\n"<>]*?\.(?:mp4|mov|mkv|webm)\b',text,re.I)
        if len(files)>1:raise ValueError('Motion reference unavailable: choose one reference video at a time.')
        if files:return {'reference':files[0],'sounds':sounds[1].strip().strip('"') if sounds else ''}
    if not source:return None
    return {'reference':source[1].strip().strip('"'),'sounds':sounds[1].strip().strip('"') if sounds else ''}


def execute(assistant,session_id,text,profile):
    spec=request(text)
    if not spec:return False
    if 'script' in spec:
        from hinglish_motion.engines import selected_engine, ENGINES
        engine=selected_engine(text,assistant._get(session_id).get('motion_engine','remotion'))
        payload={'mode':'motion','script':spec['script'],'source_paths':[],'profile':profile,'motion_style':'theme:elements',
                 'motion_engine':engine,
                 'motion_aspect':spec['aspect'],'motion_quality':spec['quality'],'motion_coverage':'full','motion_mode':'full','quality_check':True}
        assistant._message(session_id,'assistant',f'I’ll have local Qwen plan the graphic elements for your exact statement, then render them with {ENGINES[engine]}.')
        assistant._update(session_id,status='running',stage='Waiting for the shared GPU queue',selected='motion')
        job=assistant.state.create_job(payload);assistant._update(session_id,job_id=job['id'],payload=payload,brain='Local Qwen · element animation')
        while True:
            job=assistant.state.snapshot(job['id'])
            if job['status'] in ('complete','failed'):break
            if job.get('stage'):assistant._update(session_id,stage=job['stage'])
            time.sleep(.5)
        if job['status']=='failed':raise ValueError('Element motion render stopped: '+job['stage'])
        result=job['result'];videos=result.get('previews',[])
        assistant._message(session_id,'assistant','Your original element-animation draft is ready for review. Qwen chose the graphic objects and motion; your exact statement is the supporting caption.',result=result,videos=videos)
        assistant._update(session_id,status='complete',stage='Review the element animation',job_id=None,last_result=result,last_paths=videos)
        return True
    source=Path(spec['reference']).resolve()
    if not source.is_file() or source.suffix.lower() not in ('.mp4','.mov','.mkv','.webm'):
        raise ValueError('Motion reference unavailable: select one local video file.')
    if spec['sounds'] and not Path(spec['sounds']).is_dir():raise ValueError('Motion reference sound unavailable: select an existing sound folder.')
    routed=text
    from hinglish_motion.engines import selected_engine
    engine=selected_engine(text,assistant._get(session_id).get('motion_engine','hyperframes'))
    if engine!='hyperframes':
        raise ValueError('Motion engine input unavailable: use a script for Remotion / Motion Canvas. This saved reference-copy workflow uses Hyperframes.')
    if not re.search(r'^(?:Teacher package|Student knowledge|Continue project|Continue student|Local model reference):',text,re.M|re.I):routed+='\nLocal model reference: automatic'
    payload={'mode':'motion','script':routed,'source_paths':[],'profile':profile,'motion_reference':str(source),
             'motion_engine':engine,
             'motion_sounds_folder':spec['sounds'],'motion_quality':'preview','quality_check':True}
    teacher=bool(re.search(r'^Teacher package:',text,re.M|re.I))
    student=bool(re.search(r'^Student knowledge:',text,re.M|re.I))
    assistant._message(session_id,'assistant','I’ll have local Qwen author each scene using the saved teacher knowledge, then render its own layout, camera and animation choices. The reference words, assets/audio and renderer are reused; Codex will not edit the creative plan.' if student else 'I’ll render the supplied teacher-authored layers with Hyperframes, GSAP and Three.js. This comparison reuses labelled reference photo crops/audio; local model weights are unchanged.' if teacher else 'I’ll analyze this one reference with local Vision, author new layers with the local LLM, and render a short example with library sound. Other references will wait for your review.')
    assistant._update(session_id,status='running',stage='Waiting for the shared GPU queue',selected='motion')
    job=assistant.state.create_job(payload)
    assistant._update(session_id,job_id=job['id'],payload=payload,brain='Local Qwen + Vision · reference composition')
    while True:
        job=assistant.state.snapshot(job['id'])
        if job['status'] in ('complete','failed'):break
        if job.get('stage'):assistant._update(session_id,stage=job['stage'])
        time.sleep(.5)
    if job['status']=='failed':raise ValueError('Motion reference example stopped: '+job['stage'])
    result=job['result'];videos=result.get('previews',[])
    assistant._message(session_id,'assistant','The teacher-authored Motion Graphics comparison is ready. Review it before treating it as an approved learning example; model weights are unchanged.' if teacher else 'One locally authored Motion Graphics example is ready for your review. No next reference was started.',result=result,videos=videos)
    assistant._update(session_id,status='complete',stage='Review this one reference example',job_id=None,last_result=result,last_paths=videos)
    return True
