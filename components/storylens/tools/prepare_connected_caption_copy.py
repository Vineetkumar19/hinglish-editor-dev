"""Recover visible screenshot choices into a separate editable copy."""
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'output/captions/20261018-091908-b22ac7/001-0000-e11e1551-Rog Music'
TARGET=ROOT/'output/captions/connected-caption-studio/Rog Music'


def main():
    from hinglish_captions.project import cues_from_data
    from hinglish_captions.report import write_report
    TARGET.mkdir(parents=True,exist_ok=True);(TARGET/'media').mkdir(exist_ok=True)
    path=TARGET/'caption-project.json'
    if not path.exists():
        data=json.loads((SOURCE/'caption-project.json').read_text(encoding='utf-8'))
        shutil.copy2(SOURCE/'media/source.mp4',TARGET/'media/source.mp4')
        data['media']['path']=str((TARGET/'media/source.mp4').resolve())
        data.update(font='bahnschrift',word_visibility='spoken',position=.4,size=.55)
        data['cue_layouts']=[{'x':.5,'y':.4,'size':.55} for cue in data['cues']]
        # These colors/font are visible in the user's supplied screenshot.
        # Placement is an approximate reconstruction, not recovered browser state.
        data['word_colors'][0][2]='#FFD400';data['word_colors'][1][0]='#FFD400'
        data['editor_recovery']={'source_project':str(SOURCE/'caption-project.json'),
            'exact':['font: Bahnschrift','dekhta: yellow','Kissi: yellow'],
            'approximate':['40% vertical position','55% size from the previous minimum slider position'],
            'original_chrome_tab_untouched':True}
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    data=json.loads(path.read_text(encoding='utf-8'))
    files=[(label,name) for label,name in [('Captioned MP4','captioned-preview.mp4'),('Editable SRT','captions.srt'),('Styled ASS','captions.ass'),('Open Premiere / Resolve XML','CAPTIONED_SEQUENCE.xml')] if (TARGET/name).is_file()]
    write_report(TARGET/'report.html','Rog Music.mp4','media/source.mp4',cues_from_data(data['cues']),data['style'],files,data)
    print('http://127.0.0.1:8765/caption-output/connected-caption-studio/Rog%20Music/report.html',flush=True)


if __name__=='__main__':main()
