"""GPU-capable render + portable FCP 7 XML. Original footage and music are read-only."""
from pathlib import Path
from fractions import Fraction
import json
import math
import subprocess
from hinglish_cut.compute_policy import ffmpeg_h264
import time
import xml.etree.ElementTree as ET
from hinglish_beats.detect import number
from hinglish_cut.xml_export import add, rate, premiere_pathurl, video_format_dimensions


def render_cuda_shot(plan, shot, target, width, height, fit, effects, amount, cancel, base_source=None):
    """CUDA scaling, framing and beat effects; no software FFmpeg filter chain."""
    import numpy as np
    from hinglish_cut.gpu_frames import CudaFrames, zoom_box
    from hinglish_shorts.render import _Video
    from hinglish_zoom.preview import Reader
    gpu = CudaFrames()
    reader = writer = None
    try:
        fps = Fraction(plan['fps'])
        source_in, speed = (0., 1.) if base_source else (shot['source_in'], shot['speed'])
        reader = Reader(base_source or shot['path'], source_in)
        writer = _Video(target, width, height, fps, 'h264_nvenc')
        events = [(f-shot['start_frame'])/float(fps) for f in plan['beat_frames']
                  if shot['start_frame'] <= f < shot['end_frame']]
        for number in range(shot['duration_frames']):
            if cancel.is_set(): raise RuntimeError('Cinematic reel cancelled')
            t = number/float(fps)
            image = reader.frame_at(source_in+t*speed)
            if image is None: raise RuntimeError('The selected shot contains no readable video frames.')
            if reader.end_reached and source_in+t*speed > reader.last_time+.08+1/float(fps):
                raise RuntimeError('The selected shot ended before its planned beat interval. Saved shots are kept; CPU fallback was not started.')
            pixels = gpu.fit(gpu.upload(np.asarray(image.convert('RGB'))), width, height, fill=fit=='fill')
            envelope = min(1., sum(max(0., 1-abs(t-event)/.14) for event in events))
            zoom = 1+amount/100*envelope if 'punch' in effects else 1.
            dx = dy = 0.
            if 'shake' in effects:
                zoom *= 1.08
                dx, dy = amount/2*math.sin(t*83)*envelope, amount/2*math.cos(t*71)*envelope
            if zoom != 1. or dx or dy:
                pixels = gpu.crop(pixels, zoom_box(width, height, zoom, dx, dy), width, height, 'bicubic')
            if 'flash' in effects: pixels = pixels+255*amount/100*envelope
            writer.write_gpu(pixels,gpu)
        writer.finish()
    except BaseException:
        if writer is not None: writer.abort()
        raise
    finally:
        if reader is not None: reader.close()
        gpu.close()


def run_ffmpeg(args, folder, cancel):
    import imageio_ffmpeg
    if cancel.is_set(): raise RuntimeError('Cinematic reel cancelled')
    log = Path(folder)/'ffmpeg.log'
    with log.open('a',encoding='utf-8') as errors:
        process = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-y',
                                    '-threads','2','-filter_threads','1',*map(str,args)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                   stderr=errors,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline = time.monotonic()+1800
        try:
            while process.poll() is None:
                if cancel.wait(.15) or time.monotonic()>deadline:
                    process.terminate()
                    raise RuntimeError('Cinematic reel cancelled or render timed out')
            if process.returncode:
                raise RuntimeError('Video render failed: '+log.read_text(encoding='utf-8',errors='replace')[-1200:])
        finally:
            if process.poll() is None:
                process.kill();process.wait()


def effect_options(options):
    selected = options.get('effects',[])
    if not isinstance(selected,list) or len(selected)>3 or any(e not in ('punch','flash','shake') for e in selected):
        raise ValueError('Choose Punch zoom, Soft flash or Micro shake')
    return list(dict.fromkeys(selected)), number(options.get('effect_amount',8),'Effect strength',1,20)


def video_filters(plan, shot, width, height, effects, amount):
    fps=float(Fraction(plan['fps']))
    values=[]
    if effects:
        events=[(f-shot['start_frame'])/fps for f in plan['beat_frames'] if shot['start_frame']<=f<shot['end_frame']]
        # These expressions contain only validated numbers, never user-provided code.
        envelope='min(1,'+'+'.join(f'max(0,1-abs(t-{t:.6f})/0.14)' for t in events)+')' if events else '0'
        if 'punch' in effects:
            values += [f"scale=w='ceil(iw*(1+{amount/100:.6f}*({envelope}))/2)*2':h='ceil(ih*(1+{amount/100:.6f}*({envelope}))/2)*2':eval=frame",
                       f'crop={width}:{height}']
        if 'flash' in effects:
            values += [f"eq=brightness='{amount/100:.6f}*({envelope})':eval=frame"]
        if 'shake' in effects:
            values += [f'scale={math.ceil(width*1.08/2)*2}:{math.ceil(height*1.08/2)*2}',
                       f"crop={width}:{height}:x='(in_w-out_w)/2+{amount/2:.4f}*sin(t*83)*({envelope})':y='(in_h-out_h)/2+{amount/2:.4f}*cos(t*71)*({envelope})'"]
    return values


def export_xml(plan, folder, files, music):
    root=ET.Element('xmeml',version='5');seq=add(root,'sequence',id='cinematic-reel')
    add(seq,'name','Storylens Cinematic Reel'+(' - Effects' if plan['effects'] else ''))
    add(seq,'duration',plan['frames']);rate(seq,plan['fps'])
    tc=add(seq,'timecode');rate(tc,plan['fps']);add(tc,'string','00:00:00:00');add(tc,'frame',0);add(tc,'displayformat','NDF')
    for frame in plan['beat_frames']:
        if 0<=frame<plan['frames']:
            marker=add(seq,'marker');add(marker,'name','Music beat');add(marker,'comment','Storylens cinematic music beat');add(marker,'in',frame);add(marker,'out',-1)
    media=add(seq,'media');video=add(media,'video')
    video_format_dimensions(add(add(video,'format'),'samplecharacteristics'),plan['width'],plan['height'],plan['fps'])
    track=add(video,'track')
    for i,(shot,path) in enumerate(zip(plan['shots'],files),1):
        clip=add(track,'clipitem',id=f'shot-{i}');add(clip,'name',f"{shot['name']} | {shot['speed']:g}x")
        add(clip,'enabled','TRUE');rate(clip,plan['fps']);add(clip,'duration',shot['duration_frames'])
        for key,value in (('start',shot['start_frame']),('end',shot['end_frame']),('in',0),('out',shot['duration_frames'])):add(clip,key,value)
        file=add(clip,'file',id=f'shot-file-{i}');add(file,'name',Path(path).name);add(file,'pathurl',premiere_pathurl(path))
        rate(file,plan['fps']);add(file,'duration',shot['duration_frames'])
        video_format_dimensions(add(add(add(file,'media'),'video'),'samplecharacteristics'),plan['width'],plan['height'],plan['fps'])
    audio=add(media,'audio');add(audio,'numOutputChannels',2)
    characteristics=add(add(audio,'format'),'samplecharacteristics');add(characteristics,'depth',16);add(characteristics,'samplerate',48000)
    ranges=list(zip(plan['cuts'],plan['cuts'][1:])) if plan['split_music'] else [(0,plan['frames'])]
    # Two linked mono tracks preserve both stereo channels in Premiere/Resolve.
    for channel in (1,2):
        at=add(audio,'track')
        for index,(start,end) in enumerate(ranges,1):
            clip=add(at,'clipitem',id=f'music-{channel}-{index}');add(clip,'name','Soundtrack');add(clip,'enabled','TRUE');rate(clip,plan['fps'])
            add(clip,'duration',plan['frames'])
            for key,value in (('start',start),('end',end),('in',start),('out',end)):add(clip,key,value)
            file=add(clip,'file',id='soundtrack')
            if channel==1 and index==1:
                add(file,'name',Path(music).name);add(file,'pathurl',premiere_pathurl(music));rate(file,plan['fps']);add(file,'duration',plan['frames'])
                ac=add(add(add(file,'media'),'audio'),'samplecharacteristics');add(ac,'depth',16);add(ac,'samplerate',48000)
                add(file.find('./media/audio'),'channelcount',2)
            source=add(clip,'sourcetrack');add(source,'mediatype','audio');add(source,'trackindex',channel)
            for linked in (1,2):
                link=add(clip,'link');add(link,'linkclipref',f'music-{linked}-{index}');add(link,'mediatype','audio');add(link,'trackindex',linked);add(link,'clipindex',index);add(link,'groupindex',1)
    ET.indent(root,space='  ')
    path=Path(folder)/'CINEMATIC_REEL.xml';path.write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True));return path


def render(plan, folder, options, progress, cancel, base_folder=None):
    import av
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    aspect=options.get('aspect','9:16');quality=options.get('resolution','720')
    if aspect not in ('9:16','16:9','1:1') or quality not in ('720','1080','test'):
        raise ValueError('Choose a supported aspect ratio and output resolution')
    short={'720':720,'1080':1080,'test':160}[quality]
    width,height={'9:16':(short,round(short*16/9/2)*2),'16:9':(round(short*16/9/2)*2,short),'1:1':(short,short)}[aspect]
    if base_folder:
        width,height=plan['width'],plan['height']
    plan['width'],plan['height']=width,height
    effects,amount=effect_options(options);plan['effects']=effects
    plan['effect_amount']=amount if effects else 0
    plan['aspect']='16:9' if width>height else '9:16' if height>width else '1:1'
    plan['resolution']=str(min(width,height))
    if base_folder and not effects: raise ValueError('Select at least one effect before applying effects')
    fit=options.get('framing','fit')
    if fit not in ('fit','fill'): raise ValueError('Choose Fit or Fill framing')
    if not base_folder:plan['framing']=fit
    files=[]
    for i,shot in enumerate(plan['shots'],1):
        if cancel.is_set(): raise RuntimeError('Cinematic reel cancelled')
        progress(f"{'Applying effects' if base_folder else 'Rendering shot'} {i}/{len(plan['shots'])}",10+int(70*(i-1)/len(plan['shots'])))
        target=folder/f'shot-{i:03}.mp4';partial=folder/f'shot-{i:03}.partial.mp4'
        if base_folder:
            source=Path(base_folder)/f'shot-{i:03}.mp4'
            args=['-i',source];filters=[]
        else:
            args=['-ss',f"{shot['source_in']:.8f}",'-t',f"{shot['source_out']-shot['source_in']:.8f}",'-i',shot['path']]
            filters=[f"setpts=(PTS-STARTPTS)/{shot['speed']:.8f}",f"fps={plan['fps']}"]
            if fit=='fill':filters += [f'scale={width}:{height}:force_original_aspect_ratio=increase:force_divisible_by=2',f'crop={width}:{height}']
            else:filters += [f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2',f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black']
        filters+=video_filters(plan,shot,width,height,effects,amount)
        filters+=['setsar=1','tpad=stop_mode=clone:stop_duration=0.08',f"trim=end_frame={shot['duration_frames']}",'setpts=PTS-STARTPTS']
        filter_file=folder/f'shot-{i:03}.filter.txt';filter_file.write_text(','.join(filters),encoding='utf-8')
        if options.get('device') == 'cuda':
            render_cuda_shot(plan, shot, partial, width, height, fit, effects, amount, cancel,
                             base_source=source if base_folder else None)
        else:
            run_ffmpeg([*args,'-map','0:v:0','-an','-filter_script:v',filter_file,'-frames:v',shot['duration_frames'],
                        '-r',plan['fps'],*ffmpeg_h264(options.get('device','cpu'),18),'-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',partial],folder,cancel)
        with av.open(str(partial)) as check:
            count=sum(1 for _ in check.decode(video=0))
        if count!=shot['duration_frames']: raise RuntimeError('Rendered shot length does not match its beat interval')
        partial.replace(target);files.append(target)
    progress('Preparing uninterrupted soundtrack',82)
    music=folder/'soundtrack.wav'
    source_music=Path(base_folder)/'soundtrack.wav' if base_folder else Path(plan['music']['path'])
    args=[] if base_folder else ['-ss',f"{plan['music']['source_in']:.8f}"]
    run_ffmpeg([*args,'-i',source_music,'-vn','-af',f"asetpts=PTS-STARTPTS,apad,atrim=duration={plan['duration']:.9f}",
                '-t',f"{plan['duration']:.9f}",'-ar','48000','-ac','2','-c:a','pcm_s16le',music],folder,cancel)
    # Relative generated filenames contain no user strings or quoting ambiguity.
    listing=folder/'shots.concat.txt';listing.write_text('\n'.join(f"file '{p.name}'" for p in files),encoding='utf-8')
    preview=folder/'CINEMATIC_REEL.mp4';partial=folder/'CINEMATIC_REEL.partial.mp4'
    progress('Joining the beat-synced reel',90)
    run_ffmpeg(['-f','concat','-safe','1','-i',listing,'-i',music,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k',
                '-t',f"{plan['duration']:.9f}",'-movflags','+faststart',partial],folder,cancel)
    with av.open(str(partial)) as check:
        frame_count=sum(1 for _ in check.decode(video=0))
    with av.open(str(partial)) as check:
        audio_duration=sum(f.samples/f.sample_rate for f in check.decode(audio=0))
    if frame_count!=plan['frames'] or abs(audio_duration-plan['duration'])>.08:
        raise RuntimeError('Final reel failed video/audio duration validation')
    partial.replace(preview)
    xml=export_xml(plan,folder,files,music)
    (folder/'reel-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    return {'folder':str(folder.resolve()),'preview':str(preview.resolve()),'xml_files':[str(xml.resolve())],
            'frames':plan['frames'],'duration':plan['duration'],'shot_count':len(plan['shots']),
            'quality':{'exact_video_frames':True,'audio_duration_error_seconds':round(abs(audio_duration-plan['duration']),6)},
            'plan':plan}
