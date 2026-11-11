"""Offline scene and mixed-audio interpretation, with explicit inference provenance."""
import argparse,gc,json,sys,time,wave
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BASE=ROOT/'output/reference-analysis/crick-edit-editing-style'
CACHE=Path.home()/'.cache/huggingface/hub'
CLIP=CACHE/'models--sentence-transformers--clip-ViT-B-32/snapshots/327ab6726d33c0e22f920c83f2ff9e4bd38ca37f/0_CLIPModel'
CLAP=CACHE/'models--laion--clap-htsat-unfused/snapshots/8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a'
VISUAL={
 'layout':{'presenter':'a talking head video of a presenter speaking to the camera',
 'match-footage':'a cricket match television broadcast with players on the field',
 'player-cutout':'a documentary graphic with a large isolated cricket player cutout over a background',
 'archival-photograph':'an archival cricket photograph in a documentary montage',
 'photo-collage':'a composition of several framed photographs and paper layers',
 'article-evidence':'a newspaper or website article with highlighted written text',
 'scorecard-evidence':'a table of cricket scores and statistics',
 'timeline':'a history timeline with dates and portraits',
 'vintage-television':'a vintage television screen framing cricket footage',
 'map':'a geographic map illustration',
 'title-card':'a documentary title card with large prominent lettering'},
 'typography':{'condensed-heading':'large bold condensed block lettering in a documentary graphic',
 'serif-heading':'elegant serif lettering in a documentary title',
 'script-accent':'handwritten script brush lettering',
 'plain-sans':'plain sans serif captions or paragraph text',
 'red-title-block':'white words inside a red rectangular title block',
 'yellow-emphasis':'large yellow bold words over a photograph',
 'minimal-text':'a photograph or video with no prominent text'},
 'texture':{'torn-paper':'a collage of torn paper and torn edged photographs',
 'halftone-grid':'a white halftone dotted paper background and grid',
 'film-grain':'a cinematic photograph with film grain and film frame overlays',
 'sepia-archive':'a sepia brown vintage archival photograph',
 'photo-background':'a faint or blurred photograph behind a sharp foreground photograph',
 'light-leak':'a cinematic image with warm orange lens flare or light leak',
 'clean':'a clean video image without paper or film texture'}}
AUDIO={
 'voice':'a person speaking narration', 'music':'instrumental background music',
 'impact':'a deep cinematic boom impact sound effect','riser':'a rising suspenseful sound effect building tension',
 'whoosh':'a fast swoosh of air passing by','ambience':'a cricket stadium crowd ambience',
 'applause':'a crowd applauding and cheering','broadcast':'sports commentary speaking over a crowd',
 'silence':'silence or very quiet background','glitch':'television static or electronic glitch sound',
 'emotional-music':'emotional slow orchestral string music','tense-music':'dark tense suspenseful background music',
 'energetic-music':'energetic cinematic instrumental music with drums',
 'typing':'keyboard typing or clicking sounds'}

def dump(path,data):
 temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(path)

def ranked(vector,vectors,names,count=3):
 scores=np.asarray(vectors)@vector;order=np.argsort(-scores)[:count]
 return [{'label':names[i],'cosine_similarity':round(float(scores[i]),5)} for i in order]

def main(base=None):
 base=Path(base).resolve() if base else BASE
 import torch
 from PIL import Image
 from transformers import CLIPModel,CLIPProcessor
 from faster_whisper.vad import get_speech_timestamps,VadOptions
 from hinglish_sound.listen import Listener
 torch.set_num_threads(2)
 print('Loading existing offline CLIP and CLAP models on CPU.',flush=True)
 clip=CLIPModel.from_pretrained(str(CLIP),local_files_only=True).eval()
 processor=CLIPProcessor.from_pretrained(str(CLIP),local_files_only=True)
 banks={}
 for category,labels in VISUAL.items():
  with torch.inference_mode():
   inputs=processor(text=list(labels.values()),return_tensors='pt',padding=True)
   values=clip.get_text_features(**inputs)
   if not isinstance(values,torch.Tensor):values=values.pooler_output
   values=torch.nn.functional.normalize(values,dim=-1).numpy()
  banks[category]=(list(labels),values)
 listener=Listener(ROOT,model='laion/clap-htsat-unfused',threads=2,local_folder=CLAP)
 audio_names=list(AUDIO);audio_bank=listener.texts(list(AUDIO.values()))
 items=json.loads((base/'inventory.json').read_text(encoding='utf-8'))
 for number,item in enumerate(items,1):
  folder=base/item['slug']
  while not (folder/'dna-coverage.json').exists() or not (folder/'audio-analysis.json').exists():
   print('Waiting for sequential native scan: '+item['slug'],flush=True);time.sleep(20)
  scenes=json.loads((folder/'scenes.json').read_text());receipt=json.loads((folder/'dna-coverage.json').read_text())
  out=folder/'scene-interpretations.json'
  if not out.exists():
   rows=[]
   for start in range(0,len(scenes),8):
    batch=scenes[start:start+8];images=[Image.open(folder/s['representative']['file']).convert('RGB') for s in batch]
    with torch.inference_mode():
     vector=clip.get_image_features(**processor(images=images,return_tensors='pt'))
     if not isinstance(vector,torch.Tensor):vector=vector.pooler_output
     vectors=torch.nn.functional.normalize(vector,dim=-1).numpy()
    for scene,v in zip(batch,vectors):
     row={'index':scene['index'],'start':scene['start'],'end':scene['end'],'representative':scene['representative'],
          'candidates':{key:ranked(v,vec,names) for key,(names,vec) in banks.items()},
          'status':'model-assisted candidates, not confirmed object, font or layer identification'}
     rows.append(row)
    for im in images:im.close()
    if start%160==0:print(f"VISUAL {number}/{len(items)} {min(start+8,len(scenes))}/{len(scenes)}",flush=True)
   dump(out,{'model':'CLIP ViT-B/32, existing offline weights','scope':'One in-scene 256x144 representative per detected scene candidate; every native frame has separate numeric measurements.',
    'source':receipt['source'],'scenes':rows})
  out=folder/'audio-interpretations.json'
  if not out.exists():
   metrics=json.loads((folder/'audio-analysis.json').read_text())
   if metrics.get('audio_available') is False:
    dump(out,{'audio_available':False,'duration':metrics['duration'],'analysed_seconds':0,'windows':[],
              'speech_intervals':[],'speech_seconds':0,'status':'Source file has no audio stream.'})
    dump(folder/'sound-event-candidates.json',{'events':[],'audio_available':False,'status':'Original source contains no audio stream.'})
    continue
   with wave.open(str(folder/'analysis-audio.wav'),'rb') as reader:
    audio=np.frombuffer(reader.readframes(reader.getnframes()),dtype='<i2').astype(np.float32)/32768
   speech=get_speech_timestamps(audio,VadOptions(min_silence_duration_ms=250,speech_pad_ms=150),sampling_rate=16000)
   intervals=[{'start':s['start']/16000,'end':s['end']/16000} for s in speech]
   windows=[];size=160000
   for start in range(0,len(audio),size*4):
    chunks=[audio[k:min(k+size,len(audio))] for k in range(start,min(len(audio),start+size*4),size)]
    vectors=listener.audio([resample_poly(c,3,1).astype(np.float32) for c in chunks])
    for j,(chunk,v) in enumerate(zip(chunks,vectors)):
     a=(start+j*size)/16000;b=a+len(chunk)/16000
     voiced=sum(max(0,min(b,s['end'])-max(a,s['start'])) for s in intervals)
     windows.append({'start':a,'end':b,'speech_fraction':round(voiced/max(b-a,1e-8),4),
                     'candidates':ranked(v,audio_bank,audio_names,4)})
    if start%(size*20)==0:print(f'AUDIO {number}/{len(items)} {min(start+size*4,len(audio))/16000:.1f}/{len(audio)/16000:.1f}s',flush=True)
   dump(out,{'model':'CLAP HTSAT unfused, existing offline weights','duration':len(audio)/16000,
    'window_seconds':10,'analysed_seconds':sum(w['end']-w['start'] for w in windows),
    'voice_detection':'Silero VAD on the complete 16 kHz mixed track; no speaker identity or transcription implied.',
    'speech_intervals':intervals,'speech_seconds':sum(s['end']-s['start'] for s in intervals),
    'windows':windows,'status':'Mixed-track similarity candidates, not calibrated probabilities or isolated stems. Short effects can be masked by speech and music.'})
   del audio;gc.collect()
  event_path=folder/'sound-event-candidates.json'
  if not event_path.exists():
   metrics=json.loads((folder/'audio-analysis.json').read_text())
   if metrics.get('audio_available') is False:
    dump(event_path,{'events':[],'audio_available':False});continue
   with wave.open(str(folder/'analysis-audio.wav'),'rb') as reader:
    audio=np.frombuffer(reader.readframes(reader.getnframes()),dtype='<i2').astype(np.float32)/32768
   # Distribute the strongest onset candidates across the complete film, rather
   # than only sampling its loud introduction. All onsets remain in audio-analysis.
   onsets=metrics['onsets'];selected=[]
   for block in range(0,int(metrics['duration'])+1,30):
    selected.extend(sorted([o for o in onsets if block<=o['seconds']<block+30],key=lambda o:-o['strength'])[:3])
   selected.sort(key=lambda o:o['seconds']);events=[]
   boundaries=[s['start'] for s in scenes[1:]]
   for start in range(0,len(selected),4):
    batch=selected[start:start+4];clips=[]
    for onset in batch:
     a=max(0,onset['seconds']-.5);b=min(metrics['duration'],onset['seconds']+1.2)
     clips.append(resample_poly(audio[round(a*16000):round(b*16000)],3,1).astype(np.float32))
    vectors=listener.audio(clips)
    for onset,v in zip(batch,vectors):
     nearest=min(boundaries,key=lambda t:abs(t-onset['seconds'])) if boundaries else None
     events.append({**onset,'candidates':ranked(v,audio_bank,audio_names,4),
      'nearest_scene_boundary':nearest,'offset_from_scene_boundary':round(onset['seconds']-nearest,4) if nearest is not None else None,
      'status':'Short mixed-audio candidate; a speech consonant, crowd burst or drum may resemble an editing effect.'})
   dump(event_path,{'window':'0.5s before through 1.2s after onset','selection':'Up to 3 strongest measured onsets per 30 seconds; all onsets retained separately.',
    'events':events,'model':'CLAP HTSAT unfused','verified':False})
   del audio;gc.collect()
  print('Finished semantic interpretation '+item['slug'],flush=True)
 print(f'All {len(items)} offline visual/audio interpretation passes complete.',flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,default=BASE)
 args=parser.parse_args();main(args.base)
