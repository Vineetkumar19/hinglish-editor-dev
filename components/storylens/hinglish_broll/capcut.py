"""Describe a fresh editable CapCut review project, including the options deck."""
from pathlib import Path
import json


def spec(project_file,include_options=True):
    from .timeline import parse_xmeml
    from .options import rows
    file=Path(project_file);p=json.loads(file.read_text('utf-8'));t=parse_xmeml(p['timeline']['xml_path'])
    if Path(t.xml_path).name!='source-timeline.xml' or len(t.clips)!=1:return None
    if any(s.get('scale',100)!=100 for s in p['slots']):return None
    micro=lambda n:round(n*1e6)
    clips=[{'path':c.path,'start':micro(c.start),'source_in':micro(c.source_in),
            'duration':micro(c.end-c.start)} for c in t.clips]
    overlays=[{'path':str((file.parent/s['clip']).resolve()),'start':micro(s['start']),
               'source_in':micro(s.get('source_in',0)),'duration':micro(s['end']-s['start'])}
              for s in p['slots'] if s.get('clip')]
    options=[];position=t.duration+1
    for row in rows(p,file.parent) if include_options else []:
        length=min(4.,row['source_duration']-row['source_in'])
        if length<=0:continue
        options.append({'path':row['path'],'start':micro(position),'source_in':micro(row['source_in']),
                        'duration':micro(length),'name':row['name']})
        position+=length+.25
    return {'fps':float(t.fps),'width':t.width,'height':t.height,'duration':micro(max(t.duration,position if options else 0)),
            'clips':clips,'overlays':overlays,'options':options,'broll':True,'selected_only':not include_options}
