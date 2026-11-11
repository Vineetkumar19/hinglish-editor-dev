import hashlib
import io
import math
import re
import unicodedata

import cv2
import numpy as np
from PIL import Image,ImageOps

MAX_UPLOAD=25*1024*1024
MAX_PIXELS=80_000_000

def validate_screenshot(data):
    if not isinstance(data,bytes) or not 0<len(data)<=MAX_UPLOAD:
        raise ValueError('Photo screenshot invalid: choose a PNG, JPG or WebP screenshot smaller than 25 MB.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            width,height=image.size;fmt=image.format
            if fmt not in ('PNG','JPEG','WEBP') or min(width,height)<100 or width*height>MAX_PIXELS or max(width,height)>40000:
                raise ValueError('Unsupported screenshot dimensions or format')
            image.verify()
    except (OSError,ValueError,Image.DecompressionBombError) as error:
        raise ValueError('Photo screenshot invalid: choose a readable PNG, JPG or WebP screenshot with at least 100 pixels on each side.') from error
    return {'width':width,'height':height,'format':fmt,'extension':{'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}[fmt]}

def detect_tiles(image):
    """Propose large photograph rectangles; local Vision labels/includes them."""
    rgb=np.asarray(ImageOps.exif_transpose(image).convert('RGB'))
    height,width=rgb.shape[:2]
    scale=min(1,2200/width)
    if scale<1:rgb=cv2.resize(rgb,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    h,w=rgb.shape[:2]
    # Search grids normally have a repeated neutral page ground. Edge samples
    # avoid learning a photograph's colours as the page background.
    edge=np.concatenate((rgb[:,0:8].reshape(-1,3),rgb[:,-8:].reshape(-1,3)),axis=0)
    quant=(edge//8)*8
    colors,counts=np.unique(quant,axis=0,return_counts=True)
    background=colors[counts.argmax()].astype(np.int16)+4
    delta=np.max(np.abs(rgb.astype(np.int16)-background),axis=2)
    mask=(delta>24).astype(np.uint8)*255
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    min_w=max(95,w*.08);min_h=max(90,w*.065)
    for contour in contours:
        x,y,bw,bh=cv2.boundingRect(contour)
        if bw<min_w or bh<min_h or bw*bh>w*h*.65 or not .33<bw/bh<4.4:continue
        fill=np.mean(mask[y:y+bh,x:x+bw]>0)
        if fill<.43:continue
        box=[max(0,round(v/scale)) for v in (x,y,bw,bh)]
        box[2]=min(box[2],width-box[0]);box[3]=min(box[3],height-box[1])
        boxes.append(box)
    if len(boxes)>=3:
        typical=float(np.median([box[2] for box in boxes]))
        regular=[box for box in boxes if .70*typical<=box[2]<=1.3*typical]
        columns=[]
        for box in regular:
            if not any(abs(box[0]-x)<typical*.15 for x in columns):columns.append(box[0])
        if len(columns)>=2:
            boxes=[box for box in boxes if box[2]<1.5*typical]
            # At the screenshot edge adjacent images can share one contour.
            # Reuse the observed grid's columns to recover their separate rows.
            for left in columns:
                x=round(left*scale);right=min(w,round((left+typical)*scale))
                rows=(np.mean(mask[:,x+3:max(x+4,right-3)]>0,axis=1)>.55).astype(np.uint8)
                rows=cv2.morphologyEx(rows[:,None],cv2.MORPH_CLOSE,np.ones((3,1),np.uint8)).ravel()
                edges=np.diff(np.r_[0,rows,0].astype(int));starts=np.where(edges==1)[0];ends=np.where(edges==-1)[0]
                for top,bottom in zip(starts,ends):
                    # A screenshot can end halfway through its last row. Only
                    # relax height/aspect filtering at that edge and within
                    # an already-established photo column, never for chips.
                    clipped=bottom>=h-2 and bottom-top>=max(32,typical*scale*.10)
                    if bottom-top<min_h and not clipped:continue
                    candidate=[left,round(top/scale),round(typical),min(height-round(top/scale),round((bottom-top)/scale))]
                    def overlap(other):
                        a,b,c,d=candidate;e,f,g,i=other
                        area=max(0,min(a+c,e+g)-max(a,e))*max(0,min(b+d,f+i)-max(b,f))
                        return area/max(1,min(c*d,g*i))
                    if not any(overlap(other)>.55 for other in boxes):boxes.append(candidate)
    boxes.sort(key=lambda b:(round(b[1]/max(24,width*.02)),b[0]))
    result=[]
    if len(boxes)>80:raise ValueError('Photo screenshot too large: split it into screenshots with up to 80 main photos each.')
    for index,box in enumerate(boxes,1):
        x,y,bw,bh=box
        # Keep this card's heading, but never include the next photo/title in
        # the same masonry column as evidence for this card.
        following=[other[1] for other in boxes if other[1]>=y+bh and
                   max(0,min(x+bw,other[0]+other[2])-max(x,other[0]))>=min(bw,other[2])*.5]
        context_bottom=min(height,y+bh+80,min(following,default=height))
        result.append({'id':index,'box':box,'context_box':[x,max(0,y-2),bw,context_bottom-max(0,y-2)],
                       'partial':y+bh>=height-2})
    return result

def _features(image):
    rgb=np.asarray(image.convert('RGB'))
    scale=min(1,900/max(image.size))
    if scale<1:rgb=cv2.resize(rgb,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    points,desc=cv2.SIFT_create(nfeatures=900,contrastThreshold=.025).detectAndCompute(gray,None)
    return gray,points,desc

def similarity(reference,candidate):
    """Geometric feature agreement; shared colours/subjects alone are insufficient."""
    if min(reference.size)<32 or min(candidate.size)<32:return {'matched':False,'score':0,'inliers':0,'coverage':0}
    a,k1,d1=_features(reference);b,k2,d2=_features(candidate)
    small=lambda im:np.asarray(im.convert('L').resize((32,32),Image.Resampling.LANCZOS),np.float32)
    h1=cv2.dct(small(reference))[:8,:8].ravel()[1:];h2=cv2.dct(small(candidate))[:8,:8].ravel()[1:]
    distance=int(np.count_nonzero((h1>np.median(h1))!=(h2>np.median(h2))))
    result={'matched':False,'score':0.,'inliers':0,'coverage':0.,'hash_distance':distance}
    if d1 is None or d2 is None or len(k1)<6 or len(k2)<6:return result
    pairs=cv2.BFMatcher().knnMatch(d1,d2,k=2)
    good=[p[0] for p in pairs if len(p)==2 and p[0].distance<.72*p[1].distance]
    if len(good)<6:return result
    src=np.float32([k1[m.queryIdx].pt for m in good]);dst=np.float32([k2[m.trainIdx].pt for m in good])
    transform,inlier_mask=cv2.findHomography(src,dst,cv2.RANSAC,3.5)
    if transform is None or inlier_mask is None:return result
    selected=inlier_mask.ravel().astype(bool);count=int(selected.sum())
    if count<4:return result
    hull=cv2.convexHull(src[selected]);coverage=float(cv2.contourArea(hull)/max(1,a.shape[0]*a.shape[1]))
    agreement=count/len(good)
    footprint=0.
    try:
        corners=np.float32([[[0,0],[b.shape[1],0],[b.shape[1],b.shape[0]],[0,b.shape[0]]]])
        projected=cv2.perspectiveTransform(corners,np.linalg.inv(transform))[0]
        border=np.float32([[0,0],[a.shape[1],0],[a.shape[1],a.shape[0]],[0,a.shape[0]]])
        if np.isfinite(projected).all() and cv2.isContourConvex(projected):
            area,_=cv2.intersectConvexConvex(projected,border);footprint=float(area/max(1,a.shape[0]*a.shape[1]))
    except (cv2.error,np.linalg.LinAlgError):pass
    colour=0.;effective_width=effective_height=0
    try:
        ar=cv2.resize(np.asarray(reference.convert('RGB')), (a.shape[1],a.shape[0]))
        br=cv2.resize(np.asarray(candidate.convert('RGB')), (b.shape[1],b.shape[0]))
        warped=cv2.warpPerspective(br,np.linalg.inv(transform),(a.shape[1],a.shape[0]))
        valid=cv2.warpPerspective(np.ones(b.shape,np.uint8),np.linalg.inv(transform),(a.shape[1],a.shape[0])).astype(bool)
        valid[:3]=False;valid[-3:]=False;valid[:,:3]=False;valid[:,-3:]=False
        difference=np.abs(cv2.GaussianBlur(ar,(5,5),0).astype(float)-cv2.GaussianBlur(warped,(5,5),0).astype(float)).mean(axis=2)
        if valid.any():colour=float((difference[valid]<30).mean())
        corners=np.float32([[[0,0],[a.shape[1],0],[a.shape[1],a.shape[0]],[0,a.shape[0]]]])
        projected=cv2.perspectiveTransform(corners,transform)[0]
        factor=max(candidate.size)/max(b.shape)
        effective_width=round(min(np.linalg.norm(projected[1]-projected[0]),np.linalg.norm(projected[2]-projected[3]))*factor)
        effective_height=round(min(np.linalg.norm(projected[3]-projected[0]),np.linalg.norm(projected[2]-projected[1]))*factor)
    except (cv2.error,np.linalg.LinAlgError):pass
    matched=footprint>=.78 and colour>=.90 and ((count>=10 and coverage>=.20 and agreement>=.65) or (count>=7 and coverage>=.30 and distance<=10 and agreement>=.75))
    score=min(1.,.35*min(count/28,1)+.35*min(coverage/.65,1)+.30*agreement)
    return {**result,'matched':bool(matched),'score':round(score,4),'inliers':count,'coverage':round(coverage,4),'agreement':round(agreement,4),'footprint':round(footprint,4),'pixel_agreement':round(colour,4),'effective_width':effective_width,'effective_height':effective_height}

def _text(value,limit):
    if not isinstance(value,str):raise ValueError('Photo analysis incomplete: a readable label is missing.')
    value=' '.join(value.split())
    if len(value)>limit:raise ValueError('Photo analysis incomplete: a label is too long.')
    return value

def normalise_reading(value,tiles):
    if not isinstance(value,dict) or not isinstance(value.get('photos'),list):raise ValueError('Photo analysis incomplete: no photo list was returned.')
    query=_text(value.get('query',''),220);title=_text(value.get('title','Photo collection'),100)
    known={row['id']:row for row in tiles};seen=set();photos=[]
    for row in value['photos']:
        if not isinstance(row,dict) or type(row.get('id')) is not int or row['id'] not in known or row['id'] in seen:
            raise ValueError('Photo analysis incomplete: a photo does not belong to this screenshot.')
        seen.add(row['id'])
        if type(row.get('include')) is not bool:raise ValueError('Photo analysis incomplete: choose photo or page control.')
        if not row['include']:continue
        entry={k:_text(row.get(k,''),220 if k=='query' else 300) for k in ('caption','publisher','query','description')}
        if not entry['query'] or re.search(r'https?://|file:|javascript:|[\x00-\x08]',entry['query'],re.I):
            raise ValueError('Photo analysis incomplete: provide search words, not links or commands.')
        photos.append({**known[row['id']],**entry})
    if seen!=set(known):raise ValueError('Photo analysis incomplete: some visible photo tiles were omitted.')
    order={row['id']:i for i,row in enumerate(tiles)}
    photos.sort(key=lambda row:order[row['id']])
    return {'query':query,'title':title or 'Photo collection','photos':photos}

def photo_filename(index,title,digest,fmt):
    value=unicodedata.normalize('NFKD',title).encode('ascii','ignore').decode()
    slug=re.sub(r'[^a-zA-Z0-9]+','-',value).strip('-').lower()[:65] or 'photo'
    extension={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','AVIF':'.avif','GIF':'.gif'}.get(fmt,'.png')
    return f'{int(index):03d}-{slug}-{digest[:8]}{extension}'

def pixel_hash(image):
    image=ImageOps.exif_transpose(image).convert('RGB')
    return hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()
