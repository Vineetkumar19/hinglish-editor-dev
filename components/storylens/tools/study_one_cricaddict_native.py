"""Interpret every native frame of ONE reference with the cached local CLIP model."""
import csv,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.analyze_documentary_reference import facts,scan,write_json
from tools.classify_crick_edit_dna import CLIP,VISUAL

BASE=ROOT/'output/reference-analysis/cricAddict-by-video/reference-01'
OLD=ROOT/'output/reference-analysis/crick-edit-editing-style/reference-01'

def main():
    import torch
    from transformers import CLIPModel,CLIPProcessor
    BASE.mkdir(parents=True,exist_ok=True)
    item=json.loads((OLD.parent/'inventory.json').read_text(encoding='utf8'))[0]
    source=facts(Path(item['path']));prior=json.loads((OLD/'dna-coverage.json').read_text(encoding='utf8'))
    if source!=prior['source']:raise ValueError('Reference changed since the previous measurements')
    expected=prior['native_frames_measured'];began=time.time()
    write_json(BASE/'source.json',{'name':item['name'],'slug':'reference-01',**source})
    completed=BASE/'native-vision-coverage.json'
    if completed.exists() and json.loads(completed.read_text())['source']==source:
        print('Full native-frame interpretation already complete',flush=True);return
    torch.set_num_threads(2)
    model=CLIPModel.from_pretrained(str(CLIP),local_files_only=True).eval()
    processor=CLIPProcessor.from_pretrained(str(CLIP),local_files_only=True,use_fast=False)
    banks={}
    for key,labels in VISUAL.items():
        with torch.inference_mode():
            features=model.get_text_features(**processor(text=list(labels.values()),return_tensors='pt',padding=True))
            if not isinstance(features,torch.Tensor):features=features.pooler_output
            banks[key]=(list(labels),torch.nn.functional.normalize(features,dim=-1).numpy())
    embeddings=np.lib.format.open_memmap(BASE/'native-clip-embeddings.npy',mode='w+',dtype='float32',shape=(expected,model.config.projection_dim))
    csvfile=(BASE/'native-visual-candidates.csv').open('w',newline='',encoding='utf8');writer=csv.writer(csvfile)
    writer.writerow(['frame','relative_seconds',*[f'{key}_{name}' for key in banks for name in ('candidate','cosine_similarity')]])
    pending=[];count=0;first_rate=None;last=0
    def flush():
        nonlocal count,first_rate,last
        if not pending:return
        with torch.inference_mode():
            features=model.get_image_features(**processor(images=[p[0] for p in pending],return_tensors='pt'))
            if not isinstance(features,torch.Tensor):features=features.pooler_output
            values=torch.nn.functional.normalize(features,dim=-1).numpy()
        if count+len(values)>expected:raise ValueError('More source frames than verified inventory')
        embeddings[count:count+len(values)]=values
        for (_,t,index),v in zip(pending,values):
            row=[index,round(t,6)]
            for names,bank in banks.values():
                scores=bank@v;best=int(scores.argmax());row.extend([names[best],round(float(scores[best]),5)])
            writer.writerow(row)
        count+=len(values);pending.clear()
        if count>=64 and first_rate is None:
            first_rate=count/(time.time()-began)
            print(f'Initial measured throughput {first_rate:.2f} frames/s; estimated full frame pass {expected/first_rate/60:.1f} min',flush=True)
        if time.time()-last>=20:
            csvfile.flush();embeddings.flush()
            write_json(BASE/'progress.json',{'stage':'Every-native-frame local vision','status':'running','frames':count,'total_frames':expected,
                'elapsed_seconds':time.time()-began,'estimated_remaining_seconds':(expected-count)/max(.01,count/(time.time()-began)),
                'other_videos_started':False,'vision_model':'Offline CLIP ViT-B/32 float32 CPU; two threads'})
            last=time.time()
    def callback(image,t,index,delta):
        pending.append((image.copy(),t,index))
        if len(pending)==16:flush()
    write_json(BASE.parent/'decoder-settings.json',{'decoder':'h264_cuvid'})
    try:
        result=scan(Path(item['path']),BASE,callback);flush()
    finally:csvfile.close();embeddings.flush()
    if result['decoded_frames']!=expected or count!=expected:raise ValueError('Native frame interpretation incomplete')
    write_json(completed,{'status':'complete','source':source,'native_frames':count,'semantic_frames':count,'elapsed_seconds':time.time()-began,
        'encoder':'CLIP ViT-B/32','encoder_dimensions':model.config.projection_dim,'embedding_file':'native-clip-embeddings.npy',
        'semantics':'Every native frame has local similarity candidates. Not human-certified font, player, camera or layer identities.',
        'motion_evidence':'../../continuous-documentary-memory/crick-edit-editing-style/reference-01/continuous-motion.csv',
        'new_neural_weights_trained':False,'cloud_inference':False,'other_videos_started':False})
    write_json(BASE/'progress.json',{'stage':'Every-native-frame local vision complete','status':'complete','frames':count,'total_frames':expected})
    print('COMPLETE one reference, every native frame interpreted:',count,flush=True)

if __name__=='__main__':main()
