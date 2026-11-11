"""Small real runtime checks. No media edits, posts, downloads or model changes."""
from pathlib import Path
import sys,json,time,traceback,hashlib
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
out=root/'output/gpu-routing-20261029';target=out/'runtime-integration.json'


def save(data):target.write_text(json.dumps(data,indent=2),encoding='utf8')


def main():
    import requests
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import preferences
    from hinglish_cut.ollama_gpu import post
    data={'status':'waiting_for_gpu_slot','owner_apps_changed':False,'models_changed':False,'cpu_fallback':False}
    save(data)
    with gpu_lock(root):
        s=requests.Session();s.trust_env=False
        local=preferences(root);model=local['planning_model']
        # A tiny technical response, with the same configured context budget.
        # Do not replace the owner's model or drop saved instructions in any job.
        data.update(status='checking_configured_model_gpu',model=model);save(data)
        body={'model':model,'messages':[{'role':'user','content':'Reply with the single word OK.'}],
              'stream':False,'think':False,'keep_alive':'2s','options':{'num_ctx':local.get('context_limit',12288),'num_predict':8,'temperature':0}}
        started=time.monotonic()
        response=post(root,s,'http://127.0.0.1:11434/api/chat',json=body,timeout=600)
        response.raise_for_status();answer=response.json()
        receipt=root/'cache/app/gpu-residency'/(hashlib.sha256(model.encode()).hexdigest()[:16]+'.json')
        data['model_check']={'residency':json.loads(receipt.read_text()),'done':answer.get('done'),
                             'response':answer.get('message',{}).get('content'),'elapsed_seconds':round(time.monotonic()-started,2)}
        data['status']='checking_browser_hardware';save(data)
        # Let only this owned tiny request's short keep-alive expire.
        time.sleep(3)
        from hinglish_motion.render import SceneRenderer
        scene=SceneRenderer(256,144,device='cuda')
        try:data['browser_gpu']=scene.gpu_renderer
        finally:scene.close()
        data['status']='actual_model_and_browser_gpu_passed';save(data)
        print(json.dumps(data,indent=2))


if __name__=='__main__':
    try:main()
    except BaseException as error:
        previous=json.loads(target.read_text()) if target.exists() else {}
        save(dict(previous,status='failed',error=str(error),details=traceback.format_exc(),cpu_fallback=False))
        raise
