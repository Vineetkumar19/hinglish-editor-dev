"""Bounded web-video downloads with an explicitly discoverable bundled ffmpeg."""
import hashlib
import os
from pathlib import Path
import shutil
import time


def _fetch_worker(root,item,need,result):
    try:result.put((True,str(_download(root,item,need))))
    except Exception as error:result.put((False,str(error)[:2000]))


def download(root,item,need):
    """Keep network tools bounded in their own process, including FFmpeg children."""
    import multiprocessing
    import queue
    from .recovery import read_json,write_json
    failed=Path(root)/'cache/broll/unavailable'/(hashlib.sha256(item.download_url.encode()).hexdigest()+'.json')
    previous=read_json(failed,{})
    if previous and time.time()-previous.get('time',0)<600:
        raise ValueError('This video source recently failed. Continuing with other candidates.')
    context=multiprocessing.get_context('spawn')
    result=context.Queue(maxsize=1)
    worker=context.Process(target=_fetch_worker,args=(str(root),item,need,result),daemon=True)
    worker.start()
    try:
        try:ok,value=result.get(timeout=75)
        except queue.Empty:
            # A bounded per-source timeout is a reason to move on, not to
            # spend another 75 seconds immediately retrying the same source.
            raise ValueError('This B-roll source did not respond within 75 seconds. Continuing with other candidates.') from None
        if not ok:raise ValueError(value)
        failed.unlink(missing_ok=True)
        return Path(value)
    except Exception as error:
        from hinglish_app.user_messages import diagnostics
        try:write_json(failed,{'time':time.time(),'details':diagnostics(error)})
        except OSError:pass
        raise
    finally:
        worker.join(timeout=1)
        if worker.is_alive():
            # This process was created above solely for this download. Its
            # descendants are downloader helpers, never shared model services.
            import psutil
            try:
                process=psutil.Process(worker.pid)
                children=process.children(recursive=True)
                for child in reversed(children):
                    try:child.kill()
                    except psutil.NoSuchProcess:pass
            except psutil.NoSuchProcess:pass
            worker.kill();worker.join(timeout=3)
        result.close()


def _download(root,item,need):
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import download_range_func
    from hinglish_visuals.websearch import _not_live
    import imageio_ffmpeg
    root=Path(root)
    # yt-dlp discovers ffmpeg by its standard executable name. The imageio
    # wheel's versioned executable name can fail that discovery on Windows.
    tools=root/'tools/broll-ffmpeg';tools.mkdir(parents=True,exist_ok=True)
    bundled=Path(imageio_ffmpeg.get_ffmpeg_exe())
    ffmpeg=tools/('ffmpeg.exe' if bundled.suffix.lower()=='.exe' else 'ffmpeg')
    if not ffmpeg.exists() or ffmpeg.stat().st_size!=bundled.stat().st_size:
        shutil.copy2(bundled,ffmpeg)
    start=0.
    if item.duration>150:start=max(3.,min(item.duration*.12,item.duration-55))
    end=start+max(50.,need+10)
    if item.duration>0:end=min(end,item.duration)
    key=hashlib.sha1(f'v3|{item.download_url}|{start}|{end}'.encode()).hexdigest()[:20]
    folder=root/'cache/broll/web-video';folder.mkdir(parents=True,exist_ok=True)
    def completed():
        from .library import probe_video
        ready=[]
        for p in folder.glob(key+'.*'):
            if p.suffix.lower() not in ('.mp4','.webm','.mkv','.mov'):continue
            try:info=probe_video(p)
            except Exception:info=None
            if info and info[0]>=need:ready.append(p)
            else:p.unlink(missing_ok=True)
        return ready
    ready=completed()
    if ready:return ready[0]
    options={'format':'bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b[height<=1080]/b',
             'outtmpl':str(folder/(key+'.%(ext)s')),'quiet':True,'no_warnings':True,
             'noplaylist':True,'retries':1,'socket_timeout':20,'noprogress':True,
             'fragment_retries':1,'external_downloader_args':{'ffmpeg_i':['-rw_timeout','15000000']},
             'max_filesize':400*1024*1024,'match_filter':_not_live,
             'ffmpeg_location':str(ffmpeg.resolve()),'download_ranges':download_range_func(None,[(start,end)])}
    # This installed yt-dlp also checks FFmpegFD.available() without forwarding
    # ffmpeg_location. Make the bundled executable discoverable for that check.
    previous_path=os.environ.get('PATH','')
    os.environ['PATH']=str(tools.resolve())+os.pathsep+previous_path
    try:
        with YoutubeDL(options) as ydl:
            info=ydl.extract_info(item.download_url,download=False) or {}
            if info.get('live_status')=='was_live':
                raise ValueError('This archived live stream cannot provide a reliable short B-roll download. Choose another clip.')
            actual=float(info.get('duration') or 0)
            if actual>1800:
                raise ValueError('This source is over 30 minutes long. Trying a shorter B-roll video to keep the preview responsive.')
            # Search-engine duration metadata can be wrong. Never seek past the
            # actual end and accept an empty MP4 container as a downloaded clip.
            if actual:
                start=max(0.,min(start,actual-need))
                end=min(actual,start+max(50.,need+10))
            ydl.params['download_ranges']=download_range_func(None,[(start,end)])
            ydl.download([item.download_url])
    finally:
        os.environ['PATH']=previous_path
    ready=completed()
    if not ready:raise ValueError('This web clip could not be downloaded. Choose another suggested clip.')
    return ready[0]
