"""Native Remotion / Motion Canvas adapters for the existing typed scene plans.

The model still owns the content/recipe. Each selected engine owns its frame
clock. No Hyperframes render is used as a substitute for a native engine.
"""
import base64
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import math
import mimetypes
from hinglish_cut.compute_policy import h264_profile,ffmpeg_h264
from hinglish_cut.model_preferences import preferred_device
from pathlib import Path
import subprocess
import tempfile
import threading

from PIL import Image, ImageFont
from .engines import ROOT, RUNTIME, ENGINES, NATIVE_TEMPLATES, ensure_engine

FONT=ROOT/'hinglish_motion/web/fonts/Inter-Bold.ttf'


def _fit(text, width, height, size):
    """Fit full text with the bundled font, rather than truncating input words."""
    for pixels in range(round(size), max(10, round(size*.45)), -1):
        font=ImageFont.truetype(str(FONT),pixels);lines=[];line=''
        for word in str(text).split():
            test=(line+' '+word).strip()
            if line and font.getlength(test)>width:lines.append(line);line=word
            else:line=test
        if line:lines.append(line)
        if all(font.getlength(t)<=width for t in lines) and len(lines)*pixels*1.12<=height:
            return '\n'.join(lines),pixels
    raise ValueError('Motion engine layout invalid: text does not fit its saved box. Shorten this scene or split it before rendering.')


def scene_graph(scene,width,height,fps):
    if scene.get('template')=='object_motion':
        graph=json.loads(json.dumps(scene['data']['graph']))
        if graph['width']!=width or graph['height']!=height:raise ValueError('Motion engine layout invalid: object graph canvas size changed.')
        graph.update(fps=float(fps),duration=float(scene['duration']))
        return graph
    caption=scene.get('data',{}).get('source_caption')
    if caption:
        child={**scene,'data':{k:v for k,v in scene['data'].items() if k!='source_caption'}}
        graph=scene_graph(child,width,round(height*.76),fps);graph['height']=height
        words,size=_fit(caption,width*.86,height*.18,min(width,height)*.045)
        graph['nodes'].append({'id':'source-caption','kind':'text','x':width*.07,'y':height*.79,'w':width*.86,'h':height*.18,'fill':'#ffffff' if graph['background']!='#ffffff' else '#101318','text':words,'fontSize':size,'keys':[{'t':t,'x':0,'y':0,'scale':1,'rotation':0,'opacity':1} for t in (0,1)]})
        return graph
    template=scene.get('template')
    if template not in NATIVE_TEMPLATES:
        raise ValueError(f'Motion engine style unavailable: {template} needs its original Hyperframes renderer. Choose a supported studio style.')
    d=scene.get('data',{});duration=float(scene.get('duration',0))
    if not math.isfinite(duration) or duration<=0:raise ValueError('Motion engine layout invalid: a positive scene duration is required.')
    theme=scene.get('theme',{});theme=theme if isinstance(theme,dict) else {}
    bg=theme.get('--bg','#101318');accent=theme.get('--accent','#66d9c1')
    try:rgb=tuple(int(bg[i:i+2],16) for i in (1,3,5))
    except (ValueError,TypeError):bg='#101318';rgb=(16,19,24)
    ink='#101318' if sum(rgb)>450 else '#f7f7f4';nodes=[]
    graph={'width':width,'height':height,'fps':float(fps),'duration':duration,'background':bg,'nodes':nodes}
    def pose(t,x=0,y=0,scale=1,rotation=0,opacity=1):return dict(t=t,x=x,y=y,scale=scale,rotation=rotation,opacity=opacity)
    def add(id,kind,x,y,w,h,fill=ink,**extra):
        node=dict(id=id,kind=kind,x=x,y=y,w=w,h=h,fill=fill,keys=[pose(0),pose(1)],**extra);nodes.append(node);return node
    def text(id,value,x,y,w,h,size,color=ink,parent=''):
        if not value:return
        value,font=_fit(str(value),w,h,size)
        return add(id,'text',x,y,w,h,color,text=value,fontSize=font,parent=parent)
    def entrance(n,delay=0):
        if n is None:return
        at=min(.3,max(.08,.55/duration));motion=d.get('motion','rise')
        start=pose(0,y=height*.045,opacity=0)
        if motion=='slide-left':start=pose(0,x=width*.16,opacity=0)
        elif motion=='slide-right':start=pose(0,x=-width*.16,opacity=0)
        elif motion=='push':start=pose(0,scale=.8,opacity=0)
        n['keys']=[start,pose(min(.85,at+delay)),pose(1,y=-height*.025 if motion=='float' else 0)]
    if template=='element_motion':
        s=d['scene'];graph['background']=s['background'];specs={o['id']:o for o in s['objects']};sizes={}
        region=add('graphic-region','rect',width*.05,height*.08,width*.9,height*.65,'transparent')
        def make(o):
            if o['id'] in sizes:return
            parent=o.get('parent')
            if parent:make(specs[parent]);pw,ph=sizes[parent]
            else:pw,ph=region['w'],region['h'];parent=region['id']
            w,h=o['w']*pw,o['h']*ph;sizes[o['id']]=(w,h)
            n=add(o['id'],o['kind'],0,0,w,h,'transparent' if o['kind']=='frame' else o['fill'],parent=parent,stroke=o['stroke'],strokeWidth=o['stroke_width'],radius=o['radius']*pw,clip=o['clip'])
            n['keys']=[pose(k['t'],k['x']*pw,k['y']*ph,k['scale'],k['rotation'],k['opacity']) for k in o['keys']]
            if o.get('label'):text(o['id']+'-label',o['label'],w*.07,h*.07,w*.86,h*.86,min(width*.04,w*.16,h*.27),o['stroke'],o['id'])
        for o in s['objects']:make(o)
        text('source-caption',s['caption'],width*.08,height*.8,width*.84,height*.15,width*.045)
        return graph
    title=d.get('title') or d.get('value') or '';label=d.get('label') or ''
    portrait=height>width;short=min(width,height)
    if template in ('asset_hero','product_card'):
        assets=d.get('assets') or scene.get('assets') or []
        if template=='asset_hero' and not assets:raise ValueError('Motion engine asset unavailable: this scene requires its downloaded image.')
        for i,a in enumerate(assets[:2]):
            src=a.get('src') or a.get('file')
            if not src:raise ValueError('Motion engine asset unavailable: the chosen image is missing.')
            file=Path(src)
            if str(src).startswith('file:'):
                from urllib.parse import urlparse,unquote
                file=Path(unquote(urlparse(src).path).lstrip('/'))
            if not file.is_file():raise ValueError('Motion engine asset unavailable: restore the saved local image before retrying.')
            mime=mimetypes.guess_type(file.name)[0] or 'image/png';url='data:'+mime+';base64,'+base64.b64encode(file.read_bytes()).decode()
            n=add('asset-'+str(i),'image',width*(.12+i*.36 if len(assets)>1 else .16),height*.13,width*(.38 if len(assets)>1 else .68),height*.43,src=url)
            entrance(n,i*.04)
        top=.61 if assets else .32
        entrance(text('title',title,width*.08,height*top,width*.84,height*.15,short*.083,accent))
        text('label',label,width*.09,height*(top+.17),width*.82,height*.12,short*.042)
    elif template=='explainer_steps':
        text('title',title,width*.08,height*.08,width*.84,height*.16,short*.07,accent)
        items=d.get('items') or []
        for i,value in enumerate(items[:4]):
            y=height*(.3+i*.145);card=add('step-'+str(i),'rect',width*.1,y,width*.8,height*.12,'#24303c',radius=short*.02)
            entrance(card,i*.05);text('step-text-'+str(i),str(value),width*.04,height*.01,width*.72,height*.1,short*.043,'#ffffff',card['id'])
    else:
        main=d.get('value') if template=='motion_number' else title
        n=text('main',main,width*.07,height*.29,width*.86,height*.3,short*(.16 if template=='motion_number' else .11),accent)
        if n:entrance(n)
        text('support',label,width*.1,height*.63,width*.8,height*.14,short*.048)
    # A failed empty plan must not become a successful blank video.
    if not nodes:raise ValueError('Motion engine layout invalid: no drawable scene content was planned.')
    return graph


class NativeSceneRenderer:
    def __init__(self,width,height,engine,device='cpu'):
        self.device=device
        ensure_engine(engine);self.width,self.height,self.engine=width,height,engine;self.name=ENGINES[engine];self._files={};self._scene=None
    def _graph(self,scene,fps=30):return scene_graph(scene,self.width,self.height,fps)
    def load(self,scene):self._scene=scene
    def check(self,scene):self._graph(scene);return []
    def sound_events(self):return []
    def _key(self,scene):return hashlib.sha256(json.dumps(scene,sort_keys=True).encode()).hexdigest()
    def render(self,scene,target,fps,progress=None):
        target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
        if scene.get('mode')=='overlay':raise ValueError('Motion engine format unavailable: Remotion and Motion Canvas currently export full-screen MP4. Select All full screen or Hyperframes for transparent overlays.')
        graph=self._graph(scene,fps);source=target.with_suffix('.scene.json');source.write_text(json.dumps(graph),'utf-8')
        if self.engine=='remotion':
            self._command(['render','remotion',str(source.resolve()),str(target.resolve()),self.device])
        else:self._motion_canvas(graph,target)
        self._files[self._key(scene)]=target
        target.with_suffix('.engine.json').write_text(json.dumps({'engine':self.engine,'native':True,'hyperframes_fallback':False,'scene':source.name,'visual_approval':False},indent=2),'utf-8')
        return target
    @staticmethod
    def _command(args):
        result=subprocess.run(['C:/Program Files/nodejs/node.exe',str(RUNTIME/'build.cjs'),*args],cwd=RUNTIME,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1200)
        if result.returncode:raise RuntimeError('Motion engine render stopped: '+(result.stderr or result.stdout)[-2500:])
    def _motion_canvas(self,graph,target):
        from playwright.sync_api import sync_playwright
        from imageio_ffmpeg import get_ffmpeg_exe
        folder=RUNTIME/'dist/motion-canvas'
        if not (folder/'index.html').is_file():raise ValueError('Motion engine unavailable: build the Motion Canvas runtime before rendering.')
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(folder)));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        images=target.with_suffix('.frames');images.mkdir(exist_ok=True);received=set()
        def receive(data,frame):
            index=int(frame);(images/f'{index:06d}.png').write_bytes(base64.b64decode(data));received.add(index)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='chrome',headless=True,args=['--enable-gpu','--enable-gpu-rasterization','--disable-software-rasterizer'] if self.device=='cuda' else ['--disable-gpu']);page=browser.new_page()
                try:
                    if self.device=='cuda':
                        from hinglish_cut.browser_gpu import require_browser_gpu
                        require_browser_gpu(page)
                    page.expose_function('storylensFrame',receive)
                    page.add_init_script('window.__storylensInput='+json.dumps(graph).replace('<','\\u003c'))
                    page.goto(f'http://127.0.0.1:{server.server_port}/');page.wait_for_function('typeof window.storylensRender === "function"',timeout=60000)
                    page.evaluate('window.storylensRender()')
                finally:browser.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
        count=max(1,round(graph['duration']*graph['fps']))
        if not set(range(count)).issubset(received):raise RuntimeError('Motion engine render stopped: Motion Canvas did not export every expected frame. Saved PNG frames are retained.')
        result=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-framerate',str(graph['fps']),'-i',str(images/'%06d.png'),'-frames:v',str(count),*ffmpeg_h264(self.device,18),'-pix_fmt','yuv420p','-movflags','+faststart',str(target)],capture_output=True,timeout=600)
        if result.returncode:raise RuntimeError('Motion engine render stopped: '+result.stderr.decode(errors='replace')[-1000:])
    def frame(self,seconds,alpha=False):
        import av,numpy as np
        path=self._files.get(self._key(self._scene))
        if not path:raise RuntimeError('Motion engine render stopped: the saved scene must render before its preview can be read.')
        with av.open(str(path)) as c:
            last=None
            for f in c.decode(video=0):
                last=f
                if (f.time or 0)>=seconds:break
            if last is None:raise RuntimeError('Motion engine render stopped: the saved scene has no video frames.')
            return last.to_ndarray(format='rgba' if alpha else 'rgb24')
    def still(self,scene,seconds,target):self.load(scene);Image.fromarray(self.frame(seconds)).save(target);return Path(target)
    def close(self):pass
