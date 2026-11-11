"""Read-only planning diagnostics: never dispatch the returned tool plan."""
from pathlib import Path


def check(assistant,session_id):
    from .assistant import ACTIVE
    if any(s['status'] in ACTIVE for s in assistant.sessions.values()):
        raise ValueError('Wait for the current Storylens task before checking local inference.')
    snapshot=assistant.snapshot(session_id)
    if snapshot['status'] in ACTIVE:raise ValueError('This chat is working; wait before checking its planner.')
    users=[m for m in snapshot['messages'] if m['role']=='user']
    if not users:raise ValueError('This chat has no request to check.')
    current=users[-1];text=current['text']
    history=[m for m in snapshot['messages'][:snapshot['messages'].index(current)]]
    attachments=[{'name':a['name'],'kind':Path(a['path']).suffix}
                 for a in snapshot.get('attachments',[]) if a['id'] in current.get('attachments',[])]
    diagnostics=[];stages=[]
    from .assistant_plan import plan
    from hinglish_niche.profiles import Profiles,use
    from hinglish_cut.gpu_lock import gpu_lock
    result=None;model='';error=''
    try:
        with assistant.state.work_lock,gpu_lock(assistant.root),use(Profiles(assistant.root).context(snapshot.get('profile','general'))):
            result,model=plan(assistant.root,text,history,attachments,bool(snapshot['last_paths']),
                progress=stages.append,memory_context=assistant.context_memory(text,session_id),
                browser_context={k:v for k,v in assistant.state.local_browser.snapshot().items() if k!='jobs'},
                diagnostics=diagnostics)
    except (ValueError,RuntimeError) as issue:
        error=str(issue)
        if diagnostics:model=diagnostics[-1].name
    usage=[getattr(brain,'last_usage',{}) for brain in diagnostics]
    from .assistant_request_status import pipeline_is_current,review_is_current
    return {'execution':False,'message':'Read-only planner check. No tools, queues or uploads were started.',
            'request_scope':{'pipeline_is_current':pipeline_is_current(snapshot),
                'review_is_current':review_is_current(snapshot,snapshot.get('publishing_review') or {})},
            'model':model,'usage':usage,'context_accepted':result is not None or any(u.get('input_tokens',0)>0 for u in usage),
            'plan_valid':result is not None,'validation_error':error,'plan':result,'stages':stages[-5:]}
