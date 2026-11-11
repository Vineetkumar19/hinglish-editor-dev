"""Measure a cached small LOCAL vision model on this reference's first panel."""
import base64,json,time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/reference-analysis/cricAddict-by-video/reference-01'
s=requests.Session();s.trust_env=False
start=time.time()
try:
 r=s.post('http://127.0.0.1:11434/api/chat',json={'model':'moondream:latest','stream':False,'keep_alive':0,
  'options':{'num_ctx':2048,'num_thread':4,'num_gpu':99,'num_predict':180,'temperature':0},
  'messages':[{'role':'user','content':'This panel contains 15 chronological video frames, left to right then next row, one per second from 0 to 14 seconds. Describe the visible editing design and changes: image placement, text, background, book/paper/collage, colour. Do not invent person names or audio. Use concise English, no more than 90 words.',
   'images':[base64.b64encode((OUT/'review-panels/0000.jpg').read_bytes()).decode()]}]},timeout=(15,500));r.raise_for_status()
 answer={'elapsed_seconds':time.time()-start,'model':'moondream:latest','response':r.json(),'cloud':False}
 (OUT/'small-vision-benchmark.json').write_text(json.dumps(answer,indent=2),encoding='utf8')
 print(json.dumps({'elapsed_seconds':answer['elapsed_seconds'],'content':answer['response']['message']['content']},ensure_ascii=False),flush=True)
finally:s.close()
