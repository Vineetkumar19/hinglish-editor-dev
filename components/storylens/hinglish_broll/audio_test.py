"""An explicit owner-requested audio-only B-roll test, retaining the source on disk."""
from pathlib import Path
import subprocess


def black_video(source, target, max_side=480):
    import av
    import imageio_ffmpeg
    with av.open(str(source)) as container:
        if not container.streams.audio:
            raise ValueError('This video has no audio. Choose a video with speech for the B-roll test.')
        duration=float(container.duration)/1_000_000
        stream=container.streams.video[0]
        width,height=stream.width,stream.height
    # Small test canvas to keep memory low; the real source is never altered.
    factor=min(1.,max_side/max(width,height)) if max_side else 1.
    width,height=max(2,round(width*factor/2)*2),max(2,round(height*factor/2)*2)
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    partial=target.with_name(target.stem+'.partial.mp4')
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y',
             '-f','lavfi','-i',f'color=c=black:s={width}x{height}:r=30',
             '-i',str(source),'-map','0:v:0','-map','1:a:0','-t',str(duration),
             '-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',
             '-movflags','+faststart',str(partial)]
    try:
        subprocess.run(command,check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        partial.replace(target)
        return target
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
