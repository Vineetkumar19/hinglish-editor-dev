"""A short native-editor review of the approved first style's motion changes."""
import json
import subprocess
import argparse
from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_cut.model import Media
from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.kinetic_gold import sample_cues
from hinglish_captions.project import write_project
from hinglish_captions.report import write_report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--vertical',action='store_true')
    vertical=parser.parse_args().vertical
    source=Path('output/captions/kinetic-gold-50s-review/caption-style-one-50s.mp4').resolve()
    name='kinetic-gold-vertical-motion-review' if vertical else 'kinetic-gold-premiere-motion-review'
    width,height=(720,1280) if vertical else (1280,720)
    folder=(Path('output/captions')/name).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/('vertical-motion-10s.mp4' if vertical else 'motion-review-10s.mp4')
    subprocess.run([get_ffmpeg_exe(),'-nostdin','-v','error','-y','-ss','10.75','-i',str(source),
                    '-t','10','-vf',f'scale={width}:{height},setsar=1','-c:v','libx264','-threads','2','-preset','ultrafast',
                    '-crf','24','-c:a','aac',str(target)],check=True)
    cues=[]
    for c in sample_cues():
        if c.start<10.75 or c.start>=20.75:continue
        words=tuple(CaptionWord(w.text,round(w.start-10.75,6),round(min(10,w.end-10.75),6)) for w in c.words if w.start<20.75)
        cues.append(CaptionCue(words,round(c.start-10.75,6),round(min(10,c.end-10.75),6)))
    from hinglish_cut.media import probe
    media=probe(target)
    p=write_project(folder/'caption-project.json',media,cues,'kinetic_gold_draft','source',target.name,position=.5)
    p.update(review_draft=True,word_visibility='phrase',preview_stale=True,
             review_notes='10-second Premiere motion check. Editable foreground words; shadows and brush strokes on a separate transparent layer.')
    (folder/'caption-project.json').write_text(json.dumps(p,indent=2),'utf-8')
    write_report(folder/'report.html','Caption style one - '+('vertical' if vertical else 'Premiere')+' motion check',target.name,cues,p['style'],[],p)
    print(folder/'report.html')

if __name__=='__main__':main()
