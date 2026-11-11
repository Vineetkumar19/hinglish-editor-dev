"""Owner-requested fifty-second browser review; only reference style one."""
import json
import subprocess
from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_cut.model import Media
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.kinetic_gold import sample_cues
from hinglish_captions.project import write_project
from hinglish_captions.report import write_report

def main():
    source=Path('D:/Full Drive/Styles/Videos/Caption 08 - Kinetic Gold.mp4')
    folder=Path('output/captions/kinetic-gold-50s-review').resolve();folder.mkdir(parents=True,exist_ok=True);(folder/'media').mkdir(exist_ok=True)
    ff=get_ffmpeg_exe()
    subprocess.run([ff,'-nostdin','-v','error','-y','-f','lavfi','-i','color=c=black:s=736x414:r=48:d=50','-stream_loop','2','-i',str(source),'-t','50','-map','0:v','-map','1:a:0?','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','24','-c:a','aac',str(folder/'caption-style-one-50s.mp4')],check=True)
    subprocess.run([ff,'-nostdin','-v','error','-y','-stream_loop','2','-i',str(source),'-t','50','-c','copy',str(folder/'original-reference.mp4')],check=True)
    cues=[]
    for repeat in range(3):
        shift=repeat*21.666667
        for cue in sample_cues():
            if cue.start+shift>=50:continue
            words=tuple(CaptionWord(w.text,round(w.start+shift,6),round(min(50,w.end+shift),6)) for w in cue.words if w.start+shift<50)
            cues.append(CaptionCue(words,round(cue.start+shift,6),round(min(50,cue.end+shift),6)))
    media=Media('kinetic-gold-50s-review',str(folder/'caption-style-one-50s.mp4'),50,'48',736,414,2,48000)
    project=write_project(folder/'caption-project.json',media,cues,'kinetic_gold_draft','source','caption-style-one-50s.mp4',position=.5)
    project.update(review_draft=True,word_visibility='phrase',reference_source=str(source),preview_stale=True,
        review_notes='Reference one only. Original 21.67-second narration repeats to fill the requested 50-second browser review. Caption layers only; no corner decorations. Compact support gaps; Perfect and Saal are separate slides. Font identity and full frame parity remain under review; not approved.')
    (folder/'caption-project.json').write_text(json.dumps(project,indent=2,ensure_ascii=False),'utf-8')
    write_report(folder/'report.html','Caption style one · 50-second review','caption-style-one-50s.mp4',cues,'kinetic_gold_draft',[('Original reference','original-reference.mp4')],project)
    (folder/'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>Storylens · Caption style one comparison</title>
<style>body{margin:0;padding:28px;background:#111315;color:#f1f2f4;font:15px Arial}header{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}h1{font-size:22px;margin:0}p{color:#aeb7c1}a,button{color:white;background:#28313c;border:1px solid #455262;border-radius:8px;padding:12px 16px;text-decoration:none;cursor:pointer}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}video{width:100%;background:black;border-radius:10px}h2{font-size:16px;font-weight:500}.controls{display:flex;gap:12px;align-items:center;margin-top:24px}input{flex:1}output{font-variant-numeric:tabular-nums;min-width:110px}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>
<header><h1>Caption style one · review</h1><a href="report.html">Open Caption Studio</a></header>
<p>Original reference beside the recreated caption layers. The 21.7-second reference repeats for this 50-second preview.</p>
<div class="pair"><section><h2>Original reference</h2><video id="original" src="original-reference.mp4" playsinline></video></section><section><h2>Recreated captions · draft</h2><video id="replica" src="captioned-preview.mp4" muted playsinline></video></section></div>
<div class="controls"><button id="play">Play both</button><button id="prev" aria-label="Previous frame">−1 frame</button><button id="next" aria-label="Next frame">+1 frame</button><input aria-label="Comparison time" id="seek" type="range" min="0" max="50" step="0.0208333333" value="0"><output id="time">0.000 s</output></div>
<script>const a=document.querySelector('#original'),b=document.querySelector('#replica'),play=document.querySelector('#play'),seek=document.querySelector('#seek'),out=document.querySelector('#time');function pause(){a.pause();b.pause();play.textContent='Play both'}function jump(t){pause();a.currentTime=b.currentTime=Math.max(0,Math.min(49.979167,t));seek.value=t;out.textContent=Number(t).toFixed(3)+' s'}play.onclick=()=>{if(a.paused){b.currentTime=a.currentTime;Promise.all([a.play(),b.play()]).then(()=>play.textContent='Pause both')}else pause()};seek.oninput=()=>jump(+seek.value);document.querySelector('#prev').onclick=()=>jump(a.currentTime-1/48);document.querySelector('#next').onclick=()=>jump(a.currentTime+1/48);a.onended=pause;function tick(){if(!a.paused){if(Math.abs(a.currentTime-b.currentTime)>.045)b.currentTime=a.currentTime;seek.value=a.currentTime;out.textContent=a.currentTime.toFixed(3)+' s'}requestAnimationFrame(tick)}tick();</script>''','utf-8')
    print(folder/'report.html')

if __name__=='__main__':main()
