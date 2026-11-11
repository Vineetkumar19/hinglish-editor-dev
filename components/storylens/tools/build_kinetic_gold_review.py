"""Build only the first owner's reference as a ten-second review project."""
import json
import subprocess
from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_cut.model import Media
from hinglish_captions.kinetic_gold import sample_cues
from hinglish_captions.project import write_project
from hinglish_captions.report import write_report

def main():
    source=Path('D:/Full Drive/Styles/Videos/Caption 08 - Kinetic Gold.mp4')
    folder=Path('output/captions/kinetic-gold-review-2').resolve();folder.mkdir(parents=True,exist_ok=True)
    (folder/'media').mkdir(exist_ok=True)
    ff=get_ffmpeg_exe()
    subprocess.run([ff,'-nostdin','-v','error','-y','-f','lavfi','-i','color=c=black:s=736x414:r=48:d=10.75','-i',str(source),'-t','10.75','-map','0:v','-map','1:a:0?','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','24','-c:a','aac',str(folder/'first-reference-preview.mp4')],check=True)
    subprocess.run([ff,'-nostdin','-v','error','-y','-i',str(source),'-t','10.75','-c','copy',str(folder/'original-reference.mp4')],check=True)
    media=Media('kinetic-gold-reference-one',str(folder/'first-reference-preview.mp4'),10.75,'48',736,414,2,48000)
    cues=[q for q in sample_cues() if q.start<10.75];project=write_project(folder/'caption-project.json',media,cues,'kinetic_gold_draft','source','first-reference-preview.mp4',position=.5)
    project.update(reference_source=str(source),review_draft=True,word_visibility='phrase',preview_stale=True,
        review_notes='First reference only. Caption typography and motion review; source stickers and decoration are not caption layers. Font identity is visually approximated. Horizontal maximum seven words, vertical four. Await owner approval before the second reference.')
    (folder/'caption-project.json').write_text(json.dumps(project,indent=2,ensure_ascii=False),'utf-8')
    write_report(folder/'report.html','First reference · review','first-reference-preview.mp4',cues,'kinetic_gold_draft',[('Original reference (first section)','original-reference.mp4')],project)
    print(folder/'report.html')

if __name__=='__main__':main()
