"""Fit foreground tool planning without repeatedly injecting archived context."""
import copy
import json
import re
from pathlib import Path


def compact(data,lean=False,history_options=None):
    result=copy.deepcopy(data)
    # Request, attachments, allowed source IDs, dates and review receipts stay
    # intact. Retrieved chat prose is optional background, not tool authority.
    from .chat_context import recent
    result['conversation']=recent(result.get('conversation',[]), **(history_options or {}))
    memory=result.get('shared_memory',{})
    memory.pop('messages',None)
    memory.pop('saved_media',None)
    active=memory.get('active_task',{})
    active.pop('conversation',None)  # already supplied as foreground history
    runtime=memory.get('runtime_facts',{})
    runtime.pop('tools',None)  # already supplied as tool definitions
    if lean:
        # Reusable prose and writing preferences are not routing authority.
        # Preserve exact request, schema, source IDs, accounts, dates and receipts.
        memory.pop('workflow_knowledge',None)
        memory.pop('runtime_facts',None)
        result.pop('preferences',None)
        result['conversation']=[m for m in result['conversation'] if m.get('role')=='user']
        # A single editing request must not carry the entire publishing and
        # browser setup procedure. These are optional runtime background here,
        # never the injected creator profile, source/receipt IDs or tool schema.
        # Delivery/account requests and pending delivery evidence keep it all.
        foreground=' '.join([str(result.get('request',''))]+[str(m.get('text','')) for m in result['conversation']])
        delivery=re.search(r'\b(?:publish\w*|upload\w*|schedul\w*|post(?:ing|ed|s)?|queue\w*|accounts?|signed.in|chrome|browser|instagram|youtube)\b',foreground,re.I)
        editing=re.search(r'\b(?:visuals?|videos?|images?|captions?|b.roll|clean|zoom|sound|motion|cinematic|beats?|thumbnail)\b',foreground,re.I)
        pending=any(active.get(k) for k in ('publishing_review','publication','distribution','campaign','remote_receipts'))
        if editing and not delivery and not pending:
            omitted=[]
            for key in ('distribution_workflow','chrome_connection'):
                if key in result:result.pop(key);omitted.append(key)
            if omitted:result['omitted_optional_context']=omitted
    result['context_note']='Archived chat prose was omitted to fit the local context. Current request, source IDs and tool evidence are unchanged. Clarify missing older facts; never guess them.'
    return result


def fit(brain,system,data,schema,max_tokens,lean=False):
    """Budget input plus answer space before calling the local model."""
    from hinglish_cut.model_preferences import preferences
    from hinglish_niche.profiles import inject
    root=getattr(brain,'root',None)
    cap=preferences(root).get('context_limit',8192) if isinstance(root,(str,Path)) else 8192
    from hinglish_cut.feature_context import limits, history_options
    selected=limits(root,'assistant') if isinstance(root,(str,Path)) else None
    if selected:cap=selected[1]
    history=history_options(root) if selected else {}
    budget=cap-max_tokens-512
    result=copy.deepcopy(data) if selected and not lean else compact(data,lean=lean,history_options=history)
    def estimate(value):
        # Include the same creator guidance Brain.json will attach. It is
        # required context: neither normal planning nor the lean fallback
        # silently replaces the owner's profile with General.
        full_system,full_value=inject(system,value,root=root if isinstance(root,(str,Path)) else None)
        # Conservative UTF-8 estimate, including the grammar/template overhead.
        return (len(json.dumps([full_system,full_value,schema],ensure_ascii=False,separators=(',',':')).encode('utf-8'))+2)//3+128
    if estimate(result)>budget:result=compact(data,lean=True,history_options=history)
    if selected:
        conversation=result.get('conversation',[])
        while estimate(result)>budget and conversation:
            conversation.pop(0)
            result['context_note']='Older conversation was omitted from this request to preserve the current task and reply budget. Full history remains saved; retrieve older facts rather than guessing.'
    if estimate(result)>budget:
        raise ValueError('This request contains too much required planning information for the local context. No work started. Split the source batches into separate requests; their saved queues will remain independent.')
    return result


def ask(brain,system,data,schema,**options):
    bounded=fit(brain,system,data,schema,options.get('max_tokens',2400))
    try:
        return brain.json(system,bounded,schema,**options)
    except RuntimeError as error:
        message=str(error).lower()
        if 'http 400' not in message or not ('context' in message and ('exceed' in message or 'too long' in message)):raise
        bounded=fit(brain,system,data,schema,options.get('max_tokens',2400),lean=True)
        try:
            return brain.json(system,bounded,schema,**options)
        except RuntimeError as retry:
            message=str(retry).lower()
            if 'http 400' in message and 'context' in message and ('exceed' in message or 'too long' in message):
                raise ValueError('The local planning context is still too large. No work started; the current request and saved files are preserved.') from retry
            raise
