"""Refresh existing caption editors without changing saved text/style/timing."""
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
USER_FOLDER=ROOT/'output/captions/20261018-091908-b22ac7/001-0000-e11e1551-Rog Music'


def main():
    from hinglish_captions.project import cues_from_data
    from hinglish_captions.report import write_report
    backup=ROOT/'output/validation/caption-studio-editing/original-project'
    backup.mkdir(parents=True,exist_ok=True)
    for name in ('caption-project.json','report.html','captions.srt','captions.ass','CAPTIONED_SEQUENCE.xml','captioned-preview.mp4'):
        source=USER_FOLDER/name;target=backup/name
        if source.is_file() and not target.exists():
            shutil.copy2(source,target)
    count=0
    for path in (ROOT/'output/captions').rglob('caption-project.json'):
        data=json.loads(path.read_text(encoding='utf-8'));folder=path.parent
        cues=cues_from_data(data['cues'])
        files=[('Open Premiere / Resolve XML','CAPTIONED_SEQUENCE.xml'),('Editable SRT','captions.srt'),
               ('Styled ASS','captions.ass'),('Roman Hinglish transcript','transcript.txt')]
        if (folder/'captioned-preview.mp4').is_file():files.append(('Captioned MP4','captioned-preview.mp4'))
        write_report(folder/'report.html',Path(data['media']['path']).name,data['source_relative'],cues,data['style'],files,data)
        count+=1
    print(json.dumps({'studios_refreshed':count,'saved_project_unchanged':(USER_FOLDER/'caption-project.json').read_bytes()==(backup/'caption-project.json').read_bytes(),'backup':str(backup)},indent=2),flush=True)


if __name__=='__main__':main()
