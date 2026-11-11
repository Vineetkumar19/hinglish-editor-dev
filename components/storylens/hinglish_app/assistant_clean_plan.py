"""Small local planner for cleanup of this chat's latest finished video."""
import re


def requested(text, has_output):
    from .assistant_publish_intent import positive
    value=positive(text)
    return bool(has_output and re.search(r'\bsmart clean\b',value,re.I)
        and re.search(r'\b(?:video you just|latest (?:video|output)|this video|arranged video)\b',value,re.I)
        and not re.search(r'\b(?:script edit|publish|upload|schedule|captions?|music|b.roll|shorts?)\b',value,re.I))


def plan(brain,text,history,memory):
    from .assistant_plan import validate_plan
    from .assistant_plan_context import ask
    schema={'type':'object','additionalProperties':False,'properties':{
        'reply':{'type':'string'},'question':{'type':'string','enum':['']},
        'combine':{'type':'boolean'},'steps':{'type':'array','minItems':1,'maxItems':1,'items':{
            'type':'object','additionalProperties':False,'properties':{
                'tool':{'type':'string','enum':['clean']},
                'options':{'type':'object','properties':{},'additionalProperties':False}},
            'required':['tool','options']}}},'required':['reply','question','combine','steps']}
    system=('You are the local Storylens cleanup planner. The owner explicitly requested Smart Clean '
        'on this chat\'s latest completed video. The runner supplies that output as input and keeps '
        'its script order and selected takes. Return one clean tool step with empty options. '
        'Execute now, without another readiness question. Do not rerun Script Edit or select original '
        'clips. Do not add other features or publish anything. Your reply describes starting work; '
        'claim completion only after tool results. Full creator guidance is supplied separately.')
    data={'request':text,'conversation':history,'shared_memory':memory or {},
          'active_input':'Latest completed video in this chat; its path is owned by the runner.'}
    for attempt in range(2):
        result=validate_plan(ask(brain,system,data,schema,max_tokens=400,think=False))
        if not result['question'] and [s['tool'] for s in result['steps']]==['clean']:return result
        if attempt:raise ValueError('The local model could not start cleanup of the completed video. The video is preserved.')
        data={**data,'invalid_answer':result,'validation_error':
            'The latest finished video is already available. Return one clean step and an empty question.'}
