"""Frame-indexed, read-only reference measurements. Not source-stem truth or training."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
import av,numpy as np,soundfile as sf
from PIL import Image,ImageDraw
from scipy.signal import find_peaks
from .library import decode

def measure(root,source,output):
    source=Path(source).resolve()
    if not source.is_file() or source.suffix.lower() not in {'.mp4','.mov','.mkv','.webm'}:
        raise ValueError('Choose a readable local reference video.')
    with source.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    folder=Path(root)/'library/reelmimic/sound'/digest[:24]
    study=folder/'study';study.mkdir(parents=True,exist_ok=True)
    saved=folder/('source'+source.suffix.lower())
    if not saved.exists():shutil.copy2(source,saved)
    audio=decode(source,48000,mono=False)
    sf.write(study/'original.wav',audio.T,48000,subtype='FLOAT')
    mono=audio.mean(axis=0);hop=480
    padded=np.pad(mono,(0,(-len(mono))%hop));blocks=padded.reshape(-1,hop)
    power=np.mean(blocks**2,axis=1);levels=10*np.log10(np.maximum(power,1e-12))
    spectra=np.abs(np.fft.rfft(blocks*np.hanning(hop),axis=1))
    flux=np.r_[0,np.maximum(0,np.diff(spectra,axis=0)).mean(axis=1)]
    prominence=max(float(np.percentile(flux,80)-np.percentile(flux,35)),1e-5)
    peaks,_=find_peaks(flux,prominence=prominence,distance=7)
    np.savez_compressed(study/'audio-features.npz',time=np.arange(len(blocks))*.01,
        rms_db=levels,flux=flux,spectral_magnitude=spectra)
    (study/'frames').mkdir(exist_ok=True);(study/'sheets').mkdir(exist_ok=True)
    rows=[];previous=None;page=[];sheet_paths=[]
    with av.open(str(source)) as container:
        stream=container.streams.video[0];fps=float(stream.average_rate)
        seconds=float(stream.duration*stream.time_base) if stream.duration is not None else container.duration/1e6
        portrait=stream.height>stream.width
        width,height=(160,284) if portrait else (240,135)
        cols,per_page=(8,32) if portrait else (6,48)
        def flush():
            if not page:return
            canvas=Image.new('RGB',(cols*width,((len(page)+cols-1)//cols)*(height+18)),'#141414')
            draw=ImageDraw.Draw(canvas)
            for j,(index,t,picture) in enumerate(page):
                x=(j%cols)*width;y=(j//cols)*(height+18)
                draw.text((x+2,y+1),f'{index} | {t:.3f}s',fill='white');canvas.paste(picture,(x,y+18))
            path=study/'sheets'/f'page-{len(sheet_paths):03d}.jpg';canvas.save(path,quality=85)
            sheet_paths.append(str(path.resolve()));page.clear()
        for index,frame in enumerate(container.decode(stream)):
            t=float(frame.pts*frame.time_base) if frame.pts is not None else index/fps
            picture=frame.to_image().convert('RGB')
            small=np.asarray(picture.resize((96,64)).convert('L'),np.float32)/255
            change=float(np.abs(small-previous).mean()) if previous is not None else 0.
            previous=small
            a=max(0,min(len(levels)-1,int(t/.01)));b=min(len(levels),max(a+1,int((t+1/fps)/.01)))
            rows.append(dict(frame=index,time=t,visual_change=change,rms_db=float(levels[a:b].mean()),
                onset_flux=float(flux[a:b].max()),near_silence_in_full_mix=bool(np.max(levels[a:b])<-45)))
            thumb=picture.copy();thumb.thumbnail((width,height))
            tile=Image.new('RGB',(width,height),'#000');tile.paste(thumb,((width-thumb.width)//2,(height-thumb.height)//2))
            tile.save(study/'frames'/f'{index:06d}.jpg',quality=78)
            page.append((index,t,tile))
            if len(page)==per_page:flush()
        flush()
        video=dict(width=stream.width,height=stream.height,fps=str(stream.average_rate),seconds=seconds,
                   declared_frames=stream.frames,decoded_frames=len(rows),all_frames_measured=True,
                   all_frames_on_contact_sheets=True)
    events=[dict(time=round(float(i*.01),4),nearest_frame=int(np.argmin([abs(r['time']-i*.01) for r in rows])),
                 kind='measured_audio_change_candidate',flux=float(flux[i])) for i in peaks if i*.01<seconds]
    (study/'frame-timeline.json').write_text(json.dumps(rows,indent=1),'utf-8')
    (study/'audio-change-candidates.json').write_text(json.dumps(events,indent=2),'utf-8')
    summary=dict(source=str(source),saved_source=str(saved),sha256=digest,folder=str(folder.resolve()),
      study=str(study.resolve()),name=source.stem,video=video,sheets=sheet_paths,audio_changes=len(events),
      caveats=['Frame/audio measurements are observations, not exact sound identities.',
       'Onset candidates include speech, percussion and codec changes; they are not an SFX count.',
       'Mixed audio does not expose exact source files or hidden layers.'])
    (study/'measurement.json').write_text(json.dumps(summary,indent=2),'utf-8')
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',default='.');parser.add_argument('--source',action='append',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--separate',action='store_true');args=parser.parse_args()
    root=Path(args.root).resolve();output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for source in args.source:
        row=measure(root,source,output);rows.append(row)
        (output/'manifest.json').write_text(json.dumps(dict(references=rows),indent=2),'utf-8')
        print(f"Measured every frame: {row['name']} — {row['video']['decoded_frames']} frames",flush=True)
        if args.separate:
            study=Path(row['study']);target=study/'voice.wav'
            if not target.exists():
                with (study/'separation.log').open('w',encoding='utf-8') as log:
                    result=subprocess.run([sys.executable,str(root/'tools/sound-separation-runtime/separate.py'),
                        '--input',str(study/'original.wav'),'--output',str(target),'--device','cpu'],
                        stdout=log,stderr=subprocess.STDOUT,timeout=900,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode:raise RuntimeError('Reference voice separation stopped; inspect separation.log.')
            original,sr=sf.read(study/'original.wav',always_2d=True,dtype='float32');voice,vsr=sf.read(target,always_2d=True,dtype='float32')
            if sr!=vsr or original.shape!=voice.shape:raise RuntimeError('Reference audio separation changed timing.')
            sf.write(study/'nonvocal-residual.wav',original-voice,sr,subtype='FLOAT')
            print('Saved aligned voice/non-vocal estimates (not isolated SFX/music)',flush=True)

if __name__=='__main__':main()
