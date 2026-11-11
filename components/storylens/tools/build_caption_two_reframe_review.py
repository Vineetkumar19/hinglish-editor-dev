"""Build an editable review using the replacement reference's native word events."""
from pathlib import Path
import json,subprocess,shutil
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_captions.caption_two import reference_cues
from hinglish_captions.project import write_project
from hinglish_captions.report import write_report
from hinglish_cut.media import probe
from tools.study_caption_two_replacement import SOURCE

def main():
    folder=Path('output/captions/caption2-glow-cursor-review').resolve();folder.mkdir(parents=True,exist_ok=True)
    source=folder/'caption2-reference-audio.mp4'
    subprocess.run([get_ffmpeg_exe(),'-v','error','-nostdin','-y','-f','lavfi','-i','color=black:s=720x1280:r=30:d=50','-stream_loop','-1','-i',str(SOURCE),'-map','0:v','-map','1:a','-t','50','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','24','-c:a','aac',str(source)],check=True)
    shutil.copy2(SOURCE,folder/'reference-video.mp4')
    from hinglish_captions.core import CaptionCue,CaptionWord
    cues=[]
    for offset in (0,16.9,33.8):
        for cue in reference_cues():
            words=tuple(CaptionWord(w.text,w.start+offset,min(50,w.end+offset)) for w in cue.words if w.start+offset<50)
            if words:cues.append(CaptionCue(words,cue.start+offset,min(50,cue.end+offset)))
    p=write_project(folder/'caption-project.json',probe(source),cues,'caption_2','source',source.name,position=732/1280)
    p.update(review_draft=False,owner_approved=True,preview_stale=True,word_visibility='phrase',reference_grouping=True,review_notes='Owner-approved glow/shadow typography and source word groups, with cursor removed.')
    (folder/'caption-project.json').write_text(json.dumps(p,indent=2),'utf-8')
    write_report(folder/'report.html','English · Caption 2 replacement review',source.name,cues,'caption_2',[('Reference video','reference-video.mp4')],p)
    print(folder/'report.html')

if __name__=='__main__':main()
