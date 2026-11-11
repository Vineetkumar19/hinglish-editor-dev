"""One-minute preview of distinct documentary image sequences, using owned reference study panels."""
import argparse,html,json,subprocess,sys
from fractions import Fraction
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from hinglish_motion.render import SceneRenderer
from hinglish_shorts.render import _Video

FOLDER=ROOT/'output/reference-analysis/cricket-documentaries/motion-stories'
VIDEO_NAME='DOCUMENTARY_MOTION_STORIES_60S.mp4'
SCENE_SECONDS=12
ASSETS=ROOT/'output/reference-analysis/cricket-documentaries/demo/assets'
SHOTS=[
 ('map',0,'The road to this moment','Forward camera travel along a drawn timeline; new images enter from the right and earlier ones leave on the left'),
 ('slate',1,'Reel of memories','Equal, aligned film windows advance as one connected strip; photographs keep their source proportions'),
 ('night',0,'Under the lights','One centred image at a time; aperture reveals and focus dissolves replace the previous photograph'),
 ('glass',0,'A different lens','Three equal glass doors open on separate hinges; photographs stay inside the panels'),
 ('album',0,'Pages of the journey','Photographs ride turning pages; the previous image stays on the left page while the next appears on the right')]

def main(only=None,stills_only=False):
    FOLDER.mkdir(parents=True,exist_ok=True)
    renderer=SceneRenderer(1280,720);fps=Fraction(60)
    final=FOLDER/VIDEO_NAME
    part=FOLDER/f'replacement-{only:02}.mp4' if only else final
    writer=None if stills_only else _Video(part,1280,720,fps,'libx264')
    results=[]
    try:
        for index,(style,variant,label,motion) in enumerate(SHOTS):
            if only and index+1!=only:continue
            order=[40,20,31]
            data={'label':label,'archive_style':style,'archive_variant':variant,
                  'archive_grade':'monochrome' if style=='ink' and variant==0 else 'colour',
                  'assets':[{'src':(ASSETS/f'panel-{second}.jpg').as_uri(),'enter_at':at} for second,at in zip(order,[.05,4,8])]}
            scene={'index':index,'template':'archive_board','mode':'full','duration':SCENE_SECONDS,'speed':1,'data':data}
            issues=renderer.check(scene)
            if issues:raise ValueError(str(issues))
            name=f'{index+1:02}-{style}-{variant}'
            renderer.still(scene,10.6,FOLDER/(name+'.jpg'))
            renderer.load(scene)
            canvas=Image.new('RGB',(4*320,2*202),'#11191d');draw=ImageDraw.Draw(canvas)
            composition=renderer.page.locator('.archive-world').get_attribute('data-composition')
            for j,t in enumerate([0,.7,2,4.3,5.2,7.5,8.5,10.8]):
                frame=Image.fromarray(renderer.frame(t)).resize((320,180))
                x=j%4*320;y=j//4*202;canvas.paste(frame,(x,y));draw.text((x+6,y+183),f'{index*SCENE_SECONDS+t:.2f}s',fill='white')
            canvas.save(FOLDER/(name+'-motion.jpg'),quality=90)
            if writer:renderer.write_scene(writer,scene,fps)
            results.append({'shot':index+1,'start':index*SCENE_SECONDS,'end':(index+1)*SCENE_SECONDS,'style':style,'variant':variant,'composition':composition,
                            'label':label,'motion':motion,'layout_issues':issues,'still':name+'.jpg','contacts':name+'-motion.jpg'})
            print(f'Rendered {index+1}/{len(SHOTS)}: {composition}',flush=True)
        if writer:writer.finish()
    except BaseException:
        if writer:writer.abort()
        raise
    finally:renderer.close()
    if only and not stills_only:
        from imageio_ffmpeg import get_ffmpeg_exe
        start=(only-1)*SCENE_SECONDS;end=only*SCENE_SECONDS;filters=[];clips=[]
        if start:
            filters.append(f'[0:v]trim=end={start},setpts=PTS-STARTPTS[before]');clips.append('[before]')
        clips.append('[1:v]')
        if end<60:
            filters.append(f'[0:v]trim=start={end}:end=60,setpts=PTS-STARTPTS[after]');clips.append('[after]')
        filters.append(''.join(clips)+f'concat=n={len(clips)}:v=1:a=0[out]')
        target=FOLDER/'DOCUMENTARY_MOTION_STORIES_60S-updated.mp4'
        subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-y','-threads','2',
            '-i',str(final),'-i',str(part),'-filter_complex_threads','2','-filter_complex',';'.join(filters),
            '-map','[out]','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
            '-r','60','-fps_mode','cfr','-video_track_timescale','15360','-threads','2',str(target)],check=True)
        target.replace(final)
        previous=json.loads((FOLDER/'shots.json').read_text(encoding='utf-8'))
        results=[results[0] if item['shot']==only else item for item in previous]
    (FOLDER/'shots.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    rows=''.join(f'<tr><td>{r["start"]:02}–{r["end"]:02}s</td><td>{r["composition"].replace("-"," ").title()}</td><td>{html.escape(r["motion"])}</td></tr>' for r in results)
    figures=''.join(f'<figure><a href="{r["contacts"]}"><img src="{r["still"]}" loading="lazy"></a><figcaption>{r["start"]:02}–{r["end"]:02}s · {r["composition"].replace("-"," ").title()}<br>{html.escape(r["motion"])}</figcaption></figure>' for r in results)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Documentary photographs — five scene structures</title><style>body{font:17px/1.6 system-ui;background:#07131e;color:#e7eced;max-width:1200px;margin:auto;padding:30px}video{width:100%;border-radius:12px;box-shadow:0 25px 90px #0008}h1{font:44px/1.15 Georgia,serif;color:#ead9b9}a{color:#b5d9ed}table{width:100%;border-collapse:collapse;margin:25px 0}td,th{padding:12px;border-bottom:1px solid #344147;text-align:left;vertical-align:top}main{display:grid;grid-template-columns:1fr 1fr;gap:28px}figure{margin:0}img{width:100%;border-radius:8px}figcaption{font-size:14px;padding:8px 0;color:#bfd0d6}@media(max-width:700px){main{grid-template-columns:1fr}}</style><h1>Five ways to move through photographs.</h1><p>One minute · 60fps · 720p. Five scene structures: a travelling timeline, an aligned film reel, a centred photographic dissolve, hinged glass panels and turning album pages. The same three photographs are used throughout.</p><video src="'''+VIDEO_NAME+'''" controls playsinline preload="metadata"></video><p>Silent visual study using cropped panels from your documentary references. Click any image below to inspect eight moments of its animation.</p><table><tr><th>Time</th><th>Scene</th><th>How the photographs move</th></tr>'''+rows+'</table><main>'+figures+'</main><p><a href="../demo/assets/provenance.json">Reference panel sources</a> · <a href="shots.json">Preview timeline</a> · <a href="../demo-motion-v3/report.html">Previous preview</a></p></html>'
    (FOLDER/'report.html').write_text(page,encoding='utf-8')
    print('Finished one-minute preview: '+str(FOLDER/'report.html'),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shot',type=int,choices=range(1,len(SHOTS)+1));parser.add_argument('--stills',action='store_true')
    args=parser.parse_args();main(args.shot,args.stills)
