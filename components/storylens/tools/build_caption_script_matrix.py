"""Four thirty-second English/Hinglish projects for live Storylens checks."""
import json,html,subprocess,shutil
from dataclasses import replace
from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_captions.core import CaptionWord,build_cues
from hinglish_captions.project import write_project
from hinglish_captions.report import write_report
from hinglish_captions.template_patterns import bind_patterns
from hinglish_cut.media import probe

SCRIPTS=[
('01-english-business','English · Business and storytelling',
 'Your business does not need another perfect plan. It needs a story people remember. Start with one honest question. What problem can you solve today? Show the process, explain your decisions, and share the small results. Confidence grows through action. Consistency creates trust. Even an ordinary idea can become extraordinary when you give it a clear direction. Make something useful, learn from the response, and keep going.'),
('02-english-journey','English · A journey and a deadline',
 'At sunrise, 3 friends reached the railway station with 20 minutes to spare. Their tickets were ready, but one important bag was missing. Inside were the photographs from their first adventure. Should they leave without it? A quiet announcement changed everything. The station manager had found the bag beside a tea stall. One small act of responsibility saved an unforgettable journey. Sometimes the best stories begin with a completely unexpected delay.'),
('03-hinglish-creator','Hinglish · A creator takes action',
 'Kal maine decide kiya ki ab perfect moment ka wait nahi karunga. Phone uthaya, camera on kiya, aur apni pehli story record kar di. Shuru mein confidence bilkul nahi tha. Lekin har chhoti practice ke saath baat clear hone lagi. Tumhe sab kuch pehle din samajhna zaroori nahi hai. Bas ek useful idea share karo, audience ki baat suno, aur agla video thoda better banao. Improvement action lene se aati hai.'),
('04-hinglish-business','Hinglish · An experiment with numbers',
 'Ek chhote business ne 30 din ka experiment shuru kiya. Roz ek honest video, hafte mein 2 customer stories, aur har comment ka simple jawab. Pehle 7 din response slow tha. Phir ek customer ne apna experience share kiya. Kya badla? Unhone complicated marketing chhod kar real problems samjhani shuru ki. Trust badha, conversations badhi, aur naye orders aaye. Strategy tab kaam karti hai jab consistency aur clear communication saath chalti hain.')
]


def main():
    root=Path(__file__).resolve().parents[1];base=root/'output/captions/script-pattern-validation';base.mkdir(parents=True,exist_ok=True)
    source=base/'silent-30s.mp4'
    if not source.exists():
        subprocess.run([get_ffmpeg_exe(),'-v','error','-nostdin','-y','-f','lavfi','-i','color=black:s=720x1280:r=30:d=30','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t','30','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','30','-c:a','aac',str(source)],check=True)
    items=[]
    for key,title,text in SCRIPTS:
        folder=base/key;folder.mkdir(exist_ok=True);video=folder/'source.mp4'
        if not video.exists():shutil.copy2(source,video)
        tokens=text.split();weights=[max(3,min(10,len(t.strip('.,?!'))))+(3 if t[-1] in '.?!' else 0) for t in tokens];total=sum(weights);clock=0;words=[]
        for token,weight in zip(tokens,weights):
            end=clock+30*weight/total;words.append(CaptionWord(token,clock,end));clock=end
        raw=build_cues(words,max_words=7,max_chars=46,max_seconds=3)
        # The synthetic words are continuous; omit build_cues' optional tail
        # where it would overlap the next caption's timed words.
        cues=bind_patterns([replace(q,end=min(30,q.end,raw[i+1].start if i+1<len(raw) else 30)) for i,q in enumerate(raw)])
        p=write_project(folder/'caption-project.json',probe(video),cues,'caption_2','source',video.name)
        p.update(preview_stale=True,omit_source_video=True,word_visibility='phrase',review_draft=False,validation_script=title,validation_duration=30)
        (folder/'caption-project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),'utf-8')
        (folder/'script.txt').write_text(text+'\n','utf-8')
        write_report(folder/'report.html',title,video.name,cues,'caption_2',[],p)
        items.append(dict(id=key,title=title,text=text,words=len(tokens),duration=30,cues=len(cues),url=f'/caption-output/script-pattern-validation/{key}/report.html'))
    (base/'scripts.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),'utf-8')
    links=''.join(f'<article><h2>{html.escape(i["title"])}</h2><p>{html.escape(i["text"])}</p><a href="{i["url"]}">Open 30-second Storylens preview</a></article>' for i in items)
    (base/'index.html').write_text('<!doctype html><html><meta charset="utf-8"><title>Four script caption review</title><style>body{max-width:1000px;margin:40px auto;background:#101112;color:#eee;font:17px/1.65 system-ui}article{padding:24px;background:#1b1d20;border:1px solid #363a40;border-radius:14px;margin:20px 0}a{color:#9fd7ff}h1{font-size:30px}h2{font-size:22px}</style><h1>Four scripts · 30 seconds each</h1><p>Two English and two Hinglish scripts. Check every remaining template in Storylens. Caption 1 is excluded. These are silent caption previews with a 30-second reading timeline.</p>'+links+'</html>','utf-8')
    print(json.dumps([{k:i[k] for k in ('id','words','cues','duration')} for i in items]))


if __name__=='__main__':main()
