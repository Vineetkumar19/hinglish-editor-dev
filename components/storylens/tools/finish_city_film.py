from pathlib import Path
import json, subprocess
import av, numpy as np
from PIL import Image
from imageio_ffmpeg import get_ffmpeg_exe

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/motion/chatgpt-madurai-after-ten-20261024'
target=OUT/'MOTION_GRAPHICS.mp4'
subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(OUT/'FILM-SILENT.mp4'),'-i',str(OUT/'soundtrack.wav'),'-c:v','copy','-c:a','aac','-b:a','192k','-t','50','-movflags','+faststart',str(target)],check=True)
timings=json.loads((OUT/'timings.json').read_text())
indices=[s['start']+int((s['end']-s['start'])*f) for s in timings for f in (.18,.5,.82)]
samples={}
with av.open(str(target)) as container:
    v=container.streams.video[0]
    summary={'width':v.width,'height':v.height,'fps':float(v.average_rate),'duration':float(container.duration/av.time_base),'audio_streams':len(container.streams.audio)}
    count=0
    for i,frame in enumerate(container.decode(v)):
        count+=1
        if i in indices:
            samples[i]=frame.to_ndarray(format='rgb24')
    summary['decoded_frames']=count
sheet=Image.new('RGB',(720,426*6))
changes=[]
for row in range(6):
    pics=[samples[k] for k in indices[row*3:row*3+3]]
    for col,pic in enumerate(pics):sheet.paste(Image.fromarray(pic).resize((240,426)),(col*240,row*426))
    # Ignore the lower captions; measure changes in the illustrated scene itself.
    a,b=pics[0][300:1040],pics[-1][300:1040]
    changes.append(round(float(np.mean(np.max(np.abs(a.astype(float)-b.astype(float)),axis=2)>15)),4))
sheet.save(OUT/'review/rendered-motion-frames.jpg',quality=93)
Image.fromarray(samples[indices[1]]).save(OUT/'poster.jpg',quality=95)
summary['scene_foreground_changed_pixel_fractions']=changes
summary['validation']='Decoded full exported MP4; inspected sampled scene frames and movement sequences. Creative quality is pending owner review. No Storylens engine replacement or local-model improvement is claimed.'
summary['authorship']='ChatGPT: visual direction, SVG artwork, animation and sound edit. Owner: supplied script. Remotion: rendering. Local Qwen was not used for this comparison version.'
summary['sound']='Existing credited instrumental music and 15 timed effects. No voice narration.'
summary['output']=str(target)
(OUT/'render-verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Madurai / After Ten — ChatGPT version</title><style>body{margin:0;background:#0c1525;color:#fff2d2;font:16px system-ui;text-align:center}main{max-width:900px;margin:auto;padding:18px}h1{font-size:22px;margin:0 0 6px}p{color:#afbfcb;margin:8px 0 16px}video{display:block;max-height:82vh;max-width:100%;margin:auto;border-radius:9px}a{color:#ffcc6a}</style><main><h1>Madurai / After Ten</h1><p>ChatGPT-authored · 50 seconds · Remotion · music and sound effects</p><video controls playsinline preload="auto" poster="poster.jpg" src="MOTION_GRAPHICS.mp4"></video><p>Your script, illustrated city scenes, object animation and camera movement.<br>No voice narration. <a href="CREDITS.txt">Audio credits</a></p></main></html>''',encoding='utf-8')
assert summary['decoded_frames']==1500 and summary['audio_streams']==1
assert all(x>.015 for x in changes),changes
print(json.dumps(summary,indent=2))
