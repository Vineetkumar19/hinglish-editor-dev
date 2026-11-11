"""AI Video orchestration; models plan, existing bounded renderers create media."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

METHODS=('generative','reference','motion')

def capabilities(root):
    root=Path(root)
    return {'methods':[{'id':'generative','name':'Prompt to video','tools':'Qwen · Z-Image · Wan 2.2'},
                       {'id':'reference','name':'Reference guided','tools':'Agent Reach · ReelMimic · Qwen Vision · Wan 2.2'},
                       {'id':'motion','name':'Motion / 3D','tools':'Qwen · GSAP · Hyperframes · Three.js'}],
            'agent_reach_installed':(root/'tools/agent-reach-runtime/agent_reach').is_dir(),
            'motion_runtime_installed':(root/'tools/hyperframes-runtime/node_modules/hyperframes/bin/hyperframes.mjs').is_file(),
            'limits':['Reference guidance is approximate, not model training or exact recreation.',
                      '3D scenes export as rendered video, not native editable 3D.',
                      'Public YouTube links or local videos; other platforms can require a local download.']}

def analyse_reference(root,value,folder,progress=print):
    root=Path(root).resolve();folder=Path(folder);source=Path(value)
    receipt={'source':value,'tools':[],'weight_training':False}
    if value.startswith(('https://','http://')):
        host=(urlparse(value).hostname or '').lower()
        if urlparse(value).scheme!='https' or host not in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):
            raise ValueError('AI Video reference unsupported: use a public YouTube link or a local video file.')
        runtime=root/'tools/agent-reach-runtime'
        if not (runtime/'agent_reach').is_dir():
            raise RuntimeError('AI Video reference reader unavailable: restore the installed Agent Reach runtime or use a local video.')
        progress('Reading the public reference with Agent Reach; no account login is used.')
        # Public YouTube only. Use the installed read-only backend, never a
        # model-generated shell command or an authenticated browser channel.
        code='import sys,json;sys.path.insert(0,sys.argv[1]);from agent_reach.channels.youtube import YouTubeChannel;print(json.dumps(YouTubeChannel()._ytdlp_read(target=sys.argv[2],timeout=90)))'
        try:
            done=subprocess.run([sys.executable,'-c',code,str(runtime),value],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=100,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if done.returncode:raise RuntimeError(done.stderr[-1200:])
            receipt['metadata']=json.loads(done.stdout);receipt['tools'].append('Agent Reach · public YouTube metadata')
            (folder/'reference-reader.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
            from imageio_ffmpeg import get_ffmpeg_exe
            target=folder/'reference-sample.%(ext)s'
            download=subprocess.run([sys.executable,'-m','yt_dlp','--no-playlist','--no-warnings','--download-sections','*0-10',
                '--max-filesize','100M','--ffmpeg-location',get_ffmpeg_exe(),'-f','best[height<=480][ext=mp4]/best[height<=480]',
                '-o',str(target),value],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if download.returncode:raise RuntimeError(download.stderr[-1200:])
            source=next(folder.glob('reference-sample.*'));receipt['sample_seconds']=10
        except (subprocess.TimeoutExpired,RuntimeError,ValueError,StopIteration) as error:
            receipt['technical_details']=str(error);(folder/'reference-reader.json').write_text(json.dumps(receipt,indent=2),'utf8')
            raise RuntimeError('AI Video reference read failed: the public video could not be read. Use a local reference file; diagnostics are saved with this job.') from error
    if not source.is_file() or source.suffix.lower() not in ('.mp4','.mov','.mkv','.webm','.avi'):
        raise ValueError('AI Video reference missing: choose an existing local video or a public YouTube link.')
    progress('Measuring reference shots, colour and movement, then reading frames with local Vision.')
    from hinglish_cut.reelmimic import learn
    # Both current and older Storylens servers dispatch this feature only
    # inside _run_job's GPU lock. Direct CLI ingestion still acquires its lock.
    held=(os.environ.get('STORYLENS_GPU_LOCK_HELD')==str(root)
          or os.environ.get('STORYLENS_REFERENCE_FEATURE')=='aivideo')
    saved=learn(root,'aivideo',source,select=False,gpu_already_held=held,retry_vision=True)
    profile=json.loads(saved.read_text('utf8'))
    if not profile.get('visual_reading'):
        raise RuntimeError('AI Video reference vision unavailable: frame analysis did not finish. Restore the configured local Vision model and retry; measurements are saved.')
    receipt.update(profile=profile,profile_path=str(saved),tools=receipt['tools']+['ReelMimic','local Qwen Vision'])
    (folder/'reference-analysis.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
    return {'name':profile['name'],'source_sha256':profile['source_sha256'],'measured':profile['measured'],
            'visual_reading':profile['visual_reading'],'receipt':str(folder/'reference-analysis.json'),'weight_training':False}

def motion_script(script):
    """Paginate source sentences without rewriting words or stranding one word."""
    pages=[]
    for line in re.split(r'(?<=[.!?।])\s+|\n+',script):
        words=line.split()
        if not words:continue
        count=math.ceil(len(words)/12)
        size,extra=divmod(len(words),count)
        start=0
        for index in range(count):
            end=start+size+(index<extra)
            pages.append(' '.join(words[start:end]));start=end
    return '\n'.join(pages)


def run_motion(root,input_path,script,settings,progress=print):
    from hinglish_motion.pipeline import run
    from hinglish_motion.settings import MotionSettings
    progress('AI Video · Motion / 3D: planning with local Qwen and rendering GSAP / Hyperframes scenes.')
    render_script=motion_script(script) if not input_path else script
    result=run(root,input_path,render_script,MotionSettings(style='theme:'+settings.motion_style,count=settings.count,
        mode='full',coverage='full',aspect=settings.aspect,brain=settings.brain,check=settings.check,
        quality=settings.quality,assets='web',preserve_script_text=True),progress)
    receipt={'feature':'aivideo','method':'motion','style':settings.motion_style,'quality':settings.quality,
             'script':script,'render_script':render_script,'preserve_script_text':True,
             'tools':['Qwen','GSAP','Hyperframes']+(['Three.js / ThreeUI'] if settings.motion_style in ('orbit','studio') else []),
             'result':str(result),'native_3d_editability':False}
    Path(result).with_name('ai-video-production.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
    return result
