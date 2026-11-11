"""Sequential local GPU transcription with existing source-linked checkpoints."""
import json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BASE=ROOT/'output/reference-analysis/crick-edit-editing-style'
folder=ROOT/'tools/cuda-reference-runtime/bin'
handle=os.add_dll_directory(str(folder));os.environ['PATH']=str(folder)+os.pathsep+os.environ['PATH']
from tools.analyze_documentary_reference import fast_transcript
for item in json.loads((BASE/'inventory.json').read_text(encoding='utf-8')):
 output=BASE/item['slug']
 while not (output/'audio-analysis.json').exists():time.sleep(20)
 metrics=json.loads((output/'audio-analysis.json').read_text())
 if metrics.get('audio_available') is False:
  print('No narration available '+item['slug'],flush=True);continue
 print('Narration '+item['slug'],flush=True)
 fast_transcript(Path(item['path']),output,ROOT,device='cuda',batch_size=4)
print('All available narration tracks transcribed.',flush=True)
