"""Supplement live Storylens checks with word coverage and frame-bound audits.

This samples the actual Storylens renderer; it is not a Premiere test and does
not replace the live application checks recorded separately.
"""
import json,math,sys,gc
from pathlib import Path
from PIL import ImageFont
from hinglish_captions import scene_capture
from hinglish_captions.project import cues_from_data
from hinglish_captions.renderer import draw_editor_caption
from hinglish_captions.styles import SELECTABLE_TEMPLATES


def main():
    root=Path(__file__).resolve().parents[1];base=root/'output/captions/script-pattern-validation';results=[]
    projects=sorted(base.glob('*/caption-project.json'))
    selected=set(sys.argv[1:])
    for style in SELECTABLE_TEMPLATES:
        if style=='caption_1' or selected and style not in selected:continue
        for file in projects:
            p=json.loads(file.read_text('utf-8'));cues=cues_from_data(p['cues']);failures=[];frames=0;coverage=0
            for qi,cue in enumerate(cues):
                seen=set();times={min(cue.end-.005,w.start+.12) for w in cue.words}
                times.update([cue.start+.05,(cue.start+cue.end)/2,cue.end-.005])
                for t in sorted(times):
                    try:
                        with scene_capture.capture():
                            img=draw_editor_caption(360,640,cue,t,style,'template',{'x':.5,'y':.65,'size':1},'phrase')
                            rows=scene_capture.words(img)
                        frames+=1
                        for r in rows:
                            if r.get('alpha',1)<.01:continue
                            seen.add(r['index'])
                            f=ImageFont.truetype(r['font_path'],max(2,round(r['size_px'])))
                            if Path(r['font_path']).name=='Inter-Variable.ttf' and r.get('weight') in (400,700,900):f.set_variation_by_name({400:'Regular',700:'Bold',900:'Black'}[r['weight']])
                            boxes=[]
                            for j,c in enumerate(r['text']):
                                if c.isspace():continue
                                b=f.getbbox(c);x=f.getlength(r['text'][:j])+j*f.size*r.get('tracking',0);boxes.append((x+b[0],b[1],x+b[2],b[3]))
                            w=(max(b[2] for b in boxes)-min(b[0] for b in boxes))*r['sx'];h=(max(b[3] for b in boxes)-min(b[1] for b in boxes))*r['sy']
                            box=[r['x']-w/2,r['y']-h/2,r['x']+w/2,r['y']+h/2]
                            if r.get('alpha',1)>.15 and (box[0]<-1 or box[1]<-1 or box[2]>361 or box[3]>641):
                                item=dict(cue=qi,time=round(t,3),word=r['text'],bounds=[round(v,1) for v in box])
                                if not any(a.get('cue')==qi and a.get('word')==r['text'] for a in failures):failures.append(item)
                    except Exception as e:
                        failures.append(dict(cue=qi,time=round(t,3),error=str(e)));break
                missing=sorted(set(range(len(cue.words)))-seen)
                if missing:failures.append(dict(cue=qi,missing=[cue.words[i].text for i in missing]))
                coverage+=len(seen)
            result=dict(style=style,script=file.parent.name,frames=frames,words=coverage,expected=sum(len(c.words) for c in cues),issues=failures)
            results.append(result)
            (base/'renderer-audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf-8')
            print(style,file.parent.name,'frames',frames,'words',coverage,'issues',len(failures),flush=True)
            # Keep one case in memory; no batch video renders or editor projects.
            for module in list(sys.modules.values()):
                if getattr(module,'__name__','').startswith('hinglish_captions.'):
                    for value in vars(module).values():
                        if callable(value) and hasattr(value,'cache_clear'):
                            try:value.cache_clear()
                            except Exception:pass
            gc.collect()
    print('CASES',len(results),'ISSUES',sum(len(r['issues']) for r in results),flush=True)


if __name__=='__main__':main()
