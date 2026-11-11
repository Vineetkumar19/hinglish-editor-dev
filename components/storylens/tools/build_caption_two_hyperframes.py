"""Generate an editable, locally rendered Hyperframes Caption 2 composition."""
from pathlib import Path
import argparse
import html
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BASE=ROOT/'output/captions/hyperframes-caption-two'


def build(text,duration,output):
    from hinglish_captions.caption_two import composition,profile,reference_lines,page_ranges
    from hinglish_captions.caption_one import font,text_metrics
    from hinglish_captions.core import CaptionCue,CaptionWord
    from hinglish_captions.template_patterns import pattern_context
    local=json.loads((BASE/'local-llm-plan.json').read_text('utf-8'))
    measured=json.loads((BASE/'reference/motion-fit.json').read_text('utf-8'))
    cfg=profile();output.mkdir(parents=True,exist_ok=True)
    assets=output/'assets';(assets/'fonts').mkdir(parents=True,exist_ok=True);(output/'compositions').mkdir(exist_ok=True)
    winner=json.loads((BASE/'reference/font-fit.json').read_text('utf-8'))[0]
    font_name=winner['font']
    for name in [font_name,'StorylensInterCaption-Regular.ttf','Inter-LICENSE.txt']:
        shutil.copyfile(ROOT/'hinglish_captions/fonts'/name,assets/'fonts'/name)
    shutil.copyfile(ROOT/'tools/hyperframes-runtime/node_modules/gsap/dist/gsap.min.js',assets/'gsap.min.js')
    groups=[]
    for line in text.splitlines():
        words=line.split()
        groups.extend(words[a:b] for a,b in page_ranges(words))
    if not groups:raise ValueError('Paste at least one caption line.')
    slots=[1,2,5,0,4,8,3]
    body=[];timelines=[];evidence=[]
    entry=local['plan'];entry_seconds=max(.12,min(.23,float(entry['entry_seconds'])))
    entry_y=max(0,min(12,float(entry['entry_y'])));entry_blur=max(0,min(7,float(entry['entry_blur'])))
    for number,words in enumerate(groups):
        slot=slots[number%len(slots)];recipe=cfg['recipes'][slot];start=number*duration/len(groups);end=(number+1)*duration/len(groups)
        timing=recipe['starts'];source_duration=(recipe['end']-recipe['start'])/30
        starts=[]
        for j in range(len(words)):
            k=min(len(timing)-1,int((j+.5)*len(timing)/len(words)))
            onset=(timing[k]-recipe['start'])/30/source_duration
            starts.append(start+.05+onset*max(.1,end-start-.3))
        cue=CaptionCue(tuple(CaptionWord(w,starts[j],starts[j+1] if j+1<len(words) else end) for j,w in enumerate(words)),start,end,recipe['text'],slot)
        with pattern_context(cue):plan=composition(words)
        def runs(row,size):
            path=ROOT/'hinglish_captions/fonts'/('StorylensInterCaption-Regular.ttf' if row.get('regular') else font_name)
            selected=font(str(path),max(2,round(size)))
            tracking=row.get('tracking',plan.get('tracking',cfg['tracking']) if row['role']=='main' else cfg['support_tracking'])
            result=[];cursor=0
            for i in row['words']:
                advance,left,right=text_metrics(str(path),selected.size,words[i],tracking)
                result.append({'i':i,'text':words[i],'font':selected,'tracking':tracking,'x':cursor,'left':left,'right':right,'enter_y':row.get('enter_y')})
                cursor+=advance+selected.size*(.17 if row['role']=='main' else .21)
            left=min((r['x']+r['left'] for r in result),default=0);right=max((r['x']+r['right'] for r in result),default=0)
            return result,right-left,left
        # Keep the reference type proportions; only a genuinely long row fits
        # down. Do not shrink every main word to reserve a generic 1.24 zoom.
        lines=reference_lines(plan,runs,720*.88,720,1,720,1280,cfg)
        left=min((r['_x']+run['x']+run['left'] for r,rs,_,_ in lines for run in rs),default=360)
        right=max((r['_x']+run['x']+run['right'] for r,rs,_,_ in lines for run in rs),default=360)
        peak_limit=720*.94/max(1,right-left)
        track=measured[slot]
        keys=[[t,1+max(-.15,min(peak_limit-1,scale-1))] for t,scale in track['camera_keys']]
        main=next((r for r in plan['rows'] if r['role']=='main'),None)
        anchor=min((starts[i] for i in main['words']),default=start) if main else start
        gid=f'cue-{number+1}';camera=f'{gid}-camera'
        body.append(f'<svg id="{gid}" class="clip" data-start="{start:.6f}" data-duration="{end-start:.6f}" data-track-index="1" width="720" height="1280" viewBox="0 0 720 1280" aria-label="{html.escape(" ".join(words),quote=True)}"><g id="{camera}">')
        timelines.append(f'tl.set("#{camera}",{{scale:{keys[0][1]},svgOrigin:"360 832"}},0);')
        for (t0,s0),(t1,s1) in zip(keys,keys[1:]):
            timelines.append(f'tl.to("#{camera}",{{scale:{s1},duration:{t1-t0:.6f},ease:"none"}},{anchor+t0:.6f});')
        positions=[]
        for row,rs,extents,y in lines:
            for run in rs:
                i=run['i'];x=row['_x']+run['x'];baseline=y+1280*.15
                content=bool(''.join(c for c in words[i].lower() if c.isalnum())) and ''.join(c for c in words[i].lower() if c.isalnum()) not in cfg['keyword_stop_words']
                green=content and (row['role']=='main' or i in row.get('green',[]))
                color=cfg['green'] if green else cfg['white'];wid=f'{gid}-word-{i+1}'
                family='CaptionRegular' if row.get('regular') else 'CaptionBold'
                weight=400 if row.get('regular') else 700
                body.append(f'<text id="{wid}" data-var-text="{wid}" x="{x:.4f}" y="{baseline:.4f}" fill="{color}" font-family="{family}" font-weight="{weight}" font-size="{run["font"].size}" letter-spacing="{run["tracking"]*run["font"].size:.4f}" class="word">{html.escape(words[i])}</text>')
                dy=max(-12,min(12,row.get('enter_y',entry_y)))
                timelines.append(f'tl.fromTo("#{wid}",{{opacity:0,y:{dy},filter:"blur({entry_blur}px)"}},{{opacity:1,y:0,filter:"blur(0px)",duration:{entry_seconds},ease:"power3.out",immediateRender:false}},{starts[i]:.6f});')
                positions.append({'index':i,'text':words[i],'x':x,'baseline':baseline,'size':run['font'].size,'color':color,'start':starts[i]})
        body.append('</g></svg>')
        evidence.append({'id':gid,'words':words,'start':start,'end':end,'recipe_slot':slot,'camera_anchor':anchor,'positions':positions})
    scene='''<template><style>
#root{position:absolute;inset:0;background:#000;overflow:visible}
@font-face{font-family:CaptionBold;src:url('assets/fonts/FONT');font-weight:700}
@font-face{font-family:CaptionRegular;src:url('assets/fonts/StorylensInterCaption-Regular.ttf');font-weight:400}
svg{position:absolute;inset:0;overflow:visible}.word{opacity:0;font-kerning:normal;paint-order:stroke fill;filter:none}
</style><div id="root" data-composition-id="captions" data-width="720" data-height="1280">BODY</div>
<script>document.fonts.ready.then(()=>{const tl=gsap.timeline({paused:true});TIMELINES
window.__timelines=window.__timelines||{};window.__timelines.captions=tl;});</script></template>'''
    scene=scene.replace('FONT',font_name).replace('BODY','\n'.join(body)).replace('TIMELINES','\n'.join(timelines))
    (output/'compositions/captions.html').write_text(scene,'utf-8')
    root='''<!doctype html><html><head><meta charset="utf-8"><title>Caption 2 — Hyperframes reference rebuild</title>
<style>html,body{margin:0;background:#000}#main{position:relative;width:720px;height:1280px;background:#000}</style>
<script src="assets/gsap.min.js"></script></head><body>
<div id="main" data-composition-id="main" data-start="0" data-duration="DURATION" data-width="720" data-height="1280" data-fps="30">
<div id="captions" class="clip" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="DURATION" data-track-index="1" data-track-kind="captions" data-width="720" data-height="1280"></div></div>
<script>window.__timelines=window.__timelines||{};window.__timelines.main=gsap.timeline({paused:true});</script></body></html>'''
    (output/'index.html').write_text(root.replace('DURATION',str(duration)),'utf-8')
    (output/'caption-layout.json').write_text(json.dumps({'duration':duration,'width':720,'height':1280,'fps':30,'font':font_name,'local_model':local['model'],'word_limit':5,'visible_ink_gap':cfg['visible_ink_gap'],'groups':evidence},indent=2),'utf-8')
    (output/'script.txt').write_text(text,'utf-8')
    (output/'SPEC.md').write_text('Caption 2 reference reconstruction. Black720x1280,30fps; text anchor(.5,.65). Maximum5 words/slide. Complete visible-ink rows computed before reveal. Gap2.7px; no cursor, dot, slash or cards. Camera tracks fitted from507 source frames; occluded/card sections cannot be claimed as exact fits. Local model receipts are in the parent folder. Source word groups exceeding five words are adapted to the owner limit. No pixel-exact identity is claimed.\n','utf-8')
    print(json.dumps({'project':str(output),'groups':len(groups),'duration':duration,'model':local['model']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--script-file',type=Path);parser.add_argument('--duration',type=float,default=10);parser.add_argument('--output',type=Path,default=BASE/'project');args=parser.parse_args()
    text=args.script_file.read_text('utf-8-sig') if args.script_file else 'to Understand your value\nyour Content is failing\nif You record with confidence\nMake your story matter today'
    if not 3<=args.duration<=180:raise ValueError('Choose a duration between3 and180 seconds.')
    build(text,args.duration,args.output)
