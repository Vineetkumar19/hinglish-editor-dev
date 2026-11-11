"""Read the actual reference video and save bounded visual/motion evidence."""
import av,json,hashlib
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parents[2];source=Path('D:/Full Drive/Styles/Videos/Caption 02 - Lime Keyword Zoom.mp4')
out=root/'output/caption-two-ae';out.mkdir(exist_ok=True)
selected={7,10,15,25,42,55,65,75,84,124,178,235,294,490};tiles=[];track=[]
import numpy as np
with av.open(str(source)) as video:
    for i,frame in enumerate(video.decode(video=0)):
        im=frame.to_image().convert('RGB');pixels=np.asarray(im);mask=(pixels[:,:,0]>135)&(pixels[:,:,1]>175)&(pixels[:,:,2]<155)&(pixels[:,:,1]>pixels[:,:,0]*.96)
        # Caption-area lime ink only; this excludes most surrounding footage.
        mask[:round(im.height*.35)]=False;mask[round(im.height*.68):]=False
        yy,xx=np.where(mask);track.append({'frame':i,'time':float(frame.time or 0),'lime_box':[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())] if len(xx) else None})
        if i in selected:
            crop=im.crop((0,round(im.height*.34),im.width,round(im.height*.7))).resize((360,230));ImageDraw.Draw(crop).text((4,4),str(i),fill='white');tiles.append(crop)
sheet=Image.new('RGB',(360*4,230*((len(tiles)+3)//4)),(16,16,16))
for i,im in enumerate(tiles):sheet.paste(im,(i%4*360,i//4*230))
sheet.save(out/'actual-reference-study.jpg',quality=92)
(out/'reference-inspection.json').write_text(json.dumps({'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'decoded_frames':len(track),'track':track},indent=2),encoding='utf8')
print('Decoded',len(track),'actual source frames;',out/'actual-reference-study.jpg')
