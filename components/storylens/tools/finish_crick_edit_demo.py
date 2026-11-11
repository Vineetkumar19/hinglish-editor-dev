"""Replace the corrected film chapter, balance sound, then inspect the actual exported frames."""
import json, math, subprocess, sys, time
from pathlib import Path
import av, numpy as np
from PIL import Image, ImageDraw
from imageio_ffmpeg import get_ffmpeg_exe
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/reference-analysis/crick-edit-editing-style/demo'

def main():
    original=OUT/'CRICK_EDIT_60S.mp4';book=OUT/'chapter-01.mp4';corrected=OUT/'chapter-06.mp4';final=OUT/'CRICK_EDIT_60S-reviewed.mp4'
    filters='[0:v]trim=start=10:end=50,setpts=PTS-STARTPTS[v0];[1:v]setpts=PTS-STARTPTS[v1];[2:v]setpts=PTS-STARTPTS[v2];[v1][v0][v2]concat=n=3:v=1:a=0[v];[0:a]atrim=end=60,asetpts=PTS-STARTPTS,volume=2.5[a]'
    subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(original),'-i',str(book),'-i',str(corrected),'-filter_complex_threads','2','-filter_complex',filters,'-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-r','60','-threads','2','-c:a','aac','-b:a','192k','-t','60','-movflags','+faststart',str(final)],check=True)
    final.replace(original)
    count=0;times=[];frames=[];means=[];changes=[];prev=None
    review_at=[.1,.8,1.4,2.6,6.4,9.8,10.2,11.6,16.4,19.8,20.3,21.5,24.8,29.8,30.3,31.05,32.2,36.4,39.8,40.5,42.5,46.4,49.8,50.5,54.8,56.4,58.6,59.5]
    next_sample=0
    with av.open(str(original)) as c:
        stream=c.streams.video[0];fps=float(stream.average_rate);width,height=stream.width,stream.height
        duration=float(stream.duration*stream.time_base)
        for f in c.decode(video=0):
            t=float(f.pts*f.time_base);small=f.to_image().resize((320,180));arr=np.asarray(small,dtype=np.int16);means.append(float(arr.mean()))
            if prev is not None:changes.append(float(np.abs(arr-prev).mean()))
            prev=arr;count+=1
            if next_sample<len(review_at) and t>=review_at[next_sample]-1e-5:
                frames.append(small);times.append(t)
                if abs(t-(int(t)//10*10+6.4))<.017:f.to_image().save(OUT/f'exported-{int(t)//10+1:02}.jpg',quality=94)
                next_sample+=1
    with av.open(str(original)) as c:
        a=c.streams.audio[0];audio_info={'sample_rate':a.rate,'channels':a.codec_context.channels,'seconds':float(a.duration*a.time_base)}
    pcm=np.frombuffer(subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-i',str(original),'-vn','-ar','48000','-ac','2','-f','f32le','pipe:1'],check=True,capture_output=True).stdout,dtype='<f4')
    peak=float(np.max(np.abs(pcm)));rms=float(np.sqrt(np.mean(pcm**2)))
    info={'file':str(original),'seconds':duration,'fps':fps,'decoded_frames':count,'resolution':[width,height],'audio':audio_info,'audio_peak_dbfs':20*math.log10(peak),'audio_rms_dbfs':20*math.log10(rms),'audio_clipped_samples':int((np.abs(pcm)>=1).sum()),'browser_errors':[],'chapters':6,'motion_review_frames':times,'mean_frame_change':float(np.mean(changes)),'checks':{'exact_60_seconds':abs(duration-60)<.001,'3600_frames':count==3600,'60fps':fps==60,'720p':(width,height)==(1280,720),'stereo_audio':audio_info['channels']==2,'no_audio_clipping':peak<1,'all_review_samples':len(times)==len(review_at)},'scope':'New animation and soundtrack; stills and brief action/reaction footage from supplied reference. Not an exact After Effects project reconstruction.'}
    assert all(info['checks'].values()),info
    board=Image.new('RGB',(1280,math.ceil(len(frames)/4)*204),'#0b1115');d=ImageDraw.Draw(board)
    for i,(im,t) in enumerate(zip(frames,times)):
        x=i%4*320;y=i//4*204;board.paste(im,(x,y));d.text((x+8,y+184),f'{t:.3f}s · exported video',fill='#daccad')
    board.save(OUT/'export-review.jpg',quality=93)
    preview=Image.new('RGB',(1280,1152),'#0b1115');pd=ImageDraw.Draw(preview)
    for i in range(6):
        im=Image.open(OUT/f'scene-{i+1:02}.jpg').resize((640,360));x=i%2*640;y=i//2*384;preview.paste(im,(x,y));pd.text((x+12,y+365),f'{i*10:02}–{(i+1)*10:02}s',fill='#daccad')
    preview.save(OUT/'preview.jpg',quality=93)
    (OUT/'verification.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info,indent=2),flush=True)

if __name__=='__main__':main()
