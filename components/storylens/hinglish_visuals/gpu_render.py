"""CUDA full-frame visuals. Static font/assets are still prepared once on CPU."""
from fractions import Fraction
import numpy as np
from hinglish_cut.gpu_frames import with_cuda_frames,zoom_box


def compose(gpu,image,width,height,anchor_y=.5):
    from .render import similar_shape
    pixels=gpu.upload(np.asarray(image.convert('RGBA')))
    sh,sw=pixels.shape[-2:]
    if similar_shape(sw,sh,width,height):
        flat=pixels[:,:3]*(pixels[:,3:4]/255)
        scale=max(width/sw,height/sh)
        fw,fh=max(width,round(sw*scale)),max(height,round(sh*scale))
        flat=gpu.resize(flat,fw,fh,'bicubic')
        x,y=(fw-width)//2,min(fh-height,max(0,round((fh-height)*anchor_y)))
        return flat[...,y:y+height,x:x+width]
    small=gpu.fit(pixels[:,:3],max(8,width//12),max(8,height//12),fill=True)
    # For tiny test canvases use a bounded Gaussian radius.
    sigma=min(3.,(min(small.shape[-2:])-1)/4)
    canvas=gpu.resize(gpu.blur(small,sigma),width,height,'bicubic')*.5
    margin=round(min(width,height)*.04)
    scale=min((width-2*margin)/sw,(height-2*margin)/sh)
    fw,fh=max(1,round(sw*scale)),max(1,round(sh*scale))
    front=pixels  # over() resizes premultiplied RGBA, avoiding dark alpha edges.
    x,y=(width-fw)//2,(height-fh)//2
    shadow=gpu.torch.zeros((1,1,height,width),device='cuda')
    sy=y+margin//3
    shadow[...,sy:min(height,sy+fh),x:x+fw]=150/255
    canvas*=1-gpu.blur(shadow,max(.5,margin/2)).clamp(0,1)
    canvas[...,y:y+fh,x:x+fw]=gpu.over(canvas[...,y:y+fh,x:x+fw],front)
    return canvas


@with_cuda_frames
def still(image_path,seconds,width,height,fps,target,device='cuda',_gpu=None):
    from .render import load_picture,_frames,PUSH,ease_sine
    from hinglish_shorts.render import _Video
    count=_frames(seconds,fps)
    base=compose(_gpu,load_picture(image_path),round(width*PUSH),round(height*PUSH),.4)
    writer=_Video(target,width,height,fps,'h264_nvenc')
    try:
        for i in range(count):
            scale=1+(PUSH-1)*ease_sine(i/max(1,count-1))
            frame=_gpu.crop(base,zoom_box(base.shape[-1],base.shape[-2],scale),width,height)
            writer.write_gpu(frame,_gpu)
        return writer.finish()
    except BaseException:writer.abort();raise


@with_cuda_frames
def video(source,offset,seconds,width,height,fps,target,device='cuda',_gpu=None):
    from .render import _frames,ease_sine
    from hinglish_shorts.render import _Video
    from hinglish_zoom.preview import Reader
    count=_frames(seconds,fps);reader=Reader(source,offset)
    writer=None
    try:
        writer=_Video(target,width,height,Fraction(fps),'h264_nvenc')
        for i in range(count):
            image=reader.frame_at(offset+i/float(fps))
            if image is None:raise RuntimeError('The GPU visual has no readable source frame. Saved project is kept.')
            base=compose(_gpu,image,width,height)
            scale=1+.035*ease_sine(i/max(1,count-1))
            writer.write_gpu(_gpu.crop(base,zoom_box(width,height,scale),width,height,'bicubic'),_gpu)
        return writer.finish()
    except BaseException:
        if writer is not None:writer.abort()
        raise
    finally:reader.close()
