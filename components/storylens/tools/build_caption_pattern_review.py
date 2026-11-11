"""Ten-second live editor regression with saved patterns and editable wording."""
import json,subprocess
from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.project import write_project
from hinglish_captions.report import write_report
from hinglish_cut.media import probe


def main():
    root=Path(__file__).resolve().parents[1];folder=root/'output/captions/caption-pattern-review-10s';folder.mkdir(parents=True,exist_ok=True)
    video=folder/'pattern-review.mp4'
    subprocess.run([get_ffmpeg_exe(),'-v','error','-nostdin','-y','-f','lavfi','-i','color=black:s=720x1280:r=30:d=10','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t','10','-c:a','aac','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','30',str(video)],check=True)
    originals=['Kaafi Overthinking ke baad','kaam shuru karne ke Baad aati hai','Confidence','Why one single post','your Content is failing']
    cues=[]
    for i,text in enumerate(originals):
        words=text.split();start=i*2
        cues.append(CaptionCue(tuple(CaptionWord(w,start+j*.9/len(words),start+(j+1)*.9/len(words)) for j,w in enumerate(words)),start,start+2,text,i))
    p=write_project(folder/'caption-project.json',probe(video),cues,'kinetic_gold_draft','source',video.name)
    p.update(preview_stale=True,demo=False,demo_background='black',omit_source_video=True)
    (folder/'caption-project.json').write_text(json.dumps(p,indent=2),'utf-8')
    write_report(folder/'report.html','Template script-change check',video.name,cues,'kinetic_gold_draft',[],p)
    print(folder/'report.html')


if __name__=='__main__':main()
