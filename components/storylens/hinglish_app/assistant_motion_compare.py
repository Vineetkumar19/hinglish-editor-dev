"""Explicit two-engine comparisons run as one normally queued Storylens job."""
import re
import time


def execute(assistant,session_id,text,profile):
    if not (re.search(r'\bremotion\b',text,re.I) and re.search(r'\bmotion[ -]canvas\b',text,re.I) and re.search(r'\b(?:create|make|render|prepare|compare)\b',text,re.I)):return False
    source=re.search(r'^Script image:\s*(.+)$',text,re.M|re.I)
    objects=re.search(r'^Saved script:\s*(.+)$',text,re.M|re.I)
    if not source and not objects:return False
    seconds=re.search(r'\b(\d+(?:\.\d+)?)\s*[- ]?second',text,re.I)
    payload={'mode':'motion','script':text,'source_paths':[],'profile':profile,'motion_engine':'remotion','motion_style':'theme:studio','motion_quality':'preview','motion_mode':'full','motion_coverage':'full','motion_aspect':'9:16','motion_compare_seconds':float(seconds[1]) if seconds else 50,'quality_check':True}
    if source:payload['motion_compare_script_image']=source[1].strip().strip('"')
    if objects:
        payload['motion_object_script']=objects[1].strip().strip('"')
        # The owner reviews creative output. Native frame/plan checks still run;
        # the generic evaluator must not regenerate this local-model film.
        payload['quality_check']=False
    resume=re.search(r'^Continue object film:\s*(.+)$',text,re.M|re.I)
    if resume:payload['motion_object_continue']=resume[1].strip()
    previous=re.search(r'^Continue comparison:\s*(.+)$',text,re.M|re.I)
    if previous:payload['motion_compare_correction']=previous[1].strip()
    assistant._message(session_id,'assistant','I’ll resume the saved object film, keeping its image layers, independent movement and camera tracks. Local Qwen will repair its invisible colours; both engines will render that saved plan.' if resume else 'Local Qwen will author image layers, moving graphic objects and explicit camera tracks using your saved script. The same 50-second graph will render in Remotion and Motion Canvas.' if objects else 'Local Vision will transcribe your script image. Local Qwen will plan the animation once, then Remotion and Motion Canvas will each render the same 50-second plan. These are two separate native engine drafts for your comparison.')
    assistant._update(session_id,status='running',stage='Waiting for the shared GPU queue',selected='motion')
    job=assistant.state.create_job(payload);assistant._update(session_id,job_id=job['id'],payload=payload,brain='Local Qwen + Vision · Remotion / Motion Canvas')
    while True:
        job=assistant.state.snapshot(job['id'])
        if job['status'] in ('complete','failed'):break
        if job.get('stage'):assistant._update(session_id,stage=job['stage'])
        time.sleep(.5)
    if job['status']=='failed':raise ValueError('Motion comparison stopped: '+job['stage'])
    result=job['result'];assistant._message(session_id,'assistant','Both native engine drafts are ready for comparison. Local Qwen authored the shared plan; visual approval is yours.',result=result,videos=result.get('previews',[]))
    assistant._update(session_id,status='complete',stage='Review both engine drafts',job_id=None,last_result=result,last_paths=result.get('previews',[]))
    return True
