"""CPU-only per-second visual interpretation, following cached video scans."""
import gc,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.deepen_documentary_memory import OUT,SETS,read,source_records
from tools.analyze_documentary_reference import write_json
from tools.classify_crick_edit_dna import CLIP,VISUAL,ranked
from hinglish_niche.reference_dna import StyleDatabase
from hinglish_niche.style_memory import StyleEmbedder

def main():
    import torch
    from PIL import Image
    from transformers import CLIPModel,CLIPProcessor
    torch.set_num_threads(2)
    model=CLIPModel.from_pretrained(str(CLIP),local_files_only=True).eval()
    processor=CLIPProcessor.from_pretrained(str(CLIP),local_files_only=True,use_fast=False)
    banks={}
    for key,labels in VISUAL.items():
        with torch.inference_mode():
            vectors=model.get_text_features(**processor(text=list(labels.values()),return_tensors='pt',padding=True))
            if not isinstance(vectors,torch.Tensor):vectors=vectors.pooler_output
            banks[key]=(list(labels),torch.nn.functional.normalize(vectors,dim=-1).numpy())
    encoder=StyleEmbedder(ROOT);completed=[];start=time.time()
    jobs=[]
    for style,base in SETS.items():
        oldbase=ROOT/'output/reference-analysis'/base
        jobs.extend((style,item,oldbase/item['slug']) for item in read(oldbase/'inventory.json'))
    for n,(style,item,old) in enumerate(jobs,1):
        folder=OUT/style/item['slug'];receipt=folder/'motion-coverage.json'
        while not receipt.exists():time.sleep(10)
        full=read(receipt)
        if not full['full_source']:raise ValueError('Partial motion source cannot become complete memory')
        semantic=folder/'semantic-seconds.json'
        files=sorted((folder/'frames').glob('*.jpg'))
        previous=read(semantic) if semantic.exists() else {}
        if previous.get('source')!=full['source'] or len(previous.get('frames',[]))!=len(files):
            rows=[];print(f'PER-SECOND VISUAL {n}/{len(jobs)}: {item["name"]} ({len(files)} frames)',flush=True)
            for a in range(0,len(files),16):
                batch=files[a:a+16];images=[Image.open(p).convert('RGB') for p in batch]
                with torch.inference_mode():
                    features=model.get_image_features(**processor(images=images,return_tensors='pt'))
                    if not isinstance(features,torch.Tensor):features=features.pooler_output
                    vectors=torch.nn.functional.normalize(features,dim=-1).numpy()
                for path,v in zip(batch,vectors):rows.append({'second':int(path.stem),'file':str(path),
                    'candidates':{key:ranked(v,bank,names) for key,(names,bank) in banks.items()}})
                for image in images:image.close()
                if a%128==0:print(f'Visual candidates {min(a+16,len(files))}/{len(files)}',flush=True)
            write_json(semantic,{'source':full['source'],'model':'Offline CLIP ViT-B/32, float32 CPU, two threads',
                'scope':'One actual source frame every second; all native frames have separate motion measurements.',
                'frames':rows,'status':'Similarity candidates, not verified exact fonts or recovered AE layer identities.'})
        seconds=read(folder/'motion-seconds.json');offset=read(folder/'scan.json')['source']['seconds']
        # Frame offset is already encoded in the motion file; old scene labels
        # use relative video time and require the original first native PTS.
        import csv
        with (old/'frame-metrics.csv').open(newline='',encoding='utf8') as f:offset=float(next(csv.DictReader(f))['source_pts_seconds'])
        records=source_records(item,old,folder,seconds,offset)
        for a in range(0,len(records),64):
            chunk=records[a:a+64];vectors=encoder.encode([r['text'] for r in chunk])
            for r,v in zip(chunk,vectors):r.update(vector=v,model=encoder.model_name)
        db=StyleDatabase(ROOT/'library/creator-profiles/editing-dna.sqlite3')
        try:db.replace_source(style,'continuous:'+item['slug'],records)
        finally:db.close()
        completed.append({'style':style,'source':item['name'],'visual_seconds':len(files),'indexed_seconds':len(records)})
        write_json(OUT/'semantic-progress.json',{'status':'running','completed_sources':len(completed),'sources':completed,'elapsed_seconds':time.time()-start})
        del records;gc.collect()
    while not (OUT/'coverage.json').exists():time.sleep(10)
    coverage=read(OUT/'coverage.json');coverage.update(visual_semantic_seconds=sum(c['visual_seconds'] for c in completed),
        per_second_visual_model='Offline CLIP ViT-B/32 float32 CPU',semantic_elapsed_seconds=time.time()-start,
        limits='All native frames measured; one CLIP interpretation per second. Semantic labels, 10s CLAP audio windows, onset types and beats are candidates. No verified fonts, isolated stems, physical AE camera or fine-tuned language-model weights.')
    write_json(OUT/'coverage.json',coverage)
    write_json(OUT/'semantic-progress.json',{'status':'complete','completed_sources':len(completed),'sources':completed,'elapsed_seconds':time.time()-start})
    print('COMPLETE per-second visual memory',flush=True)

if __name__=='__main__':main()
