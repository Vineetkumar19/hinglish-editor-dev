"""Optional visual retrieval using the existing specialist encoder, never a planner."""
from pathlib import Path
import json,gc
from .curation import file_hash,digest,Store
from .media_index import normalize_search_filters, search_clips

RECIPE='three-ordered-frames-mean-normalized-v1'

def run_visual(root,request,folder,stop,progress):
    import av,numpy as np
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_storage import role
    from hinglish_broll.vl_embedding import encode
    from .retrieval_loader import load_encoder_streaming
    from hinglish_app.workbench_jobs import atomic_json
    root=Path(root);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if request.get('provider')!='installed_visual_retrieval' or not request.get('fallback_reason'):
        raise ValueError('Choose and record the available visual retrieval provider before indexing.')
    id=request['dataset_id']
    if not isinstance(id,str) or len(id)!=32 or any(c not in '0123456789abcdef' for c in id):raise ValueError('Choose a saved footage dataset.')
    job=json.loads((root/'output/workbench'/id/'job.json').read_text('utf-8'))
    if job['kind']!='footage' or job['status']!='complete':raise ValueError('Finish footage extraction before visual indexing.')
    rows=job['result']['assets'];database=Store(root/'cache/curation/projects.sqlite3')
    try:review=database.get(id);rows=review['candidates']
    except ValueError:pass
    filters=normalize_search_filters(request.get('filters',{}))
    query=request.get('query','')
    if not isinstance(query,str) or len(query)>2000:raise ValueError('Use a short visual query.')
    selected=role(root,'broll_vision');model_path=Path(selected.get('path',''))
    weights=model_path/'model.safetensors'
    if not weights.is_file():raise ValueError('The configured local visual retrieval weights are unavailable; no automatic download was started.')
    progress('Verifying visual retrieval weights',1)
    identity=file_hash(weights)
    expected=next((v.get('sha256') for v in selected.get('verified',[]) if v.get('file')=='model.safetensors'),None)
    if expected and expected!=identity:raise ValueError('The installed visual retrieval weights changed.')
    import hinglish_broll.vl_embedding as encoder_source
    from . import retrieval_loader
    model_id=digest({'weights':identity,'encoder':file_hash(encoder_source.__file__),'loader':file_hash(retrieval_loader.__file__),'recipe':RECIPE})
    cache=root/'cache/curation/visual'/model_id;cache.mkdir(parents=True,exist_ok=True)
    indexed=[];todo=[];source_hashes={}
    for row in rows:
        if stop.is_set():raise InterruptedError('Visual indexing stopped; completed vectors are kept.')
        source_hashes.setdefault(row['source'],None)
        if source_hashes[row['source']] is None:source_hashes[row['source']]=file_hash(row['source'])
        if source_hashes[row['source']]!=row['source_sha256']:raise ValueError('An original source changed. Re-analyze it before indexing.')
        clip_hash=file_hash(row['path']);key=digest({'clip_hash':clip_hash,'model_id':model_id});file=cache/(key+'.json')
        if file.exists():
            saved=json.loads(file.read_text('utf-8'));indexed.append({**row,'embedding':saved['vector'],'embedding_model':model_id})
        else:todo.append((row,clip_hash,file))
    query_file=cache/('query-'+digest(query)+'.json');query_vector=None
    if query and query_file.exists():query_vector=json.loads(query_file.read_text('utf-8'))['vector']
    if todo or (query and query_vector is None):
        progress('Waiting for shared GPU reservation',5)
        with gpu_lock(root):
            import torch
            if torch.cuda.mem_get_info()[0]<6*1024**3:raise ValueError('Visual retrieval needs 6 GiB free GPU memory. Existing apps/models were preserved.')
            model=processor=None
            try:
                progress('Loading the installed retrieval encoder',6)
                model,processor=load_encoder_streaming(model_path,progress,stop)
                for number,(row,clip_hash,file) in enumerate(todo,1):
                    if stop.is_set():raise InterruptedError('Visual indexing stopped; completed vectors are kept.')
                    targets={round(row['output_frames']*f) for f in (.1,.5,.9)};pictures=[]
                    with av.open(row['path']) as media:
                        media.streams.video[0].thread_count=2
                        for frame_number,frame in enumerate(media.decode(video=0)):
                            if frame_number in targets:pictures.append(frame.to_image())
                    if len(pictures)!=3:raise ValueError('The candidate does not contain all required temporal samples.')
                    vectors=encode(model,processor,'cuda',images=pictures);vector=vectors.mean(axis=0);vector/=max(float(np.linalg.norm(vector)),1e-12)
                    if not np.isfinite(vector).all():raise ValueError('The visual encoder returned non-finite values.')
                    if file_hash(row['path'])!=clip_hash:raise ValueError('The candidate changed during encoding.')
                    values=vector.tolist();atomic_json(file,{'vector':values,'model_id':model_id,'clip_hash':clip_hash,'recipe':RECIPE})
                    indexed.append({**row,'embedding':values,'embedding_model':model_id})
                    progress(f'Visual vectors {number}/{len(todo)}',5+90*number/max(1,len(todo)))
                if query and query_vector is None:
                    query_vector=encode(model,processor,'cuda',texts=[query])[0].tolist();atomic_json(query_file,{'vector':query_vector,'model_id':model_id,'query':query})
            finally:
                del model,processor;gc.collect();torch.cuda.empty_cache()
    index={'dataset_id':id,'model_id':model_id,'model':'Qwen3-VL-Embedding-2B','weights_sha256':identity,'recipe':RECIPE,'fallback_reason':request['fallback_reason'],'source_hashes':source_hashes,'rows':indexed,'editorial_decisions':'unchanged; vectors are retrieval evidence only'}
    atomic_json(folder/'visual-index.json',index)
    result={'dataset_id':id,'model_id':model_id,'index_path':str(folder/'visual-index.json'),'candidate_count':len(indexed),'fallback_reason':request['fallback_reason'],'approval_state':'retrieval_only'}
    if query or filters:
        result.update(query=query, filters=filters, matches=[
            {k:v for k,v in row.items() if k!='embedding'}
            for row in search_clips(indexed,query,filters=filters,query_vector=query_vector,embedding_model=model_id)
        ])
    return result
