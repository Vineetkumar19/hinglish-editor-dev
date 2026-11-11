"""Source-hashed tutorial ingestion and complete spoken-content transcription.

Reference files are data. No rendered video, model download or weight training.
"""
import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import av
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')


def ingest(root, source):
    from .library import decode
    source = Path(source).resolve()
    with source.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    folder = Path(root) / 'library/reelmimic/sound' / digest[:24]
    study = folder / 'tutorial'
    study.mkdir(parents=True, exist_ok=True)
    saved = folder / ('source' + source.suffix.lower())
    if not saved.exists():
        shutil.copy2(source, saved)
    measured = study / 'measurement.json'
    if measured.is_file():
        return json.loads(measured.read_text('utf-8'))
    wav = study / 'speech-input.wav'
    audio = decode(saved, 16000, mono=True)[0]
    sf.write(wav, audio, 16000, subtype='PCM_16')
    n = len(audio) // 1600
    rms = 10 * np.log10(np.maximum(np.mean(audio[:n*1600].reshape(n,1600)**2, axis=1),1e-12))
    np.savez_compressed(study/'audio-envelope.npz', time=np.arange(n)*.1,rms_db=rms)
    del audio
    frames = study/'frames';frames.mkdir(exist_ok=True)
    sheets = study/'sheets';sheets.mkdir(exist_ok=True)
    picks=[];frame_changes=[];prev=None;next_sample=0.;page=[];pages=[]
    def flush():
        if not page:return
        canvas=Image.new('RGB',(1280,((len(page)+4)//5)*164),'#141414');draw=ImageDraw.Draw(canvas)
        for j,(t,p) in enumerate(page):
            x=(j%5)*256;y=(j//5)*164
            draw.text((x+3,y+2),f'{int(t//60)}m {t%60:05.2f}s | {t:.2f}s',fill='white')
            canvas.paste(p,(x,y+20))
        path=sheets/f'page-{len(pages):03d}.jpg';canvas.save(path,quality=90)
        pages.append(str(path.resolve()));page.clear()
    with av.open(str(saved)) as c:
        stream=c.streams.video[0];fps=float(stream.average_rate)
        seconds=c.duration/1e6;decoded=0
        for i,frame in enumerate(c.decode(stream)):
            t=float(frame.pts*frame.time_base) if frame.pts is not None else i/fps
            tiny=frame.reformat(width=96,height=54,format='gray').to_ndarray().astype(np.float32)/255
            change=float(np.abs(tiny-prev).mean()) if prev is not None else 0.
            frame_changes.append((i,t,change));prev=tiny;decoded+=1
            if t+.001<next_sample:continue
            picture=frame.to_image().convert('RGB');picture.save(frames/f'{i:07d}.jpg',quality=88)
            tile=picture.resize((256,144));page.append((t,tile))
            picks.append(dict(frame=i,time=t,path=str((frames/f'{i:07d}.jpg').resolve())))
            next_sample+=10
            if len(page)==20:flush()
        flush()
        video=dict(width=stream.width,height=stream.height,seconds=seconds,fps=str(stream.average_rate),declared_frames=stream.frames,decoded_frames=decoded)
    np.savez_compressed(study/'frame-change.npz',values=np.array(frame_changes))
    row=dict(source=str(source),saved_source=str(saved.resolve()),sha256=digest,study=str(study.resolve()),name=source.stem,video=video,
        sampled_frames=picks,sheets=pages,audio=str(wav.resolve()),method='Every video frame decoded for change measurements; review sheets sample every 10 seconds. Original audio transcribed separately. Not every-frame semantic interpretation.')
    write(measured,row)
    return row


def transcribe(root, rows, device):
    from contextlib import nullcontext
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import release_ollama
    pending=[r for r in rows if not (Path(r['study'])/'transcript.json').exists()]
    if not pending:return
    print('Waiting for the shared GPU queue; other jobs stay running.' if device=='cuda' else 'Transcribing on CPU.',flush=True)
    with gpu_lock(root) if device=='cuda' else nullcontext():
        print('Transcription worker acquired its queue slot.',flush=True)
        if device=='cuda':release_ollama(root)
        dll_handle=None
        if device=='cuda' and os.name=='nt':
            import torch
            runtime=Path(torch.__file__).parent/'lib'
            dll_handle=os.add_dll_directory(str(runtime))
            os.environ['PATH']=str(runtime)+os.pathsep+os.environ.get('PATH','')
        from faster_whisper import WhisperModel,BatchedInferencePipeline
        location=json.loads((Path(root)/'models/meaning-upgrade.json').read_text('utf-8'))['speech_path']
        model=WhisperModel(location,device=device,compute_type='float16' if device=='cuda' else 'int8',cpu_threads=6,local_files_only=True)
        engine=BatchedInferencePipeline(model=model)
        for row in pending:
            t=time.monotonic();study=Path(row['study'])
            print('Transcribing complete tutorial: '+row['name'],flush=True)
            segments,info=engine.transcribe(row['audio'],beam_size=3 if device=='cuda' else 1,batch_size=8 if device=='cuda' else 4,
                condition_on_previous_text=False,vad_filter=True,word_timestamps=False)
            result=dict(source_sha256=row['sha256'],model='Systran/faster-whisper-large-v3',device=device,
                        language=info.language,language_probability=info.language_probability,segments=[],
                        caveat='Automatic transcription, not verbatim verified speech. Names/numbers may be wrong; the soundtrack is not separated into individual effects.')
            for s in segments:
                result['segments'].append(dict(start=s.start,end=s.end,text=s.text,avg_logprob=s.avg_logprob,no_speech_probability=s.no_speech_prob))
                write(study/'transcript.partial.json',result)
            result['inference_seconds']=round(time.monotonic()-t,2)
            write(study/'transcript.json',result)
            (study/'transcript.txt').write_text('\n'.join(f"[{s['start']:.2f}–{s['end']:.2f}] {s['text'].strip()}" for s in result['segments']),'utf-8')
            print(f"Saved {len(result['segments'])} segments for {row['name']} ({result['inference_seconds']} seconds)",flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--source',action='append',default=[])
    p.add_argument('--output',required=True);p.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    p.add_argument('--ingest-only',action='store_true');p.add_argument('--transcribe-only',action='store_true');a=p.parse_args()
    root=Path(a.root).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if a.transcribe_only:rows=json.loads((out/'manifest.json').read_text('utf-8'))['references']
    else:
        rows=[]
        for source in a.source:
            row=ingest(root,source);rows.append(row);write(out/'manifest.json',dict(references=rows))
            print(f"Ingested {row['name']}: {row['video']['seconds']:.1f}s, {row['video']['decoded_frames']} decoded frames",flush=True)
    if not a.ingest_only:transcribe(root,rows,a.device)


if __name__=='__main__':main()
