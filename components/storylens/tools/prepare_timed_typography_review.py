"""Create a review copy with linked sizing and word-timed original typography."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from hinglish_captions.project import cues_from_data
    from hinglish_captions.report import write_report
    source=ROOT/'output/captions/restored-original-typography/Rog Music/caption-project.json'
    data=json.loads(source.read_text(encoding='utf-8'))
    folder=ROOT/'output/captions/linked-timed-typography/Rog Music'
    (folder/'media').mkdir(parents=True,exist_ok=True)
    video=folder/'media/source.mp4'
    if not video.exists():os.link(source.parent/data['source_relative'],video)
    scale=float(data.get('size',1))
    data['media']['path']=str(video.resolve())
    data.update(style='typography_5',font='template',word_visibility='styled_spoken',position=.22,size=scale,
                cue_layouts=[{'x':.5,'y':.22,'size':scale} for _ in data['cues']])
    (folder/'caption-project.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    files=[('Open Premiere / Resolve XML','CAPTIONED_SEQUENCE.xml'),('Editable SRT','captions.srt'),
           ('Styled ASS','captions.ass'),('Roman Hinglish transcript','transcript.txt')]
    write_report(folder/'report.html','Rog Music.mp4','media/source.mp4',cues_from_data(data['cues']),data['style'],files,data)
    print(str(folder/'report.html'))


if __name__=='__main__':main()
