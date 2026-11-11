"""Sequential native-frame motion audit + model-independent, source-linked memory."""
import argparse,csv,gc,hashlib,html,json,os,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.analyze_documentary_reference import facts,scan,write_json
from hinglish_niche.continuous_motion import ContinuousMotionScan,VERSION,motion_brief
from hinglish_niche.reference_dna import StyleDatabase
from hinglish_niche.style_memory import StyleEmbedder

OUT=ROOT/'output/reference-analysis/continuous-documentary-memory'
SETS={'beneath-documentary-edit':'cricket-documentaries','crick-edit-editing-style':'crick-edit-editing-style'}
def read(path):return json.loads(path.read_text(encoding='utf8'))
def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def source_records(item,old,new,seconds,offset):
    visual=read(old/'scene-interpretations.json')['scenes'];audio=read(old/'audio-interpretations.json')
    sound=read(old/'audio-analysis.json');events=read(old/'sound-event-candidates.json')
    if isinstance(events,dict):events=events.get('events',events.get('candidates',[]))
    transcript=read(old/'transcript.json') if (old/'transcript.json').exists() else []
    features=np.load(old/'audio-features.npy',mmap_mode='r') if (old/'audio-features.npy').exists() else None
    scenes=read(old/'scenes.json');cuts=[s['start']+offset for s in scenes[1:]]
    semantic_path=new/'semantic-seconds.json'
    fine_semantics={r['second']:r for r in read(semantic_path)['frames']} if semantic_path.exists() else {}
    colours={};counts={}
    with (old/'visual-features.csv').open(newline='',encoding='utf8') as file:
        for row in csv.DictReader(file):
            sec=int(float(row['seconds'])+offset)
            vals=np.array([float(row[k]) for k in ['brightness','contrast','saturation','edge_density']])
            colours[sec]=colours.get(sec,np.zeros(4))+vals;counts[sec]=counts.get(sec,0)+1
    records=[];lines=[]
    for r in seconds:
        a=r['start'];b=min(item['seconds'],a+1);scene=next((s for s in visual if s['start']+offset<=a<s['end']+offset),None)
        candidates=scene['candidates'] if scene else {}
        if a in fine_semantics:candidates=fine_semantics[a]['candidates']
        windows=[w for w in audio.get('windows',[]) if w['start']<b and w['end']>a]
        labels=list(dict.fromkeys(c['label'] for w in windows for c in w.get('candidates',[])[:3]))
        speech=sum(max(0,min(b,s['end'])-max(a,s['start'])) for s in audio.get('speech_intervals',[]))
        spoken=' '.join(s['text'] for s in transcript if s['start']<b and s['end']>a)
        nearby_events=[e for e in events if a<=e.get('seconds',e.get('time',-1))<b]
        onsets=[e for e in sound.get('onsets',[]) if a<=e['seconds']<b]
        beats=[t for reg in sound.get('tempo_regions',[]) for t in reg.get('beat_candidates_seconds',[]) if a<=t<b]
        f=features[int(a/.02):int(b/.02)] if features is not None else None
        metrics={'rms':float(np.mean(f[:,1])),'spectral_centroid_hz':float(np.mean(f[:,4])),
                 'bass_fraction':float(np.mean(f[:,5])),'positive_flux':float(np.mean(f[:,6]))} if f is not None and len(f) else {}
        colour=(colours[a]/counts[a]).tolist() if a in colours else []
        layout=candidates.get('layout',[{'label':'unclassified'}])[0]['label']
        labels_by_category={k:v[:3] for k,v in candidates.items()}
        data={'source_path':item['path'],'source_name':item['name'],'motion':r,
          'native_frame_curve':str(new/'continuous-motion.csv'),'visual':{'scene_candidate':layout,
          'typography_overlay_texture_candidates':labels_by_category,'colour_brightness_contrast_saturation_edges':colour,
          'cut_candidates_seconds':[t for t in cuts if a<=t<b],'pace_scene_seconds':(scene['end']-scene['start']) if scene else None},
          'audio':{'available':sound.get('audio_available',True),'voice_fraction':min(1,speech/max(.001,b-a)),
          'mixed_track_candidates':labels,'onset_candidates':onsets,'classified_event_candidates':nearby_events,
          'beat_candidates_seconds':beats,'measurements_20ms_aggregated':metrics},'narration_asr':spoken,
          'status':'Native-frame motion and 20ms audio measured; inherited scene CLIP and 10s CLAP labels are candidates, not per-frame verified semantics, isolated stems or recovered physical camera.'}
        if a in fine_semantics:
            data['visual']['semantic_frame']=fine_semantics[a]['file']
            data['status']='Native-frame motion + 20ms audio; local CLIP candidate labels on one actual frame EVERY second. Audio CLAP uses the existing full 10s windows and sampled onset clips. Not verified font/object identities, isolated stems or physical camera.'
        text=f"{item['name']} {a:.0f}-{b:.2f}s. {layout}. Movement: {motion_brief(r)}. Tracked fraction {r['tracked_frame_fraction']:.2f}; moving fraction {r['motion_fraction_of_measurable_time']}. Audio candidates: {', '.join(labels)}. {len(onsets)} onset candidates, {len(beats)} beat candidates. Narration (fallible ASR): {spoken[:400]}"
        record={'start':a,'end':b,'kind':'continuous-motion-second','text':text,'data':data}
        records.append(record);lines.append(json.dumps(record,ensure_ascii=False))
    (new/'editing-seconds.jsonl').write_text('\n'.join(lines)+'\n',encoding='utf8')
    return records

def main(args):
    OUT.mkdir(parents=True,exist_ok=True);start=time.time();coverage=[];embedder=None
    inventories=[]
    for style,base in SETS.items():
        oldbase=ROOT/'output/reference-analysis'/base
        for item in read(oldbase/'inventory.json'):inventories.append((style,item,oldbase/item['slug']))
    if args.benchmark:inventories=inventories[:1]
    for i,(style,item,old) in enumerate(inventories,1):
        source=facts(Path(item['path']));prior=read(old/'dna-coverage.json')
        if source!=prior['source']:raise ValueError('Source changed; do not reuse stale evidence: '+item['path'])
        folder=OUT/('benchmark' if args.benchmark else style)/item['slug'];folder.mkdir(parents=True,exist_ok=True)
        with (old/'frame-metrics.csv').open(newline='',encoding='utf8') as f:offset=float(next(csv.DictReader(f))['source_pts_seconds'])
        parent=folder.parent;write_json(parent/'decoder-settings.json',{'decoder':'h264_cuvid'})
        receipt=folder/'motion-coverage.json';completed=read(receipt) if receipt.exists() else {}
        if completed.get('source')!=source or completed.get('version')!=VERSION or args.benchmark:
            print(f'NATIVE MOTION {i}/{len(inventories)}: {item["name"]}',flush=True)
            collector=ContinuousMotionScan(folder,offset)
            try:result=scan(Path(item['path']),folder,collector,max_seconds=args.benchmark)
            except BaseException:collector.file.close();raise
            seconds=collector.close()
            if not args.benchmark and result['decoded_frames']!=prior['native_frames_measured']:
                raise ValueError('Native frame count differs from original complete scan')
            completed={'source':source,'version':VERSION,'full_source':not bool(args.benchmark),
              'native_frames':result['decoded_frames'],'per_second_records':len(seconds),
              'motion_sampling':'Adjacent native frames; sparse local feature tracking in a 3x3 image grid on every pair.',
              'seconds':result['last_frame_seconds'],'elapsed_seconds':result['scan_seconds'],
              'physical_camera_recovered':False,'fine_tuned_weights':False}
            write_json(receipt,completed)
        else:
            print(f'Reusing full native-motion audit {i}/{len(inventories)}: {item["name"]}',flush=True)
            seconds=read(folder/'motion-seconds.json')
        if args.benchmark:
            print(json.dumps(completed,indent=2),flush=True);return
        records=source_records(item,old,folder,seconds,offset)
        if embedder is None:embedder=StyleEmbedder(ROOT)
        for n in range(0,len(records),64):
            chunk=records[n:n+64];vectors=embedder.encode([r['text'] for r in chunk])
            for row,v in zip(chunk,vectors):row.update(vector=v,model=embedder.model_name)
        db=StyleDatabase(ROOT/'library/creator-profiles/editing-dna.sqlite3')
        try:db.replace_source(style,'continuous:'+item['slug'],records)
        finally:db.close()
        entry={'style':style,'name':item['name'],'path':item['path'],'seconds':item['seconds'],**completed,
          'records':len(records),'record_file':str(folder/'editing-seconds.jsonl')}
        coverage.append(entry);write_json(OUT/'progress.json',{'status':'running','completed_sources':len(coverage),
          'total_sources':len(inventories),'elapsed_seconds':time.time()-start,'coverage':coverage})
        del records;gc.collect();print(f'Indexed {len(seconds)} seconds from {item["name"]}',flush=True)
    write_json(OUT/'coverage.json',{'status':'complete','sources':coverage,'native_frames':sum(c['native_frames'] for c in coverage),
      'seconds':sum(c['source']['seconds'] for c in coverage),'second_records':sum(c['records'] for c in coverage),
      'elapsed_seconds':time.time()-start,'model_independent':True,'embedding_model':StyleEmbedder.model_name,
      'limits':'Every native frame has image motion measurements; semantics remain scene candidates. Audio is the mixed track, not isolated stems. No recovered AE keyframes or physical camera. No neural weight fine-tuning.'})
    rows=''.join(f'<tr><td>{html.escape(c["name"])}</td><td>{c["native_frames"]:,}</td><td>{c["records"]:,}</td><td>{c["source"]["seconds"]/60:.1f} min</td></tr>' for c in coverage)
    (OUT/'report.html').write_text(f'''<!doctype html><html><meta charset="utf-8"><title>Continuous documentary memory</title><style>body{{background:#10161b;color:#eee;font:17px/1.6 system-ui;max-width:1100px;margin:auto;padding:30px}}td,th{{padding:10px;border-bottom:1px solid #40505b;text-align:left}}a{{color:#ecc781}}</style><h1>Continuous documentary editing memory</h1><p>All {len(coverage)} references analysed sequentially. Every native frame contributes to image-motion measurements; every second is indexed with visual and audio context. Both user-selected motion brains are saved independently of Ollama.</p><p>The records describe pan, zoom, rotation, local-flow disagreement, cuts, image movement, scene typography/texture candidates, colour, pace, voice presence, mixed-track sound labels, onset candidates and beat candidates. Layer disagreement is a parallax/subject/text candidate, not a recovered physical 3D camera. Fonts and isolated music/effects are not claimed to be recovered from flattened videos.</p><table><tr><th>Video</th><th>Native frames</th><th>Indexed seconds</th><th>Duration</th></tr>{rows}</table><p><a href="coverage.json">Coverage receipt</a> · <a href="../../../library/creator-profiles/documentary-memory/manifest.json">Portable memory manifest</a></p></html>''',encoding='utf8')
    write_json(OUT/'progress.json',{'status':'complete','completed_sources':len(coverage),'total_sources':len(inventories)})
    print('COMPLETE continuous documentary memory',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--benchmark',type=float);main(parser.parse_args())
