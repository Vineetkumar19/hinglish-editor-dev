"""One fifteen-second native Premiere validation sample of approved Caption 2."""
import json,subprocess
from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_captions.caption_two import reference_cues,profile
from hinglish_captions.project import write_project
from hinglish_captions.report import write_report
from hinglish_cut.media import probe

def main():
    root=Path(__file__).resolve().parents[1];folder=root/'output/captions/caption2-final-premiere-15s'
    folder.mkdir(parents=True,exist_ok=True);target=folder/'caption2-glow-15s.mp4'
    source=root/'output/captions/caption2-glow-cursor-review/caption2-reference-audio.mp4'
    subprocess.run([get_ffmpeg_exe(),'-v','error','-nostdin','-y','-i',str(source),'-t','15','-vf','setsar=1','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','24','-c:a','aac',str(target)],check=True)
    # End only on complete caption groups; the final .2s is the next cut boundary.
    cues=[c for c in reference_cues() if c.end<=15]
    p=write_project(folder/'caption-project.json',probe(target),cues,'caption_2','source',target.name,position=profile()['position'])
    p.update(review_draft=False,preview_stale=True,word_visibility='phrase',owner_approved=True,omit_source_video=True,review_notes='Cursor removed, restrained glow, shared .65 anchor and source video layer omitted. Fifteen-second Premiere check.')
    (folder/'caption-project.json').write_text(json.dumps(p,indent=2),'utf-8')
    write_report(folder/'report.html','English · Caption 2 · Premiere check',target.name,cues,'caption_2',[],p)
    print(folder/'report.html')

if __name__=='__main__':main()
