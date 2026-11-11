"""Bounded local planning for script-referenced raw takes.

The local model selects the steps. Files come from owner attachments and the
ordinary runner reads the attached script; this planner never edits footage.
"""
import re


SYSTEM = '''You are Storylens's local raw-take editing planner. Return the requested JSON.
The owner supplied a reference .txt script and source clips. Use Script Edit to
arrange clips by that script's meaning, then Smart Clean only when requested for
this step. Script Edit only means do not start Smart Clean yet, even when the
owner says they will request it next. Match approximate scripts to actual speech;
do not invent narration, change spoken wording, or generate missing footage.
The runner reads the attached .txt verbatim; leave tool options empty. Never ask
the owner to paste a script that is already attached. The selected clips are the
active inputs, not old outputs or media mentioned in recalled chats. For arranged
clips combined into one video set combine=true. Select only script and clean;
publishing and other features are unavailable in this scoped request. Answer
questions without starting work, and clarify only genuinely missing information.
An explicit start/use/run/edit command with both reference .txt and video inputs
is authorization to execute now. Never ask whether the owner is ready or wants
to proceed. Earlier assistant errors are failed attempts, not current tool facts.
Select a tool plan for the current valid request; do not repeat those old errors.
Follow the latest request, preserving the current source scope and step order.
Never claim editing succeeded before tool results. Creator guidance is provided
in full separately and remains subject to the current owner's request.'''


def requested(text, attachments):
    from .assistant_publish_intent import positive
    value=positive(text)
    if not any(a.get('kind')=='.txt' for a in attachments):return False
    if not re.search(r'\bscript edit\b',value,re.I):return False
    # Other affirmative workflows retain the general planner. Merely naming
    # shooting context in the attached script cannot request another feature.
    return not re.search(r'\b(?:upload|publish|post|schedule|captions?|subtitles?|'
                         r'b.roll|zoom|sound|music|shorts?|reels?|thumbnail|gaming|'
                         r'motion graphics|ai images?|ai video)\b',value,re.I)


def plan(brain,text,history,attachments,memory):
    from .assistant_plan import validate_plan
    from .assistant_plan_context import ask
    schema={'type':'object','additionalProperties':False,'properties':{
        'reply':{'type':'string'},'question':{'type':'string'},
        'combine':{'type':'boolean'},'steps':{'type':'array','maxItems':2,'items':{
            'type':'object','additionalProperties':False,'properties':{
                'tool':{'type':'string','enum':['script','clean']},
                'options':{'type':'object','additionalProperties':False,'properties':{}}},
            'required':['tool','options']}}},'required':['reply','question','combine','steps']}
    ready=(any(a.get('kind')=='.txt' for a in attachments) and
           any(a.get('kind') in ('.mp4','.mov','.mkv','.webm','.mxf','.avi','.mts','.m2ts') for a in attachments) and
           bool(re.search(r'\b(?:start|use|run|arrange|combine|edit)\b',text,re.I)))
    script_only=bool(re.search(r'\bscript edit only\b',text,re.I))
    if ready:
        # Complete owner inputs and an explicit execution command need a plan,
        # not a second authorization. The local model still selects the steps.
        schema['properties']['question']['enum']=['']
        schema['properties']['steps']['minItems']=1
    if script_only:
        schema['properties']['steps']['maxItems']=1
        schema['properties']['steps']['items']['properties']['tool']['enum']=['script']
    data={'request':text,'conversation':history,'attachments':attachments,
          'shared_memory':memory or {},
          'reference_script':'The attached .txt is read verbatim by the runner after planning.',
          'input_readiness':{'complete':ready,'video_count':sum(a.get('kind')!='.txt' for a in attachments),
                             'action':'Execute the current editing request now; no additional confirmation is needed.' if ready else 'Clarify only missing inputs.'}}
    for attempt in range(2):
        result=validate_plan(ask(brain,SYSTEM,data,schema,max_tokens=700,think=False))
        tools=[s['tool'] for s in result['steps']]
        error=''
        if ready and (result['question'] or not tools):
            error='The reference script and video clips are supplied, and the owner explicitly asked to start. Return an execution plan with a script step, question empty; do not ask for readiness or repeat prior errors.'
        if any(t not in ('script','clean') for t in tools):
            error='Only Script Edit and Smart Clean are available for this reference-script request.'
        if tools and 'script' not in tools:
            error='This request explicitly asks for Script Edit; include the script tool.'
        if tools and tools not in (['script'],['script','clean']):
            error='Run Script Edit once first, then Smart Clean once if requested. Return steps in that order; do not clean before arranging or repeat a step.'
        if 'clean' in tools and re.search(r'\bscript edit only\b',text,re.I):
            error='This step is Script Edit only. Smart Clean is requested for a later turn; omit clean now.'
        if not error:return result
        if attempt:raise ValueError('The local model could not plan the requested script editing step: '+error)
        data={**data,'invalid_answer':result,'validation_error':error}

