"""Read-only checks of all boundary options in the recorded Romanized KKR campaign."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    from hinglish_cut.model import Word
    from hinglish_shorts.source import open_video
    from hinglish_publish.campaign_boundaries import candidates
    from hinglish_publish.campaign import valid_picks
    folder=ROOT/'output/campaigns/chat-b4969419cc3f476f-1f68d8be'
    state=json.loads((folder/'campaign.json').read_text('utf-8'))
    words=[Word(**w) for w in json.loads((folder/'words.json').read_text('utf-8'))]
    duration=open_video(state['source']).duration
    rows=[]
    previous=[]
    for clip in state['clips']:
        future=[c['pick'] for c in state['clips'] if c['index']>clip['index']]
        options=candidates(words,clip['pick'],duration,state['max_seconds_exclusive'],previous,future)
        assert options,clip['index']
        assert any(c['original_moment'] for c in options)
        for candidate in options:
            valid_picks(previous+[{'pieces':[[candidate['start'],candidate['end']]]}]+future,duration,60)
        rows.append({'clip':clip['index'],'candidate_count':len(options),'original_moment_preserved':True,
                     'all_non_overlapping_and_within_source':True})
        previous.append(clip['pick'])
    result={'source':state['source'],'read_only':True,'model_inference':False,'renders':0,'uploads':0,'clips':rows}
    (ROOT/'output/campaigns/candidate-regression.json').write_text(json.dumps(result,indent=2),'utf-8')
    print(json.dumps(result,indent=2))
