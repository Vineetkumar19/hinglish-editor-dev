"""English preview of reference two. The reference supplies design, not language."""
import json,re,subprocess,wave,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PHRASES=['Why one single post','is not enough today.','Your audience needs more.','ONE POST CHANGES NOTHING.',
 'People need','a clear reason','to stop,','listen,','and care.','Think about your','middle and bottom funnel.',
 'Create','reels that connect.','Tell a story','with real meaning.','Then','they will trust you.',
 'But without','a message,','you might lose clients.','Good design','supports your words.','A simple idea',
 'can make','a powerful impact.','Keep the spacing tight.','Let each line','arrive with purpose.',
 'Make the important words','stand out.','Build a connection,','stay consistent,','and keep improving.',
 'That is how','your story becomes','worth remembering.']

def main():
    timing=json.loads((ROOT/'tmp/serif-circle-english/timing.json').read_text('utf-8-sig'))
    audio=ROOT/'tmp/serif-circle-english/narration.wav'
    with wave.open(str(audio)) as f:duration=f.getnframes()/f.getframerate()
    tokens=list(re.finditer(r'\S+',timing['text']))
    assert ' '.join(PHRASES).lower()==timing['text'].lower()
    events=sorted(timing['words'],key=lambda w:w['character'])
    starts=[next(float(e['start']) for e in events if e['character']==t.start()) for t in tokens]
    groups=[];cursor=0
    for phrase in PHRASES:
        n=len(phrase.split());groups.append(dict(text=phrase,starts=starts[cursor:cursor+n],end=starts[cursor+n] if cursor+n<len(starts) else duration));cursor+=n
    path=ROOT/'hinglish_captions/serif_circle_reference.json';cfg=json.loads(path.read_text('utf-8'))
    if 'reference_sample_groups' not in cfg:cfg['reference_sample_groups']=cfg['sample_groups']
    cfg.update(revision=3,preview_language='English',supported_languages=['English','Hinglish'],sample_groups=groups,
      fonts=dict(sans='Inter-SemiBold.ttf',serif='PlayfairDisplay-BoldItalic.ttf',italic='InterDisplay-SemiBoldItalic.ttf'),size=56,tracking=-.05,
      notes='Reference two supplies motion, typography and alignment only. Preview content is English, timed to a fresh offline English narration. English and Hinglish use the same style. Original Portuguese samples are private measurement data, not preview content.')
    # Retain measured source compositions; add equivalent English/Hinglish roles.
    cfg['recipes']=[r for r in cfg['recipes'] if r.get('language') not in ('English','Hinglish')]
    def row(ids,y,**kw):
        if kw.get('face')=='serif':kw.setdefault('tracking',-.07);kw.setdefault('size',88)
        return dict(words=ids,y=y,**kw)
    green_path=[[[203,123],[300,174],[520,174],[552,125]],[[552,125],[584,79],[447,41],[313,37]],[[313,37],[188,29],[152,64],[200,92]],[[200,92],[238,119],[340,142],[426,142]]]
    red_path=[[[200,205],[310,258],[565,219],[590,118]],[[590,118],[625,5],[445,-15],[265,21]],[[265,21],[125,45],[100,108],[160,152]],[[160,152],[200,189],[320,211],[450,184]]]
    underline_path=[[[205,166],[310,160],[520,158],[520,166]],[[520,166],[512,178],[265,190],[250,198]],[[250,198],[240,207],[433,211],[427,224]]]
    def annotation(kind,trigger,path,color,stroke,duration,**kw):return dict(kind=kind,trigger=trigger,path=path,y=0,color=color,stroke=stroke,duration=duration,linear=True,**kw)
    def build(text,rows,decorations=()):return dict(text=text,language='English',motion='rise',rows=rows,decorations=list(decorations))
    patterns=[
      build(PHRASES[0],[row([0],0,x=330),row([1],35,x=404),row([2],77,x=343,face='serif'),row([3],137,x=404,face='serif')],
        [annotation('circle',2,green_path,'#21E890',4,.45)]),
      build(PHRASES[1],[row([0,1],0),row([2],36),row([3],72)]),
      build(PHRASES[2],[row([0],0,x=400,face='italic'),row([1],34,x=357),row([2],77,x=355,face='serif',color='#08EF86'),row([3],130,x=389,face='serif')],
        [annotation('scribble',2,underline_path,'#FFFFFF',2.5,.60,glow=True,taper=True,delay=.10)]),
      build(PHRASES[3],[row([0,1],40),row([2],88),row([3],136)],
        [annotation('circle',0,red_path,'#F00031',6,.65)]),
      build(PHRASES[10],[row([0],10,x=310,face='serif'),row([1],10,x=495),row([2],65,x=360,face='serif'),row([3],111,x=380)],
        [annotation('scribble',2,[[[x,y-15] for x,y in segment] for segment in underline_path],'#21E890',2.5,.60,glow=True,taper=True)]),
      build(PHRASES[12],[row([0],0,face='italic'),row([1],35),row([2],70)]),
      build(PHRASES[16],[row([0],55,x=300,face='italic'),row([1],55,x=420),row([2],94),row([3],133)],
        [annotation('circle',0,[[[360+(x-360)*.82,y+8] for x,y in segment] for segment in red_path],'#F00031',5,.65)]),
      build(PHRASES[19],[row([0,1],0),row([2],47,face='serif',color='#F00031'),row([3],99)]),
      build(PHRASES[24],[row([0],0,face='italic'),row([1],36),row([2],72)]),
      build(PHRASES[25],[row([0,1],0),row([2],36),row([3],72)]),
      build(PHRASES[30],[row([0],0,face='italic'),row([1],36),row([2],72)]),
    ]
    known={r['text'] for r in patterns}
    for phrase in PHRASES:
        if phrase not in known:patterns.append(dict(text=phrase,language='English',motion='rise',rows=[row(list(range(len(phrase.split()))),0)]))
    cfg['recipes'].extend(patterns)
    cfg['font_identification']={'serif':'Playfair Display Bold Italic','sans':'Inter SemiBold','evidence':'Glyph silhouette comparisons against source frames; strongest measured candidates, original project font metadata unavailable.','source':'https://github.com/google/fonts/tree/main/ofl/playfairdisplay'}
    path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),'utf-8')
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.media import probe
    from hinglish_captions.serif_circle import sample_cues,profile
    from hinglish_captions.project import write_project
    from hinglish_captions.report import write_report
    profile.cache_clear()
    folder=ROOT/'output/captions/serif-circle-english-v2-review';folder.mkdir(parents=True,exist_ok=True)
    video=folder/'english-caption-preview.mp4'
    subprocess.run([get_ffmpeg_exe(),'-nostdin','-v','error','-y','-f','lavfi','-i',f'color=black:s=720x1280:r=30:d={duration}','-i',str(audio),'-map','0:v','-map','1:a','-t',str(duration),'-c:v','libx264','-threads','2','-preset','ultrafast','-crf','24','-pix_fmt','yuv420p','-c:a','aac',str(video)],check=True)
    cues=sample_cues();media=probe(video)
    p=write_project(folder/'caption-project.json',media,cues,'serif_circle_draft','source',video.name,position=.65625,reference_script=timing['text'])
    p.update(review_draft=cfg.get('approval',{}).get('status')!='approved',preview_language='English',word_visibility='phrase',preview_stale=True,
       review_notes='English narration and captions. Reference two supplies the visual style only. Owner approval pending.',
       demo_narration={'voice':timing['voice'],'timing':'Offline speech engine word audio positions','language':'English'})
    (folder/'caption-project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),'utf-8')
    (folder/'transcript.txt').write_text(timing['text'],'utf-8')
    write_report(folder/'report.html','English · Serif Circle review',video.name,cues,p['style'],[('English script','transcript.txt')],p)
    print(f'English preview: {duration:.2f}s, {len(tokens)} words, {len(cues)} captions. {folder / "report.html"}')

if __name__=='__main__':main()
