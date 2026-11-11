"""Use actual planner schema on unseen events before a large model export."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/sound-training/20261030-production-decisions'
def main():
 global OUT
 if len(sys.argv)>1:
  OUT=Path(sys.argv[1]).resolve()
  if not OUT.is_relative_to((ROOT/'output/sound-training').resolve()):raise ValueError('Invalid training output')
 from tools.sound_training import export_adapter,runtime_gate
 if not (OUT/'adapter.gguf').is_file():raise RuntimeError('Export the trained adapter first')
 from hinglish_sound.layers import plan_layers
 class Capture:
  def ask(self,system,data,schema,**kwargs):self.system,self.data,self.schema=system,data,schema;return {'layers':[]}
 b=Capture();events=[dict(id='rail-97',time=1.,end=4.,kind='foley',precision='visual_interval',label='Train moving on rails',sound_evidence='Steel wheels rolling and rumbling over rails'),dict(id='jetty-13',time=4.,end=7.,kind='ambience',precision='visual_interval',label='Small lake waves hit a wooden jetty',sound_evidence='Lake water lapping wooden supports')]
 plan_layers(b,events,'Travel montage with existing song; make the physical sources audible.','calm',2,['foley','ambience'],composition={'seconds':7})
 import revision
 revision.SYSTEM=b.system;revision.GATE=[('unseen-production-schema',json.dumps(b.data),'',['Actual rail and lake sources; complete intervals; numeric final levels; no arbitrary UI effects'])]
 runtime_gate.OUT=OUT;runtime_gate.SCHEMA=b.schema;runtime_gate.system_prompt=lambda system:system
 def check(response):
  choice=response['choices'][0];text=choice['message'].get('content','')
  try:parsed=json.loads(text)
  except ValueError:parsed={}
  layers=parsed.get('layers',[])
  complete=choice.get('finish_reason')=='stop' and bool(layers) and all(isinstance(r.get('target_level_db'),(int,float)) and isinstance(r.get('strength'),int) for r in layers)
  return dict(format_complete=complete,finish_reason=choice.get('finish_reason'),text=text,parsed=parsed,usage=response.get('usage'),timings=response.get('timings'))
 runtime_gate.check_response=check
 runtime_gate.main(compare_case_ids=set(),context_tokens=8192)
 print((OUT/'runtime-gate-comparison.json').read_text(),flush=True)
if __name__=='__main__':main()
