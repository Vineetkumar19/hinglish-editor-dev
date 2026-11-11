"""Estimate soft shadow/glow from source edge rings; keep uncertainty explicit."""
from pathlib import Path
import json,cv2,numpy as np
from PIL import Image
from scipy.optimize import lsq_linear
root=Path(__file__).resolve().parents[2];out=root/'output/caption-two-ae/fidelity-rebuild';results=[]
for index in [41,83]:
 rgb=np.asarray(Image.open(out/f'source-{index:04d}.png')).astype(np.float32)/255;r,g,b=[rgb[:,:,i] for i in range(3)]
 mask=((r>.5)&(g>.73)&(b<.61)&(g>r*.99)).astype(np.float32);mask[:500]=0;mask[820:]=0
 # Preserve only the dominant main row, excluding the separate green footer.
 count=mask.sum(axis=1);bands=[]
 for y in np.flatnonzero(count>8):
  if not bands or y-bands[-1][-1]>3:bands.append([y])
  else:bands[-1].append(y)
 band=max(bands,key=lambda band:mask[band[0]:band[-1]+1].sum());mask[:band[0]]=0;mask[band[-1]+1:]=0
 yy,xx=np.where(mask);x0,x1=max(0,xx.min()-22),min(720,xx.max()+23);y0,y1=max(0,yy.min()-22),min(1280,yy.max()+23)
 image=rgb[y0:y1,x0:x1];m=mask[y0:y1,x0:x1];removed=cv2.dilate((m*255).astype('uint8'),np.ones((5,5),np.uint8));background=cv2.inpaint((image*255).astype('uint8'),removed,9,cv2.INPAINT_TELEA).astype(float)/255
 ring=(cv2.dilate(m,np.ones((19,19),np.uint8))>0)&(cv2.dilate(m,np.ones((3,3),np.uint8))==0)
 # Do not fit the red exclusion graphic or unrelated white support lettering.
 ring&=~((image[:,:,0]>.65)&(image[:,:,0]>image[:,:,1]*1.5));ring&=~(np.min(image,axis=2)>.74)
 fill=np.median(image[m>0],axis=0);observed=(image-background)[ring].reshape(-1);best=None
 glows=[cv2.GaussianBlur(m,(0,0),s) for s in [1,4]]
 for dy in range(1,7):
  shifted=np.roll(m,dy,axis=0);shifted[:dy]=0
  for blur in [1,2,3,4,5]:
   shadow=cv2.GaussianBlur(shifted,(0,0),blur)
   components=[((fill-background)*v[:,:,None])[ring].reshape(-1) for v in glows]+[(-background*shadow[:,:,None])[ring].reshape(-1)]
   matrix=np.stack(components,axis=1);fit=lsq_linear(matrix,observed,bounds=(0,[.6,.6,.85]));mse=float(np.mean((matrix@fit.x-observed)**2))
   if best is None or mse<best['mse']:best={'shadow_y':dy,'shadow_blur':blur,'white_or_lime_glow_sigma':[1,4],'coefficients':fit.x.tolist(),'mse':mse}
 results.append({'frame':index,'fit':best,'method_limit':'Background is estimated by local inpainting; this does not uniquely identify original glow/shadow settings.'})
(out/'effect-edge-fit.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(json.dumps(results))
