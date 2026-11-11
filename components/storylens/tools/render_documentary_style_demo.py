"""Render the personal chapter looks with labelled, reference-derived study panels."""
import html,json,sys
from fractions import Fraction
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from hinglish_motion.render import SceneRenderer
from hinglish_shorts.render import _Video
FOLDER=ROOT/'output/reference-analysis/cricket-documentaries/demo'

def main():
    assets=FOLDER/'assets';records=json.loads((assets/'provenance.json').read_text(encoding='utf-8'))
    for second,box in [(31,(350,230,1390,820)),(40,(650,210,1420,990))]:
        target=assets/f'panel-{second}.jpg'
        Image.open(assets/f'source-{second}.jpg').crop(box).save(target,quality=94)
        records.append({'file':target.name,'source':records[0]['source'],'seconds':second,'crop':box,'use':'Style study only; not certified historical-match imagery'})
    records=list({record['file']:record for record in records}.values())
    (assets/'provenance.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    fps=Fraction(60);renderer=SceneRenderer(960,540);writer=_Video(FOLDER/'DOCUMENTARY_STYLE_STUDY.mp4',960,540,fps,'libx264')
    results=[]
    try:
        for style in ('slate','map','sepia','ink','glass','album','night'):
            data={'label':'Mumbai Indians · A Journey','archive_style':style,'archive_grade':'monochrome' if style=='ink' else 'colour',
                  'assets':[{'src':(assets/f'panel-{second}.jpg').as_uri(),'enter_at':at} for second,at in [(20,0),(31,1.15),(40,2.55)]]}
            scene={'template':'archive_board','mode':'full','duration':6,'speed':.9,'data':data}
            problems=renderer.check(scene)
            if problems:raise ValueError(style+': '+str(problems))
            renderer.still(scene,4.4,FOLDER/(style+'.jpg'))
            renderer.write_scene(writer,scene,fps)
            results.append({'look':style,'seconds':6,'fps':60,'layout_problems':problems})
            print('Rendered chapter study: '+style,flush=True)
        writer.finish()
    except BaseException:writer.abort();raise
    finally:renderer.close()
    (FOLDER/'validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    cards=''.join(f'<figure><img src="{r["look"]}.jpg"><figcaption>{html.escape(r["look"])}</figcaption></figure>' for r in results)
    (FOLDER/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Documentary style study</title><style>body{font:18px/1.6 system-ui;background:#11191d;color:#eee;max-width:1100px;margin:auto;padding:35px}video{width:100%}main{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0}img{width:100%}a{color:#91d8e5}</style><h1>Your documentary chapter looks</h1><p>A 42-second, 60fps renderer study with three separate image-entry times in each chapter. Silent preview; this is an adaptation, not an exact reconstruction of your After Effects project.</p><p>The study uses cropped panels extracted from your own finished reference at 20,31 and40 seconds. They are not automatically certified as historical-match images. <a href="assets/provenance.json">Source record</a></p><video src="DOCUMENTARY_STYLE_STUDY.mp4" controls preload="metadata"></video><main>'+cards+'</main>',encoding='utf-8')
    print('Study complete: '+str(FOLDER/'report.html'))

if __name__=='__main__':main()
