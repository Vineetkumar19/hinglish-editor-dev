"""Resume a saved local-Qwen film; repair visibility without redesigning it."""
import base64
from dataclasses import asdict
from fractions import Fraction
from html import escape
import hashlib
import json
import os
from pathlib import Path


def contrast(a,b):
    def lum(c):
        rgb=[int(c[i:i+2],16)/255 for i in (1,3,5)];v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
        return sum(x*w for x,w in zip(v,(.2126,.7152,.0722)))
    x,y=sorted((lum(a),lum(b)));return (y+.05)/(x+.05)


def run(root,source,progress=print):
    from .reference_composer import ask,save,obj,arr
    from .comparison import timed_lines
    from .native_engines import NativeSceneRenderer
    from .pipeline import render_scenes,finish,PROJECT
    from .settings import MotionSettings
    from hinglish_visuals.brain import open_brain
    root=Path(root).resolve();source=Path(source).resolve()
    if not source.is_relative_to(root/'output/motion') or not (source/'shared-graphs.json').is_file():raise ValueError('Object motion invalid: select the saved object film.')
    folder=source/'visible-graphics';folder.mkdir(exist_ok=True)
    raw=json.loads((source/'local-object-plan.json').read_text('utf-8'));original=json.loads((source/'shared-graphs.json').read_text('utf-8'))
    sections=json.loads((source/'script.json').read_text('utf-8'));lines=timed_lines(sections,50)
    os.environ['STORYLENS_REFERENCE_FEATURE']='motion_original'
    palette_file=folder/'local-visibility-colours.json'
    if palette_file.is_file():colours=json.loads(palette_file.read_text('utf-8'))['answer']['accents']
    else:
        brain=open_brain(root,'ollama',progress=progress);brain.cache_enabled=False
        try:
            progress('Local Qwen correcting only its invisible graphic colours')
            result=ask(brain,folder,'local-visibility-colours','Your saved motion graphics are rendered, but your SVG accents are identical to the backgrounds and therefore invisible. Choose a high-contrast readable accent for each scene, contrast ratio at least 4.5. Return ONLY six #RRGGBB colours in order. Do not change objects, positions, animation or script.',{'scenes':[{'background':s['background'],'old_accent':s['accent'],'script':sections[i]['spoken']} for i,s in enumerate(raw['answer']['scenes'])]},obj({'accents':arr({'type':'string','pattern':'^#[0-9a-fA-F]{6}$'},6,6)}),250,think=False)
            colours=result['accents']
        finally:brain.close()
    scenes=json.loads(json.dumps(original['scenes']));repairs=[]
    for i,(scene,author) in enumerate(zip(scenes,raw['answer']['scenes'])):
        old,new=author['accent'],colours[i]
        if contrast(new,author['background'])<4.5:raise ValueError('Object motion invalid: Qwen’s visibility colour still lacks readable contrast. Saved plan is preserved.')
        if contrast(old,author['background'])>=4.5:continue
        for n in scene['data']['graph']['nodes']:
            if n.get('src','').startswith('data:image/svg+xml;base64,'):
                svg=base64.b64decode(n['src'].split(',',1)[1]).decode('utf-8');n['src']='data:image/svg+xml;base64,'+base64.b64encode(svg.replace(old,new).encode()).decode()
        repairs.append({'scene':i+1,'original_accent':old,'local_model_repaired_accent':new,'contrast':contrast(new,author['background'])})
    # A repair may only change SVG pixels, never model-authored geometry/time.
    for before,after in zip(original['scenes'],scenes):
        for a,b in zip(before['data']['graph']['nodes'],after['data']['graph']['nodes']):
            assert {k:v for k,v in a.items() if k!='src'}=={k:v for k,v in b.items() if k!='src'}
    save(folder/'binding-repair.json',{'source':str(source),'source_plan_sha256':hashlib.sha256((source/'local-object-plan.json').read_bytes()).hexdigest(),'creative_model':raw['model'],'repairs':repairs,'geometry_and_camera_unchanged':True,'new_scene_plan_authored':False})
    save(folder/'shared-graphs.json',{'model':raw['model'],'scenes':scenes,'manual_creative_edits':False})
    audio=None
    if (source/'sound-events.json').is_file() and json.loads((source/'sound-events.json').read_text('utf-8')):
        from hinglish_sound.library import decode
        if (source/'remotion/MOTION_GRAPHICS.mp4').is_file():audio=decode(source/'remotion/MOTION_GRAPHICS.mp4',48000,limit=50)
    results=[]
    for engine in ('remotion','motion-canvas'):
        out=folder/engine;out.mkdir(exist_ok=True)
        settings=MotionSettings(engine=engine,style='theme:studio',aspect='9:16',quality='preview',mode='full',coverage='full')
        project={'version':3,'tool':'Motion Graphics','settings':asdict(settings),'style':'theme:studio','style_name':'Qwen object film','theme':{},'speed':1,'width':360,'height':640,'fps':'30','seconds':50,'scenes':json.loads(json.dumps(scenes)),'full':True,'lines':[{'id':l.id,'start':l.start,'end':l.end,'text':l.text} for l in lines],'timeline':None,'model':raw['model']}
        save(out/PROJECT,project);renderer=NativeSceneRenderer(360,640,engine)
        progress(engine+': rendering the saved object/camera plan with Qwen’s visible colours')
        try:render_scenes(renderer,out,project,progress=progress);finish(out,project,renderer,audio=audio,progress=progress)
        finally:renderer.close()
        import av
        with av.open(str(out/'MOTION_GRAPHICS.mp4')) as c:count=sum(1 for _ in c.decode(video=0))
        if count!=1500:raise ValueError('Object motion invalid: the result is not 50 seconds.')
        results.append({'engine':engine,'frames':count,'seconds':50,'video':str(out/'MOTION_GRAPHICS.mp4')});save(folder/'receipt.json',{'model':raw['model'],'same_graphs':True,'results':results,'visual_approval':False,'colour_repair_by_local_model':True})
    page=folder/'report.html';page.write_text('<!doctype html><meta charset="utf-8"><title>Qwen object motion</title><style>body{background:#101318;color:white;font:16px system-ui;margin:24px}main{display:flex;gap:24px}video{height:75vh;max-width:44vw}</style><h1>Local Qwen · objects, images and camera tracks</h1><p>Two 50-second native drafts. The owner reviews design quality.</p><main>'+''.join('<section><h2>'+escape(r['engine'])+'</h2><video controls src="'+r['engine']+'/MOTION_GRAPHICS.mp4"></video></section>' for r in results)+'</main>','utf-8')
    return page
