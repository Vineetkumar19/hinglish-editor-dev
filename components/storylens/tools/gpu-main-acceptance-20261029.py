"""Activate/check real main-app inference and selected model roles, serially."""
from pathlib import Path
import sys,json,time,base64,traceback
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
out=root/'output/gpu-routing-20261029';target=out/'main-activation-acceptance.json'


def save(record):target.write_text(json.dumps(record,indent=2),encoding='utf8')


def main():
    import requests
    from hinglish_cut.model_preferences import preferences
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.ollama_gpu import post
    s=requests.Session();s.trust_env=False;base='http://127.0.0.1:8765';ollama='http://127.0.0.1:11434'
    bridge=s.get(base+'/api/bridge',timeout=5);bridge.raise_for_status();h={'X-Hinglish-Token':bridge.json()['token']}
    record={'status':'checking_main_application','main_service_reloaded':True,'publishing_started':False,'owner_media_changed':False,'models_changed':False,'model_results':[]}
    save(record)
    response=s.post(base+'/api/assistant/session',headers=h,json={},timeout=10);response.raise_for_status();identity=response.json()['id']
    record['main_chat_id']=identity;save(record)
    response=s.post(base+'/api/assistant/message',headers=h,json={'session':identity,'profile':'general',
        'message':'GPU activation check: explain in one short sentence what Smart Clean does. Do not edit files, create media, upload or schedule anything.'},timeout=10)
    response.raise_for_status()
    snapshots={};started=time.monotonic()
    while True:
        response=s.get(base+'/api/assistant/session',headers=h,params={'id':identity},timeout=15);response.raise_for_status();chat=response.json()
        state=s.get(ollama+'/api/ps',timeout=5);state.raise_for_status()
        for model in state.json().get('models',[]):
            snapshots[model['name']]={key:model.get(key) for key in ('name','size','size_vram','context_length')}
        record['main_chat_status']=chat['status'];record['main_stage']=chat.get('stage');save(record)
        if chat['status'] not in ('planning','running','transcribing'):
            record['main_app']={'status':chat['status'],'brain':chat.get('brain'),'stage':chat.get('stage'),
                'elapsed_seconds':round(time.monotonic()-started,2),'gpu_snapshots':list(snapshots.values()),'job_id':chat.get('job_id')}
            save(record)
            if chat['status'] in ('failed','error'):raise RuntimeError('The real main chat did not finish; inspect its saved stage.')
            if not snapshots:raise RuntimeError('No real model residency was observed in the main application check.')
            if any(m.get('size',0)<=0 or m.get('size_vram',0)<m['size'] for m in snapshots.values()):raise RuntimeError('Main application GPU residency was incomplete.')
            break
        time.sleep(1)
    local=preferences(root)
    def unload(model):
        response=s.post(ollama+'/api/generate',json={'model':model,'keep_alive':0},timeout=60)
        response.raise_for_status()
    with gpu_lock(root):
        # Only models used by this verification are unloaded between tests.
        for model in snapshots:unload(model)
        picture=base64.b64encode((out/'frame-validation/face.png').read_bytes()).decode('ascii')
        for role,endpoint,body in [
            ('vision','/api/chat',{'model':local['vision_model'],'messages':[{'role':'user','content':'Name the two main colors. Be brief.','images':[picture]}],
                                   'stream':False,'think':False,'keep_alive':'2s','options':{'num_ctx':8192,'num_predict':24,'temperature':0}}),
            ('embedding','/api/embed',{'model':local['embedding_model'],'input':['Storylens GPU activation verification.'],
                                    'keep_alive':'2s','truncate':False,'options':{'num_ctx':4096}})]:
            record['status']='checking_'+role+'_gpu';save(record);start=time.monotonic()
            response=post(root,s,ollama+endpoint,json=body,timeout=600);response.raise_for_status();answer=response.json()
            resident=s.get(ollama+'/api/ps',timeout=5).json().get('models',[])
            row=next(m for m in resident if m.get('name') in (body['model'],body['model']+':latest'))
            result={'role':role,'model':body['model'],'size':row['size'],'size_vram':row['size_vram'],'context_length':row.get('context_length'),
                    'fully_gpu':row['size']==row['size_vram'],'elapsed_seconds':round(time.monotonic()-start,2)}
            if role=='vision':result.update(done=answer.get('done'),response=answer.get('message',{}).get('content','')[:200])
            else:result.update(vector_count=len(answer.get('embeddings',[])),dimensions=len((answer.get('embeddings') or [[]])[0]))
            record['model_results'].append(result);save(record)
            if not result['fully_gpu']:raise RuntimeError(role+' did not remain fully GPU-resident.')
            unload(body['model'])
    record['status']='main_and_selected_models_gpu_verified';save(record);print(json.dumps(record,indent=2))


if __name__=='__main__':
    try:main()
    except BaseException as error:
        record=json.loads(target.read_text()) if target.exists() else {}
        record.update(status='failed',error=str(error),details=traceback.format_exc());save(record)
        raise
