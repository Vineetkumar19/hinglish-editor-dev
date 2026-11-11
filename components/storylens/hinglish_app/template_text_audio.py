"""Decode just the final audio edit map. No AE render, mux, browser or network."""
from pathlib import Path
import hashlib
import json
import math
import re
import wave

RATE=16000

def local_file(value):
    if not isinstance(value,str) or value.startswith(('\\\\','//')) or re.match(r'^[a-z]+://',value,re.I):raise ValueError('Template Text audio: choose a local narrated video/audio file.')
    path=Path(value).resolve()
    if str(path).startswith(('\\\\','//')) or not path.is_absolute() or not path.is_file() or path.suffix.lower() not in ('.mp4','.mov','.mkv','.avi','.webm','.mxf','.m4v','.wav','.mp3','.m4a','.aac','.flac','.aiff','.aif','.ogg'):raise ValueError('Template Text audio: relink the final video/audio, or choose it in Settings.')
    return path

def cache_key(snapshot):
    sources=[]
    for row in snapshot['audio']:
        path=local_file(row['path']);stat=path.stat();sources.append({**row,'path':str(path),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns})
    return hashlib.sha256(json.dumps({'version':2,'duration':snapshot['duration'],'audio':sources},sort_keys=True).encode()).hexdigest()

def decode_map(snapshot,destination,check=lambda:None):
    import av
    import numpy as np
    duration=snapshot['duration'];mix=np.zeros(round(duration*RATE),dtype=np.float32)
    # Decode each shared source once, including original stream offsets. This is
    # bounded to a two-hour composition and source intervals actually requested.
    grouped={}
    for row in snapshot['audio']:grouped.setdefault(str(local_file(row['path'])),[]).append(row)
    for filename,rows in grouped.items():
        check();need=max(r['source_in']+(r['end']-r['start'])*r['rate'] for r in rows);begin=min(r['source_in'] for r in rows)
        if need-begin>7200:raise ValueError('Template Text audio: source selection exceeds the supported audio window.')
        source=np.zeros(math.ceil((need-begin)*RATE)+RATE,dtype=np.float32);filled=0
        with av.open(filename) as container:
            if not container.streams.audio:raise ValueError('Template Text audio: this file has no narration audio. Choose the final narrated video/audio.')
            if len(container.streams.audio)>1:raise ValueError('Template Text audio: this file has multiple audio streams. Choose a final narration mix with one stream.')
            stream=container.streams.audio[0];resampler=av.AudioResampler(format='fltp',layout='mono',rate=RATE)
            # AE source time starts at its footage zero, not the first audio packet.
            videos=container.streams.video;offset=float(videos[0].start_time*videos[0].time_base) if videos and videos[0].start_time is not None else float((stream.start_time or 0)*stream.time_base)
            if begin>1:container.seek(max(0,int((begin+offset-.5)*av.time_base)))
            for frame in container.decode(stream):
                check()
                if frame.pts is not None and float(frame.pts*frame.time_base)-offset>need+.5:break
                for converted in resampler.resample(frame):
                    if converted.pts is None:raise ValueError('Template Text audio: audio packet timing is unavailable. Choose a final WAV narration mix.')
                    position=round((float(converted.pts*converted.time_base)-offset-begin)*RATE);pixels=converted.to_ndarray().reshape(-1)
                    a=max(0,position);b=min(len(source),position+len(pixels))
                    if b>a:source[a:b]=pixels[a-position:b-position];filled=max(filled,b)
        if filled<max(0,round((need-begin-max(.5,min(2,duration*.01)))*RATE)):raise ValueError('Template Text audio: the chosen audio ends before this timeline. Choose the matching final narration mix.')
        for row in rows:
            a=max(0,round(row['start']*RATE));b=min(len(mix),round(row['end']*RATE))
            for offset in range(a,b,RATE*60):
                stop=min(b,offset+RATE*60);positions=(row['source_in']-begin)*RATE+np.arange(offset-a,stop-a)*row['rate'];indices=np.floor(positions).astype('int64');fraction=positions-indices
                left=np.clip(indices,0,len(source)-1);right=np.clip(indices+1,0,len(source)-1)
                mix[offset:stop]+=(source[left]*(1-fraction)+source[right]*fraction)*row.get('gain',1)
    peak=float(np.max(np.abs(mix))) if len(mix) else 0
    if peak<.0001:raise ValueError('Template Text audio: no audible narration was found. Choose the final narrated video/audio.')
    mix=np.clip(mix/max(1,peak),-1,1)
    with wave.open(str(destination),'wb') as out:out.setparams((1,2,RATE,0,'NONE','not compressed'));out.writeframes((mix*32767).astype('<i2').tobytes())
    return destination
