"""Render the reviewed cricAddicting patterns as a new, deterministic 60-second study."""
import argparse, html, json, math, subprocess, sys, time, wave
from pathlib import Path
from io import BytesIO
from fractions import Fraction
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from hinglish_shorts.render import _Video
from imageio_ffmpeg import get_ffmpeg_exe
OUT=ROOT/'output/reference-analysis/crick-edit-editing-style/demo'
FPS=60
SHOTS=[
    ('The first page','A perspective book leaf turns, settles, then an ink aperture reveals the portrait. Warm desk light and a slow camera push.'),
    ('A force of nature','A real player silhouette sharpens in front of large red lettering. The heading and script accent arrive on separate beats.'),
    ('Anatomy of pace','Three readable editorial notes receive separate coloured highlight sweeps. A restrained push keeps the evidence readable.'),
    ('The archive','A physical CRT frame holds static, flickering type and a dark beat before footage plays inside the curved screen.'),
    ('More than a moment','Irregular torn-paper masks reveal two photographs at different depths, over a ghosted photographic background. An ink circle draws around the story.'),
    ('Release and reaction','A rounded film gate preserves the broadcast frame. Action gives way to a reaction hold, then a clean closing title.')]

def soundtrack():
    rate=48000;n=rate*60;t=np.arange(n,dtype=np.float32)/rate
    bed=np.zeros(n,dtype=np.float32)
    # Original instrumental bed, no reference voice/music is reused.
    chords=[(110,130.81,164.81),(87.31,110,130.81),(130.81,164.81,196),(98,123.47,146.83)]
    for start in range(0,60,6):
        duration=min(7.5,60-start);tt=np.arange(int(rate*duration),dtype=np.float32)/rate
        env=np.minimum(1,tt/1.2)*np.minimum(1,(duration-tt)/1.5)
        chord=chords[(start//6)%4];sig=np.zeros_like(tt)
        for j,f in enumerate(chord):
            sig+=(np.sin(2*np.pi*f*tt+.02*np.sin(tt*1.7+j))+.2*np.sin(2*np.pi*2*f*tt))/len(chord)
        bed[start*rate:start*rate+len(tt)]+=sig*env*.048
    for k in range(80):
        start=k*.75;tt=np.arange(int(.55*rate),dtype=np.float32)/rate
        length=min(len(tt),n-int(start*rate));sig=np.sin(2*np.pi*(55*tt+12*.02*(1-np.exp(-tt/.02))))*np.exp(-tt*9)*.052
        bed[int(start*rate):int(start*rate)+length]+=sig[:length]
        if k%4==2:
            tt=np.arange(int(1.7*rate),dtype=np.float32)/rate;f=[440,523.25,659.25,587.33][(k//4)%4]
            note=(np.sin(2*np.pi*f*tt)+.24*np.sin(2*np.pi*2*f*tt))*np.exp(-tt*3)*np.minimum(1,tt/.014)*.014
            length=min(len(tt),n-int(start*rate));bed[int(start*rate):int(start*rate)+length]+=note[:length]
    stereo=np.stack([bed,bed.copy()]);receipts=[]
    def sfx(category,name,at,gain,seconds=None):
        path=ROOT/'library/sfx-pro'/category/(name+'.mp3')
        cmd=[get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-i',str(path),'-ar',str(rate),'-ac','2']
        if seconds:cmd+=['-t',str(seconds)]
        cmd+=['-f','f32le','pipe:1']
        samples=np.frombuffer(subprocess.run(cmd,check=True,capture_output=True).stdout,dtype='<f4').reshape(-1,2).T.copy()
        if samples.shape[1]==0:return
        samples*=gain/max(.03,float(np.max(np.abs(samples))))
        fade=min(2400,samples.shape[1]//3);samples[:,-fade:]*=np.linspace(1,0,fade)
        offset=round(at*rate);length=min(samples.shape[1],n-offset);stereo[:,offset:offset+length]+=samples[:,:length]
        receipts.append({'at':at,'source':str(path.relative_to(ROOT)),'peak_gain':gain,'seconds':length/rate})
    for at in [.35,40.2,42]:sfx('whoosh','paper_slide_mixkit1530',at,.13,2)
    for at in [9.65,19.65,39.65,49.65]:sfx('whoosh','short_transition_sweep_mixkit175',at,.13,1)
    for at in [10.05,50.05]:sfx('impact','cinematic_whoosh_deep_impact_mixkit1143',at,.16,3)
    for at in [20.65,22.55,24.45]:sfx('whoosh','fast_small_sweep_transition_mixkit166',at,.055,.7)
    sfx('glitch','glitch_static_mixkit1457',30.05,.09,1.8)
    sfx('glitch','small_electric_glitch_mixkit2595',31.0,.09,.5)
    sfx('glitch','intro_text_glitch_mixkit2950',31.8,.10,.5)
    sfx('riser','cinematic_rumbling_swell_mixkit2664',46.7,.105,3)
    envelope=np.minimum(1,t/1.4)*np.minimum(1,(60-t)/1.7)
    stereo*=envelope;stereo=np.tanh(stereo*1.5)/1.5
    peak=float(np.max(np.abs(stereo)));rms=float(np.sqrt(np.mean(stereo**2)))
    with wave.open(str(OUT/'soundtrack.wav'),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes((stereo.T*32767).astype('<i2').tobytes())
    (OUT/'soundtrack.json').write_text(json.dumps({'music':'Original procedural minor-key instrumental bed','reference_audio_reused':False,'effects':receipts,'peak_dbfs':20*math.log10(peak),'rms_dbfs':20*math.log10(rms)},indent=2),encoding='utf-8')
    return stereo.astype(np.float32)

def main(stills=False,chapter=None):
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True,exist_ok=True)
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True,args=['--allow-file-access-from-files'])
        page=browser.new_page(viewport={'width':1280,'height':720},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((ROOT/'hinglish_motion/web/crick_demo.html').as_uri())
        page.evaluate('d => window.mgLoad(d)',{'assets':(OUT/'assets').as_uri()})
        page.evaluate('document.fonts.ready.then(() => true)')
        def frame(t):
            page.evaluate('t => window.mgSeek(t)',t)
            return Image.open(BytesIO(page.screenshot(type='jpeg',quality=95))).convert('RGB')
        board=Image.new('RGB',(1280,1152),'#0b1115');d=ImageDraw.Draw(board)
        for i,(name,description) in enumerate(SHOTS):
            if chapter and i+1!=chapter:continue
            im=frame(i*10+6.4);im.save(OUT/f'scene-{i+1:02}.jpg',quality=94)
            x=i%2*640;y=i//2*384;board.paste(im.resize((640,360)),(x,y));d.text((x+15,y+364),f'{i*10:02}–{i*10+10:02}s  {name}',fill='#eedfbd')
            contact=Image.new('RGB',(1280,406),'#0b1115');cd=ImageDraw.Draw(contact)
            for j,s in enumerate([.1,.65,1.4,2.6,4,6,8.4,9.75]):
                small=frame(i*10+s).resize((320,180));xx=j%4*320;yy=j//4*203;contact.paste(small,(xx,yy));cd.text((xx+8,yy+185),f'{i*10+s:.2f}s',fill='white')
            contact.save(OUT/f'scene-{i+1:02}-motion.jpg',quality=90)
        if not chapter:board.save(OUT/'preview.jpg',quality=93)
        if errors:raise ValueError(errors)
        print('Six compositions and 48 motion checkpoints prepared',flush=True)
        if stills:browser.close();return
        target=OUT/(f'chapter-{chapter:02}.mp4' if chapter else 'CRICK_EDIT_60S.mp4')
        writer=_Video(target,1280,720,Fraction(FPS),'libx264',audio=True)
        writer.stream.thread_count=2
        started=time.time()
        try:
            start=(chapter-1)*10 if chapter else 0;end=chapter*10 if chapter else 60
            for n in range(FPS*start,FPS*end):
                writer.write(np.asarray(frame(n/FPS)))
                if n%(FPS*5)==0:print(f'Rendered {n/FPS:.0f}/60 seconds ({time.time()-started:.1f}s elapsed)',flush=True)
            writer.write_audio(soundtrack()[:,start*48000:end*48000]);writer.finish()
        except BaseException:writer.abort();raise
        finally:browser.close()
    if errors:raise ValueError(errors)
    if chapter:return
    shots=[{'start':i*10,'end':(i+1)*10,'name':name,'motion':description} for i,(name,description) in enumerate(SHOTS)]
    (OUT/'timeline.json').write_text(json.dumps(shots,indent=2),encoding='utf-8')
    tiles=''.join(f'<figure><a href="scene-{i+1:02}-motion.jpg"><img src="scene-{i+1:02}.jpg"></a><figcaption><b>{i*10:02}–{(i+1)*10:02}s · {html.escape(name)}</b><br>{html.escape(description)}</figcaption></figure>' for i,(name,description) in enumerate(SHOTS))
    body='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>cricAddict · one minute</title><style>body{background:#091116;color:#ddd7c9;font:17px/1.65 system-ui;max-width:1200px;margin:auto;padding:35px}h1{font:52px Georgia;color:#eadabb}video{width:100%;border-radius:12px;box-shadow:0 20px 80px #0007}a{color:#d9b573}main{display:grid;grid-template-columns:1fr 1fr;gap:25px;margin-top:30px}figure{margin:0}img{width:100%;border-radius:7px}figcaption{padding:10px 0;font-size:15px}small{color:#aaa}@media(max-width:700px){main{grid-template-columns:1fr}body{padding:16px}h1{font-size:36px}}</style><small>cricAddict · VISUAL + SOUND STUDY</small><h1>The art of pace.</h1><p>One minute. Six distinct scene structures, built from the editing patterns observed across your nine references.</p><video src="CRICK_EDIT_60S.mp4" controls playsinline preload="metadata" poster="scene-02.jpg"></video><p>60 seconds · 1280 × 720 · 60fps · stereo. Click a chapter image to inspect eight moments of its animation.</p><main>'''+tiles+'''</main><p>This is a newly animated style study, using stills and short silent footage excerpts from the Dale Steyn reference you supplied. The book, typography, notes, CRT frame, masks, camera movement and soundtrack were created for this preview. Editorial notes are chapter ideas, not a claimed published article or cricket statistics. The TV and film-window action is reference footage, not AI-generated cricket.</p><p><a href="assets/provenance.json">Image and footage sources</a> · <a href="soundtrack.json">Sound sources</a> · <a href="verification.json">Export checks</a> · <a href="../report.html">Reference analysis</a></p></html>'''
    (OUT/'report.html').write_text(body,encoding='utf-8')
    print('Complete: '+str(OUT/'CRICK_EDIT_60S.mp4'),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stills',action='store_true');parser.add_argument('--chapter',type=int,choices=range(1,7));args=parser.parse_args();main(args.stills,args.chapter)
