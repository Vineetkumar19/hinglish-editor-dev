"""Measure the supplied Caption 2 reference and obtain a recorded local-LLM plan."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/captions/hyperframes-caption-two'
SOURCE=Path('D:/Full Drive/Styles/Videos/Caption 02 - Lime Keyword Zoom.mp4')


def measure():
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    from imageio_ffmpeg import get_ffmpeg_exe
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'reference').mkdir(exist_ok=True)
    chosen={42:'Prospects',84:'Understand',124:'Content',178:'content',235:'Camera Stresses',294:'You record',490:'Your plate'}
    rows=[];frames={}
    proc=subprocess.Popen([get_ffmpeg_exe(),'-v','error','-i',str(SOURCE),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
    frame=0
    while True:
        raw=proc.stdout.read(720*1280*3)
        if not raw:break
        if len(raw)!=720*1280*3:raise RuntimeError('Incomplete decoded reference frame')
        frame+=1;rgb=np.frombuffer(raw,dtype=np.uint8).reshape(1280,720,3)
        r,g,b=[rgb[:,:,i].astype(np.int16) for i in range(3)]
        mask=(r>130)&(g>185)&(g>r*.99)&(b<155)&(b<r*.75)
        mask[:130]=False;mask[1100:]=False;mask[:,:12]=False;mask[:,708:]=False
        active=np.flatnonzero(mask.sum(axis=1)>8);bands=[]
        for y in active:
            if not bands or y-bands[-1][-1]>3:bands.append([int(y)])
            else:bands[-1].append(int(y))
        candidates=[]
        for band in bands:
            y0,y1=band[0],band[-1]+1
            yy,xx=np.nonzero(mask[y0:y1]);pixels=len(xx)
            if pixels>700 and y1-y0>15:
                x0,x1=int(xx.min()),int(xx.max())+1
                if x1-x0>80:candidates.append((pixels,[x0,y0,x1,y1]))
        box=max(candidates,default=(0,None))[1]
        rows.append({'frame':frame-1,'time':round((frame-1)/30,6),'lime_ink_box':box})
        if frame in chosen:
            im=Image.fromarray(rgb);im.save(OUT/'reference'/f'frame-{frame:04d}.png')
            if box:
                x0,y0,x1,y1=box
                target=Image.fromarray((mask[y0:y1,x0:x1]*255).astype('uint8'))
                target.save(OUT/'reference'/f'ink-{frame:04d}.png')
                frames[frame]=(chosen[frame],target)
    code=proc.wait()
    if code:raise RuntimeError(proc.stderr.read().decode('utf-8','replace'))
    (OUT/'reference/frame-measurements.json').write_text(json.dumps({'source':str(SOURCE),'fps':30,'width':720,'height':1280,'frames':rows},indent=2),'utf-8')
    recipes=json.loads((ROOT/'hinglish_captions/caption_two_reference.json').read_text('utf-8'))['recipes']
    tracks=[]
    for slot,recipe in enumerate(recipes):
        main=next(row for row in recipe['rows'] if row['role']=='main')
        onset=min(recipe['starts'][i] for i in main['words']);complete=max(recipe['starts'][i] for i in main['words'])
        samples=[]
        for i in range(complete+4,recipe['end']-3,2):
            box=rows[i]['lime_ink_box']
            if box:samples.append(((i-onset)/30,box[2]-box[0]))
        if slot in (3,6,7) or len(samples)<5:
            tracks.append({'slot':slot,'camera_anchor':'main','camera_keys':[[0,1],[1,1]],'measured':False,'reason':'Occluded caption or excluded card; no reliable text-camera fit.'});continue
        steady=float(np.median([w for _,w in samples[-max(3,len(samples)//4):]]))
        times=np.array([t for t,_ in samples]);scale=np.array([w/steady for _,w in samples]);best=None
        for rate in np.arange(2,14,.1):
            basis=np.exp(-rate*times);amplitude=float(np.dot(scale-1,basis)/max(.0001,np.dot(basis,basis)))
            error=float(np.mean((scale-(1+amplitude*basis))**2))
            if best is None or error<best[0]:best=(error,amplitude,float(rate))
        error,amplitude,rate=best
        if max(abs(scale-1))<.025:amplitude=0
        amplitude=max(-.15,min(.45,amplitude))
        keys=[[round(t,3),round(1+amplitude*np.exp(-rate*t),5)] for t in np.arange(0,1.401,1/30)]
        tracks.append({'slot':slot,'camera_anchor':'main','camera_keys':keys,'measured':True,'steady_ink_width':steady,'fit_rmse':round(error**.5,5),'amplitude':round(amplitude,5),'rate':round(rate,3),'sample_count':len(samples)})
    (OUT/'reference/motion-fit.json').write_text(json.dumps(tracks,indent=2),'utf-8')
    # Compare letter silhouettes independently of camera size and video backdrop.
    fonts=ROOT/'hinglish_captions/fonts'
    candidates=['Inter-Bold.otf','StorylensInterCaption-Bold.ttf','StorylensInterCaption-Black.ttf','StorylensInterReference-Bold.ttf','StorylensInterReference-Black.ttf','Inter-SemiBold.ttf']
    fits=[]
    def normalize_ink(im):
        box=im.getbbox()
        return im.crop(box).resize((384,64),Image.Resampling.LANCZOS) if box else Image.new('L',(384,64))
    for name in candidates:
        font=ImageFont.truetype(str(fonts/name),200)
        for tracking in [-.075,-.065,-.045,-.03,-.018,0]:
            scores=[]
            for frame in [42,84,124]:
                word,target=frames[frame]
                im=Image.new('L',(2200,350));pen=ImageDraw.Draw(im)
                for j,c in enumerate(word):pen.text((20+font.getlength(word[:j])+j*200*tracking,20),c,font=font,fill=255)
                ink=im.crop(im.getbbox());a=np.asarray(normalize_ink(ink))>96;z=np.asarray(normalize_ink(target))>96
                iou=float((a&z).sum()/max(1,(a|z).sum()))
                aspect_error=abs(ink.width/ink.height-target.width/target.height)/(target.width/target.height)
                scores.append({'frame':frame,'iou':round(iou,4),'aspect_error':round(aspect_error,4),'score':round(iou-.4*aspect_error,4)})
            fits.append({'font':name,'tracking':tracking,'score':round(sum(s['score'] for s in scores)/len(scores),4),'samples':scores})
    fits.sort(key=lambda x:-x['score'])
    (OUT/'reference/font-fit.json').write_text(json.dumps(fits,indent=2),'utf-8')
    sheet=Image.new('RGB',(1440,3*420),'#080808');pen=ImageDraw.Draw(sheet)
    for k,frame in enumerate([42,84,124,178,235,294]):
        im=Image.open(OUT/'reference'/f'frame-{frame:04d}.png')
        box=rows[frame-1]['lime_ink_box']
        cy=(box[1]+box[3])/2 if box else 640
        crop=im.crop((0,max(0,int(cy)-170),720,min(1280,int(cy)+210)))
        x=(k%2)*720;y=(k//2)*420
        sheet.paste(crop,(x,y+32));pen.text((x+12,y+8),f'Frame {frame-1}, {chosen[frame]}',fill='white')
    sheet.save(OUT/'reference/typography-study.jpg',quality=94)
    print(json.dumps({'decoded_frames':len(rows),'best_font_fits':fits[:3]}),flush=True)


def models():
    import requests
    from PIL import Image
    from hinglish_visuals.evaluator import VisionModel
    from hinglish_visuals.brain import open_brain
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import preferences
    from hinglish_niche.profiles import Profiles,use
    from hinglish_publish.memory import CreatorMemory
    OUT.mkdir(parents=True,exist_ok=True)
    config=preferences(ROOT);profiles=Profiles(ROOT);full_context=profiles.context(profiles.read()['selected'])
    full_context['saved_caption_preferences']=CreatorMemory(ROOT,full_context['profile']).writing_context()
    instructions=(ROOT/'AGENTS.md').read_text('utf-8')
    vision_schema={'type':'object','properties':{'observed_style':{'type':'string','maxLength':300},'row_relationships':{'type':'array','maxItems':4,'items':{'type':'string','maxLength':120}},'entrance_motion':{'type':'string','maxLength':200},'avoid_generic_changes':{'type':'array','maxItems':3,'items':{'type':'string','maxLength':100}}},'required':['observed_style','row_relationships','entrance_motion','avoid_generic_changes']}
    with gpu_lock(ROOT):
        print('Asking the configured local vision model to inspect the reference typography.',flush=True)
        vision=VisionModel(ROOT)
        from hinglish_visuals.evaluator import _png64,_for_model
        from hinglish_cut.model_preferences import configure_request
        body={'model':vision.model,'stream':False,'think':False,'format':vision_schema,
              'options':{'temperature':0,'seed':3,'num_ctx':8192,'num_predict':1600},
              'messages':[{'role':'system','content':'Analyze caption typography only. Return concise JSON, under200 words. Do not reproduce the source text. A still contact sheet does not establish exact motion. No cursor/dot/slash/cards/background. Preserve varied large-word hierarchy, not a generic stack.'},
                          {'role':'user','content':'Inspect these six source caption crops. Describe the visible typography and compact relative alignment. Motion is inferred unless supported by measured frame tracks.','images':[_png64(_for_model(Image.open(OUT/'reference/typography-study.jpg')))]}]}
        configure_request(ROOT,body)
        response=vision.session.post(vision.url+'/api/chat',json=body,timeout=600);response.raise_for_status();raw=response.json()
        (OUT/'local-vision-response.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),'utf-8')
        result=json.loads(raw['message']['content'])
        receipt={'model':vision.model,'result':result,'usage':{'input_tokens':raw.get('prompt_eval_count'),'output_tokens':raw.get('eval_count')}}
        (OUT/'local-vision-review.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf-8');vision.session.close()
        # Release only this request's vision model before the larger planner.
        session=requests.Session();session.trust_env=False
        response=session.post('http://127.0.0.1:11434/api/generate',json={'model':vision.model,'keep_alive':0},timeout=60);response.raise_for_status();session.close()
        print('Asking the configured local planner for a constrained Hyperframes recipe.',flush=True)
        fit=json.loads((OUT/'reference/font-fit.json').read_text('utf-8'))
        schema={'type':'object','properties':{
            'font_file':{'type':'string','enum':[fit[0]['font']]},'tracking':{'type':'number','enum':[fit[0]['tracking']]},
            'entry_seconds':{'type':'number','enum':[.16,.23]},'entry_y':{'type':'number','enum':[0,8,12]},'entry_blur':{'type':'number','enum':[4,6]},
            'camera_seconds':{'type':'number','enum':[1.4]},'camera_start_scale':{'type':'number','enum':[1.0]},
            'rationale':{'type':'string'},'script_transfer_rules':{'type':'array','items':{'type':'string'}}},
            'required':['font_file','tracking','entry_seconds','entry_y','entry_blur','camera_seconds','camera_start_scale','rationale','script_transfer_rules']}
        data={'request':'Use Hyperframes with the local model to recreate the supplied caption text style frame by frame. Keep a plain black background, initial center x.5,y.65, maximum five words per slide and2.7px ink gaps at720px width; do not add cursor, red dot, red slash or red boxes. Keep the varied original role sizes and typography. Return a conservative numerical plan, preserving observed evidence over generic animation defaults.',
              'full_creator_profile':full_context,'owner_guidance':instructions,'vision_review':receipt,'measured_font_fits':fit[:6],
              'original_recipes':[{k:v for k,v in r.items() if k!='camera_keys'} for r in json.loads((ROOT/'hinglish_captions/caption_two_reference.json').read_text('utf-8'))['recipes']],
              'measured_camera_motion':[{k:v for k,v in t.items() if k!='camera_keys'} for t in json.loads((OUT/'reference/motion-fit.json').read_text('utf-8'))],
              'hyperframes_contract':(ROOT/'cache/hyperframes-docs/SKILL.md').read_text('utf-8'),
              'measurement_limits':'The color mask measures lime letter ink, not white support or camera motion behind people. Use frame evidence, not invented certainty. Select the highest measured font score. Timing and word indices come from the original supplied frame annotations. Clamp entry movement to12px maximum to keep compact lines readable.'}
        brain=open_brain(ROOT,'ollama')
        try:
            with use(full_context):plan=brain.json('You are the local caption motion designer. Produce the requested bounded JSON recipe for an editable seekable Hyperframes composition, using supplied measurements and latest owner preferences. Do not rewrite script words. Measured camera tracks override generic global zoom curves. Do not claim a still sheet establishes exact easing. Return concise JSON, not prose.',data,schema,max_tokens=1300,think=False)
            output={'model':brain.model,'usage':brain.last_usage,'plan':plan}
            (OUT/'local-llm-plan.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),'utf-8')
            print(json.dumps({'model':brain.model,'usage':brain.last_usage,'plan':plan}),flush=True)
        finally:brain.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['measure','models']);args=parser.parse_args()
    (measure if args.stage=='measure' else models)()
