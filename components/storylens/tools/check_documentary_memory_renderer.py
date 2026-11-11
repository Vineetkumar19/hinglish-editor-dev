"""Small live renderer/continuity smoke check; no creative video export."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hinglish_motion.render import SceneRenderer
from hinglish_niche.documentary import ANIMATIONS

def main():
    folder=ROOT/'output/reference-analysis/continuous-documentary-memory/browser-smoke';folder.mkdir(exist_ok=True)
    assets=ROOT/'output/reference-analysis/crick-edit-editing-style/demo/assets'
    scene={'template':'archive_board','mode':'full','duration':3,'theme':'archive','speed':1,'continuity_audit':True,
      'data':{**{k:ANIMATIONS[0][k] for k in ['archive_style','archive_variant']},'archive_composition':'road-travel',
      'label':'Renderer check','assets':[{'src':(assets/'bowler.jpg').as_uri(),'enter_at':0},
      {'src':(assets/'portrait.jpg').as_uri(),'enter_at':.8}]}}
    class Writer:
        count=0
        def write(self,pixels,format):self.count+=1
    renderer=SceneRenderer(640,360);writer=Writer()
    try:renderer.write_scene(writer,scene,6,audit_folder=folder)
    finally:renderer.close()
    result=json.loads((folder/'review.json').read_text(encoding='utf8'))
    photos=result.get('foreground_photo_geometry',{})
    if writer.count!=18 or not photos.get('available'):raise ValueError('Live photo geometry audit unavailable')
    (folder/'result.json').write_text(json.dumps({'status':'passed','frames':writer.count,'foreground_photo_trace_available':True,
      'new_video_generated':False,'approved_animation_modified':False,'continuity_review':result},indent=2),encoding='utf8')
    print('LIVE RENDERER CHECK PASSED',writer.count,'frames; foreground photo trace available',flush=True)

if __name__=='__main__':main()
