"""Replan the saved recovery scan with real local editorial choices and cached audio evidence."""
import json,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hinglish_app.template_text import save
from hinglish_app.template_text_model import build_slots,signature,validate_snapshot
from hinglish_app.template_text_editor import select_headings
from hinglish_cut.model_storage import configure
from hinglish_cut.gpu_lock import gpu_lock
from hinglish_visuals.brain import open_brain
from hinglish_niche.profiles import Profiles,use

root=Path(__file__).resolve().parents[1]
repair=root/'output/template-text-repair'
previous=root/'output/template-text/2272a61ba50c48dda0ebc9ae'
read=lambda p:json.loads(p.read_text('utf-8-sig'))
scan=validate_snapshot(read(repair/'scene-heading-snapshot.json'))
request=read(previous/'request.json')
if signature(scan['audio'])!=signature(request['snapshot']['audio']):
    raise SystemExit('Narration mapping changed; cached word timing cannot be reused.')
key=uuid.uuid4().hex[:24];folder=root/'output/template-text'/key
folder.mkdir();save(repair/'scene-heading-job.json',{'id':key,'path':str(folder)})
request.update(snapshot=scan,snapshot_sha256=signature(scan))
save(folder/'request.json',request)
words=read(previous/'heading-word-evidence.json')['words']
save(folder/'heading-word-evidence.json',{'words':words,'source_job':previous.name,'audio_mapping_verified':True})
slots=build_slots(scan,words);save(folder/'slots.json',slots)
actions=[{'id':s['id'],'template_layer_id':s['template_layer_id'],'text_id':s['text_id'],
          'action':'hide','role':'body','text':'','word_indices':[]} for s in slots if s['policy']!='skip']
receipts=[];started=time.time();configure(root)
def progress(stage,percent):
    save(folder/'status.json',{'id':key,'status':'running','stage':stage,'progress':percent,'seconds':time.time()-started})
try:
    with gpu_lock(root):
        brain=open_brain(root,'ollama');brain.request_timeout=600;brain.request_attempts=1
        profiles=Profiles(root);creator=profiles.context(profiles.read()['selected'])
        save(folder/'creator-context.json',creator)
        def ask(system,data,schema,tokens):
            with use(creator):answer=brain.json(system,data,schema,max_tokens=tokens,think=False)
            receipts.append({'model':getattr(brain,'model',brain.name),'input':data,'answer':answer})
            save(folder/'editor-model-receipts.json',receipts)
            return answer
        try:actions=select_headings(slots,actions,ask,progress,lambda v:save(folder/'heading-selection.json',v))
        finally:brain.close()
    count=sum(a['action']=='replace' for a in actions)
    if not count:raise ValueError('No supported headings; nothing will be applied.')
    skipped=[{'id':s['id'],'reason':s['reason']} for s in slots if s['policy']=='skip']
    plan={'version':1,'job_id':key,'project_id':scan['project_id'],'composition_id':scan['composition_id'],
          'fingerprint':scan['fingerprint'],'snapshot_sha256':signature(scan),'actions':actions,
          'warnings':scan.get('warnings',[]),'skipped':skipped}
    save(folder/'plan.json',plan)
    lookup={s['id']:s for s in slots}
    originals=[];seen=set()
    for t in scan['templates']:
        for row in t['texts']:
            identity=(row['comp_id'],row['layer_index'])
            if identity in seen:continue
            seen.add(identity);originals.append({'comp_id':row['comp_id'],'layer_index':row['layer_index'],
                                               'text':row['text'],'enabled':row['current_enabled']})
    save(repair/'scene-heading-native-seed.json',{'plan':plan,'originals':originals,
         'heading_runs':{a['id']:lookup[a['id']]['runs'] for a in actions if a['action']=='replace'}})
    save(folder/'status.json',{'id':key,'status':'ready','stage':'Scene headings ready for native review.',
                             'replacements':count,'seconds':time.time()-started})
    print('Scene heading plan:',key,'replacements:',count,flush=True)
except Exception as error:
    save(folder/'status.json',{'id':key,'status':'failed','error':str(error)});raise
