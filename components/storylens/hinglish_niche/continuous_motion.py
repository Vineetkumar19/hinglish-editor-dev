"""Native-frame motion measurements; flattened exports do not reveal an AE camera."""
import csv
import json
import math
from pathlib import Path

import cv2
import numpy as np

VERSION = 1


class ContinuousMotionScan:
    """Track image features between EVERY adjacent frame, not only scene medians.

    Local flow disagreement is evidence for layered/subject motion, not proof of
    Z-depth, physical camera parameters or recovered After Effects keyframes.
    """
    def __init__(self, folder, source_offset=0):
        cv2.setNumThreads(2)
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.file=(self.folder/'continuous-motion.csv').open('w',newline='',encoding='utf8')
        self.writer=csv.writer(self.file)
        self.writer.writerow(['frame','source_seconds','span_seconds','cut_candidate','pixel_change',
            'tracked_points','global_inliers','dx_px_per_second','dy_px_per_second',
            'zoom_fraction_per_second','rotation_degrees_per_second','local_residual_px_per_second',
            'moving_cell_fraction','cell_flow_json'])
        self.offset=source_offset;self.previous=None;self.previous_t=None;self.hist=None
        self.n=0;self.seconds=[];self.bucket=[];self.bucket_number=None

    def __call__(self, rgb,t,index,delta):
        t+=self.offset
        gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
        hist=cv2.calcHist([gray],[0],None,[32],[0,256]);cv2.normalize(hist,hist)
        hist_change=cv2.compareHist(self.hist,hist,cv2.HISTCMP_BHATTACHARYYA) if self.hist is not None else 0
        cut=self.previous is not None and ((delta>18 and hist_change>.24) or delta>47)
        dt=t-self.previous_t if self.previous_t is not None else 0
        values={'frame':index,'at':t,'span':dt,'cut':bool(cut),'change':delta,'points':0,
            'inliers':None,'dx':None,'dy':None,'zoom':None,'rotation':None,'residual':None,'moving_cells':None,'cells':[]}
        if self.previous is not None and dt>0 and not cut:
            points=cv2.goodFeaturesToTrack(self.previous,96,.008,5,blockSize=3)
            if points is not None and len(points)>=8:
                moved,status,error=cv2.calcOpticalFlowPyrLK(self.previous,gray,points,None,
                    winSize=(15,15),maxLevel=2,criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,15,.01))
                if moved is not None:
                    keep=(status[:,0]==1)&np.isfinite(moved[:,0,:]).all(axis=1)&(error[:,0]<25)
                    a=points[keep].reshape(-1,2);b=moved[keep].reshape(-1,2)
                    values['points']=len(a)
                    if len(a)>=8:
                        matrix,mask=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,
                            ransacReprojThreshold=1.25,maxIters=300,confidence=.95)
                        if matrix is not None:
                            predicted=a@matrix[:,:2].T+matrix[:,2]
                            flow=(b-a)/dt;residual=np.linalg.norm(b-predicted,axis=1)/dt
                            scale=math.hypot(matrix[0,0],matrix[1,0])
                            # Similarity translation depends on rotation origin;
                            # use movement at the centre to describe visible pan.
                            centre=np.array([gray.shape[1]/2,gray.shape[0]/2])
                            centre_flow=(matrix[:,:2]@centre+matrix[:,2]-centre)/dt
                            values.update(inliers=float(mask.mean()),dx=float(centre_flow[0]),dy=float(centre_flow[1]),
                                zoom=(scale-1)/dt,rotation=math.degrees(math.atan2(matrix[1,0],matrix[0,0]))/dt,
                                residual=float(np.median(residual)))
                            cells=[]
                            for y in range(3):
                                for x in range(3):
                                    selected=(a[:,0]>=x*gray.shape[1]/3)&(a[:,0]<(x+1)*gray.shape[1]/3)&(a[:,1]>=y*gray.shape[0]/3)&(a[:,1]<(y+1)*gray.shape[0]/3)
                                    if selected.sum()<3:continue
                                    movement=np.median(flow[selected],axis=0)
                                    cells.append({'cell':y*3+x,'points':int(selected.sum()),'dx':round(float(movement[0]),4),
                                        'dy':round(float(movement[1]),4),'residual':round(float(np.median(residual[selected])),4)})
                            values['cells']=cells
                            values['moving_cells']=sum(math.hypot(c['dx'],c['dy'])>.35 for c in cells)/len(cells) if cells else None
        self.writer.writerow([index,round(t,6),round(dt,6),int(cut),round(delta,5),values['points'],
            *[None if values[k] is None else round(values[k],6) for k in ['inliers','dx','dy','zoom','rotation','residual','moving_cells']],
            json.dumps(values['cells'],separators=(',',':'))])
        number=int(t)
        if self.bucket_number is not None and number!=self.bucket_number:self.finish_second()
        self.bucket_number=number;self.bucket.append(values);self.n+=1
        self.previous=gray;self.previous_t=t;self.hist=hist

    def finish_second(self):
        if not self.bucket:return
        rows=self.bucket;good=[r for r in rows if r['inliers'] is not None and r['inliers']>=.5]
        duration=sum(r['span'] for r in rows if not r['cut'])
        moving=sum(r['span'] for r in good if math.hypot(r['dx'],r['dy'])>.35 or abs(r['zoom'])>.002 or abs(r['rotation'])>.15 or r['residual']>.4)
        def median(k):
            valid=[r[k] for r in good if r[k] is not None]
            return round(float(np.median(valid)),6) if valid else None
        self.seconds.append({'start':self.bucket_number,'end':max(r['at']+max(0,r['span']) for r in rows),
            'native_frames':len(rows),'first_frame':rows[0]['frame'],'last_frame':rows[-1]['frame'],
            'tracked_frame_fraction':len(good)/len(rows),'cut_candidates':sum(r['cut'] for r in rows),
            'motion_fraction_of_measurable_time':round(moving/duration,5) if duration and good else None,
            'median':{k:median(k) for k in ['dx','dy','zoom','rotation','residual','moving_cells']},
            'classification':'unmeasurable' if len(good)<len(rows)*.35 else ('continuous image motion' if moving/max(duration,.001)>.7 else 'intermittent or weak image motion'),
            'status':'Image-space measurements at 256x144; texture, subject movement and moving text can imitate layer/camera motion.'})
        self.bucket=[]

    def close(self):
        self.finish_second();self.file.close()
        (self.folder/'motion-seconds.json').write_text(json.dumps(self.seconds,indent=2),encoding='utf8')
        return self.seconds


def motion_brief(row):
    m=row['median'];phrases=[]
    if m['zoom'] is not None and abs(m['zoom'])>.002:phrases.append('push-in' if m['zoom']>0 else 'pull-out')
    if m['dx'] is not None and abs(m['dx'])>.35:phrases.append('rightward image flow' if m['dx']>0 else 'leftward image flow')
    if m['dy'] is not None and abs(m['dy'])>.35:phrases.append('downward image flow' if m['dy']>0 else 'upward image flow')
    if m['rotation'] is not None and abs(m['rotation'])>.15:phrases.append('rotational movement')
    if m['residual'] is not None and m['residual']>.4:phrases.append('different local movement: parallax/subject/text candidate')
    return ', '.join(phrases) or row['classification']


def continuity_review(seconds,quiet_limit=.75):
    """Conservative camera-motion warnings, not an aesthetic quality score.

    Local residual alone is excluded: grain, overlays and flicker can change
    pixels while the principal photographs remain stationary.
    """
    quiet=[];unknown=[];start=None;end=None
    for row in seconds:
        m=row['median'];measurable=row['tracked_frame_fraction']>=.5 and m['dx'] is not None
        moving=measurable and (math.hypot(m['dx'],m['dy'])>.35 or abs(m['zoom'])>.002 or abs(m['rotation'])>.15)
        if not measurable:unknown.append([row['start'],row['end']])
        if measurable and not moving:
            if start is None:start=row['start']
            end=row['end']
        elif start is not None:
            if end-start>=quiet_limit:quiet.append([start,end])
            start=None
    if start is not None and end-start>=quiet_limit:quiet.append([start,end])
    return {'needs_review':bool(quiet),'low_camera_motion_ranges':quiet,'unmeasurable_ranges':unknown,
        'grain_alone_counts_as_camera':False,'scope':'Image-space global motion; moving subjects/layers and flat texture remain ambiguous. Review focal images, readable evidence and real action separately.',
        'warnings':['Camera/photo movement needs review after the entrance; texture motion alone is insufficient.'] if quiet else []}
