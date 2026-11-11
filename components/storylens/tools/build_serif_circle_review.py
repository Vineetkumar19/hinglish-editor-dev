"""Rebuild the second reference's review and its measured caption profile."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Full Drive/Styles/Videos/Caption 06 - Serif Circle.mp4')

def make_profile():
    words=json.loads((ROOT/'tmp/herb-reference-two/words.json').read_text('utf-8'))
    groups=[]
    def add(text,starts,end=None):
        if groups and groups[-1].get('end') is None:groups[-1]['end']=starts[0]
        groups.append(dict(text=text,starts=starts,end=end))
    add('Por que um único post',[.033,.11,.30,.4667,.7667],1.20)
    add('não vai fazer com que',[1.2333,1.32,1.4333,1.7333,1.83],2.0)
    add('seu cliente venda mais?',[2.0,2.1667,2.6667,3.0333],3.40)
    # Short reference cuts, followed by the measured multi-line compositions.
    ranges=[(13,14,'Se ele'),(15,16,'não tem'),(17,17,'uma'),(18,18,'base'),(19,19,'pra'),(20,20,'converter'),
            (21,21,'um'),(22,22,'dois'),(23,23,'dez'),(24,24,'ou'),(25,25,'vinte'),
            (26,29,'NÃO VÃO ADIANTAR NADA'),(30,30,'nunca'),(31,31,'que'),(32,32,'isso'),(33,33,'vai'),(34,34,'fazer'),(35,35,'um'),
            (36,36,'insta flopado'),(37,37,'virar'),(38,38,'uma'),(39,39,'máquina'),(40,41,'de vendas'),
            (42,43,'Ele precisa'),(44,44,'entender'),(45,45,'que'),(46,47,'um post'),(48,49,'vai atuar'),(50,51,'muito bem'),(52,52,'pra'),(53,53,'converter'),(54,54,'uma'),(55,55,'base'),(56,57,'ou seja'),
            (58,64,'meio e fundo de funil.'),(65,65,'Existem'),(66,66,'exceções'),(67,68,'como'),(69,70,'tráfego pago'),(71,72,'ou um'),(73,75,'reels que explodiu'),(76,77,'e tem'),(78,78,'muita'),(79,79,'gente'),(80,80,'entrando'),(81,82,'no perfil'),
            (83,83,'Mas'),(84,85,'se você'),(86,87,'não explicar'),(88,88,'isso'),(89,89,'pra'),(90,90,'ele'),(91,92,'meu amigo'),(93,97,'ele vai montar em você.'),
            (98,99,'Ele vai'),(100,100,'querer'),(101,101,'alterar'),(102,103,'ele vai'),(104,104,'querer'),(105,105,'explicações'),(106,107,'do porquê'),(108,109,'ele não'),(110,110,'tá'),(111,111,'atraindo'),(112,112,'e'),(113,113,'vendendo'),(114,114,'mais'),
            (115,117,'E no fim'),(118,118,'vocês'),(119,119,'dois'),(120,121,'vão se'),(122,122,'sentir'),(123,123,'frustrados'),(124,124,'Ele'),(125,131,'por não ter o resultado que imaginou'),(132,133,'e você'),(134,138,'por ter perdido um cliente'),
            (139,140,'e além'),(141,141,'disso'),(142,142,'toda'),(143,144,'a jornada'),(145,145,'dele'),(146,147,'ter sido'),(148,148,'um'),(149,149,'saco'),
            (150,150,'Então'),(151,151,'deixa'),(152,152,'claro'),(153,154,'a função'),(155,156,'do seu'),(157,157,'serviço'),(158,159,'Se não'),(160,160,'fechar'),(161,161,'tudo'),(162,162,'bem'),(163,163,'Talvez'),(164,165,'no futuro'),(166,166,'você'),(167,167,'ainda'),(168,168,'tenha'),(169,169,'uma'),(170,170,'chance')]
    for a,b,text in ranges:
        start=round(words[a]['start']+.12,4);end=round(words[b]['end']+.12,4);count=len(text.split())
        if a==13:start=3.4
        if b-a+1==count:starts=[round(words[i]['start']+.12,4) for i in range(a,b+1)];starts[0]=start
        else:starts=[round(start+(end-start)*i/count,4) for i in range(count)]
        add(text,starts)
    groups[-1]['end']=49.733333
    def row(ids,y,**kw):return dict(words=ids,y=y,**kw)
    def circle(trigger,y,**kw):return dict(kind='circle',trigger=trigger,y=y,color='#58F69D',duration=.65,stroke=3,**kw)
    def scribble(trigger,y,color='#FFFFFF'):return dict(kind='scribble',trigger=trigger,y=y,color=color,duration=.7,stroke=2,glow=True)
    recipes=[
      dict(text='Por que um único post',motion='rise',rows=[row([0,1],0,x=330),row([2],45,x=404),row([3],95,x=343,face='serif',size=88),row([4],155,x=404,face='serif',size=88)],decorations=[circle(3,125)]),
      dict(text='não vai fazer com que',motion='rise',rows=[row([0,1],0),row([2],45),row([3,4],90)]),
      dict(text='seu cliente venda mais?',motion='rise',rows=[row([0],0,x=400,face='italic',size=56),row([1],45,x=357),row([2],95,x=355,face='serif',size=90,color='#58F69D'),row([3],155,x=389,face='serif',size=86)],decorations=[scribble(2,210)]),
      dict(text='NÃO VÃO ADIANTAR NADA',motion='rise',rows=[row([0,1],0),row([2],54),row([3],108)],decorations=[dict(kind='circle',trigger=0,y=55,rx=240,ry=110,color='#E9003F',duration=.85,stroke=3)]),
      dict(text='insta flopado',motion='cut',rows=[row([0],0),row([1],0)],replace_words=True),
      dict(text='meio e fundo de funil.',motion='rise',rows=[row([0],0,face='serif',size=88),row([1],-20,x=460),row([2],65,face='serif',size=88),row([3,4],118)],decorations=[scribble(2,159,'#58F69D')]),
      dict(text='ele vai montar em você.',motion='rise',rows=[row([0],0,x=320,face='italic',size=56),row([1],0,x=399),row([2],54),row([3,4],108)],decorations=[dict(kind='circle',trigger=2,y=55,rx=240,ry=110,color='#E9003F',duration=.65,stroke=3)]),
      dict(text='por não ter o resultado que imaginou',motion='rise',rows=[row([0,1],0),row([2],45),row([3,4],100,face='serif',size=86,color='#58F69D'),row([5,6],160)]),
      dict(text='por ter perdido um cliente',motion='rise',rows=[row([0,1],0),row([2],60,face='serif',size=88,color='#E9003F'),row([3,4],120)])
    ]
    # These reference words use the contrasting sans italic, without an extra effect.
    for text in ('alterar','explicações'):
        recipes.append(dict(text=text,motion='cut',rows=[row([0],0,face='italic',size=56)]))
    recipes.append(dict(text='reels que explodiu',motion='cut',rows=[row([0],0,face='italic',x=224),row([1,2],0,x=418)]))
    cfg=dict(revision=1,status='review_draft',reference_file=str(SOURCE),reference_fps=30,
             fonts=dict(sans='Inter-Medium.otf',serif='timesbi.ttf',italic='ariali.ttf'),size=52,tracking=-.035,
             recipes=recipes,sample_groups=groups,
             notes='Frame-measured opening and annotation compositions; later cuts aligned to local word timing. Font matches are visual approximations pending owner review. Vertical four words; horizontal seven. Caption-only adaptation.')
    (ROOT/'hinglish_captions/serif_circle_reference.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),'utf-8')

def build_source_study():
    make_profile()
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.media import probe
    from hinglish_captions.serif_circle import sample_cues
    from hinglish_captions.project import write_project
    from hinglish_captions.report import write_report
    folder=ROOT/'output/captions/serif-circle-reference-review';folder.mkdir(parents=True,exist_ok=True)
    video=folder/'serif-circle-reference-50s.mp4'
    if not video.exists():
        subprocess.run([get_ffmpeg_exe(),'-nostdin','-v','error','-y','-f','lavfi','-i','color=black:s=720x1280:r=30:d=49.733333','-i',str(SOURCE),'-map','0:v','-map','1:a','-t','49.733333','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','24','-pix_fmt','yuv420p','-c:a','aac',str(video)],check=True)
    cues=sample_cues();media=probe(video)
    p=write_project(folder/'caption-project.json',media,cues,'serif_circle_draft','source',video.name,position=.65625)
    p.update(review_draft=True,word_visibility='phrase',preview_stale=True,review_notes='Second reference draft: white captions, italic emphasis and drawn annotations. Owner approval pending.')
    (folder/'caption-project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),'utf-8')
    write_report(folder/'report.html','Second reference · Serif Circle',video.name,cues,p['style'],[],p)
    print(folder/'report.html')

if __name__=='__main__':
    from tools.build_serif_circle_english import main
    main()
