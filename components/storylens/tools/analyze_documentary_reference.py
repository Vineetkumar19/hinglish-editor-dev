"""Bounded, resumable reference inspection. One source is decoded at a time; originals are never copied."""
import argparse, csv, hashlib, html, json, math, os, queue, re, subprocess, threading, time
from collections import deque
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from imageio_ffmpeg import get_ffmpeg_exe

WIDTH, HEIGHT = 256, 144

def write_json(path, value):
    def scalar(value):
        if isinstance(value,np.generic):return value.item()
        raise TypeError(f'Unsupported JSON value: {type(value).__name__}')
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2,ensure_ascii=False,default=scalar),encoding='utf-8');temp.replace(path)

def facts(path):
    with av.open(str(path)) as c:
        v=c.streams.video[0]
        return {'path':str(path),'bytes':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns,
                'seconds':float(v.duration*v.time_base) if v.duration else float(c.duration)/av.time_base,
                'fps':str(v.average_rate),'declared_frames':v.frames,'width':v.width,'height':v.height}

def scan(path, folder, frame_analyzer=None, max_seconds=None):
    folder.mkdir(parents=True,exist_ok=True);source=facts(path)
    done=folder/'scan.json'
    if frame_analyzer is None and done.exists() and json.loads(done.read_text(encoding='utf-8'))['source']==source:
        print('Reusing completed native-frame scan',flush=True);return json.loads(done.read_text(encoding='utf-8'))
    (folder/'frames').mkdir(exist_ok=True)
    settings=folder.parent/'decoder-settings.json'
    configured=json.loads(settings.read_text(encoding='utf-8')) if settings.exists() else {}
    decoder=configured.get('decoder',os.environ.get('DOCUMENTARY_HW_DECODER','d3d11va' if os.name=='nt' else ''))
    hardware=['-hwaccel','d3d11va'] if decoder=='d3d11va' else []
    if decoder=='h264_cuvid':
        # NVDEC resizes before transferring frames to RAM. Every native frame is
        # still decoded; this avoids copying a full 4K frame for a tiny timeline.
        hardware=['-c:v','h264_cuvid','-resize',f'{WIDTH}x{HEIGHT}']
    if hardware:
        probe=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin',*hardware,'-i',str(path),'-t','1','-an','-f','null','-'],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if probe.returncode:
            print('Hardware reference decoder unavailable; using software decoding',flush=True)
            decoder='';hardware=[]
    command=[get_ffmpeg_exe(),'-hide_banner','-nostdin',*hardware,'-threads','2','-i',str(path),'-an','-sn','-dn','-vf',f'scale={WIDTH}:{HEIGHT}:flags=fast_bilinear,format=rgb24,showinfo','-fps_mode','passthrough','-f','rawvideo','pipe:1']
    if max_seconds is not None:command[command.index('-an'):command.index('-an')]=['-t',str(max_seconds)]
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    stamps=queue.Queue();errors=deque(maxlen=10)
    def stderr():
        for raw in iter(process.stderr.readline,b''):
            line=raw.decode('utf-8','replace');match=re.search(r'n:\s*(\d+).*?pts_time:([\d.e+\-]+)',line)
            if match:stamps.put((int(match[1]),float(match[2])))
            elif 'error' in line.lower():errors.append(line.strip())
        stamps.put(None)
    reader=threading.Thread(target=stderr,daemon=True);reader.start()
    peaks=[];prev=None;count=0;sampled=set();first=None;last=None;began=time.time();last_progress=-1
    with (folder/'frame-metrics.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.writer(file);writer.writerow(['frame','source_pts_seconds','relative_seconds','mean_pixel_change','brightness'])
        try:
            while True:
                chunk=process.stdout.read(WIDTH*HEIGHT*3)
                if not chunk:break
                while len(chunk)<WIDTH*HEIGHT*3:
                    more=process.stdout.read(WIDTH*HEIGHT*3-len(chunk))
                    if not more:raise ValueError('Partial decoded frame')
                    chunk+=more
                stamp=stamps.get(timeout=60)
                if stamp is None or stamp[0]!=count:raise ValueError('Decoded frame/PTS mismatch')
                pts=stamp[1];first=pts if first is None else first;t=max(0,pts-first);last=t
                frame=np.frombuffer(chunk,dtype=np.uint8).reshape(HEIGHT,WIDTH,3)
                delta=float(np.abs(frame.astype(np.int16)-prev).mean()) if prev is not None else 0
                if frame_analyzer is not None:frame_analyzer(frame,t,count,delta)
                writer.writerow([count,pts,round(t,6),round(delta,4),round(float(frame.mean()),4)])
                if delta>13:peaks.append({'frame':count,'time':round(t,6),'change':round(delta,3)})
                sec=int(t+1e-5)
                if sec not in sampled:
                    Image.fromarray(frame).save(folder/'frames'/f'{sec:05d}.jpg',quality=84);sampled.add(sec)
                prev=frame.astype(np.int16);count+=1
                progress=int(t//30)
                if progress!=last_progress:
                    print(f'Native-frame scan: {t:.1f}/{source["seconds"]:.1f}s, {count} frames, {count/max(1,time.time()-began):.0f} decoded fps',flush=True);last_progress=progress
            code=process.wait()
            if code:raise RuntimeError('Decoder failed: '+'; '.join(errors))
            reader.join(2)
        except BaseException:
            process.kill();process.wait();raise
    grouped=[]
    for peak in sorted(peaks,key=lambda p:-p['change']):
        if all(abs(peak['time']-p['time'])>=1.5 for p in grouped):grouped.append(peak)
        if len(grouped)==30:break
    result={'source':source,'decoder':decoder or 'software','decoded_frames':count,'last_frame_seconds':last,'sampled_seconds':len(sampled),
            'requested_limit_seconds':max_seconds,'full_source':max_seconds is None,
            'seconds_without_sample':[n for n in range(int(source['seconds'])) if n not in sampled],
            'largest_changes':sorted(grouped,key=lambda p:p['time']),'scan_seconds':round(time.time()-began,1),
            'coverage':'Every decoded native frame measured at 256x144 RGB; one saved image per source second. Pixel changes are cues, not semantic scene labels. Visually reviewed frames are recorded separately.'}
    write_json(done,result);sheets(folder,1,'every-second');sheets(folder,5,'overview');return result

def sheets(folder, stride, prefix):
    files=[p for p in sorted((folder/'frames').glob('*.jpg')) if int(p.stem)%stride==0]
    output=folder/prefix;output.mkdir(exist_ok=True)
    for start in range(0,len(files),60):
        batch=files[start:start+60];canvas=Image.new('RGB',(5*WIDTH,math.ceil(len(batch)/5)*(HEIGHT+22)),'#10141b');draw=ImageDraw.Draw(canvas)
        for n,path in enumerate(batch):
            x=n%5*WIDTH;y=n//5*(HEIGHT+22)
            with Image.open(path) as image:canvas.paste(image,(x,y))
            seconds=int(path.stem);draw.text((x+5,y+HEIGHT+3),f'{seconds//60:02}:{seconds%60:02}  ({seconds}s)',fill='white')
        canvas.save(output/f'sheet-{start//60+1:03}.jpg',quality=88)


def detail(path,folder,start,duration=2):
    """Native-rate small frames for a bounded animation window; no huge media copy."""
    stem=f'{start:.3f}'.replace('.','_');target=folder/'details'/stem;target.mkdir(parents=True,exist_ok=True)
    subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-y','-threads','2','-ss',str(max(0,start)),'-i',str(path),'-t',str(duration),'-an','-vf','scale=384:216:flags=lanczos','-fps_mode','passthrough',str(target/'frame-%04d.jpg')],check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    rate=float(__import__('fractions').Fraction(facts(path)['fps']));files=sorted(target.glob('frame-*.jpg'))
    selected=files[::3]  # native frames retained, contact sheet displays 50ms steps at 60fps
    for i in range(0,len(selected),40):
        batch=selected[i:i+40];canvas=Image.new('RGB',(5*384,math.ceil(len(batch)/5)*238),'#10141b');draw=ImageDraw.Draw(canvas)
        for n,p in enumerate(batch):
            x=n%5*384;y=n//5*238
            with Image.open(p) as image:canvas.paste(image,(x,y))
            draw.text((x+5,y+219),f'{start+(int(p.stem.split("-")[-1])-1)/rate:.3f}s',fill='white')
        canvas.save(target/f'contact-{i//40+1:02}.jpg',quality=86)
    write_json(target/'coverage.json',{'start':start,'duration':duration,'saved_native_frames':len(files),'contact_stride_frames':3,'note':'Seek-window native frame extraction; contact sheet has 50ms steps at 60fps.'})


def transcript(path,folder,root):
    from dataclasses import asdict
    from hinglish_shorts.source import open_video,transcribe
    words=transcribe(root,open_video(path),'cpu',lambda s:print(s,flush=True))
    write_json(folder/'words.json',[asdict(w) for w in words])
    lines=[];current=[];begin=0
    for word in words:
        if not current:begin=word.start
        current.append(word.text)
        if word.end-begin>=6:
            lines.append({'start':begin,'end':word.end,'text':' '.join(current)});current=[]
    if current:lines.append({'start':begin,'end':words[-1].end,'text':' '.join(current)})
    write_json(folder/'transcript.json',lines)
    (folder/'transcript.txt').write_text('\n'.join(f'[{p["start"]:.2f}–{p["end"]:.2f}] {p["text"]}' for p in lines),encoding='utf-8')


def fast_transcript(path,folder,root,device='cpu',batch_size=1):
    import gc
    import wave
    from faster_whisper import WhisperModel
    from uroman import Uroman
    completed=folder/'transcript.json'
    if completed.exists():return
    audio=folder/'analysis-audio.wav'
    if not audio.exists():
        subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-threads','2','-i',str(path),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(audio)],check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    manifest=json.loads((root/'models/meaning-upgrade.json').read_text(encoding='utf-8'))
    compute='int8_float16' if device=='cuda' else 'int8'
    model=WhisperModel(manifest['speech_path'],device=device,compute_type=compute,cpu_threads=2,num_workers=1,local_files_only=True)
    transcriber=model
    if batch_size>1:
        from faster_whisper import BatchedInferencePipeline
        transcriber=BatchedInferencePipeline(model)
    romanizer=Uroman();lines=[];words=[];resume=0.0
    checkpoint=folder/'speech-checkpoint.jsonl';checkpoint_meta=folder/'speech-checkpoint-source.json'
    source=facts(path)
    if checkpoint.exists() and checkpoint_meta.exists() and json.loads(checkpoint_meta.read_text(encoding='utf-8'))==source:
        valid_rows=[]
        for row in checkpoint.read_text(encoding='utf-8').splitlines():
            try:entry=json.loads(row)
            except json.JSONDecodeError:break
            valid_rows.append(row)
            lines.append(entry['line']);words.extend(entry['words']);resume=entry['line']['end']
        checkpoint.write_text('\n'.join(valid_rows)+('\n' if valid_rows else ''),encoding='utf-8')
        print(f'Resuming completed reference speech segments after {resume:.1f}s',flush=True)
    else:
        checkpoint.write_text('',encoding='utf-8');write_json(checkpoint_meta,source)
    # VAD still works on a resumed audio array, with source timestamps restored below.
    speech_input=str(audio)
    if resume:
        with wave.open(str(audio),'rb') as reader:
            reader.setpos(min(reader.getnframes(),round(resume*reader.getframerate())))
            speech_input=np.frombuffer(reader.readframes(reader.getnframes()),dtype='<i2').astype(np.float32)/32768
    try:
        options={'batch_size':batch_size} if batch_size>1 else {}
        segments,info=transcriber.transcribe(speech_input,language='hi',beam_size=1,temperature=0,word_timestamps=True,condition_on_previous_text=False,vad_filter=True,**options)
        with (folder/'transcript.partial.jsonl').open('w',encoding='utf-8') as output:
            for line in lines:output.write(json.dumps(line,ensure_ascii=False)+'\n')
            for seg in segments:
                line={'start':seg.start+resume,'end':seg.end+resume,'text':romanizer.romanize_string(seg.text.strip(),lcode='hin'),'raw_text':seg.text.strip()}
                lines.append(line);output.write(json.dumps(line,ensure_ascii=False)+'\n');output.flush()
                segment_words=[]
                for w in seg.words or []:
                    segment_words.append({'start':float(w.start+resume),'end':float(w.end+resume),'text':romanizer.romanize_string(w.word.strip(),lcode='hin'),'probability':float(w.probability),'aligned':False,'timestamp_source':'Whisper ASR, not a forced-alignment receipt'})
                words.extend(segment_words)
                with checkpoint.open('a',encoding='utf-8') as saved:saved.write(json.dumps({'line':line,'words':segment_words},ensure_ascii=False)+'\n')
                print(f'Local int8 reference speech: {line["end"]:.1f}s',flush=True)
    finally:del transcriber,model;gc.collect()
    write_json(folder/'words.json',words);write_json(completed,lines)
    (folder/'transcript.txt').write_text('\n'.join(f'[{p["start"]:.2f}–{p["end"]:.2f}] {p["text"]}' for p in lines),encoding='utf-8')
    write_json(folder/'speech-coverage.json',{'backend':f'local faster-whisper large-v3-turbo, {device} {compute}, batch {batch_size}, beam1, VAD','source_seconds':facts(path)['seconds'],'segments':len(lines),'words':len(words),'warning':'Automatic speech recognition and ASR word timestamps are fallible; names, numbers and interpretation require review. Music-only spans may have no transcript.'})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--out',required=True);parser.add_argument('--root',default='.');parser.add_argument('--transcribe',action='store_true');parser.add_argument('--fast-transcribe',action='store_true');parser.add_argument('--speech-only',action='store_true');parser.add_argument('--detail',type=float,nargs='*');args=parser.parse_args()
    path=Path(args.input).resolve();folder=Path(args.out).resolve()
    if args.speech_only:
        fast_transcript(path,folder,Path(args.root).resolve())
    elif args.detail is not None:
        for start in args.detail:detail(path,folder,start)
    else:
        result=scan(path,folder);print(json.dumps({'frames':result['decoded_frames'],'folder':str(folder)}),flush=True)
        if args.transcribe:transcript(path,folder,Path(args.root).resolve())
        if args.fast_transcribe:fast_transcript(path,folder,Path(args.root).resolve())
if __name__=='__main__':main()
