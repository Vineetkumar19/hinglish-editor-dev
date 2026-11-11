"""Replay recorded local choices without inference, editing, rendering or uploading."""
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    from hinglish_cut.model import Word
    from hinglish_shorts.source import open_video
    from hinglish_shorts.find import find_shorts
    from hinglish_shorts.settings import ShortsSettings
    from hinglish_publish.campaign import valid_picks
    folder=ROOT/'output/campaigns/chat-b4969419cc3f476f-f00b564b'
    state=json.loads((folder/'campaign.json').read_text('utf-8'))
    words=[Word(**w) for w in json.loads((folder/'words.json').read_text('utf-8'))]
    decisions=[json.loads(p.read_text('utf-8')) for p in sorted(folder.glob('decision-*.json'))]
    class Replay:
        name='Recorded local-model decisions'
        def json(self,system,data,schema,**options):
            for decision in decisions:
                if decision['system']==system and decision['input'].get('part')==data.get('part'):
                    return copy.deepcopy(decision['answer'])
            raise AssertionError('Replay must not make a new model call')
    video=open_video(state['source'])
    settings=ShortsSettings(count='7',min_length=20,max_length=58.4,pieces=1,device='cuda',brain='ollama')
    old,_,_=find_shorts(Replay(),words,settings,lambda _:None)
    before_error=None
    try:
        valid_picks([s.to_dict() for s in old],video.duration,60)
    except ValueError as error:
        before_error=str(error)
    fixed,_,_=find_shorts(Replay(),words,settings,lambda _:None,source_duration=video.duration,max_overlap=0)
    valid_picks([s.to_dict() for s in fixed],video.duration,60)
    receipt={'source_seconds':video.duration,'before_error':before_error,'read_only':True,
             'model_choices_replayed':True,'clip_count':len(fixed),
             'maximum_end_before':max(e for s in old for _,e in s.pieces),
             'maximum_end_after':max(e for s in fixed for _,e in s.pieces),
             'all_bounds_passed':True,'files_rendered':0,'uploads':0}
    (ROOT/'output/campaigns/bounds-regression.json').write_text(json.dumps(receipt,indent=2),'utf-8')
    print(json.dumps(receipt,indent=2))
    assert before_error=='Clip outside source duration'
    assert len(fixed)==7
