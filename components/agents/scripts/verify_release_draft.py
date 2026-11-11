"""Save one unapproved internal review draft in StoryLens's real ledger."""
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
folder=ROOT/'data/real-delivery-acceptance'
from core import config
config._LOADED=True
os.environ.update(DATA_DIR=str(folder),DB_URL='sqlite:///'+str(folder/'suite.db'),DRY_RUN='false',
    NOTIFY_CHANNELS='store',LOG_LEVEL='CRITICAL',SUITE_INTEGRATIONS_FILE=str(ROOT/'profiles/workflow_integrations.json'))
from core.store import Store
from core.workflow_service import WorkflowService
service=WorkflowService(Store())
delivery=json.loads((folder/'result.json').read_text())
video=next(r for r in delivery['render']['artifacts'] if r['type']=='mp4')
caption=('A short visual sequence opening with a woman checking her phone.\n\n'
    'Instagram: https://www.instagram.com/vineet_editz19/\n\n'
    '#BrandNewDay #NewDay #VisualStorytelling #ShortFilm #FilmScene #PhoneScene #VideoEditing #VideoClip #ScreenTime #MobilePhone')
task=service.create('content_release','Internal review draft: existing excerpt, no release authorization',
    {'body_revision':'owner-excerpt-1','preview_only':True,
     'edit_approval_ref':'Unapproved technical excerpt. Local draft only; owner edit approval remains pending.',
     'rights_evidence':'Owner authorized local acceptance with selected existing files. No publishing-rights assertion.',
     'packages':[{'platform':'youtube','profile':'gaming','account':'UCtc3vpF9QPHAM7lTYCCulyg',
         'time':'2026-11-05T18:00:00+05:30','title':'Brand New Day — A Short Visual Sequence',
         'caption':caption,'artifact':video,'intro_id':'source-excerpt','visibility':'private'}]},
    'native-publisher-draft-v1')
if task['state']=='queued':task=service.prepare(task['task_id'])
if task['state']=='waiting_for_review' and task['result'].get('approval_id'):
    task=service.decide(task['task_id'],True)
for aid in task['result'].get('review_ids',[]):
    from core.hitl import ApprovalQueue
    if ApprovalQueue(service.store).get(aid)['status']=='pending':
        task=service.decide(task['task_id'],True,aid)
deadline=time.monotonic()+60
while True:
    task=service.dispatch(task['task_id'])
    receipts=task['result'].get('destinations',{})
    if task['state']=='succeeded' or any(v.get('status')=='failed' or v.get('error') for v in receipts.values()):break
    if time.monotonic()>deadline:break
    time.sleep(.5)
result={'task_id':task['task_id'],'state':task['state'],'destinations':task['result'].get('destinations',{}),
        'sent':False,'published':False,'scheduled_for_release':False,'edit_approved':False,
        'time_scope':'Proposed metadata only; native job remains draft and is not authorized to execute.'}
(folder/'release-draft-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
raise SystemExit(0 if task['state']=='succeeded' else 1)
