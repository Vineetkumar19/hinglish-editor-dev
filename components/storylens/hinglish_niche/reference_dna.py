"""Measured editing references. Heuristic motion/cut/audio labels retain their uncertainty."""
import csv
import json
import math
import re
import sqlite3
from pathlib import Path

import cv2
import numpy as np
from scipy import signal


class VisualScan:
    """Every native frame: colour, texture, change and phase correlation.

    Sparse optical-flow similarity transforms are sampled at up to 5 Hz. They
    describe image motion, not a recovered physical camera or separated layers.
    """
    def __init__(self, folder):
        cv2.setNumThreads(2)
        self.folder=Path(folder)
        self.file=(self.folder/'visual-features.csv').open('w',newline='',encoding='utf-8')
        self.writer=csv.writer(self.file)
        self.writer.writerow(['frame','seconds','pixel_change','histogram_change','brightness','contrast','saturation',
                             'red','green','blue','edge_density','phase_dx','phase_dy','phase_response',
                             'affine_scale','affine_rotation_degrees','affine_inlier_fraction','layer_motion_residual'])
        self.previous=None;self.hist=None;self.flow_frame=None;self.flow_time=-1
        self.scenes=[];self.start=0.;self.last=0.;self.n=0;self.sums=np.zeros(7);self.motion=[]
        self.boundaries=[];self.pending_boundary=0.
        (self.folder/'scene-keyframes').mkdir(exist_ok=True)
        self.scene_frame=None;self.scene_frame_time=None;self.scene_frame_index=None;self.scene_edge=-1.

    def finish_scene(self,end,boundary):
        if not self.n:return
        m=self.sums/self.n
        good=[x for x in self.motion if x['inliers']>=.5 and .85<x['scale']<1.15]
        zoom=[(x['scale']-1)/max(.01,x['span']) for x in good]
        image='scene-keyframes/scene-'+str(len(self.scenes)).zfill(5)+'.jpg'
        from PIL import Image
        Image.fromarray(self.scene_frame).save(self.folder/image,quality=88)
        self.scenes.append({'index':len(self.scenes),'start':round(self.start,6),'end':round(end,6),
            'duration':round(end-self.start,6),'frames':self.n,'boundary_candidate':boundary,
            'representative':{'file':image,'seconds':round(self.scene_frame_time,6),'frame':self.scene_frame_index,
                              'selection':'An in-scene native frame with high edge detail; not an adjacent-scene thumbnail.'},
            'colour':{'brightness':round(m[0],3),'contrast':round(m[1],3),'saturation':round(m[2],3),
                      'mean_rgb':[round(v,3) for v in m[3:6]],'edge_density':round(m[6],4)},
            'camera_estimate':{'samples':len(good),'zoom_rate_median':float(np.median(zoom)) if zoom else None,
                               'affine_motion_samples':self.motion,
                               'note':'Image-space estimate; subject movement and perspective can imitate a camera pan, zoom or parallax.'}})
        self.start=end;self.n=0;self.sums[:]=0;self.motion=[];self.scene_frame=None;self.scene_edge=-1.

    def __call__(self,frame,t,index,delta):
        gray=cv2.cvtColor(frame,cv2.COLOR_RGB2GRAY)
        hsv=cv2.cvtColor(frame,cv2.COLOR_RGB2HSV)
        hist=cv2.calcHist([hsv],[0,1],None,[16,8],[0,180,0,256]);cv2.normalize(hist,hist)
        hist_change=float(cv2.compareHist(self.hist,hist,cv2.HISTCMP_BHATTACHARYYA)) if self.hist is not None else 0.
        dx=dy=response=0.;scale=rotation=inliers=residual=None
        cut=index>0 and t-self.start>=.25 and ((delta>18 and hist_change>.24) or delta>47)
        if cut:
            self.finish_scene(t,{'time':t,'pixel_change':delta,'histogram_change':hist_change,
                                 'kind':'hard-change candidate','verified':False})
            self.boundaries.append(t);self.flow_frame=None
        elif self.previous is not None:
            (dx,dy),response=cv2.phaseCorrelate(self.previous.astype(np.float32),gray.astype(np.float32))
        if self.flow_frame is not None and t-self.flow_time>=.2 and not cut:
            points=cv2.goodFeaturesToTrack(self.flow_frame,60,.015,6)
            if points is not None and len(points)>=8:
                moved,status,_=cv2.calcOpticalFlowPyrLK(self.flow_frame,gray,points,None,winSize=(15,15),maxLevel=2)
                a=points[status[:,0]==1].reshape(-1,2);b=moved[status[:,0]==1].reshape(-1,2)
                if len(a)>=8:
                    matrix,mask=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=2)
                    if matrix is not None:
                        scale=float(math.hypot(matrix[0,0],matrix[1,0]));rotation=float(math.degrees(math.atan2(matrix[1,0],matrix[0,0])))
                        inliers=float(mask.mean());pred=a@matrix[:,:2].T+matrix[:,2]
                        residual=float(np.median(np.linalg.norm(b-pred,axis=1)))
                        self.motion.append({'time':round(t,4),'span':round(t-self.flow_time,4),'scale':round(scale,5),
                            'rotation':round(rotation,3),'dx':round(float(matrix[0,2]),3),'dy':round(float(matrix[1,2]),3),
                            'inliers':round(inliers,3),'residual':round(residual,3)})
        if self.flow_frame is None or t-self.flow_time>=.2:self.flow_frame=gray.copy();self.flow_time=t
        edges=float((cv2.Canny(gray,70,160)>0).mean())
        if self.scene_frame is None or edges>self.scene_edge:
            self.scene_frame=frame.copy();self.scene_frame_time=t;self.scene_frame_index=index;self.scene_edge=edges
        values=[float(gray.mean()),float(gray.std()),float(hsv[:,:,1].mean()),*frame.mean(axis=(0,1)).tolist(),edges]
        self.sums+=values;self.n+=1;self.last=t
        self.writer.writerow([index,round(t,6),round(delta,4),round(hist_change,4),*[round(v,4) for v in values],
                              round(dx,4),round(dy,4),round(response,4),scale,rotation,inliers,residual])
        self.previous=gray;self.hist=hist

    def close(self,duration):
        self.finish_scene(duration,None);self.file.close()
        (self.folder/'scenes.json').write_text(json.dumps(self.scenes,indent=2)+'\n',encoding='utf-8')
        return self.scenes


def audio_features(audio,rate=16000):
    """Complete mixed-track analysis in 20-ms blocks. No invented isolated stems."""
    audio=np.asarray(audio,np.float32)
    if audio.ndim!=1 or not len(audio):raise ValueError('Supply a non-empty mono audio track.')
    hop=int(rate*.02);n=math.ceil(len(audio)/hop)
    frames=np.pad(audio,(0,n*hop-len(audio))).reshape(n,hop)
    rms=np.sqrt(np.mean(frames*frames,axis=1)+1e-12);peak=np.max(np.abs(frames),axis=1)
    zcr=np.mean(frames[:,1:]*frames[:,:-1]<0,axis=1)
    spectrum=np.abs(np.fft.rfft(frames*np.hanning(hop),n=512,axis=1)).astype(np.float32)
    frequencies=np.fft.rfftfreq(512,1/rate)
    centroid=(spectrum@frequencies)/np.maximum(spectrum.sum(axis=1),1e-8)
    bass=spectrum[:,frequencies<180].sum(axis=1)/np.maximum(spectrum.sum(axis=1),1e-8)
    flux=np.zeros(n,np.float32)
    if n>1:flux[1:]=np.maximum(0,np.diff(spectrum,axis=0)).mean(axis=1)
    prominent,_=signal.find_peaks(flux,height=float(np.median(flux)+2.5*np.std(flux)),distance=10,prominence=float(np.std(flux)))
    onsets=[{'seconds':round(float(i*.02),3),'strength':float(flux[i]),'rms_dbfs':float(20*np.log10(rms[i]+1e-9)),
             'bass_fraction':float(bass[i]),'verified_sound_type':None} for i in prominent]
    regions=[]
    for start in range(0,n,1500):
        end=min(n,start+1500);env=flux[start:end]-flux[start:end].mean()
        ac=signal.correlate(env,env,mode='full',method='fft')[len(env)-1:]
        lo,hi=16,min(51,len(ac));lag=lo+int(np.argmax(ac[lo:hi])) if hi>lo else 0
        confidence=float(ac[lag]/max(ac[0],1e-8)) if lag else 0.
        beats=[]
        if lag and confidence>.12:
            phase=max(range(min(lag,len(env))),key=lambda p:float(np.maximum(env[p::lag],0).sum()))
            beats=[round((start+i)*.02,4) for i in range(phase,len(env),lag)]
        regions.append({'start':start*.02,'end':min(end*.02,len(audio)/rate),'bpm_estimate':round(3000/lag,2) if lag and confidence>.12 else None,
                        'beat_candidates_seconds':beats,
                        'periodicity_confidence':confidence,'status':'mixed-track rhythmic estimate, not verified musical beats'})
    arrays=np.stack([np.arange(n)*.02,rms,peak,zcr,centroid,bass,flux],axis=1)
    return arrays,{'duration':len(audio)/rate,'sample_rate':rate,'analysis_hop_seconds':.02,
        'final_block_padding_samples':n*hop-len(audio),
        'beat_grid_version':1,
        'peak_dbfs':float(20*np.log10(max(float(np.max(np.abs(audio))),1e-9))),
        'rms_dbfs':float(20*np.log10(np.sqrt(np.mean(audio*audio))+1e-9)),
        'onsets':onsets,'tempo_regions':regions,
        'note':'Full mixed audio measured. Voice, music and effects overlap; this is not source-separated stem analysis.'}


class StyleDatabase:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS records(
            id TEXT PRIMARY KEY, style TEXT NOT NULL, source TEXT NOT NULL, start REAL, end REAL,
            kind TEXT NOT NULL, text TEXT NOT NULL, data TEXT NOT NULL, embedding BLOB, model TEXT);
            CREATE INDEX IF NOT EXISTS style_time ON records(style,source,start);
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(id UNINDEXED,style UNINDEXED,text);''')

    def replace_source(self,style,source,records):
        with self.db:
            self.db.execute('DELETE FROM search_index WHERE id IN (SELECT id FROM records WHERE style=? AND source=?)',(style,source))
            self.db.execute('DELETE FROM records WHERE style=? AND source=?',(style,source))
            for i,row in enumerate(records):
                key=f'{style}/{source}/{i}'
                vector=row.get('vector');blob=np.asarray(vector,np.float32).tobytes() if vector is not None else None
                self.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?)',(key,style,source,row.get('start'),row.get('end'),
                    row['kind'],row['text'],json.dumps(row.get('data',{}),ensure_ascii=False),blob,row.get('model')))
                self.db.execute('INSERT INTO search_index VALUES(?,?,?)',(key,style,row['text']))

    def search_vector(self,style,vector,limit=5,kinds=None,model=None):
        q=np.asarray(vector,np.float32);q=q/max(np.linalg.norm(q),1e-8)
        sql='SELECT id,source,start,end,kind,text,data,embedding FROM records WHERE style=? AND embedding IS NOT NULL'
        parameters=[style]
        if model is not None:
            sql+=' AND model=?';parameters.append(model)
        if kinds:
            kinds=list(dict.fromkeys(kinds))
            sql+=' AND kind IN ('+','.join('?' for _ in kinds)+')'
            parameters.extend(kinds)
        rows=self.db.execute(sql,parameters).fetchall()
        results=[]
        for row in rows:
            v=np.frombuffer(row[7],dtype=np.float32)
            if len(v)!=len(q):continue
            results.append({'id':row[0],'source':row[1],'start':row[2],'end':row[3],'kind':row[4],
                            'text':row[5],'data':json.loads(row[6]),'similarity':float(v@q/max(np.linalg.norm(v),1e-8))})
        return sorted(results,key=lambda r:-r['similarity'])[:limit]

    def search_text(self,style,query,limit=5,kinds=None):
        tokens=list(dict.fromkeys(re.findall(r'\w+',query,flags=re.UNICODE)))[:24]
        if not tokens:return []
        match=' OR '.join('"'+t+'"' for t in tokens)
        sql='''SELECT r.id,r.source,r.start,r.end,r.kind,r.text,r.data,bm25(search_index)
          FROM search_index JOIN records r ON r.id=search_index.id
          WHERE search_index MATCH ? AND r.style=?'''
        params=[match,style]
        if kinds:
            sql+=' AND r.kind IN ('+','.join('?' for _ in kinds)+')';params.extend(kinds)
        sql+=' ORDER BY bm25(search_index) LIMIT ?';params.append(limit)
        return [{'id':r[0],'source':r[1],'start':r[2],'end':r[3],'kind':r[4],'text':r[5],
          'data':json.loads(r[6]),'similarity':None,'retrieval_method':'keyword fallback'} for r in self.db.execute(sql,params)]

    def close(self):self.db.close()
