"""Apply owner feedback: remove warning cards and match soft bloom/shadow."""
import json
from pathlib import Path

def refine():
    path=Path(__file__).resolve().parents[1]/'hinglish_captions/caption_two_reference.json'
    p=json.loads(path.read_text('utf-8'));p['layout_revision']=10
    p['appearance']={'shadow_y':3,'shadow_blur':3,'shadow_opacity':.45,'lime_glow':[[4,.08],[1,.06]],'white_glow':[[2,.035]]}
    p['cursor']={'enabled':False,'times':[],'duration':2,'click_at':.95,'click_seconds':.22,'fade_at':1.55,'description':'Removed at owner request; no cursor or click animation.'}
    p['position']=.65
    for r in p['recipes']:r.pop('position',None)
    p['recipes'][1]['tracking']=-.065
    p['recipes'][1].update(plane_size=70,plane_dx=60,plane_dy=-12,plane_angle=-18)
    for r in p['recipes']:
        r['plane']=False
        if r['text']=='even if You record you are unsure':r['rows'][-1]['regular']=True
    cards=next((i for i,r in enumerate(p['recipes']) if any(row['role']=='card' for row in r['rows'])),None)
    if cards is not None:
        old=p['recipes'][cards]
        one=dict(old,text='what to say?',starts=old['starts'][:3],end=old['starts'][3],motion='out',main_size=112,rows=[{'words':[0,1],'role':'support','align':'top_left','size':52},{'words':[2],'role':'main'}])
        two=dict(old,text='how it turn to revenue?',start=old['starts'][3],starts=old['starts'][3:],motion='out',main_size=112,rows=[{'words':[0,1,2,3],'role':'support','align':'top_left','size':42},{'words':[4],'role':'main'}])
        p['recipes'][cards:cards+1]=[one,two]
    p['approval'].update(status='approved',date='2026-10-23',latest_feedback='Remove the mouse cursor; rest is perfect. Check in Premiere Pro. Native verification pending.')
    path.write_text(json.dumps(p,indent=2)+'\n','utf-8')

if __name__=='__main__':refine()
