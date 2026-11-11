"""Render a saved caption composition through Hyperframes' deterministic seek API."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import time


def build(project_folder,settings,require_gpu=False):
    output=project_folder/'hyperframes';output.mkdir(exist_ok=True)
    project=json.loads((project_folder/'caption-project.json').read_text('utf-8'))
    width,height=project['width']//2,project['height']//2
    text=(project_folder/'report.html').read_text('utf-8')
    # The report bundles its fonts and all seven style renderers. Reuse their
    # real text drawing, not a video/PNG pretending to be a new animation.
    text=re.sub(r'<script\s+src="[^"]+"[^>]*>\s*</script>','',text)
    # A real <video> makes Hyperframes wait for media seek events, while this
    # composition needs only a deterministic caption clock. Keep the editor's
    # element API with a non-media clock so there is no second playback clock.
    clock=f'''<div id="video"></div><script>
const hfVideo=document.getElementById('video');
hfVideo.currentTime=0;hfVideo.duration={settings['duration']};hfVideo.paused=true;
hfVideo.readyState=4;hfVideo.videoWidth={width};hfVideo.videoHeight={height};
hfVideo.pause=()=>{{hfVideo.paused=true;}};hfVideo.play=()=>Promise.resolve();
</script>'''
    text=re.sub(r'<video id="video"[^>]*>\s*</video>',lambda _:clock,text)
    feedback=(Path(__file__).parents[1]/'hinglish_app/static/feedback.js').read_text('utf-8')
    text=text.replace('</head>','<script>'+feedback+'</script></head>')
    text=text.replace('requestAnimationFrame(studioPlayback)','void 0')
    text=text.replace('<main class="app">',f'<main class="app" id="hf-caption-root" data-composition-id="main" data-no-timeline data-start="0" data-duration="{settings["duration"]}" data-width="{width}" data-height="{height}" data-fps="30">')
    text=text.replace('<div id="stage" class="stage">',f'<div id="stage" class="stage clip" data-start="0" data-duration="{settings["duration"]}" data-track-index="1" data-track-kind="captions">')
    css=f'''<style>
html,body{{margin:0!important;width:{width}px!important;height:{height}px!important;overflow:hidden!important;background:#000!important}}
body>header,body>footer,.app>:not(.preview),#captionSelection,.studio-floating-controls{{display:none!important}}
.app{{display:block!important;position:absolute!important;inset:0!important;padding:0!important;margin:0!important;width:100%!important;height:100%!important}}
.preview{{position:absolute!important;inset:0!important;width:100%!important;height:100%!important;max-height:none!important;border:0!important;border-radius:0!important;background:black!important}}
#stage{{position:absolute!important;inset:0!important;width:100%!important;height:100%!important;max-width:none!important;aspect-ratio:auto!important;background:black!important}}
#video{{visibility:hidden!important}}#captionSelection{{visibility:hidden!important}}
</style>'''
    # Hyperframes emits the target time for every output frame. No playback or
    # real-time clock is involved, and complete-row positions remain fixed.
    driver='''<script>
let hfCaptionTime=0;
Object.defineProperty(video,'currentTime',{configurable:true,get:()=>hfCaptionTime,set:t=>{hfCaptionTime=Number(t)||0}});
video.pause();
window.__hf=window.__hf||{};window.__hf.buildReady=window.__hf.buildReady||{};
const hfCaptionReady=document.fonts.ready.then(()=>{draw();});
window.__hf.buildReady.captions=hfCaptionReady;
window.addEventListener('hf-seek',event=>{
 hfCaptionTime=Math.max(0,Math.min(studioDuration-.0001,Number(event.detail.time)||0));
 event.detail.waitUntil(hfCaptionReady.then(()=>{draw();}));
});
</script>'''
    text=text.replace('</head>',css+'</head>').replace('</body>',driver+'</body>')
    if require_gpu:
        from hinglish_cut.browser_gpu import ready_guard
        text=ready_guard(text)
    (output/'index.html').write_text(text,'utf-8')
    shutil.copyfile(project_folder/'source.mp4',output/'source.mp4')
    (output/'script.txt').write_text(settings['text'],'utf-8')
    return output


def render(root,project_folder,settings,job_folder,progress):
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(root):
        return _render(root,project_folder,settings,job_folder,progress)


def _render(root,project_folder,settings,job_folder,progress):
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.compute_policy import hyperframes_flags
    from hinglish_cut.compute_policy import heavy_device
    root=Path(root);runtime=root/'tools/hyperframes-runtime/node_modules'
    node=Path('C:/Program Files/nodejs/node.exe');cli=runtime/'hyperframes/bin/hyperframes.mjs'
    chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
    ffprobe=runtime/'@ffprobe-installer/win32-x64/ffprobe.exe'
    if not all(p.is_file() for p in (node,cli,chrome,ffprobe)):
        raise RuntimeError('Hyperframes preview tools are missing. Choose Local LLM + Vision or restore the local Hyperframes installation.')
    project=build(project_folder,settings,require_gpu=heavy_device(root)=='cuda')
    env=dict(os.environ,HYPERFRAMES_NO_TELEMETRY='1',HYPERFRAMES_BROWSER_PATH=str(chrome),
             HYPERFRAMES_FFMPEG_PATH=get_ffmpeg_exe(),HYPERFRAMES_FFPROBE_PATH=str(ffprobe))
    progress('Hyperframes is rendering your saved caption patterns…')
    log_file=job_folder/'hyperframes-render.log';confirmed=False
    with log_file.open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(node),str(cli),'render',str(project),'--output',str(project_folder/'caption-preview.mp4'),
            '--fps','30','--workers','1','--quality','draft',*hyperframes_flags(heavy_device(root)),'--json'],env=env,cwd=root,
            stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+900
        try:
            while process.poll() is None:
                evidence=log_file.read_text('utf-8',errors='replace')
                confirmed='artifact validated' in evidence and 'Render complete' in evidence
                if confirmed:
                    # Some CLI versions keep a watcher alive after the final
                    # verified render receipt. Reap only this owned process tree.
                    try:process.wait(timeout=3)
                    except subprocess.TimeoutExpired:break
                elif time.monotonic()>deadline:raise RuntimeError('Hyperframes could not render within fifteen minutes. Keep the project and retry a shorter preview.')
                else:time.sleep(1)
        finally:
            if process.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                else:process.terminate()
                process.wait(timeout=20)
    if process.returncode and not confirmed:raise RuntimeError('Hyperframes could not render this preview. Technical details: '+log_file.read_text('utf-8')[-2500:])
    import av
    with av.open(str(project_folder/'caption-preview.mp4')) as container:
        stream=container.streams.video[0]
        if not stream.frames or abs(float(container.duration/1e6)-settings['duration'])>.15:
            raise RuntimeError('Hyperframes returned an incomplete preview. Keep your script and retry.')
    return {'engine':'Hyperframes','version':json.loads((runtime/'hyperframes/package.json').read_text('utf-8'))['version'],
            'composition':str(project),'fresh_local_model_inference':False,'clock':'hf-seek'}
