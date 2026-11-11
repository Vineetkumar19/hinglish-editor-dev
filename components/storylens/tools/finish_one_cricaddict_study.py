"""Finish the first video's local learning, sample and portable style evidence."""
import base64,csv,hashlib,html,json,math,sqlite3,sys,time,traceback,zipfile
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from study_one_cricaddict_director import OUT,STYLE,load,save,select_window,direct_sample,validate
OLD=ROOT/'output/reference-analysis/continuous-documentary-memory/crick-edit-editing-style/reference-01'

def refine_assets():
 import requests
 from PIL import Image,ImageDraw
 from render_one_cricaddict_sample import prepare_media,crop_asset,cached_isolation
 words=load('sample-words.json');errors,scenes=validate(load('local-plan.json'),words)
 if errors:raise ValueError(str(errors))
 _,_,assets=prepare_media(scenes)
 import numpy as np
 blank=[]
 for i,s in enumerate(scenes):
  for p in s['photos']:
   if p['asset']=='photo' and float(np.asarray(Image.open(p['path']).convert('RGB')).std())<1:
    blank.append(f'Scene {i+1} {s["effect"]}: selected word-onset source still is a blank frame, not a usable photograph. Non-book photo rigs require that same first cue and would also be blank. Choose a nonblank real source cue only where the API permits it, or an existing source-playback rig. Do not invent an image.')
 if blank:
  save('asset-validation.json',{'plan_sha256':hashlib.sha256((OUT/'local-plan.json').read_bytes()).hexdigest(),'problems':blank,'cloud':False,'quality_revision':2})
  return blank
 needed=[p for s in scenes for p in s['photos'] if p['asset']=='photo'];results=[]
 requested={Path(s['photos'][0]['path']).name:(s['name_first']+' '+s['name_last']).strip() for s in scenes if s['effect']=='crick-hero'}
 session=requests.Session();session.trust_env=False
 item={'type':'object','properties':{'asset':{'type':'string'},'use_crop':{'type':'boolean'},
  'box':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'integer','enum':list(range(101))}},
  'suitable_isolated_subject':{'type':'boolean'},'matches_requested_name':{'type':'string','enum':['yes','no','uncertain']},'observation':{'type':'string','maxLength':120}},
  'required':['asset','use_crop','box','suitable_isolated_subject','matches_requested_name','observation'],'additionalProperties':False}
 schema={'type':'object','properties':{'assets':{'type':'array','items':item}},'required':['assets'],'additionalProperties':False}
 try:
  for start in range(0,len(needed)):
   # One image per request avoids ambiguous panel-relative ROI coordinates.
   batch=needed[start:start+1];panel=Image.new('RGB',(960,564),'#101820');draw=ImageDraw.Draw(panel)
   selected=Path(batch[0]['path']);source_hash=hashlib.sha256(selected.read_bytes()).hexdigest()
   cache=OUT/'asset-decisions'/selected.with_suffix('.json').name
   if cache.exists():
    cached=json.loads(cache.read_text(encoding='utf8'))
    if cached.get('source_sha256')==source_hash and cached.get('requested_name','')==requested.get(selected.name,'') and cached.get('protocol_revision')==3:
     results.append(cached['decision']);continue
   for i,p in enumerate(batch):
    path=Path(p['path']);im=Image.open(path).convert('RGB');panel.paste(im.resize((960,540)),(0,0))
    draw.text((7,543),path.name,fill='white')
   from io import BytesIO
   b=BytesIO();panel.save(b,format='JPEG',quality=93);image=base64.b64encode(b.getvalue()).decode()
   names=[Path(p['path']).name for p in batch]
   body={'model':'qwen2.5vl:7b','stream':False,'format':schema,'keep_alive':'10m',
    'options':{'num_ctx':4096,'num_predict':1100,'num_gpu':0,'num_thread':4,'num_batch':128,'temperature':0},
    'messages':[{'role':'system','content':'You are a local factual visual asset resolver, not a creative director. Each labelled row is an actual source image. Find an existing photograph/player region inside each image, excluding baked titles and documentary borders if safely possible. Return INTEGER PERCENTAGES [left,top,right,bottom], 0–100, relative to the FULL IMAGE ABOVE ITS LABEL. Left must be smaller than right; top smaller than bottom. Never invent identity or a crop. use_crop=false and [0,0,100,100] if uncertain or the full composition is necessary. suitable_isolated_subject=true only if an obvious single subject can be isolated from its photograph. Exactly one result per supplied asset. English observation under100chars; JSON only.'},
     {'role':'user','content':json.dumps({'assets':names,'requested_subjects':{n:requested.get(n,'') for n in names},'identity_check':'Where a requested subject is named, choose yes only when the selected visible person can be recognized as that person. If not recognizable, return uncertain; do not guess. Reject a different person with no. No identity claim is needed when requested name is empty.','coordinate_order':['left_percent','top_percent','right_percent','bottom_percent'],'coordinate_contract':'Return INTEGER PERCENTAGES 0–100 relative to the full image above the label. This overrides any earlier normalized-coordinate wording. Full image is [0,0,100,100]. When uncertain choose use_crop=false.'}),'images':[image]}]}
   print('LOCAL ASSET REVIEW '+', '.join(names),flush=True);t=time.time()
   r=session.post('http://127.0.0.1:11434/api/chat',json=body,timeout=(15,1000));r.raise_for_status();raw=r.json()
   save(f'asset-review-{start}-response.json',{'raw':raw,'elapsed_seconds':time.time()-t,'cloud':False})
   answer=json.loads(raw['message']['content'])['assets']
   if sorted(a['asset'] for a in answer)!=sorted(names):raise ValueError('Local asset review omitted or invented an image')
   for a in answer:
    if not a['use_crop']:a['box']=[0,0,1,1]
    else:a['box']=[v/100 for v in a['box']]
    x0,y0,x1,y1=a['box']
    if not 0<=x0<x1<=1 or not 0<=y0<y1<=1 or (x1-x0)*(y1-y0)<.04:raise ValueError('Local asset crop is invalid; no assistant crop substituted')
   results+=answer
   cache.parent.mkdir(exist_ok=True)
   cache.write_text(json.dumps({'source_sha256':source_hash,'requested_name':requested.get(selected.name,''),'protocol_revision':3,'decision':answer[0]},indent=2),encoding='utf8')
 finally:
  session.post('http://127.0.0.1:11434/api/generate',json={'model':'qwen2.5vl:7b','keep_alive':0},timeout=60);session.close()
 save('local-asset-review.json',{'model':'qwen2.5vl:7b','assets':results,'cloud':False,'purpose':'Resolve original source photograph regions only; no new generated imagery.'})
 byname={r['asset']:r for r in results};problems=[]
 import numpy as np
 for i,s in enumerate(scenes):
  for p in s['photos']:
   if p['asset']=='photo':
    pixels=np.asarray(Image.open(p['path']).convert('RGB'))
    if float(pixels.std())<1:
     problems.append(f'Scene {i+1} {s["effect"]}: selected word-onset source still is a blank frame, not a usable photograph. Non-book photo rigs require that same first cue and would also be blank. Choose a nonblank real source cue only where the API permits it, or an existing source-playback rig. Do not invent an image.')
 for i,s in enumerate(scenes):
  if s['effect'] in ('crick-hero','crick-evidence'):
   p=Path(s['photos'][0]['path']).name
   if s['effect']=='crick-hero' and byname[p]['matches_requested_name']!='yes':
    problems.append(f'Scene {i+1} {s["effect"]}: local vision cannot confirm the chosen image matches the requested name {requested[p]}. Use another appropriate existing rig; never label an uncertain person with a guessed name.')
    continue
   if not byname[p]['suitable_isolated_subject']:problems.append(f'Scene {i+1} {s["effect"]}: local vision says selected original image has no suitable isolated subject: '+byname[p]['observation']+' Choose a different cue or use TV/film/paper/book. Never invent a subject.')
   else:
    try:
     path=Path(s['photos'][0]['path']);crop_asset(path,byname[p]);cached_isolation(path)
    except ValueError as error:problems.append(f'Scene {i+1} {s["effect"]}: offline subject isolation failed for the locally selected source image: {error}. Choose a different source cue or another existing rig; no assistant subject substitution.')
 save('asset-validation.json',{'plan_sha256':hashlib.sha256((OUT/'local-plan.json').read_bytes()).hexdigest(),'problems':problems,'cloud':False,'quality_revision':2})
 return problems

def validate_analysis():
 import numpy as np
 from tools.analyze_documentary_reference import facts
 source=load('source.json');current=facts(Path(source['path']));receipt=load('native-vision-coverage.json')
 if current!=receipt['source']:raise ValueError('Source changed during review')
 bank=np.load(OUT/'native-clip-embeddings.npy',mmap_mode='r');counts=defaultdict(lambda:defaultdict(Counter));total=0;previous=-1
 with (OUT/'native-visual-candidates.csv').open(encoding='utf8',newline='') as file:
  for row in csv.DictReader(file):
   index=int(row['frame']);t=float(row['relative_seconds'])
   if index!=total or t<=previous:raise ValueError('Frame coverage missing or unordered')
   previous=t;total+=1
   for key in ('layout','typography','texture'):counts[int(t)][key][row[key+'_candidate']]+=1
 if total!=22564 or bank.shape!=(total,512) or not np.isfinite(bank).all():raise ValueError('Incomplete native visual bank')
 norms=np.linalg.norm(bank,axis=1)
 if abs(norms-1).max()>.001:raise ValueError('Native CLIP vectors are not normalized')
 review=load('local-visual-review.json');seconds=[s for r in review['intervals'] for s in r['sampled_seconds']]
 if seconds!=list(range(math.ceil(source['seconds']))):raise ValueError('Every-second vision panel coverage incomplete')
 from study_one_cricaddict_review import complete_observations
 if not all(complete_observations(r.get('observations')) for r in review['intervals']):raise ValueError('Incomplete local sentences must be repaired before memory or direction')
 evidence=[json.loads(line) for line in (OLD/'editing-seconds.jsonl').read_text(encoding='utf8').splitlines()]
 for r in review['intervals']:
  fractions=[e['data']['motion']['motion_fraction_of_measurable_time'] for e in evidence if r['start']<=e['start']<r['end']]
  values=[f for f in fractions if f is not None]
  r['measured_motion_fraction_mean']=sum(values)/len(values) if values else None
  r['quality_flags']=[]
  description=' '.join(r['observations'].get('movement_observations',[])).lower()
  if 'camera' in description:r['quality_flags'].append('Camera wording is a local interpretation, not a recovered physical camera. Native image/layer motion measurements take precedence over claims about camera setup.')
  if 'static' in description and values and sum(values)/len(values)>.4:r['quality_flags'].append('Static wording does not negate the recorded image/layer movement; compare the native motion curve and source images before reusing this interpretation.')
 save('local-visual-review.json',review)
 # Restore full evidence limits on cached lessons rather than storing a
 # clipped prompt excerpt as a complete uncertainty statement. This adds
 # measured QA metadata; it does not rewrite local creative observations.
 if (OUT/'learned-lessons.json').exists():
  learned=load('learned-lessons.json')
  for lesson in learned['lessons']:
   lesson['evidence_quality_flags']=list(dict.fromkeys(flag for row in review['intervals']
    if row['start']<lesson['end'] and row['end']>lesson['start'] for flag in row.get('quality_flags',[])))
   if lesson['evidence_quality_flags']:
    lesson['uncertainty']=' '.join(lesson['evidence_quality_flags'])
  save('learned-lessons.json',learned)
 save('analysis-verification.json',{'source_unchanged':True,'native_frames':total,'all_frame_embeddings':list(bank.shape),
  'every_second_panel_samples':len(seconds),'local_vision_intervals':len(review['intervals']),'first_video_only':True,
  'embedding_encoder':'CLIP ViT-B/32 visual vectors; distinct from multilingual E5 semantic retrieval vectors',
  'visual_measurement_limits':'CLIP receives a 256x144 source thumbnail then its default 224px center crop. Every native frame is processed, but these reduced views cannot certify full-frame typography, faces or original design parameters. Full-frame every-second panels and native motion evidence complement those candidates.',
  'gaps_in_native_frame_order':0,'synthetic_between_frame_images':0})
 # This inventory describes retained evidence, rather than promoting an
 # automatic motion/audio candidate into an exact original-design claim.
 categories=Counter(c for e in evidence for c in e['data']['audio']['mixed_track_candidates'])
 effect_counts=Counter()
 for e in evidence:
  for category,candidates in e['data']['audio']['roles']['sound_effect_candidates'].items():effect_counts[category]+=len(candidates)
 pace=[e['data']['visual']['pace_scene_seconds'] for e in evidence if e['data']['visual']['pace_scene_seconds'] is not None]
 save('study-evidence-summary.json',{'source':source['name'],'native_frames':total,'source_seconds':len(evidence),
  'speech_words':len(load('fresh-words.json')),'local_visual_intervals':len(review['intervals']),
  'visual':{'cut_candidate_events':sum(e['data']['motion']['cut_candidates'] for e in evidence),
   'movement_classes':dict(Counter(e['data']['motion']['classification'] for e in evidence)),
   'native_image_flow_columns':['horizontal','vertical','zoom','rotation','residual_local_flow','moving_cells'],
   'appearance_series':['brightness','contrast','saturation','edge_density'],
   'scene_duration_candidate_range_seconds':[min(pace),max(pace)] if pace else None,
   'semantic_candidates':['layout','typography','texture'],
   'limits':'Cut, typography, texture, motion-family and scene-duration labels are candidates; no original camera, layer or font recovery.'},
  'audio':{'measurement_hop_seconds':.02,'mixed_role_second_counts':dict(categories),
   'effect_candidate_event_counts':dict(effect_counts),
   'onset_candidates':sum(len(e['data']['audio']['onset_candidates']) for e in evidence),
   'beat_candidates':sum(len(e['data']['audio']['beat_candidates_seconds']) for e in evidence),
   'limits':'Mixed audio with local VAD/ASR and similarity candidates. No isolated stems or certified music beats.'}})
 return counts

def persist(counts):
 from hinglish_niche.reference_dna import StyleDatabase
 from hinglish_niche.style_memory import StyleEmbedder
 source=load('source.json');review=load('local-visual-review.json');lessons=load('learned-lessons.json')['lessons'];words=load('fresh-words.json')
 evidence=[json.loads(line) for line in (OLD/'editing-seconds.jsonl').read_text(encoding='utf8').splitlines()]
 rows=[]
 for e in evidence:
  second=int(e['start']);labels={k:dict(v) for k,v in counts[second].items()}
  narration=' '.join(w['text'] for w in words if e['start']<=w['start']<e['end'])
  text=f'{source["name"]}, {e["start"]:.2f}–{e["end"]:.2f}s. Native-frame visual candidates: '+ '; '.join(k+': '+', '.join(f'{n} ({c} frames)' for n,c in v.items()) for k,v in labels.items())+f'. Movement: {e["data"]["motion"]["classification"]}. Fresh local narration: {narration}'
  rows.append({'kind':'single-video-second','start':e['start'],'end':e['end'],'text':text,'data':{**e['data'],
   'source':source['name'],'fresh_narration':narration,'narration_asr':narration,
   'narration_scope':'Fresh sequential local ASR words assigned by actual word-start estimates to this second; not a whole neighbouring segment or certified forced alignment.',
   'native_visual_histograms':labels,'status':'First-video measured evidence and local model candidates, not original project settings.'}})
 for r in review['intervals']:
  rows.append({'kind':'single-video-visual-review','start':r['start'],'end':r['end'],
   'text':source['name']+' '+str(r['start'])+'–'+str(r['end'])+'s. '+' '.join(s for v in r['observations'].values() for s in v)+' Interpretation limits: '+' '.join(r.get('quality_flags',[])),
   'data':{'source':source['name'],'source_path':source['path'],'model':r['model'],'observations':r['observations'],'quality_flags':r.get('quality_flags',[]),
    'sampled_seconds':r['sampled_seconds'],'status':'Local vision interpretation candidate; source every-second panel and native curves remain available.'}})
 for l in lessons:
  rows.append({'kind':'single-video-lesson','start':l['start'],'end':l['end'],'text':l['title']+'. Observed: '+l['observed']+' Reuse: '+l['reuse']+' Uncertainty: '+l['uncertainty'],
   'data':{'source':source['name'],'source_path':source['path'],'lesson':l,'model':'qwen3:8b','status':'Locally inferred lesson awaiting user aesthetic approval; does not override explicit preferences.'}})
 model=StyleEmbedder(ROOT);vectors=model.encode([r['text'] for r in rows])
 for r,v in zip(rows,vectors):r['vector']=v;r['model']=model.model_name
 db=StyleDatabase(ROOT/'library/creator-profiles/editing-dna.sqlite3')
 try:db.replace_source(STYLE,'single-video/reference-01',rows)
 finally:db.close()
 save('local-memory-receipt.json',{'style':'cricAddict','source':source['path'],'records':len(rows),'seconds':len(evidence),
  'visual_reviews':len(review['intervals']),'lessons':len(lessons),'semantic_encoder':model.model_name,
  'database':str(ROOT/'library/creator-profiles/editing-dna.sqlite3'),'new_neural_weights_trained':False,
  'ollama_model_independent':True,'preferences_overridden':False,'other_videos_started':False})
 save('every-second-evidence.json',{'source':source,'records':[{k:v for k,v in r.items() if k not in ('vector','model')} for r in rows if r['kind']=='single-video-second']})
 curriculum=ROOT/'library/creator-profiles/documentary-memory/cricaddict-curriculum.json'
 curriculum.write_text(json.dumps({'style':'cricAddict','current':'reference-01','completed':['reference-01'],
  'next':'reference-02','auto_advance':False,'source':source['path'],'report':str(OUT/'report.html'),
  'first_video_new_neural_weights_trained':False,'review_status':'Awaiting user review of first sample before next source'},indent=2),encoding='utf8')

def report():
 source=load('source.json');lessons=load('learned-lessons.json')['lessons'];verification=load('analysis-verification.json');window=load('sample-window.json')
 receipt=load('sample-render-receipt.json');memory=load('local-memory-receipt.json');review=load('local-visual-review.json')
 escape=lambda x:html.escape(str(x));lesson_html=''.join(f'<article><h3>{escape(l["title"])}</h3><p>Source {l["start"]:.2f}–{l["end"]:.2f}s</p><p><b>Observed:</b> {escape(l["observed"])}</p><p><b>Reuse:</b> {escape(l["reuse"])}</p><p class="muted">{escape(l["uncertainty"])}</p></article>' for l in lessons)
 figures=''.join(f'<figure><img loading="lazy" src="{s["still"]}"><figcaption>{s["start"]:.2f}–{s["start"]+s["seconds"]:.2f}s · {escape(s["effect"])} · {escape(s["caption"])}</figcaption></figure>' for s in load('sample-rendered-plan.json')['scenes'])
 rows=[]
 for r in load('every-second-evidence.json')['records']:
  d=r['data'];second=int(r['start']);visual='; '.join(k+': '+', '.join(sorted(v,key=v.get,reverse=True)[:2]) for k,v in d['native_visual_histograms'].items())
  rows.append(f'<tr><td>{second//60:02}:{second%60:02}</td><td><a href="frames/{second:05d}.jpg">Frame</a></td><td>{escape(visual)}</td><td>{escape(d["motion"]["classification"])}<br>Moving fraction {d["motion"]["motion_fraction_of_measurable_time"]}</td><td>{escape(d["fresh_narration"])}<br>{escape(", ".join(d["audio"]["mixed_track_candidates"]))}; {len(d["audio"]["onset_candidates"])} onset candidates</td></tr>')
 panels=''.join(f'<details><summary>{r["start"]:.0f}–{r["end"]:.2f}s · local vision review</summary><img loading="lazy" src="review-panels/{int(r["start"]):04d}.jpg"><p>{escape(" ".join(s for v in r["observations"].values() for s in v))}</p><p class="muted">{escape(" ".join(r.get("quality_flags",[])))}</p></details>' for r in review['intervals'])
 coverage_rows=''.join(f'<tr><td>{escape(name)}</td><td>{escape(evidence)}</td><td>{escape(limit)}</td></tr>' for name,evidence,limit in [
  ('Cuts / transitions / editing pace','Native frame differences, scene/cut candidates and source-linked scene durations.','Automatic boundaries are candidates; dissolves and graphic motion can imitate cuts.'),
  ('Motion graphics / image animation / camera movement','All-native-frame image flow, local every-second visual review and saved sample draw transforms.','Image-space movement does not prove original physical cameras or layer coordinates.'),
  ('Zoom / parallax','Native zoom/rotation/local residual curves and independent image/camera rig movement.','Residual flow may be text or subject motion; original 3D geometry is unknown.'),
  ('Typography / overlays / textures / colour','Every-frame similarity labels; every-second brightness, contrast, saturation and edge density.','Exact fonts, grading nodes and source overlay assets are not recovered.'),
  ('Voice','Fresh whole-video local ASR, word-time estimates and local voice activity detection.','Words and timing can contain recognition errors.'),
  ('Background music / ambience','Full-track mixed-audio features and local similarity candidates.','No isolated music or ambience stems.'),
  ('Sound effects / impacts / risers / whooshes','20ms energy, frequency and onset measurements plus sampled event candidates.','Candidate sound type is not a confirmed separated effect.'),
  ('Beat timing','Saved mixed-track beat/onset candidates alongside original narration.','Speech and impacts can imitate beats; not a human-certified music grid.'),
  ('Editing DNA / style database / vectors','Grounded local lessons, source-specific records and the existing fixed multilingual E5 retrieval index.','External persistent memory, not retrained neural weights.')])
 (OUT/'report.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>cricAddict · Video 1 · Local editing study</title><style>body{{background:#10171b;color:#eee5d6;font:17px/1.6 system-ui;max-width:1280px;margin:auto;padding:32px}}h1{{font:42px Georgia}}a{{color:#e7ba77}}video,img{{width:100%;border-radius:8px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}article{{background:#19232b;padding:20px;border:1px solid #39434a;border-radius:12px}}figure{{margin:0}}.muted{{color:#b5bec1}}table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{border-bottom:1px solid #39434a;padding:9px;vertical-align:top;text-align:left}}details{{margin:16px 0}}summary{{cursor:pointer}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}</style>
 <h1>cricAddict — one video at a time</h1><p><b>Video 1: {escape(source['name'])}</b> · {source['seconds']/60:.2f} minutes · {verification['native_frames']:,} recorded frames · {verification['every_second_panel_samples']} source seconds in local vision panels.</p>
 <video controls playsinline preload="metadata" src="CRICADDICT_REFERENCE_01_LOCAL_60S.mp4"></video><p>The local Qwen3:8B model chose this continuous source passage ({window['start']:.3f}–{window['end']:.3f}s), scene sequence, existing rigs, English copy, image cues and sound choices. Existing cricAddict rigs were reused; no new cloud choreography or cloud storyboard. Local Qwen2.5-VL reviewed every-second panels and the actual sample assets. CLIP interpreted every native frame. Original narration, music and mixed sound play at their original speed.</p>
 <p><b>What is saved:</b> {memory['records']} new searchable source-specific records, including {memory['lessons']} local lessons; fresh whole-video transcription; every-native-frame visual vectors; native image motion and 20ms mixed-audio measurements. The fixed E5 style database is independent of the selected Ollama language model. Both motion brains and explicit preferences are retained. This is retrieved local memory, not neural weight fine-tuning.</p>
 <p class="muted">A roughly 29.97fps source contains a recorded frame about every 33.37ms. No invented intermediate milliseconds were studied. Native CLIP uses reduced thumbnails with its standard centre crop, complemented by full-frame every-second panels; it cannot certify every full-resolution letter or face. Automated labels remain candidates. Image flow cannot certify a physical 3D camera; font names, isolated voice/music/effect stems and original AE keyframes cannot be recovered exactly from flattened video. Speech onsets are local Whisper estimates; export cue rounding is less than one 30fps frame. Generated quality still needs your review. No second reference was started.</p>
 <p><a href="learned-lessons.json">Local lessons and chosen passage</a> · <a href="local-plan.json">Local creative plan</a> · <a href="analysis-verification.json">Coverage proof</a> · <a href="sample-render-receipt.json">Render/model receipt</a> · <a href="sample-cue-audit.json">Cue timing</a> · <a href="sample-continuity.json">Photo movement checks</a> · <a href="native-visual-candidates.csv">Every-frame candidates</a> · <a href="native-clip-embeddings.npy">Native visual vectors</a> · <a href="every-second-evidence.json">Every-second evidence</a> · <a href="CRICADDICT_VIDEO_01_MEMORY.zip">Portable video-1 memory</a></p>
 <h2>Coverage of your learning checklist</h2><table><thead><tr><th>Area</th><th>Retained evidence</th><th>Interpretation limit</th></tr></thead><tbody>{coverage_rows}</tbody></table><p><a href="study-evidence-summary.json">Measured study inventory</a> · <a href="fresh-words.json">Fresh source word timings</a></p>
 <h2>What the local model learned from video 1</h2><div class="grid">{lesson_html}</div><h2>The local model's sample</h2><div class="grid">{figures}</div><h2>Timestamped local vision review</h2>{panels}
 <h2>Every source second</h2><table><thead><tr><th>Source time</th><th>Reference evidence only</th><th>Native frame candidates</th><th>Movement evidence</th><th>Fresh narration / mixed audio</th></tr></thead><tbody>{''.join(rows)}</tbody></table></html>''',encoding='utf8')
 from hinglish_motion.reference_policy import withdraw_report
 withdraw_report(OUT)

def archive():
 path=OUT/'CRICADDICT_VIDEO_01_MEMORY.zip';snapshot=OUT/'editing-dna.snapshot.sqlite3'
 with sqlite3.connect(ROOT/'library/creator-profiles/editing-dna.sqlite3') as db,sqlite3.connect(snapshot) as dest:db.backup(dest)
 files=list((ROOT/'library/creator-profiles/documentary-memory').rglob('*'))+[ROOT/'library/creator-profiles/crick-edit-editing-style.json',snapshot]
 files+=[p for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.csv','.npy','.html','.jpg','.png','.md') and not any(part in ('sample-source-frames','sample-assets','rejected-sample') for part in p.parts) and not p.name.startswith('sample-scene-') and p.name!='sample-final-contact-sheet.jpg']
 files+=[p for p in OLD.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.csv','.npy','.npz','.jpg')]
 with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  for p in sorted(set(files)):
   if p.is_file():z.write(p,str(p.relative_to(ROOT)).replace('\\','/'))
 with zipfile.ZipFile(path) as z:
  if z.testzip():raise ValueError('Portable first-video memory failed checksum')
 save('portable-memory-receipt.json',{'path':str(path),'bytes':path.stat().st_size,'entries':len(z.namelist()),
  'original_video_included':False,'generated_sample_included':False,'reference_evidence_analysis_only':True,'model_weights_included':False,'database_consistent_snapshot':True,'crc_validated':True})

def main():
 from hinglish_motion.reference_policy import block_reference_sample
 block_reference_sample()
 print('Waiting for first video only: complete native-frame and every-second local review',flush=True)
 while not all((OUT/p).exists() for p in ('native-vision-coverage.json','local-visual-review.json')):time.sleep(10)
 counts=validate_analysis()
 if not all((OUT/p).exists() for p in ('learned-lessons.json','sample-window.json','sample-words.json')):select_window()
 if not (OUT/'local-plan.json').exists() or load('local-plan.json').get('copy_revision')!=2:direct_sample()
 if not (OUT/'asset-validation.json').exists() or load('asset-validation.json').get('quality_revision')!=2 or load('asset-validation.json').get('problems') or load('asset-validation.json').get('plan_sha256')!=hashlib.sha256((OUT/'local-plan.json').read_bytes()).hexdigest():
  for attempt in range(4):
   problems=refine_assets()
   if not problems:break
   save(f'asset-problems-{attempt+1}.json',problems);direct_sample(problems)
  else:raise ValueError('Local director and local vision could not resolve a suitable sample subject')
 if not (OUT/'sample-render-receipt.json').exists() or load('sample-render-receipt.json')['status']!='complete':
  from render_one_cricaddict_sample import render
  render()
 if not (OUT/'local-memory-receipt.json').exists():persist(counts)
 report();archive();save('completion.json',{'status':'complete','reference':'reference-01','next_reference_started':False,
  'report':str(OUT/'report.html'),'video':str(OUT/'CRICADDICT_REFERENCE_01_LOCAL_60S.mp4'),'cloud_creative_plan':False})
 print('COMPLETE first reference, local lessons, native evidence, local 60-second sample, portable memory',flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as error:
  traceback.print_exc();save('completion-error.json',{'error':str(error),'status':'failed','reference':'reference-01'});sys.exit(1)
