"""Teacher example explicitly requested by the owner on 24 Oct 2026.

Latest instruction: ChatGPT builds first, documents the motion, then teaches
the smaller Ollama model. This supersedes local-only authorship for this
teacher artifact only. It must never be labeled as local-student output.
"""
import json,hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/motion/teacher-world-culture-20261024'
SOURCE=Path('D:/Full Drive/Styles/Motion Graphic videos/From Klickpin.com- Beautiful world culture moments and clever inspiration with easy charm with beautiful world vibes-pin-id-12947917676306804.mp4')

def text(id,words,x,y,w,size=72,color='#07090c',**kw):return dict(id=id,kind='text',text=words,x=x,y=y,w=w,size=size,color=color,**kw)
def photo(id,asset,x,y,w,h,**kw):return dict(id=id,kind='image',asset=asset,x=x,y=y,w=w,h=h,**kw)
def shape(id,x,y,w,h,color='#009f9d',**kw):return dict(id=id,kind='shape',x=x,y=y,w=w,h=h,color=color,**kw)
def camera(duration,begin=1.10,end=1.,x=0,y=0):return [dict(time=0.,scale=begin,x=0.,y=0.),dict(time=duration,scale=end,x=float(x),y=float(y))]
def shot(id,start,end,layers,**kw):return dict(id=id,start=start,end=end,background='#fff',camera=camera(end-start),layers=layers,**kw)

def build():
    scenes=[]
    scenes.append(shot('ideas',0.,1.97,[
      shape('panel',132,555,350,410,radius=18,drift=[-9,8,-20]),
      photo('seated-photo','seated',75,586,650,535,drift=[8,-8,20]),
      text('ideas','Ideas',160,305,400,85,'#009f9d',delay=0.,reveal='characters',stagger=.05),
      text('arent',"Aren’t",135,385,450,98,delay=.18,reveal='characters',stagger=.04),
      text('created','Created',40,473,640,123,delay=.48,reveal='characters',stagger=.09),
      text('just','just',480,431,180,64,label='#ffe70c',rotation=-15,delay=.72),
      text('body','Ideas are sparks of imagination\nthat shape thoughts into possibilities.',85,1135,550,27,weight=400,delay=.65)
    ],exit='left'))
    scenes[0]['camera']=[dict(time=0.,scale=1.65,x=0.,y=0.),dict(time=.55,scale=1.10,x=0.,y=0.,ease='power2.out'),dict(time=1.97,scale=.96,x=0.,y=-12.)]
    scenes.append(shot('potential',1.97,3.19,[
      shape('circle',-60,700,620,700,radius=350,drift=[15,-10,-40]),
      photo('winner-photo','winner',-40,455,690,865,drift=[-10,-12,35]),
      text('theyre',"they’re",330,230,350,86,weight=400),
      text('born','Born',370,326,255,84,outline=True,label='#fff',rotation=-6,delay=.12),
      text('with','with',365,420,280,80,weight=400,delay=.19),
      text('potential','potential',340,520,350,62,label='#009f9d',rotation=3,delay=.28),
      shape('eye-band',113,600,245,42,color='#009f9d',opacity=.5,rotation=6)
    ],entrance='right',exit='left'))
    scenes.append(shot('power',3.19,4.18,[
      text('they-have','they have the',50,515,620,66,'#dcf5f4',weight=400,delay=.02),
      text('power','POWER',20,590,680,135,'#fff',delay=.20,reveal='characters',stagger=.055),
      text('body','Power isn’t just control — it’s the ability to change\nwhat others believe is unchangeable.',85,785,550,25,'#e9ffff',weight=400,delay=.35)
    ],entrance='right',exit='left'));scenes[-1]['background']='#009d9b'
    scenes.append(shot('people-think',4.18,5.39,[
      photo('profile-photo','profile',0,430,720,850,drift=[-15,-20,25]),
      text('support','to change the way',60,275,600,53,'#fff',weight=400,delay=.02),
      text('think','people think',65,343,590,77,'#009f9d',delay=.14,reveal='characters',stagger=.035)
    ],entrance='right',exit='left'));scenes[-1]['background']='#000'
    scenes.append(shot('future',5.39,6.44,[
      shape('panel',220,-70,285,830,drift=[4,20,-40]),
      photo('rear-echo','future',115,-135,510,580,opacity=.15,drift=[0,12,-30]),
      photo('rear-person','future',100,305,520,550,drift=[-12,-10,40]),
      text('shape','shape the',65,810,610,92,font='script',weight=400,delay=.10),
      text('future-word','future',115,916,490,118,'#009f9d',delay=.18,reveal='characters',stagger=.025),
      text('body','The future isn’t something we enter.\nIt’s something we create with every\ndecision we make today.',110,1050,500,25,weight=400,delay=.25)
    ],entrance='right',exit='left'))
    scenes.append(shot('idea-brain',6.44,8.10,[
      shape('bar',-70,557,860,190,drift=[25,0,-20]),
      photo('brain-photo','brain',210,510,315,320,drift=[-6,-12,45]),
      text('if-you','if you ever have an',60,445,600,58,weight=400,delay=.08,reveal='characters',stagger=.018),
      text('idea-word','idea',180,805,360,152,'#009f9d',delay=.40,reveal='characters',stagger=.08),
      text('body','An idea is a silent revolution small\nin birth, but limitless in impact.',95,982,530,27,weight=400,delay=.55)
    ],exit='up'));scenes[-1]['camera']=camera(1.66,.80,1.03,0,-4)
    scenes.append(shot('take-seriously',8.10,9.11,[
      photo('portrait-photo','portrait',-20,500,760,800,drift=[5,-12,30]),
      text('take-it','take it',120,320,480,79,delay=.06),
      text('seriously','seriously',45,400,630,120,'#009f9d',underline=True,delay=.18,reveal='characters',stagger=.028)
    ],entrance='up'))
    scenes.append(shot('cosmos',9.11,10.24,[
      text('because','because the',80,615,560,55,'#fff',delay=.05),
      text('cosmos-word','cosmos',20,679,680,133,'#fff',delay=.15,reveal='characters',stagger=.04)
    ],mode3d='blackhole'));scenes[-1]['camera']=camera(1.13,1.32,1.)
    scenes.append(shot('chosen',10.24,10.94,[text('chose','chose you',100,665,520,85,'#f5ffff',delay=.04,reveal='characters',stagger=.025)],mode3d='galaxy'))
    scenes.append(shot('world',10.94,12.51,[
      text('to-give','to give the',70,535,580,60,'#fff',delay=.02),
      text('world-word','world',42,607,636,165,'#b7f4ef',delay=.19,reveal='characters',stagger=.035),
      text('identity','a new identity',80,785,560,57,'#fff',weight=400,delay=.64,reveal='characters',stagger=.025)
    ],mode3d='planet'))
    scenes.append(shot('spark',12.51,13.73,[
      text('spark-word','Let this spark',70,676,580,65,'#f4ffff',delay=.02,reveal='characters',stagger=.027),
      text('turn-into','turn into a',80,760,560,65,'#fff',delay=.61,reveal='characters',stagger=.025)
    ],mode3d='walker'))
    scenes.append(shot('wildfire',13.73,15.38,[text('wildfire-word','wildfire',30,680,660,143,'#009f9d',delay=.02,reveal='characters',stagger=.025)],mode3d='fire'))
    plan=dict(version=1,teacher='Codex teacher-authored worked example; no model weights updated',width=720,height=1280,duration=15.38,source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),approval='draft',uses_reference_photo_crops=True,uses_reference_audio=True,scenes=scenes)
    from hinglish_motion.teacher_memory import validate_plan
    validate_plan(plan);OUT.mkdir(parents=True,exist_ok=True);(OUT/'teacher-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf-8')
    return plan

if __name__=='__main__':build();print(OUT/'teacher-plan.json')
