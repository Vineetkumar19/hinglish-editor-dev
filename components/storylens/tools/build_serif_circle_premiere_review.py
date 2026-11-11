"""Isolated fifteen-second owner-requested Premiere validation sample."""
import json, subprocess
from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_captions.serif_circle import sample_cues
from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.project import write_project
from hinglish_captions.report import write_report
from hinglish_cut.media import probe

def main():
    root=Path(__file__).resolve().parents[1]
    folder=root/'output/captions/serif-circle-premiere-15s-review'
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/'english-serif-circle-15s.mp4'
    subprocess.run([get_ffmpeg_exe(),'-nostdin','-v','error','-y','-i',str(root/'output/captions/serif-circle-english-v2-review/english-caption-preview.mp4'),'-t','15','-vf','setsar=1','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','24','-c:a','aac',str(target)],check=True)
    cues=[]
    for c in sample_cues():
        if c.start>=15:break
        words=tuple(CaptionWord(w.text,w.start,min(15,w.end)) for w in c.words if w.start<15)
        cues.append(CaptionCue(words,c.start,min(15,c.end)))
    p=write_project(folder/'caption-project.json',probe(target),cues,'serif_circle_draft','source',target.name,position=.65625)
    p.update(review_draft=True,word_visibility='phrase',preview_stale=True,review_notes='Owner requested fifteen-second native Premiere validation. Second style remains draft.')
    (folder/'caption-project.json').write_text(json.dumps(p,indent=2),'utf-8')
    write_report(folder/'report.html','English · Serif Circle · 15-second Premiere test',target.name,cues,p['style'],[],p)
    print(folder/'report.html')

if __name__=='__main__':main()
