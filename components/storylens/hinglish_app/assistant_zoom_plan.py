"""Bounded local-model planning for one SmartZoom editing step."""
import re


def explain(brain,text,history,memory):
    """Keep current owner policy authoritative when historical chats disagree."""
    from dataclasses import asdict
    from .assistant_plan_context import ask
    from .assistant_plan import validate_plan
    from .workflow_memory import load_guide
    from hinglish_zoom.settings import profile_for
    guide=load_guide()['chunks']
    sounds_only=(bool(re.search(r'\b(?:sounds?|sfx|whoosh|swoosh|swish|woosh)\b',text,re.I)) and
                 not re.search(r'\b(?:camera|framing|focal|cadence|hold|timing|speed)\b',text,re.I))
    if sounds_only:
        # Retrieve the rule this informational question asks about. The full
        # creator profile is still injected by ask(); saved camera rules stay
        # on disk and remain authoritative for actual zoom planning.
        answer=ask(brain,
            'Answer this SmartZoom sound/transition question briefly using current_owner_policy. '
            'It overrides superseded examples in historical replies. Only the approved basic '
            'Whoosh, Swoosh, Swish, Woosh and Zoom collection may be used, including the supplied '
            'whoosh, swipe and Paper Slide files. No impacts, risers, karate, sci-fi, laser or musical '
            'effects. Cut transitions are optional; preserve approved overlays unless the current request asks for a new comparison. '
            'Full creator guidance remains applicable. This is informational: do not edit, render '
            'or publish, and do not claim any new media has been produced.',
            {'question':text,'current_owner_policy':[r['text'] for r in guide if r['id']=='smartzoom-basic-sounds'],
             'conversation':history,'shared_memory':memory or {}},
            {'type':'object','additionalProperties':False,'properties':{'reply':{'type':'string'}},'required':['reply']},
            max_tokens=350,think=False)
        return validate_plan({'reply':answer.get('reply',''),'question':'','combine':False,'steps':[]})
    rules=[r['text'] for r in guide if r['id'] in ('smartzoom-hook-and-main-points','smartzoom-basic-sounds')]
    answer=ask(brain,
        'Answer this SmartZoom question briefly using current_owner_policy and runtime_zoom_policy. '
        'They override superseded timing rules in historical assistant replies. SHORT videos now follow CUTS: '
        'zoom in smoothly at the first shot entrance, hold until the next cut, then zoom out at that '
        'new shot entrance and hold until its next cut. Alternate directions only at cuts. An eight-second '
        'shot keeps its framing for eight seconds. Never complete in and out within one shot. '
        'Restore slower easing: about 0.8 seconds IN and 0.7 seconds OUT. Lock ONE verified focal '
        'point for the entire shot: no recentering, retargeting, secondary pan or camera drift. '
        'Smoothness takes priority over fast motion. This explicitly supersedes the too-fast 0.4-second entrance and '
        'the previous 3-5-second holds and ten-second short-video timer. Long videos use major points only '
        'and can remain wide longer between those points. Saved preferences are not executed work: do not edit, render '
        'or publish, and do not claim a new video has been tested or rendered. Creator guidance remains applicable.',
        {'question':text,'current_owner_policy':rules,
         'runtime_zoom_policy':{'short':{'pacing':'cuts','cut_ramp':profile_for(60).cut_ramp,
              'cut_ramp_out':profile_for(60).cut_ramp_out,'framing':'fixed_focal',
              'first_direction':'in','hold':'until_next_cut','timer':False},'long':asdict(profile_for(600))},
         'conversation':history,'shared_memory':memory or {}},
        {'type':'object','additionalProperties':False,'properties':{'reply':{'type':'string'}},'required':['reply']},
        max_tokens=500,think=False)
    return validate_plan({'reply':answer.get('reply',''),'question':'','combine':False,'steps':[]})


def requested(text):
    from .assistant_publish_intent import instruction,positive
    value=positive(instruction(text))
    return bool(re.search(r'\b(?:smart\s*zoom|zooms?)\b',value,re.I)
        and re.search(r'\b(?:run|start|perform|execute|apply|add|use)\b',value,re.I)
        and not re.match(r'^\s*(?:how|why|what|explain|can i)\b',value,re.I)
        and not re.search(r'\b(?:smart clean|script edit|captions?|subtitles?|b[ -]?roll|smart visuals|sound design|extract|upload|publish|schedul\w*)\b',value,re.I))


def plan(brain,text,history,attachments,memory):
    from .assistant_plan import validate_plan
    from .assistant_plan_context import ask
    sources=(memory or {}).get('editing_sources',[]) if not attachments else []
    options={'zoom_style':{'type':'string','enum':['smooth','mixed','punch']},
        'zoom_strength':{'type':'string','enum':['subtle','medium','strong']},
        'zoom_frequency':{'type':'string','enum':['low','medium','high']},
        'zoom_face':{'type':'boolean'},'zoom_jump_cuts':{'type':'boolean'},
        'zoom_sounds':{'type':'boolean'},'zoom_overlays':{'type':'boolean'}}
    # The current command wins over earlier demo settings. Constrain and check
    # explicit settings rather than trusting a model to ignore old chat values.
    explicit={}
    for key,values in [('zoom_style','smooth|mixed|punch'),
                       ('zoom_strength','subtle|gentle|medium|strong'),
                       ('zoom_frequency','low|medium|high')]:
        noun=key.removeprefix('zoom_')
        matches=re.findall(r'\b('+values+r')\s+(?:zoom\s+)?'+noun+r'\b|\b'+noun+r'\s*[:=]?\s*('+values+r')\b',text,re.I)
        if matches:
            value=next(v for v in matches[-1] if v).lower()
            explicit[key]='subtle' if value=='gentle' else value
            options[key]['enum']=[explicit[key]]
    for key,positive,negative in [
        ('zoom_sounds',r'\b(?:sound effects?|sfx|whooshes?|risers?|impacts?)\b',r'\b(?:no|without|disable|turn off)\s+(?:zoom\s+)?(?:sound effects?|sounds?|sfx)\b'),
        ('zoom_overlays',r'\b(?:(?:cut|transition)\s+overlays?|light sweeps?)\b',r'\b(?:no|without|disable|turn off)\s+(?:(?:cut|transition)\s+)?overlays?\b')]:
        if re.search(positive,text,re.I):explicit[key]=True
        if re.search(negative,text,re.I):explicit[key]=False
        if key in explicit:options[key]['enum']=[explicit[key]]
    schema={'type':'object','additionalProperties':False,'properties':{
        'reply':{'type':'string','enum':['Starting SmartZoom on your video.']},'question':{'type':'string','enum':['']},
        'combine':{'type':'boolean','enum':[False]},
        'steps':{'type':'array','minItems':1,'maxItems':1,'items':{
            'type':'object','additionalProperties':False,'properties':{
                'tool':{'type':'string','enum':['zoom']},
                'options':{'type':'object','additionalProperties':False,'properties':options,'required':list(options)}},
            'required':['tool','options']}}},'required':['reply','question','combine','steps']}
    if sources:
        schema['properties']['source_id']={'type':'string','enum':[s['id'] for s in sources if s['available']]}
        schema['required'].append('source_id')
    system=('You are Storylens\'s local SmartZoom planner. Return exactly one zoom editing step. '
        'The runner supplies the attached video or selected current-chat editing_sources ID. '
        'Do not rerun earlier editing, join files, add features or publish anything. '
        'Honor the requested zoom settings: gentle/subtle means subtle strength; smooth means smooth style. '
        'Default smooth style, medium strength/frequency, face-centred true and jump cuts false. '
        'SHORT videos follow real cuts: zoom in at the opening shot, hold until its cut, zoom out at '
        'the next shot entrance and hold until its cut. Alternate in/out only at cuts, never both '
        'directions within one shot. Hold even an eight-second shot until its end. Each entrance '
        'uses the earlier slower easing (about 0.8 seconds IN, 0.7 seconds OUT, no overshoot). '
        'Lock one verified focal point per shot; never recenter or retarget during the move. '
        'There must be one clean zoom movement, no secondary sideways/up-down camera move. This replaces the earlier '
        '3-5-second holds and ten-second cadence for short videos. '
        'long videos use major script points only, without a periodic quota. '
        'Cut pacing is handled by the zoom tool; keep legacy zoom_jump_cuts false to avoid an extra '
        'instant crop. The tool checks actual shot boundaries and faces, preserving duration and audio. '
        'For sound effects, whooshes, risers or impacts synced to these zooms set zoom_sounds=true. '
        'For cut/transition overlays or light sweeps set zoom_overlays=true. These are separate optional '
        'switches: default both false unless requested. '
        'Current owner sound preference: only basic Whoosh, Swoosh, Swish, Woosh and Zoom sounds from the '
        'approved collection, including their supplied whoosh, swipe and paper-slide files. Do not use '
        'impact, riser, karate, sci-fi, laser, musical or other dramatic effects for these zooms. '
        'Each whoosh starts with its actual zoom and lasts exactly as long as that movement, '
        'mixed quietly below nearby dialogue; do not alter approved camera speed to fit a sound. '
        'Do not add a separate sound or motion step '
        'for these zoom-linked effects. On an existing SmartZoom output the tool reuses the approved '
        'camera plan instead of applying another zoom. No background music or captions are added. '
        'Choose the latest completed current-chat output for a follow-up, not original raw clips. '
        'Start the requested local edit without another readiness question; claim completion only after tool results. '
        'Full creator guidance is supplied separately and remains applicable.')
    data={'request':text,'conversation':history,'attachments':attachments,'shared_memory':memory or {}}
    for attempt in range(2):
        result=validate_plan(ask(brain,system,data,schema,max_tokens=500,think=False))
        valid=(not result['question'] and not result['combine'] and [s['tool'] for s in result['steps']]==['zoom'])
        if valid:
            valid=all(result['steps'][0]['options'].get(key)==value for key,value in explicit.items())
        if sources:valid=valid and any(s['id']==result.get('source_id') and s['available'] for s in sources)
        if valid:
            # Planning is never completion, even if an old chat's completion
            # wording leaks into the model's proposed progress reply.
            result['reply']='Starting SmartZoom on your video.'
            return result
        data.update(invalid_answer=result,validation_error='Return one zoom step and the exact available current source ID. Honor current explicit settings '+str(explicit)+'. Do not add tools or ask to start again.')
    raise ValueError('SmartZoom could not prepare its settings. Your edited video is kept; retry this one editing step.')
