"""Resume only the final local editorial stage of an unapplied saved text plan."""
import json,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hinglish_app.template_text import save
from hinglish_app.template_text_editor import select_headings
from hinglish_app.template_text_model import uncovered_headings
from hinglish_cut.model_storage import configure
from hinglish_cut.gpu_lock import gpu_lock
from hinglish_visuals.brain import open_brain
from hinglish_niche.profiles import Profiles,use
root=Path(__file__).resolve().parents[1];folder=root/'output/template-text/2272a61ba50c48dda0ebc9ae'
state=json.loads((folder/'status.json').read_text('utf8'))
if state['status']!='ready' or (folder/'native-receipt.json').exists():raise SystemExit('Only an unapplied ready plan can be reviewed.')
plan=json.loads((folder/'plan.json').read_text('utf8'));slots=json.loads((folder/'slots.json').read_text('utf8'))
save(folder/'before-final-editor.json',plan)
receipts=[];configure(root)
def progress(stage,percent):save(folder/'editor-status.json',{'stage':stage,'progress':percent,'status':'running'})
try:
 with gpu_lock(root):
  brain=open_brain(root,'ollama');brain.request_timeout=600;brain.request_attempts=1
  profile=Profiles(root);creator=profile.context(profile.read()['selected'])
  def ask(system,data,schema,tokens):
   with use(creator):answer=brain.json(system,data,schema,max_tokens=tokens,think=False)
   receipts.append({'model':getattr(brain,'model',brain.name),'answer':answer});save(folder/'editor-model-receipts.json',receipts);return answer
  try:plan['actions']=select_headings(slots,plan['actions'],ask,progress,lambda value:save(folder/'heading-selection.json',value))
  finally:brain.close()
 missing=uncovered_headings(slots,plan['actions']);count=sum(a['action']=='replace' for a in plan['actions'])
 if not count:raise ValueError('No supported headings; prior unapplied plan retained.')
 plan['warnings']=[w for w in plan['warnings'] if 'scenes still have no supported heading' not in w]
 if missing:plan['warnings'].append(str(len(missing))+' scenes still have no supported heading. Review these before treating the text pass as complete.')
 save(folder/'plan.json',plan);save(folder/'heading-coverage.json',{'replacements':count,'uncovered_scenes':[{'id':s['id'],'runs':s['runs']} for s in missing]})
 save(folder/'editor-status.json',{'status':'ready','replacements':count,'uncovered':len(missing)})
 print('Local heading review finished:',count,'replacements;',len(missing),'uncovered scenes')
except Exception as e:
 save(folder/'editor-status.json',{'status':'failed','error':str(e)});raise
