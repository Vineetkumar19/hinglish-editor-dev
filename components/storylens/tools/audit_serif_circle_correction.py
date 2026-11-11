"""Supplementary renderer evidence; no Storylens or Premiere automation."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from hinglish_captions.core import CaptionCue,CaptionWord
from hinglish_captions.serif_circle import render,profile,pages,recipe_for
from hinglish_captions.template_patterns import pattern_context
from hinglish_captions import scene_capture

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/captions/serif-circle-correction'

def cue(text,source,slot=0,start=0,duration=2.5):
    words=text.split();step=duration/len(words)
    return CaptionCue(tuple(CaptionWord(w,start+i*step,start+(i+1)*step) for i,w in enumerate(words)),start,start+duration,source,slot)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    examples=[('Your story deserves attention','Why one single post'),
              ('Small ideas create impact','Your audience needs more.'),
              ('ONE POST CHANGES EVERYTHING','ONE POST CHANGES NOTHING.'),
              ('Ideas aur kahani banao','middle and bottom funnel.'),
              ('Your next extraordinary opportunity','Why one single post'),
              ('Ab apni kahani sunao','Your audience needs more.')]
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    sheet=Image.new('RGB',(360*3,400*2),'#141414');draw=ImageDraw.Draw(sheet)
    for i,(text,source) in enumerate(examples):
        sample=cue(text,source)
        image=render(720,1280,sample,2.49)
        # Full-frame preview plus a readable crop of the design in the sheet.
        image.save(OUT/f'edited-{i+1}.png')
        crop=Image.new('RGBA',image.size,'black');crop.alpha_composite(image)
        crop=crop.crop((0,560,720,1120)).resize((360,280))
        x=i%3*360;y=i//3*400;sheet.paste(crop.convert('RGB'),(x,y+50))
        draw.text((x+8,y+8),text,font=font,fill='white')
        draw.text((x+8,y+345),source,font=font,fill='#999999')
    sheet.save(OUT/'edited-patterns.jpg')
    failures=[];cases=0;frame_count=0
    scripts=['Your next story deserves a beautiful beginning',
             'Har nayi kahani ko ek naya mauka',
             'Extraordinary transformations require consistent creative practice',
             'Ab apni soch badlo aur kahani aage badhao']
    sources=[r for r in profile()['recipes'] if r.get('reference_pattern')]
    for slot,source in enumerate(sources):
        for text in scripts:
            sample=cue(text,source['text'],slot,duration=4)
            for width,height in ((360,640),(640,360)):
                cases+=1
                for offset,page in pages(sample,width,height):
                    with pattern_context(sample):
                        recipe=recipe_for([w.text for w in page.words])
                    if recipe.get('template_pattern',recipe['text'])!=source['text']:
                        failures.append({'source':source['text'],'error':'pattern changed'})
                    for frame in range(0,8):
                        t=page.start+(page.end-page.start)*(frame+.5)/8
                        with scene_capture.capture():
                            im=render(width,height,sample,t)
                            words=scene_capture.words(im)
                        frame_count+=1;box=im.getbbox()
                        if box and (box[0]<=0 or box[1]<=0 or box[2]>=width or box[3]>=height):
                            failures.append({'source':source['text'],'text':text,'time':t,'error':'outside frame','bounds':box})
                        if any(w['index']<offset or w['index']>=offset+len(page.words) for w in words):
                            failures.append({'source':source['text'],'error':'wrong page word'})
    result={'kind':'supplementary_renderer_audit','cases':cases,'sampled_frames':frame_count,'failures':failures,
            'source_inspection':{'decoded_frames':1492,'consecutive_detail_frames':221,'source_fps':30},
            'application_validation':'Not run: owner performs Storylens testing.',
            'premiere_validation':'Not run: owner performs Premiere testing.',
            'limits':'Sampled rendered frames, not an every-frame pixel match; existing font matches remain visual approximations. Portrait pagination remains four words, horizontal seven.'}
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
