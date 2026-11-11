"""GPU-first Ollama placement, with explicitly configured model CPU offload."""
from copy import deepcopy
from pathlib import Path
import hashlib,json,time,os


def _request(session,url,body,on_content=None,**kwargs):
    if on_content is None:return session.post(url,json=body,**kwargs)
    import json as codec
    from requests import Response
    response=session.post(url,json={**body,'stream':True},stream=True,**kwargs)
    if response.status_code>=400:return response
    content='';last=None
    try:
        for line in response.iter_lines():
            if not line:continue
            packet=codec.loads(line)
            if packet.get('error'):raise RuntimeError(packet['error'])
            content+=packet.get('message',{}).get('content','')
            on_content(content)
            if packet.get('done'):last=packet
        if last is None:raise ConnectionError('The local reply stream ended before completion.')
        buffered=Response();buffered.status_code=response.status_code
        buffered._content=codec.dumps({**last,'message':{'role':'assistant','content':content}}).encode('utf-8')
        return buffered
    finally:response.close()


def post(root, session, url, *, json: dict, on_content=None, **kwargs):
    from .model_preferences import preferences
    policy = preferences(root)
    from .publishing_native import selected, post as native_post
    if selected(policy,json):
        return native_post(root,json,policy,on_content)
    if not policy.get('heavy_workloads_gpu_only'):
        return _request(session,url,json,on_content,**kwargs)
    from . import gpu_lock as slot
    if not hasattr(slot,'child_environment') or not hasattr(slot,'held_by_current_thread'):
        raise RuntimeError('Finish the current job and reload Storylens to activate the GPU policy safely. No CPU fallback was started.')
    if os.environ.get('HINGLISH_CREATOR_CONTEXT_FILE') and not os.environ.get(slot.LEASE_ENV) and not slot.held_by_current_thread(root):
        # Old running controllers do not know about signed child reservations.
        # Fail before queue acquisition instead of waiting for the parent that
        # is itself awaiting this child. Never trust the old bare-root marker.
        raise RuntimeError('Finish the current job and reload Storylens to activate the GPU policy safely. This managed worker did not receive its GPU reservation; no CPU fallback was started.')
    with slot.gpu_lock(root):
        body=deepcopy(json)
        body.setdefault('options',{})
        if url.endswith(('/api/chat', '/api/generate')):
            batch=body['options'].get('num_batch',64)
            if type(batch) is not int or batch<1:raise ValueError('The GPU processing batch must be a positive number.')
            # Prefill the SAME complete context in smaller CUDA batches. This
            # reduces graph/scratch VRAM without truncating the owner's input.
            body['options']['num_batch']=min(batch,64)
        model=body.get('model','')
        if not model or model.endswith(':cloud'):
            raise RuntimeError('GPU-only inference requires the configured local model. No CPU or cloud substitution was started.')
        selected = {policy.get(key) for key in ('planning_model','vision_model','meaning_model')}
        allow_offload = policy.get('allow_ollama_cpu_offload') is True and model.removesuffix(':latest') in {str(x).removesuffix(':latest') for x in selected if x}
        base=url.rsplit('/api/',1)[0]
        metadata=session.post(base+'/api/show',json={'model':model,'verbose':False},timeout=30)
        metadata.raise_for_status()
        info=metadata.json().get('model_info',{})
        architecture=info.get('general.architecture')
        blocks=info.get(str(architecture)+'.block_count')
        if type(blocks) is not int or not 1<=blocks<=256:
            raise RuntimeError('The local model GPU layer count could not be verified. CPU offload is blocked; keep the request and restore its model metadata.')
        # -1 is a memory heuristic and may choose CPU offload even when a full
        # allocation fits. Request all transformer blocks plus the output layer.
        body['options']['num_gpu']=-1 if allow_offload else blocks+1
        warmup={key:body[key] for key in ('model','options','keep_alive') if key in body}
        warmup.setdefault('keep_alive','30s')
        warmup['stream']=False
        if url.endswith('/api/generate'):
            warmup['prompt']=''
        else:
            warmup['input' if url.endswith('/api/embed') else 'messages']=[]
        if 'think' in body:warmup['think']=body['think']
        response=session.post(url,json=warmup,**kwargs)
        response.raise_for_status()
        state=session.get(base+'/api/ps',timeout=15)
        state.raise_for_status()
        names={model,model+':latest'}
        loaded=next((row for row in state.json().get('models',[])
                     if row.get('name') in names or row.get('model') in names),None)
        total=loaded.get('size') if loaded else None
        vram=loaded.get('size_vram') if loaded else None
        if type(total) is not int or type(vram) is not int or total<=0 or vram<=0 or (not allow_offload and vram<total):
            if allow_offload:
                raise RuntimeError('The selected local model could not be confirmed on GPU. Check NVIDIA availability, then retry. GPU-first mode allows partial CPU offload but does not silently select CPU-only inference.')
            raise RuntimeError('The selected model could not be confirmed fully in GPU memory. CPU offload is blocked; the request and saved guidance are kept. Retry when enough VRAM is free. Technical details: '+str({'model':model,'total_bytes':total,'gpu_bytes':vram}))
        record={'model':model,'size':total,'size_vram':vram,'num_ctx':body['options'].get('num_ctx'),'num_gpu':body['options']['num_gpu'],
                'checked_at':time.time(),'cpu_offload':vram<total,'cpu_offload_allowed':allow_offload,'source':'Ollama /api/ps before inference'}
        folder=Path(root)/'cache/app/gpu-residency';folder.mkdir(parents=True,exist_ok=True)
        target=folder/(hashlib.sha256(model.encode()).hexdigest()[:16]+'.json')
        import json as json_module
        target.write_text(json_module.dumps(record,indent=2),encoding='utf8')
        return _request(session,url,body,on_content,**kwargs)
