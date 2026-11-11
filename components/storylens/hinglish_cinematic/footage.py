"""Short shot bank: measured quality and temporal visual-similarity filtering.

No local reasoning model or fabricated semantic judgement. Duplicate suppression
is perceptual, not a guarantee that two different views depict different subjects.
"""
from pathlib import Path
import hashlib
import math
import statistics


def similar(a,b):
    pairs=list(zip(a['signature'],b['signature']))
    if not pairs:return False
    matches=0
    for x,y in pairs:
        distance=(int(x['hash'])^int(y['hash'])).bit_count()
        hx,hy=x['hist'],y['hist']
        color=sum(min(u,v) for u,v in zip(hx,hy))/max(1e-9,min(sum(hx),sum(hy)))
        matches+=distance<=12 and color>=.8
    return matches>=max(1,math.ceil(len(pairs)*2/3))


def candidates(samples,duration,source,shot_start=0.,shot_end=None):
    shot_end=duration if shot_end is None else shot_end
    length=min(5.,shot_end-shot_start)
    if not samples or length<.5:return []
    starts=sorted(set([shot_start,max(shot_start,shot_end-length)]+[s['time'] for s in samples if shot_start<=s['time'] and s['time']+length<=shot_end]))
    rows=[]
    for start in starts:
        region=[s for s in samples if start<=s['time']<start+length]
        if not region:continue
        score=statistics.mean(s['quality'] for s in region)
        if score<.25:continue
        # Three ordered positions describe the window, rather than just its thumbnail.
        signature=[{k:region[min(len(region)-1,round((len(region)-1)*f))][k] for k in ('hash','hist')} for f in (.15,.5,.85)]
        identity=hashlib.sha256((source+':'+str(start)).encode()).hexdigest()[:20]
        signals = {}
        for name in ('detail','exposure','usable_luma','stability'):
            values = [sample[name] for sample in region if name in sample]
            if values:
                signals[name] = round(statistics.mean(values),6)
        rows.append({'id':identity,'source':source,'start':round(start,6),'duration':round(length,6),'score':round(score,6),'signature':signature,
                     'shot_start':shot_start,'shot_end':shot_end,'quality_signals':{**signals,'mean_measured_quality':round(score,6),'sample_count':len(region),'boundary_method':'conservative adjacent-frame histogram/luma change, flash rejection; semantic review required'}})
    chosen=[]
    for row in sorted(rows,key=lambda r:(-r['score'],r['start'])):
        if any(row['start']<other['start']+other['duration']-.01 and row['start']+row['duration']>other['start']+.01 for other in chosen):continue
        chosen.append(row)
    return chosen


def select_unique(rows,best_count,*,duplicate_evidence=None):
    if best_count is not None and (type(best_count) is not int or not 1<=best_count<=100):raise ValueError('Choose between 1 and 100 Best Shots, or all candidates.')
    unique=[];duplicates=0
    for row in sorted(rows,key=lambda r:(-r['score'],r['source'],r['start'])):
        reverse={**row,'signature':list(reversed(row['signature']))}
        for old in unique:
            if similar(row,old) or similar(reverse,old):
                duplicates+=1
                if duplicate_evidence is not None:
                    duplicate_evidence.append({
                        'id':row['id'], 'source_id':row['source_id'], 'in_pts':row['in_pts'],
                        'out_pts':row['out_pts'], 'duplicate_group':old['id'],
                        'method':'temporal perceptual similarity',
                    })
                break
        else:
            unique.append({**row,'duplicate_group':row['id']} if duplicate_evidence is not None else row)
    if best_count is None:return unique,[],duplicates
    best=[];used=set()
    # Start with varied source clips, then fill with distinct additional regions.
    for row in unique:
        if len(best)<best_count and row['source'] not in used:
            best.append(row);used.add(row['source'])
    for row in unique:
        if len(best)>=best_count:break
        if row not in best:best.append(row)
    return best,[r for r in unique if r not in best],duplicates


def inspect(path,stop,progress,*,sample_seconds=.5,sample_frame=None,frame_timing=None):
    import av
    import cv2
    import numpy as np
    from hinglish_cut.media import video_rotation,orient_frame
    path=Path(path);samples=[];origin=None;last=0.;next_sample=0.;previous=None
    previous_scene=None;pending_scene=None;boundaries=[0.]
    rotation=video_rotation(path)
    with av.open(str(path)) as container:
        if not container.streams.video:raise ValueError('No video track')
        stream=container.streams.video[0];stream.codec_context.thread_count=2
        fps=float(stream.average_rate or stream.guessed_rate or 30)
        for i,frame in enumerate(container.decode(stream)):
            if stop.is_set():raise InterruptedError('Footage collection stopped. Completed files are kept.')
            if frame_timing is not None:
                frame_timing(frame)
            t=float(frame.time) if frame.time is not None else i/fps
            if origin is None:origin=t
            t-=origin;last=t+(float(frame.duration*stream.time_base) if frame.duration else 1/fps)
            tiny=frame.reformat(width=64,height=36,format='rgb24').to_ndarray()
            hsv_scene=cv2.cvtColor(tiny,cv2.COLOR_RGB2HSV)
            histogram=cv2.calcHist([hsv_scene],[0,1],None,[12,4],[0,180,0,256]).flatten();histogram/=max(1.,float(histogram.sum()))
            gray_scene=cv2.cvtColor(tiny,cv2.COLOR_RGB2GRAY).astype(np.float32)/255
            scene=(histogram,gray_scene)
            def changed(a,b,h=.50,l=.18):
                return cv2.compareHist(a[0],b[0],cv2.HISTCMP_BHATTACHARYYA)>h and float(np.abs(a[1]-b[1]).mean())>l
            if pending_scene is not None:
                boundary,before=pending_scene
                if changed(before,scene,.45,.10) and boundary-boundaries[-1]>=.2:boundaries.append(boundary)
                pending_scene=None
            if previous_scene is not None and changed(previous_scene,scene):pending_scene=(t,previous_scene)
            previous_scene=scene
            if t+.001<next_sample:continue
            next_sample=t+sample_seconds
            frame=orient_frame(frame,rotation)
            pixels=frame.reformat(width=192,height=108,format='rgb24').to_ndarray()
            gray=cv2.cvtColor(pixels,cv2.COLOR_RGB2GRAY);unit=gray.astype(np.float32)/255
            if sample_frame is not None:
                proxy=frame.reformat(width=360,height=max(2,round(frame.height*360/frame.width)),format="rgb24")
                sample_frame(t, proxy.to_ndarray())
            detail=min(1.,math.log1p(cv2.Laplacian(gray,cv2.CV_64F).var())/8)
            exposure=max(0.,1-abs(float(unit.mean())-.48)*1.9)
            usable=float(((unit>.025)&(unit<.975)).mean())
            motion=float(np.mean(np.abs(unit-previous))) if previous is not None else 0.
            stability=max(0.,1-motion*4)
            quality=.4*detail+.25*exposure+.25*usable+.1*stability
            small=cv2.resize(gray,(32,32)).astype(np.float32)
            values=cv2.dct(small)[:8,:8].flatten();median=float(np.median(values[1:]));bits=0
            for v in values:bits=(bits<<1)|int(v>median)
            hsv=cv2.cvtColor(pixels,cv2.COLOR_RGB2HSV)
            hist=cv2.calcHist([hsv],[0,1],None,[12,4],[0,180,0,256]).flatten()
            hist=(hist/max(1,float(hist.sum()))).tolist()
            samples.append({'time':round(t,6),'quality':quality,'hash':bits,'hist':hist,
                            'detail':detail,'exposure':exposure,'usable_luma':usable,'stability':stability})
            previous=unit
    if not samples:raise ValueError('No readable video frames')
    boundaries.append(last)
    rows=[]
    for a,b in zip(boundaries,boundaries[1:]):rows.extend(candidates(samples,last,str(path.resolve()),a,b))
    return rows
