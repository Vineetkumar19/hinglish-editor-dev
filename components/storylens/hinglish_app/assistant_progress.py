"""Read-only presentation of the current request's real publishing checkpoints."""
import json
import time


def present(assistant, session):
    owned=session.get('upload_workflow') or {};bridge=session.get('prepare_post_bridge') or {}
    if not (owned.get('id') or bridge.get('id')):return None
    from .prepare_post_http import service,workflow_service
    engine=service(assistant.state,recover_delivery=False)
    flow=None
    if owned.get('id'):
        flow=workflow_service(assistant.state,engine).get(owned['id'],owned['profile'])
        owner=flow.get('assistant_plan') or {}
        if owner.get('session')!=session['id'] or owner.get('message_id')!=session.get('active_request_message_id'):return None
        profile=flow['profile'];ids=flow.get('preparations',{})
    else:
        profile=bridge['profile'];ids={'preparation':bridge['id']}
        if session.get('active_request_message_id') and not any(
                m.get('prepare_post_id')==bridge['id'] for m in session.get('messages',[])) and session.get('selected')!='publish':return None
    drafts=[]
    for role,key in ids.items():
        draft=engine.get(key,profile)
        drafts.append({'role':role,**{k:draft.get(k) for k in ('id','mode','count','status','current_stage','stage_timings')},
                       'stages':{k:{} for k in draft.get('stages',{})},
                       'errors':{k:{'error':v.get('error','Needs attention')} for k,v in draft.get('errors',{}).items()},
                       'live':{'stage':draft.get('current_stage'),'message':session.get('stage','')}})
    jobs=[]
    groups=flow.get('jobs',{}) if flow else engine.get(bridge['id'],profile).get('jobs_by_platform',{})
    for role,keys in groups.items():
        for n,key in enumerate(keys,1):
            job=engine.publisher.store.get(key);remote=job.get('remote') or {}
            jobs.append({'id':key,'role':role,'platform':job['platform'],'index':n,'status':job['status'],
                         'deleted_by_owner':bool(flow and role=='long' and flow.get('owner_long_deleted')),
                         'verified':bool(remote.get('schedule_verified_at') or remote.get('publication_verified_at') or remote.get('cancellation_verified_at')),
                         'authorized':bool(job.get('authorized_at')),'due':job.get('due')})
    start=(flow or {}).get('created') or session.get('active_request_created') or session.get('created')
    end=time.time() if session.get('status') in ('running','planning','transcribing') else (flow or {}).get('updated',time.time())
    return {'drafts':drafts,'jobs':jobs,'count':(flow or {}).get('intent',{}).get('count',1),
            'status':(flow or {}).get('status',session['status']),'elapsed':max(0,end-start) if start else None,
            'workflow':bool(flow),'stage':session.get('stage','')}
