"""Burn the editable caption overlay into an MP4, preserving source audio."""
from pathlib import Path
import subprocess
from hinglish_cut.gpu_frames import with_cuda_frames


@with_cuda_frames
def _gpu_composite(source,overlay,target,device='cuda',_gpu=None):
    import av,numpy as np
    from fractions import Fraction
    from hinglish_zoom.preview import Reader
    from hinglish_shorts.render import _Video
    with av.open(str(overlay)) as movie:
        stream=movie.streams.video[0];w,h=stream.width,stream.height
        fps=Fraction(stream.average_rate)
        duration=float(stream.duration*stream.time_base) if stream.duration is not None else float(movie.duration/av.time_base)
    raw=alpha=writer=None
    try:
        raw=Reader(source);alpha=Reader(overlay)
        writer=_Video(target,w,h,fps,'h264_nvenc')
        for i in range(round(duration*float(fps))):
            image=raw.frame_at(i/float(fps));caption=alpha.frame_at(i/float(fps))
            if image is None or caption is None:raise RuntimeError('The GPU caption composite has no readable source frame. Saved captions are kept.')
            base=_gpu.fit(_gpu.upload(np.asarray(image.convert('RGB'))),w,h)
            writer.write_gpu(_gpu.over(base,_gpu.upload(np.asarray(caption.convert('RGBA')))),_gpu)
        writer.finish()
    except BaseException:
        if writer is not None:writer.abort()
        raise
    finally:
        if raw is not None:raw.close()
        if alpha is not None:alpha.close()
    return duration


def render_captioned_video(source,overlay,target,device='cuda',demo_background=None):
    from imageio_ffmpeg import get_ffmpeg_exe
    target=Path(target);partial=target.with_name(target.stem+'.partial.mp4')
    if device == 'cuda':
        video=target.with_name(target.stem+'.gpu-video.mp4')
        try:
            duration=_gpu_composite(source,overlay,video,device=device)
            done=subprocess.run([get_ffmpeg_exe(),'-nostdin','-hide_banner','-v','error','-y',
                '-i',str(video),'-i',str(source),'-map','0:v:0','-map','1:a:0','-t',str(duration),
                '-c:v','copy','-c:a','copy','-movflags','+faststart',str(partial)],
                capture_output=True,text=True,encoding='utf8',errors='replace')
            if done.returncode:raise RuntimeError('The GPU caption video could not retain its source audio: '+done.stderr[-1500:])
            partial.replace(target)
            return 'h264_nvenc'
        finally:video.unlink(missing_ok=True)
    encoder=['-c:v','h264_nvenc','-preset','p5','-cq','18','-b:v','0'] if device=='cuda' else ['-c:v','libx264','-preset','fast','-crf','18']
    import av
    with av.open(str(overlay)) as movie:
        stream=movie.streams.video[0]
        width,height=stream.width,stream.height
        duration=float(stream.duration*stream.time_base) if stream.duration is not None else float(movie.duration/av.time_base)
    # Keep solid sample backgrounds in video range throughout compositing.
    # An RGB round trip can turn white into grey before H.264 encoding.
    overlay_format='yuv420' if demo_background in ('black','white') else 'auto'
    graph=f'[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[base];[base][1:v]overlay=0:0:format={overlay_format},format=yuv420p[v]'
    done=subprocess.run([get_ffmpeg_exe(),'-nostdin','-hide_banner','-v','error','-y',
        '-i',str(source),'-i',str(overlay),'-filter_complex',graph,
        '-map','[v]','-map','0:a:0','-t',str(duration),*encoder,'-c:a','copy','-movflags','+faststart',str(partial)],
        capture_output=True,text=True,encoding='utf-8',errors='replace')
    if done.returncode:
        raise RuntimeError('The caption video could not be encoded with '+('NVIDIA NVENC' if device=='cuda' else 'H.264')+': '+done.stderr[-1500:])
    partial.replace(target)
    return 'h264_nvenc' if device=='cuda' else 'libx264'
