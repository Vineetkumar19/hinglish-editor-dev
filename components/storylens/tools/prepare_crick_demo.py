"""Extract bounded assets for the local style-study demo; leave source files untouched."""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from imageio_ffmpeg import get_ffmpeg_exe
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/reference-analysis/crick-edit-editing-style/demo'
ASSETS=OUT/'assets'

def main():
    ASSETS.mkdir(parents=True,exist_ok=True)
    inventory=json.loads((OUT.parent/'inventory.json').read_text(encoding='utf-8'))
    source=next(x['path'] for x in inventory if x['slug']=='reference-08')
    ff=get_ffmpeg_exe(); receipts=[]
    for name,second in [('bowler',35.3),('team',234.5),('portrait',739.57),('pointing',.5)]:
        target=ASSETS/(name+'.jpg')
        subprocess.run([ff,'-hide_banner','-loglevel','error','-nostdin','-y','-ss',str(second),'-i',source,'-frames:v','1','-q:v','2',str(target)],check=True)
        receipts.append({'file':target.name,'source':source,'seconds':second,'type':'reference still'})
    print('Four reference stills extracted',flush=True)
    import onnxruntime as ort
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    model=ROOT/'models/rembg/models/isnet-general-use/isnet-general-use.onnx'
    session=ort.InferenceSession(str(model),sess_options=options,providers=['CPUExecutionProvider'])
    # Clean bowling pose, without the title graphics in the reference opening.
    image=Image.open(ASSETS/'bowler.jpg').convert('RGB').crop((100,0,600,720))
    pixels=np.asarray(image.resize((1024,1024)),dtype=np.float32)/255
    pixels=pixels-.5
    result=session.run(None,{session.get_inputs()[0].name:pixels.transpose(2,0,1)[None]})[0].squeeze()
    alpha=np.clip((result-result.min())/max(1e-6,result.max()-result.min()),0,1)
    mask=Image.fromarray((alpha*255).astype('uint8')).resize(image.size,Image.Resampling.LANCZOS)
    image=image.convert('RGBA');image.putalpha(mask)
    # Remove detached small text/background remnants, retaining the largest subject component.
    import cv2
    a=np.asarray(image)[...,3].copy();count,labels,stats,_=cv2.connectedComponentsWithStats((a>90).astype('uint8'))
    if count>1:
        keep=1+np.argmax(stats[1:,cv2.CC_STAT_AREA]);a[labels!=keep]=0
        image.putalpha(Image.fromarray(a))
    image.save(ASSETS/'steyn-cutout.png')
    if (a>90).sum()<image.width*image.height*.08:raise ValueError('Player segmentation did not retain a usable subject')
    receipts.append({'file':'steyn-cutout.png','source':source,'seconds':35.3,'type':'segmented player from reference still','model':'isnet-general-use','crop':[100,0,600,720]})
    print('Player silhouette segmented offline',flush=True)
    for name,start,length in [('action',90.2,7),('reaction',234.3,5)]:
        folder=ASSETS/name;folder.mkdir(exist_ok=True)
        subprocess.run([ff,'-hide_banner','-loglevel','error','-nostdin','-y','-ss',str(start),'-i',source,'-t',str(length),'-an','-vf','fps=30,scale=960:540','-threads','2','-q:v','3',str(folder/'%04d.jpg')],check=True)
        receipts.append({'file':name+'/*.jpg','source':source,'start':start,'seconds':length,'type':'reference footage excerpt, without original audio','fps':30})
        print('Extracted '+name+' footage',flush=True)
    (ASSETS/'provenance.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    contact=Image.new('RGB',(1280,360),'#111');d=ImageDraw.Draw(contact)
    for i,name in enumerate(['bowler.jpg','team.jpg','portrait.jpg','steyn-cutout.png']):
        im=Image.open(ASSETS/name).convert('RGBA');im.thumbnail((320,320))
        contact.paste(im,(i*320+(320-im.width)//2,0),im if im.mode=='RGBA' else None)
        d.text((i*320+10,332),name,fill='white')
    contact.save(OUT/'assets-review.jpg')
    print('Prepared '+str(ASSETS),flush=True)

if __name__=='__main__':main()
