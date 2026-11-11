"""Apply the owner's replacement source compositions while retaining the old profile."""
import json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    folder=ROOT/'hinglish_captions'; path=folder/'caption_two_reference.json'
    backup=ROOT/'docs/caption-two-before-reframe-2026-10-23.json'
    if not backup.exists():shutil.copy2(path,backup)
    p=json.loads(backup.read_text('utf-8'))
    p.update(layout_revision=7,reference_grouping=True,header_min_words=0,main_max_words=2,green='#E1FF5D',approval={'status':'review','source':'family dinner ideas reference','vertical_grouping':'Owner explicitly selected Match this reference exactly on 23 October 2026'})
    p['motion'].update(text_seconds=.23,fade_seconds=.16,word_y=[[0,24],[.23,0]],word_scale=[[0,1],[.23,1]],blur=7)
    rows=p['recipes'];rows[2]['end']=136
    for r in rows:r['reference_layout']=True
    rows[0].update(header_fraction=.16,right_fraction=.20,top_lift=59,tracking=-.018,support_size=40)
    rows[0]['starts'][-2:]=[27,32]
    for r in rows[0]['rows']:
        if r['role']=='support':r['tracking']=-.075
        if r.get('align')=='bottom':r.update(size=45,dx=-7)
    rows[1].update(header_fraction=.16,plane=True)
    rows[1]['rows'][-1]['dx']=17
    rows[2].update(top_lift=85,main_size=125,main_offset=14)
    rows[2]['rows'][-1].update(size=60,dx=-45)
    rows[-1].update(main_size=116,tracking=-.03)
    rows[4]['rows']=[{'words':[0,1,2],'role':'card'},{'words':[3,4,5,6,7],'role':'card'}]
    rows[4]['motion']='focus'
    def make(text,starts,end,rows,**kw):return dict(text=text,starts=starts,start=starts[0],end=end,rows=rows,reference_layout=True,motion='out',**kw)
    rows.insert(3,make('You know content matters',[136,140,154,166],185,[{'words':[0,1],'role':'support','align':'top_left','size':70},{'words':[2],'role':'main'},{'words':[3],'role':'support','align':'bottom','size':64}],position=.208,main_size=180,top_lift=110,tracking=-.045,header_fraction=.01))
    rows[3]['motion']='focus'
    rows.insert(4,make('being on Camera Stresses you out',[194,197,203,209,222,225],246,[{'words':[0,1],'role':'support','align':'top_left','size':52,'enter_y':-50},{'words':[2,3],'role':'main','enter_y':-24},{'words':[4,5],'role':'support','align':'bottom','size':66,'green':[5]}],position=.172,main_size=80,top_lift=70,tracking=-.045,header_fraction=.145))
    rows[5]['start']=246;rows[5]['starts'][0]=246
    path.write_text(json.dumps(p,indent=2)+'\n','utf-8')
    from tools.refine_caption_two_glow import refine
    refine()
    print('Replacement Caption 2 profile saved; previous profile preserved')

if __name__=='__main__':main()
