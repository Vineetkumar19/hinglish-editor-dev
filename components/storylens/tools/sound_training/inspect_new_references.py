"""Read-only local media inspection; no claim that waveform peaks identify SFX."""
from pathlib import Path
import av, json, hashlib, subprocess
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/sound-training/20261030-revision2/references'
FILES=[Path('D:/Chrome Downloads')/('its.mee.ananyaaa_'+s+'.mp4') for s in (
 '1789132064_3983850432808064982_44065108661',
 '1791888995_4006976596745226263_44065108661',
 '1790160347_3992476316636990467_44065108661')]

def main():
    OUT.mkdir(parents=True,exist_ok=True);manifest=[]
    for n,path in enumerate(FILES,1):
        dest=OUT/f'ref{n}';dest.mkdir(exist_ok=True)
        allrows=[];tiles=[];overview=[];previous=None
        def sheet(items,name,w=192,cols=8):
            h=int(w*9/16)+19
            im=Image.new('RGB',(w*cols,h*((len(items)+cols-1)//cols)),(25,25,25));draw=ImageDraw.Draw(im)
            for k,(stamp,pic) in enumerate(items):
                x=(k%cols)*w;y=(k//cols)*h
                im.paste(pic.resize((w,h-19)),(x,y));draw.text((x+2,y+h-17),stamp,fill='white')
            im.save(dest/name,quality=90)
        with av.open(str(path)) as container:
            for i,frame in enumerate(container.decode(video=0)):
                t=float(frame.time);im=frame.to_image();small=im.resize((192,108))
                a=np.asarray(small,dtype=np.float32)
                diff=float(np.abs(a-previous).mean()) if previous is not None else 0
                previous=a
                allrows.append(dict(frame=i,time=t,mean_visual_delta=diff))
                tiles.append((f'{i} | {t:.3f}s',small))
                if i%30==0:overview.append((f'{i} | {t:.3f}s',im.resize((320,180))))
                if len(tiles)==120:sheet(tiles,f'frames-{i-119:04d}-{i:04d}.jpg');tiles=[]
            if tiles:sheet(tiles,f'frames-{i-len(tiles)+1:04d}-{i:04d}.jpg')
            sheet(overview,'overview.jpg',320,5)
        wav=dest/'audio.wav'
        subprocess.run([str(ROOT/'tools/reelmimic/bin/ffmpeg.exe'),'-v','error','-y','-i',str(path),'-vn','-ac','1','-ar','48000',str(wav)],check=True)
        import soundfile as sf
        audio,sr=sf.read(wav);hop=480
        rms=[float(np.sqrt(np.mean(audio[j:j+hop]**2))) for j in range(0,len(audio),hop)]
        (dest/'frame-audio-measurements.json').write_text(json.dumps(dict(frames=allrows,audio_rms_10ms=rms,audio_sample_rate=sr)),encoding='utf-8')
        manifest.append(dict(id=f'ref{n}',path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),decoded_frames=len(allrows),duration=len(audio)/sr,all_frames_saved_in_sheets=True,audio_perceptual_claim=False))
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest))
if __name__=='__main__':main()
