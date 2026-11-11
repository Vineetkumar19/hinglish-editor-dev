"""Offline reference inspection and editable-caption regression evidence.

This does not constitute Storylens or Premiere validation.
"""
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from PIL import Image, ImageDraw
from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.kinetic_gold import profile, render, sample_cues, plan, ink, bounds
from hinglish_captions.template_patterns import pattern_context
from hinglish_captions import scene_capture

OUT=Path('output/captions/kinetic-gold-reference-rebuild')
SOURCE=Path('D:/Full Drive/Styles/Videos/Caption 08 - Kinetic Gold.mp4')

def solid(layer):
    result=Image.new('RGB',layer.size,'black');result.paste(layer,mask=layer.getchannel('A'));return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cues=sample_cues();fps=48;count=0;sheets=[];tiles=[];comparisons=[]
    ff=Path('tools/broll-ffmpeg/ffmpeg.exe')
    process=subprocess.Popen([str(ff),'-v','error','-i',str(SOURCE),'-vf','scale=368:207','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE)
    while True:
        data=process.stdout.read(368*207*3)
        if not data:break
        if len(data)!=368*207*3:raise RuntimeError('Incomplete reference frame')
        frame=Image.frombytes('RGB',(368,207),data);time=count/fps
        # All 48 frames each second, with legible enlarged center text crops.
        tile=Image.new('RGB',(240,100),'#191919')
        tile.paste(frame.crop((35,40,335,165)).resize((240,100)),(0,0))
        ImageDraw.Draw(tile).text((2,2),f'{count} / {time:.3f}s',fill='#aaa')
        tiles.append(tile)
        if len(tiles)==48:
            sheet=Image.new('RGB',(240*8,100*6),'#191919')
            for i,part in enumerate(tiles):sheet.paste(part,((i%8)*240,(i//8)*100))
            name=f'reference-frames-{len(sheets):02d}.jpg';sheet.save(OUT/name,quality=88);sheets.append(name);tiles=[]
        q=next((q for q in cues if q.start<=time<q.end),None)
        if q and abs(time-(q.end-.08))<1/fps/2:
            pair=Image.new('RGB',(736,230),'#161616');pair.paste(frame,(0,23));pair.paste(solid(render(368,207,q,time,position=.5)),(368,23))
            ImageDraw.Draw(pair).text((4,4),f'Reference | Caption on black: {time:.3f}s',fill='white');comparisons.append(pair)
        count+=1
    if process.wait()!=0:raise RuntimeError('Reference decoding failed')
    if tiles:
        sheet=Image.new('RGB',(240*8,100*6),'#191919')
        for i,part in enumerate(tiles):sheet.paste(part,((i%8)*240,(i//8)*100))
        name=f'reference-frames-{len(sheets):02d}.jpg';sheet.save(OUT/name,quality=88);sheets.append(name)
    for start in range(0,len(comparisons),4):
        sheet=Image.new('RGB',(736,230*4),'#161616')
        for i,part in enumerate(comparisons[start:start+4]):sheet.paste(part,(0,i*230))
        sheet.save(OUT/f'comparison-{start//4:02d}.jpg',quality=94)
    cases=['Updated and saved Caption','text layouts and motion','Background stays black.',
           'We turn simple ideas into memorable stories today',
           'Aaj hum apni nayi kahani ki shuruaat karenge',
           'Extraordinarily thoughtful transformations inspire remarkable communities everywhere']
    checks=[];failures=[];edits=Image.new('RGB',(368*4,207*((len(profile()['recipes'])+3)//4)),'black')
    for slot,recipe in enumerate(profile()['recipes']):
        for text in cases:
            words=text.split();q=CaptionCue(tuple(CaptionWord(w,i*.5,(i+1)*.5) for i,w in enumerate(words)),0,len(words)*.5,recipe['text'],slot)
            with pattern_context(q):
                runs=plan(words,lambda t,f,s:ink(t,f,s)[0])
            left,top,right,bottom=bounds(runs)
            if abs((left+right)/2-368)>.01 or abs((top+bottom)/2-207)>.01:failures.append([slot,text,'anchor'])
            if [r['text'] for r in runs]!=words:failures.append([slot,text,'missing words'])
            for i,a in enumerate(runs):
                for b in runs[i+1:]:
                    overlap_x=min(a['x']+a['width']/2,b['x']+b['width']/2)-max(a['x']-a['width']/2,b['x']-b['width']/2)
                    overlap_y=min(a['y']+a['height']/2,b['y']+b['height']/2)-max(a['y']-a['height']/2,b['y']-b['height']/2)
                    if overlap_x>.1 and overlap_y>.1:failures.append([slot,text,'overlap',a['text'],b['text']])
            for W,H in [(368,207),(207,368)]:
                with scene_capture.capture():
                    layer=render(W,H,q,q.end-.001,position=.65)
                    captured=scene_capture.words(layer)
                if [r['text'] for r in captured]!=words:failures.append([slot,text,W,'capture missing words'])
                checks.append(dict(slot=slot,text=text,width=W,height=H,ink_bounds=layer.getbbox()))
            if text==cases[0]:edits.paste(solid(render(368,207,q,q.end-.001,position=.65)),((slot%4)*368,(slot//4)*207))
    edits.save(OUT/'changed-words-overview.jpg',quality=94)
    result=dict(reference=str(SOURCE),source_frames_decoded=count,source_fps=fps,chronological_sheets=sheets,
                offline_cases=len(checks),failures=failures,checks=checks,
                limitations=['Source fonts are visually matched; source font metadata is unavailable.',
                             'All source frames decoded into chronological inspection sheets; this is not an every-frame pixel-equivalence claim.',
                             'Storylens application and Premiere validation are left to the owner.'])
    (OUT/'audit.json').write_text(json.dumps(result,indent=2),'utf-8')
    print(json.dumps(dict(source_frames=count,offline_cases=len(checks),failures=failures,comparison_sheets=len(comparisons))))

if __name__=='__main__':main()
