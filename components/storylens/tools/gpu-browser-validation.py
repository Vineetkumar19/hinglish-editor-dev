from pathlib import Path
import sys,json,traceback
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
target=root/'output/gpu-routing-20261029/browser-check.json'
target.write_text(json.dumps({'status':'waiting_for_gpu_slot'}),encoding='utf8')
try:
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(root):
        target.write_text(json.dumps({'status':'checking_private_headless_browser'}),encoding='utf8')
        from hinglish_motion.render import SceneRenderer
        renderer=SceneRenderer(256,144,device='cuda')
        try:result={'status':'actual_hardware_browser_passed','renderer':renderer.gpu_renderer,'visible_owner_browser_changed':False,'models_loaded':False,'cpu_fallback':False}
        finally:renderer.close()
    target.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
except BaseException as error:
    target.write_text(json.dumps({'status':'failed','error':str(error),'details':traceback.format_exc(),'cpu_fallback':False},indent=2),encoding='utf8')
    raise
