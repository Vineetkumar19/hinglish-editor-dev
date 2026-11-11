"""Brief light overlays or real-footage cut blends; camera geometry stays fixed."""
from pathlib import Path
import xml.etree.ElementTree as ET

import av
import numpy as np
from PIL import Image,ImageFilter
from defusedxml import ElementTree as SafeET
from hinglish_cut.xml_export import add,rate,premiere_pathurl,video_format_dimensions

FOOTAGE_STYLES=('soft_dissolve','soft_wipe_left','soft_wipe_right')


def transition_frame(outgoing,incoming,progress,kind):
    """Blend the real neighbouring shots with eased, feathered motion."""
    p=float(np.clip(progress,0,1));ease=(1-np.cos(np.pi*p))/2
    if kind=='soft_dissolve':mask=ease
    else:
        width=outgoing.shape[1];edge=.12
        x=np.linspace(0,1,width,dtype=np.float32)[None,:,None]
        if kind=='soft_wipe_left':x=1-x
        boundary=ease*(1+2*edge)-edge
        u=np.clip((boundary-x+edge)/(2*edge),0,1)
        mask=u*u*(3-2*u)
    result=np.rint(outgoing.astype(np.float32)*(1-mask)+incoming.astype(np.float32)*mask).astype(np.uint8)
    # A very small mid-transition softness hides the seam without a whip-pan,
    # secondary zoom or geometric distortion of the speaker.
    if 0<p<1:result=np.asarray(Image.fromarray(result).filter(ImageFilter.GaussianBlur(float(.7*np.sin(np.pi*p)**2))))
    return result


def render_footage(path,source,seq,start,end,cut,kind):
    pixels={}
    with av.open(str(source)) as c:
        stream=c.streams.video[0]
        c.seek(max(0,int((start/float(seq.fps)-1)/stream.time_base)),stream=stream,backward=True)
        for frame in c.decode(stream):
            at=round((frame.time or 0)*float(seq.fps))
            if start<=at<end:
                image=frame.to_image().convert('RGB').resize((seq.width,seq.height),Image.Resampling.BICUBIC)
                pixels[at]=np.asarray(image)
            if at>=end:break
    if any(i not in pixels for i in range(start,end)):
        raise ValueError('The approved video could not supply all frames for a cut transition. Retry this editing step; your source is kept.')
    with av.open(str(path),'w') as out:
        video=out.add_stream('qtrle',rate=seq.fps);video.width,video.height,video.pix_fmt=seq.width,seq.height,'argb'
        for n,at in enumerate(range(start,end)):
            a=pixels[min(at,cut-1)];b=pixels[max(at,cut)]
            rgb=transition_frame(a,b,n/max(1,end-start-1),kind)
            rgba=np.concatenate([rgb,np.full((seq.height,seq.width,1),255,np.uint8)],axis=2)
            f=av.VideoFrame.from_ndarray(rgba,format='rgba');f.pts=n
            for packet in video.encode(f):out.mux(packet)
        for packet in video.encode():out.mux(packet)


def render(path,width,height,fps,frames,kind):
    x=np.linspace(-1,1,width,dtype=np.float32)[None,:]
    y=np.linspace(-1,1,height,dtype=np.float32)[:,None]
    with av.open(str(path),'w') as out:
        stream=out.add_stream('qtrle',rate=fps)
        stream.width,stream.height,stream.pix_fmt=width,height,'argb'
        for f in range(frames):
            p=f/max(1,frames-1)
            envelope=np.sin(np.pi*p)**2
            if kind=='soft_flash':alpha=np.full((height,width),.12*envelope,dtype=np.float32)
            else:
                direction=-1 if kind.endswith('left') else 1
                centre=direction*(p*3-1.5)
                alpha=.22*envelope*np.exp(-((x+.18*y-centre)/.28)**2)
            rgba=np.empty((height,width,4),dtype=np.uint8)
            rgba[:,:,:3]=(255,244,222);rgba[:,:,3]=np.rint(alpha*255).astype(np.uint8)
            frame=av.VideoFrame.from_ndarray(rgba,format='rgba');frame.pts=f
            for packet in stream.encode(frame):out.mux(packet)
        for packet in stream.encode():out.mux(packet)


def add_overlays(xml,folder,seq,events,choices,footage_source=None,device='cpu'):
    if device=='cuda' and any(choice.get('overlay','none')!='none' for choice in choices):
        raise RuntimeError('Transparent transition MOV export has no GPU encoder in this path. CPU fallback is disabled. Keep the saved zoom and disable transition overlays, or use native editable effects.')
    path=Path(folder)/'transitions';path.mkdir(exist_ok=True)
    frames=max(6,round(float(seq.fps)*.3))
    tree=SafeET.parse(xml);root=tree.getroot()
    sequence=root if root.tag=='sequence' else root.find('.//sequence')
    video=sequence.find('./media/video')
    track=None;rows=[];made={}
    for row in choices:
        kind=row['overlay']
        if kind=='none':continue
        cut=round(events[row['event']].start*float(seq.fps))
        if cut<=0:continue
        start=max(0,cut-frames//2);end=min(seq.frames,start+frames)
        footage=kind in FOOTAGE_STYLES
        if footage:
            if not footage_source:raise ValueError('This cut transition needs the approved zoom video. Select that finished video and retry; your source is kept.')
            target=path/f'{kind}-{cut}.mov'
            render_footage(target,footage_source,seq,start,end,cut,kind)
        elif kind not in made:
            made[kind]=path/f'{kind}.mov'
            render(made[kind],seq.width,seq.height,seq.fps,frames,kind)
        if not footage:target=made[kind]
        if track is None:track=add(video,'track')
        n=len(rows)+1
        item=add(track,'clipitem',id=f'zoom-transition-{n}')
        add(item,'name','SmartZoom '+kind.replace('_',' '));add(item,'enabled','TRUE');add(item,'duration',frames)
        rate(item,str(seq.fps))
        for k,v in (('start',start),('end',end),('in',0),('out',end-start)):add(item,k,v)
        file=add(item,'file',id=f'zoom-transition-file-{n}')
        add(file,'name',target.name);add(file,'pathurl',premiere_pathurl(target));rate(file,str(seq.fps));add(file,'duration',frames)
        media=add(file,'media');v=add(media,'video');video_format_dimensions(add(v,'samplecharacteristics'),seq.width,seq.height,str(seq.fps))
        add(item,'alphatype','straight')
        rows.append({'event':row['event'],'kind':kind,'cut':cut/float(seq.fps),
            'start_frame':start,'end_frame':end,'source_in':0,'path':str(target.resolve()),
            'composition':'footage_transition' if footage else 'light_overlay',
            'footage_source':str(footage_source) if footage else None,
            'max_opacity':1.0 if footage else .12 if kind=='soft_flash' else .22})
    ET.indent(root);tree.write(xml,encoding='utf-8',xml_declaration=True)
    return rows
