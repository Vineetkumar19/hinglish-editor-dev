"""Build evidence-backed editing memory, real E5 vectors and a local review page."""
import csv,html,json,sys,time,wave
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BASE=ROOT/'output/reference-analysis/crick-edit-editing-style'
from hinglish_niche.reference_dna import StyleDatabase,audio_features
from tools.analyze_documentary_reference import facts
from hinglish_niche.style_memory import StyleEmbedder

PATTERNS=[
 {'id':'history-book','name':'Historical book and portrait reveal','source':'reference-01','start':1,'end':12,
  'observation':'An old book opens on a desk. In the reviewed 1.4–3.4s window, a page turn settles before glowing ink/fire-like masks reveal two portraits; page movement and portrait appearance occur in separate phases. The film then moves into cricket photographs.',
  'application':'Use a book/page sequence for an introduction or historical chapter. Separate page movement, camera travel and portrait-mask reveal; do not reduce this sequence to another three-photo entrance.'},
 {'id':'cutout-type','name':'Player cut-out and oversized heading','source':'reference-08','start':0,'end':6,
  'observation':'Large red condensed statistics sit behind a player cut-out; a white script statistic overlays the hierarchy. In the reviewed opening, the player sharpens, red letters build across roughly the first second, and the white script accent enters around 1.1–1.3s. Yellow headings also appear later. This is a subject-led composition.',
  'application':'Use one dominant player silhouette, one short statistical heading, and a supporting accent. Animate text and subject on different timings. Use the player, team, kit and year established by verified narration context.'},
 {'id':'article-proof','name':'Article and scorecard evidence','source':'reference-02','start':8,'end':13,
  'observation':'A light halftone article composition emphasises individual phrases with yellow, blue and red highlight strips. In the reviewed 9–11s window, the blue highlight sweeps left to right around 9.65–10.0s while the article remains readable and its framing subtly changes. The player cut-out supports the article rather than covering it.',
  'application':'Hold the evidence long enough to read. Reveal only the narrated claim with a highlight sweep, then move to the next claim. Keep source labels visible. Do not fabricate statistics or unreadable article text.'},
 {'id':'crt-archive','name':'Vintage television archive','source':'reference-04','start':0,'end':6,
  'observation':'The opening places static and a large year inside a physical vintage television. The reviewed 0.5–2.5s window shows distorted year lettering around 0.95–1.15s, a readable hold, then a glitch exit and a short dark beat before match footage appears. Another reference uses a magenta-lit CRT setting.',
  'application':'Reserve the television treatment for historical broadcast chapters. Animate the screen/static and camera separately; keep playback inside its screen aperture, then transition into the archival footage.'},
 {'id':'paper-photo','name':'Torn paper and archival photo layers','source':'reference-04','start':120,'end':123,
  'observation':'Layered player photographs use irregular paper edges and a softly blurred photographic background. The foreground photographs have different sizes and depths.',
  'application':'Reveal with a paper/ink mask, use restrained foreground/background parallax and leave room for a factual label. Vary the arrangement with the story rather than repeating the same left-plus-two-right collage.'},
 {'id':'film-window','name':'Archival match film window','source':'reference-05','start':487,'end':490,
  'observation':'Historical match footage appears in a rounded film window with a small film-gate outline beside it. Red caption strips communicate a specific series result in neighbouring examples.',
  'application':'Preserve the footage aspect ratio and broadcast context. Use a film matte, mild texture and purposeful transitions; let the match action provide movement rather than sliding photos across it.'},
 {'id':'history-roster','name':'Year and roster timeline','source':'reference-03','start':0,'end':36,
  'observation':'The film uses year markers, portraits, team photographs and bold yellow headings. A reviewed 17–19s window changes from an archival team image through a bright flash into a light roster timeline, then adjusts the framing gently. Its original file has no audio track.',
  'application':'Use dates and player portraits when the script moves through eras. Advance the viewpoint along the sequence and remove old subjects from the frame. Verify era/player membership separately.'},
 {'id':'presenter-evidence','name':'Presenter, evidence, return','source':'reference-02','start':0,'end':26,
  'observation':'The opening alternates the presenter with graphic explanations, highlighted evidence and an elegant serif trophy/statistics layout. A red keyword also punctuates the presenter footage.',
  'application':'Return to the presenter between proof sections. Choose an evidence layout for factual claims and a short keyword for emphasis; do not replace every sentence with a full-screen animation.'},
 {'id':'emotional-match','name':'Match action and emotional reaction','source':'reference-09','start':920,'end':1059,
  'observation':'The later section alternates match action, player portraits, interviews and emotional reactions. Framed archive shots and photographic close-ups coexist with the broadcast footage.',
  'application':'Keep the setup and payoff of the cricket moment together. Use reaction holds and selective punch-ins, then return to the match. Let voice, crowd and score changes motivate the edit; do not infer the event merely from loudness.'}
]

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,data):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def clock(t):return f'{int(t)//60}:{int(t)%60:02}'
def aligned_scenes(folder):
 with (folder/'frame-metrics.csv').open(newline='',encoding='utf-8') as file:
  first=next(csv.DictReader(file));offset=float(first['source_pts_seconds'])
 scenes=read(folder/'scenes.json')
 for scene in scenes:
  scene['relative_start']=scene['start'];scene['relative_end']=scene['end']
  scene['start']+=offset;scene['end']+=offset
  scene['representative']['relative_seconds']=scene['representative']['seconds']
  scene['representative']['seconds']+=offset
  for sample in scene['camera_estimate']['affine_motion_samples']:sample['time']+=offset
  if scene['boundary_candidate']:scene['boundary_candidate']['time']+=offset
 write(folder/'aligned-scenes.json',{'time_origin':'Original media PTS seconds, aligned with decoded audio starting at zero.',
  'first_video_pts_seconds':offset,'raw_scene_time_origin':'Seconds relative to first decoded video frame.','scenes':scenes})
 return scenes,offset
def motion(scene):
 samples=[m for m in scene['camera_estimate']['affine_motion_samples'] if m['inliers']>=.5]
 zoom=scene['camera_estimate']['zoom_rate_median'];out=[]
 if zoom is not None and abs(zoom)>.006:out.append('image-space push-in' if zoom>0 else 'image-space pull-out')
 if samples:
  x=np.median([s['dx']/max(.01,s['span']) for s in samples]);y=np.median([s['dy']/max(.01,s['span']) for s in samples])
  if abs(x)>3:out.append('horizontal image movement')
  if abs(y)>3:out.append('vertical image movement')
  if np.median([s['residual'] for s in samples])>.8:out.append('non-uniform layer or subject movement')
 return out or ['no strong global movement measured']

def transitions(folder,scenes):
 data=np.genfromtxt(folder/'visual-features.csv',delimiter=',',skip_header=1,usecols=(1,2,3,4))
 result=[]
 if data.ndim!=2:return result
 brightness=data[:,3];peaks,_=find_peaks(brightness,height=195,prominence=55,distance=8)
 for i in peaks:
  result.append({'seconds':float(data[i,0]),'kind':'bright flash candidate','verified':False,
   'note':'Brightness spike can also be footage exposure or a white graphic.'})
 dark=brightness<8
 edges=np.diff(np.r_[False,dark,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
 for a,b in zip(starts,ends):
  if b-a>=3:
   result.append({'start':float(data[a,0]),'end':float(data[min(b,len(data)-1),0]),
    'kind':'near-black interval / possible fade endpoint','verified':False})
 return sorted(result,key=lambda r:r.get('seconds',r.get('start',0)))

def main():
 items=read(BASE/'inventory.json')
 for item in items:
  folder=BASE/item['slug']
  needed=['dna-coverage.json','scene-interpretations.json','audio-interpretations.json','sound-event-candidates.json']
  while any(not (folder/name).exists() for name in needed):
   print('Waiting for analysis '+item['slug'],flush=True);time.sleep(20)
  if read(folder/'audio-analysis.json').get('audio_available') is not False:
   while not (folder/'speech-coverage.json').exists():
    print('Waiting for narration '+item['slug'],flush=True);time.sleep(20)
 print('Building isolated E5 vector memory.',flush=True)
 embedder=StyleEmbedder(ROOT);db=StyleDatabase(ROOT/'library/creator-profiles/editing-dna.sqlite3')
 beneath=read(ROOT/'library/creator-profiles/beneath-documentary-edit.json')
 records=[{'kind':'approved-animation','text':a['name']+'. '+a['description'],
  'data':{'status':'user-approved animation setting','animation':a}} for a in beneath['animation_settings']]
 vectors=embedder.encode([r['text'] for r in records])
 for r,v in zip(records,vectors):r.update(vector=v,model=embedder.model_name)
 db.replace_source('beneath-documentary-edit','approved-settings',records)
 manual=[{'start':p['start'],'end':p['end'],'kind':'reviewed-pattern',
  'text':p['name']+'. '+p['observation']+' Editing rule: '+p['application'],
  'data':{**p,'status':'Visually reviewed distributed samples; proposed editing rule, not recovered project keyframes.'}} for p in PATTERNS]
 vectors=embedder.encode([r['text'] for r in manual])
 for r,v in zip(manual,vectors):r.update(vector=v,model=embedder.model_name)
 db.replace_source('crick-edit-editing-style','reviewed-patterns',manual)
 coverage=[];all_stats=[];indexed=len(manual)
 for item in items:
  folder=BASE/item['slug'];scenes,video_offset=aligned_scenes(folder);interpret=read(folder/'scene-interpretations.json')['scenes']
  if len(scenes)!=len(interpret) or any(s['index']!=c['index'] for s,c in zip(scenes,interpret)):
   raise ValueError('Scene interpretation coverage mismatch: '+item['slug'])
  native_receipt=read(folder/'dna-coverage.json')
  if native_receipt['source']!=facts(Path(item['path'])):raise ValueError('Original reference changed after scanning: '+item['slug'])
  if sum(s['frames'] for s in scenes)!=native_receipt['native_frames_measured']:
   raise ValueError('Frame measurement coverage mismatch: '+item['slug'])
  audio=read(folder/'audio-interpretations.json');audio_metrics=read(folder/'audio-analysis.json')
  if audio_metrics.get('audio_available') is not False and audio_metrics.get('beat_grid_version')!=1:
   with wave.open(str(folder/'analysis-audio.wav'),'rb') as reader:
    waveform=np.frombuffer(reader.readframes(reader.getnframes()),dtype='<i2').astype(np.float32)/32768
   values,audio_metrics=audio_features(waveform)
   np.save(folder/'audio-features.npy',values.astype(np.float32));write(folder/'audio-analysis.json',audio_metrics)
   del waveform,values
  words=read(folder/'words.json') if (folder/'words.json').exists() else []
  if audio.get('audio_available') is not False and abs(audio['analysed_seconds']-audio_metrics['duration'])>.025:
   raise ValueError('Audio interpretation coverage mismatch: '+item['slug'])
  onsets=audio_metrics.get('onsets',[]);records=[];layouts=Counter();texture=Counter();typefaces=Counter()
  for s,c in zip(scenes,interpret):
   candidates=c['candidates'];layout=candidates['layout'][0]['label'];typography=candidates['typography'][0]['label'];t=candidates['texture'][0]['label']
   layouts[layout]+=s['duration'];texture[t]+=s['duration'];typefaces[typography]+=s['duration']
   spoken=' '.join(w['text'] for w in words if s['start']<=(w['start']+w['end'])/2<s['end'])
   windows=[w for w in audio['windows'] if w['start']<s['end'] and w['end']>s['start']]
   heard=list(dict.fromkeys(w['candidates'][0]['label'] for w in windows))
   moves=motion(s)
   text=(f"{item['name']} at {clock(s['start'])}-{clock(s['end'])}. Scene model candidates: {layout}, {typography}, {t}. "
    f"Motion measurements: {', '.join(moves)}. Scene duration {s['duration']:.2f} seconds. "
    f"Mixed audio candidates: {', '.join(heard) or 'unavailable'}. Narration: {spoken[:1400]}")
   records.append({'start':s['start'],'end':s['end'],'kind':'scene-evidence','text':text,
    'data':{'status':'Frame metrics are measurements; visual/audio labels are model-assisted candidates; narration is automatic ASR.',
     'source_path':item['path'],'scene':s['index'],'representative':s['representative'],
     'visual_candidates':candidates,'motion_cues':moves,'colour':s['colour'],'audio_candidates':heard}})
  vectors=embedder.encode([r['text'] for r in records])
  for r,v in zip(records,vectors):r.update(vector=v,model=embedder.model_name)
  db.replace_source('crick-edit-editing-style',item['slug'],records);indexed+=len(records)
  changes=transitions(folder,scenes)
  for change in changes:
   for key in ('seconds','start','end'):
    if key in change:change[key]+=video_offset
  write(folder/'transition-candidates.json',changes)
  events=read(folder/'sound-event-candidates.json')
  for event in events['events']:
   if event.get('nearest_scene_boundary') is not None:
    event['raw_nearest_scene_boundary']=event['nearest_scene_boundary']
    event['nearest_scene_boundary']+=video_offset
    event['offset_from_scene_boundary']=round(event['seconds']-event['nearest_scene_boundary'],4)
  write(folder/'aligned-sound-events.json',events)
  durations=np.array([s['duration'] for s in scenes]);boundaries=[s['start'] for s in scenes[1:]]
  sound_near=sum(any(abs(b-o['seconds'])<=.15 for o in onsets) for b in boundaries)
  stats={'source':item['slug'],'name':item['name'],'seconds':item['seconds'],
   'scene_candidates':len(scenes),'median_scene_seconds':float(np.median(durations)),
   'scene_duration_quartiles':np.percentile(durations,[25,50,75]).tolist(),
   'candidate_changes_per_minute':len(boundaries)/item['seconds']*60,
   'layout_candidate_seconds':dict(layouts),'texture_candidate_seconds':dict(texture),'typography_candidate_seconds':dict(typefaces),
   'transition_candidates':len(changes),'onset_candidates':len(onsets),
   'boundary_onset_overlap_within_150ms':sound_near,'boundary_onset_overlap_note':'Measured temporal coincidence, not proof of sound-design intent.',
   'speech_seconds':audio['speech_seconds'],'recognised_words':len(words),
   'speech_words_per_voiced_second':len(words)/max(audio['speech_seconds'],1) if words else None,
   'audio_available':audio.get('audio_available',True)}
  write(folder/'editing-dna.json',stats);all_stats.append(stats)
  receipt=read(folder/'dna-coverage.json')
  coverage.append({'source':item['slug'],'name':item['name'],'source_seconds':item['seconds'],
   'native_frames':receipt['native_frames_measured'],'scene_candidates':len(scenes),'classified_scenes':len(interpret),
   'audio_available':stats['audio_available'],'audio_measured_seconds':audio_metrics['duration'] if stats['audio_available'] else 0,
   'audio_classified_seconds':audio['analysed_seconds'],'speech_transcribed':(folder/'speech-coverage.json').exists(),
   'sound_event_candidates':len(read(folder/'sound-event-candidates.json')['events'])})
  print('Indexed '+item['slug']+': '+str(len(records))+' scenes',flush=True)
 db.close()
 receipt={'style':'cricAddict','source_folder':str(Path(items[0]['path']).parent),
  'sources':coverage,'total_source_seconds':sum(i['seconds'] for i in items),
  'native_frames_measured':sum(c['native_frames'] for c in coverage),'scene_candidates':sum(c['scene_candidates'] for c in coverage),
  'audio_available_sources':sum(c['audio_available'] for c in coverage),'audio_analysed_seconds':sum(c['audio_measured_seconds'] for c in coverage),
  'vector_records':indexed,'vector_model':'intfloat/multilingual-e5-small','vector_dimensions':384,
  'database':str(ROOT/'library/creator-profiles/editing-dna.sqlite3'),
  'learning_method':'Persistent, source-linked measurements, reviewed editing rules and semantic retrieval. No model weights were fine-tuned.',
  'visual_scope':'Every decoded native frame measured at 256x144. Scene semantics use one in-scene keyframe, not a human interpretation of every frame.',
  'audio_scope':'Complete available mixed audio in 20ms blocks, full-track VAD, 10s CLAP windows, selected short onset windows and automatic speech timestamps. No isolated music/voice/effect stems.',
  'limits':['Scene boundaries and flash/fade cues are candidates, not hand-verified cuts.',
   'Fonts, physical cameras and separate 3D layers cannot be recovered exactly from flattened video.',
   'CLIP/CLAP similarities are not calibrated probabilities. Brief effects may be masked by speech or music.',
   'Beat estimates measure mixed-track periodicity, not confirmed musical downbeats. Cricket facts and player eras require separate verification.']}
 write(BASE/'coverage.json',receipt);write(BASE/'editing-dna.json',{'coverage':receipt,'patterns':PATTERNS,'videos':all_stats})
 profile=read(ROOT/'library/creator-profiles/crick-edit-editing-style.json')
 profile.update(analysis_status='analysis-complete',learning_method=receipt['learning_method'],learned_patterns=PATTERNS,
  rules=[p['application'] for p in PATTERNS]+['Use the selected named reference set only. Change composition, transition and pacing with the story; do not repeat one three-photo entrance across categories.',
   'Keep texture subtle and foreground text legible. Use a photographic or historically motivated background rather than a flat grey placeholder.',
   'Fit all images without stretching. Reduce word gaps when needed without compressing letter spacing.',
   'Build sound around narration: background music supports the mood, short effects punctuate motivated changes, pauses and crowd reactions retain emotional context. Choose actual licensed sounds with listening-based retrieval; do not reuse inferred source sound labels as verified assets.'],
  coverage_summary={k:receipt[k] for k in ('native_frames_measured','scene_candidates','audio_available_sources','audio_analysed_seconds','vector_records')},
  style_database=receipt['database'],report=str(BASE/'report.html'),isolation='Separate style-filtered memory. vineet documentry edit and General/Gaming remain independent.')
 write(ROOT/'library/creator-profiles/crick-edit-editing-style.json',profile)
 card={'id':'card_crick_edit_reference','name':'cricAddict','status':'approved',
  'sources':[i['path'] for i in items],
  'tokens':{'--bg':'#101318','--paper':'#eee9dc','--ink':'#191b20','--accent':'#f0d230','--alert':'#be3030','--grain':'.035','--texture':'dark','--photo':'none'},
  'speed':1.0,'notes':{'documentary_set':'crick-edit-editing-style','settings_group':'cricAddict',
   'summary':'Reference-led documentary editing: subject cut-outs, evidence highlights, archival film/television, layered paper, book openings, era timelines and reaction pacing.',
   'basis':'Measured source references and persistent style retrieval. This card does not claim to reconstruct every source animation or After Effects project.'}}
 write(ROOT/'library/motion-styles/card_crick_edit_reference.json',card)
 build_report(items,receipt,all_stats)
 print('Editing memory and report complete.',flush=True)

def build_report(items,receipt,stats):
 esc=html.escape
 cards=[]
 for item,stat in zip(items,stats):
  folder=BASE/item['slug'];scenes=read(folder/'aligned-scenes.json')['scenes'];interpret=read(folder/'scene-interpretations.json')['scenes'];audio=read(folder/'audio-interpretations.json')
  sections=[]
  for s,c in zip(scenes,interpret):
   labels=' · '.join(c['candidates'][k][0]['label'] for k in ('layout','typography','texture'))
   sections.append(f'<article class="scene" data-search="{esc(labels)}"><a href="{esc(Path(item["path"]).as_uri())}#t={s["start"]:.3f}" target="_blank"><img loading="lazy" src="{s["representative"]["file"]}"></a><b>{clock(s["start"])}–{clock(s["end"])}</b><p>{esc(labels)}</p><small>{esc(", ".join(motion(s)))}</small></article>')
  audio_rows=''.join(f'<tr><td>{clock(w["start"])}–{clock(w["end"])}</td><td>{round(w["speech_fraction"]*100)}%</td><td>{esc(", ".join(c["label"] for c in w["candidates"]))}</td></tr>' for w in audio['windows'])
  event_data=read(folder/'aligned-sound-events.json')
  effect_rows=''.join(f'<tr><td>{e["seconds"]:.2f}s</td><td>{esc(", ".join(c["label"] for c in e["candidates"]))}</td><td>{str(e.get("offset_from_scene_boundary"))}s</td></tr>' for e in event_data['events'])
  audio_page=(f'<h2>Voice, music and ambience</h2><p>Full-track voice detection and ten-second listening windows. These are overlapping mixed-track candidates, not isolated stems.</p><table><thead><tr><th>Time</th><th>Voice activity</th><th>Sound candidates</th></tr></thead><tbody>{audio_rows}</tbody></table><h2>Short sound events</h2><p>Strong onset windows sampled across the film. The last column measures time from the nearest scene boundary; coincidence does not establish intent.</p><table><thead><tr><th>Time</th><th>Candidates</th><th>Boundary offset</th></tr></thead><tbody>{effect_rows}</tbody></table>') if audio['windows'] else '<p>This original file contains no audio stream. Sound cannot be analysed.</p>'
  (folder/'audio-review.html').write_text(f'<!doctype html><meta charset="utf-8"><title>Sound review</title><link rel="stylesheet" href="../review.css"><main><a href="report.html">← Visual review</a><h1>{esc(item["name"])}</h1>{audio_page}</main>',encoding='utf-8')
  source_page=f'''<!doctype html><meta charset="utf-8"><title>{esc(item['name'])} · Editing DNA</title><link rel="stylesheet" href="../review.css"><main><a href="../report.html">← All references</a><h1>{esc(item['name'])}</h1><p>Each image is inside its scene candidate. Labels are model suggestions. Select an image to open the original video at that time.</p><video controls preload="none" src="{esc(Path(item['path']).as_uri())}"></video><p><a href="editing-dna.json">Measurements</a> · <a href="scene-interpretations.json">Visual candidates</a> · <a href="audio-interpretations.json">Voice, music and ambience</a> · <a href="sound-event-candidates.json">Short effect candidates</a> · <a href="audio-analysis.json">Onsets and rhythm estimates</a> · <a href="transition-candidates.json">Flash/fade candidates</a> · <a href="transcript.txt">Narration transcript, if audio is present</a></p><input id="filter" placeholder="Find layout, typography or texture"><div class="grid">{''.join(sections)}</div><script>document.querySelector('#filter').oninput=e=>document.querySelectorAll('.scene').forEach(s=>s.hidden=!s.dataset.search.includes(e.target.value.toLowerCase()));</script></main>'''
  (folder/'report.html').write_text(source_page,encoding='utf-8')
  source_page=source_page.replace('Voice, music and ambience</a>','Raw audio candidates</a>')
  if not (folder/'transcript.txt').exists():
   source_page=source_page.replace('<a href="transcript.txt">Narration transcript, if audio is present</a>','No source narration track')
  source_page=source_page.replace('<input id="filter"','<p><a href="audio-review.html">Open the readable voice, music and sound-effects review →</a></p><input id="filter"')
  (folder/'report.html').write_text(source_page,encoding='utf-8')
  cards.append(f'<a class="source" href="{item["slug"]}/report.html"><img loading="lazy" src="{item["slug"]}/overview-01.jpg"><h3>{esc(item["name"])}</h3><p>{clock(item["seconds"])} · {stat["scene_candidates"]} scene candidates · {"voice/audio analysed" if stat["audio_available"] else "no source audio"}</p></a>')
 patterns=''.join(f'<article><h3>{esc(p["name"])}</h3><p>{esc(p["observation"])}</p><p><b>Editing rule:</b> {esc(p["application"])}</p><a href="{p["source"]}/report.html">Reference {p["source"][-2:]} · {clock(p["start"])}</a></article>' for p in PATTERNS)
 totals=f'{receipt["native_frames_measured"]:,} native frames · {receipt["scene_candidates"]:,} scene candidates · {receipt["audio_available_sources"]} audio tracks · {receipt["vector_records"]:,} searchable Crick records'
 page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>cricAddict · Editing DNA</title><link rel="stylesheet" href="review.css"><main><p class="eyebrow">YOUR DOCUMENTARY STYLE MEMORY</p><h1>cricAddict</h1><p>{esc(totals)}</p><p>All nine videos from your reference folder have been measured sequentially. This named memory remains separate from vineet documentry edit. Its rules and semantic retrieval now guide Cricket motion planning when you select this style.</p><div class="notice"><b>What “learned” means here</b><p>{esc(receipt['learning_method'])}</p><p>{esc(receipt['visual_scope'])}</p><p>{esc(receipt['audio_scope'])}</p></div><p><a href="editing-dna.json">Full editing DNA</a> · <a href="coverage.json">Coverage receipt</a> · <a href="style-memory.md">Readable style guide</a></p><h2>Editing patterns retained</h2><div class="patterns">{patterns}</div><h2>Explore every detected scene</h2><div class="sources">{''.join(cards)}</div><h2>Interpretation limits</h2><ul>{''.join('<li>'+esc(x)+'</li>' for x in receipt['limits'])}</ul></main></html>'''
 (BASE/'report.html').write_text(page,encoding='utf-8')
 (BASE/'review.css').write_text('''*{box-sizing:border-box}body{margin:0;background:#10151c;color:#ecf0f4;font:16px/1.6 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:40px 24px}h1{font-size:44px;line-height:1.15}h2{margin-top:48px}a{color:#8edcda;text-decoration:none}a:hover{text-decoration:underline}.eyebrow{letter-spacing:.18em;color:#9fbaa9;font-size:13px}.notice,.patterns article,.source,.scene{background:#1b2430;border:1px solid #334050;border-radius:12px;padding:18px}.patterns,.sources{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}.source img{width:100%;border-radius:6px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.scene img{width:100%;display:block}.scene p{font-size:13px}.scene small{color:#abb9c8}.scene[hidden]{display:none}video{width:100%;max-height:600px;background:black}input{width:100%;padding:14px;margin:20px 0;background:#253244;color:white;border:1px solid #64748b;border-radius:8px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:12px;border-bottom:1px solid #334050;text-align:left}thead{background:#253244}''',encoding='utf-8')
 guide=['# cricAddict','',totals,'',receipt['learning_method'],'']
 for p in PATTERNS:guide+=['## '+p['name'],'',p['observation'],'',p['application'],'',f"Evidence: {p['source']} at {clock(p['start'])}–{clock(p['end'])}.",'']
 guide+=['## Visual and audio analysis','',receipt['visual_scope'],'',receipt['audio_scope'],'']+['- '+x for x in receipt['limits']]
 (BASE/'style-memory.md').write_text('\n'.join(guide),encoding='utf-8')

if __name__=='__main__':main()
