"""Correct native-runtime errors; preserve all earlier checks as regressions."""
import copy,hashlib,json
from tools.publishing_training import revision9 as v9,revision10 as v10,revision7 as v7,revision8 as v8
ROOT=v9.ROOT
PARENT=ROOT/'output/publishing-training/20261030-v12'
OUT=ROOT/'output/publishing-training/20261030-v13'

def build():
 if OUT.exists():raise RuntimeError('Keep frozen training evidence')
 status=json.loads((PARENT/'native-acceptance-status.json').read_text())
 if status['complete']!=status['total']:raise RuntimeError('Finish regression evaluation first')
 failures={r['id'] for r in json.loads((PARENT/'native-acceptance.json').read_text()) if not r['passed']}
 prior=v10.read(PARENT/'dataset/acceptance.jsonl')
 train=copy.deepcopy(v10.read(PARENT/'dataset/train.jsonl'))
 for row in prior:
  if row['id'] in failures:
   for i in range(4):
    r=copy.deepcopy(row);r['id']=f'v13-correction-{i}-'+r['id']
    data=json.loads(r['messages'][1]['content'])
    if i:
     field='spoken_content' if row['family']=='instagram_copy' else 'tool_evidence'
     data[field]=['','Current verified observation: ','Source excerpt: ','Evidence for this task: '][i]+data[field]
    r['messages'][1]['content']=json.dumps(data);train.append(r)
 # Contrast a saved remote ID after submission with an upload whose ID is unknown.
 contrasts=[
 ('The saved video ID and queue job exist. Schedule may have been submitted, but readback is unavailable. Do not insert any new upload.','reuse_saved_jobs'),
 ('Upload transfer ended without a saved remote video ID or usable transfer session. The remote outcome is uncertain.','reconcile_upload'),
 ('Scheduling submission lost its response. The exact remote video ID and existing queue job are saved; their final release state needs reconciliation.','reuse_saved_jobs'),
 ('The original private upload is verified and processing is complete. Schedule was never submitted and one authorized attempt remains.','retry_saved_release'),
 ('The original private upload exists. The visibility selector failed and all bounded release retries are exhausted.','report_connector_failure')]
 for i,(e,d) in enumerate(contrasts):
  r=v7.state_row(f'v13-contrast-{i}',e,d);r['messages'][0]['content']=v8.STATE;train.append(r)
 held=[]
 subjects=[('Punjab Kings','fielding'),('Animal Crossing','teamwork'),('Sunrisers Hyderabad','bowling'),('Counter Strike','strategy'),('Royal Challengers Bengaluru','leadership'),('Kolkata Knight Riders','batting')]
 for i,(subject,theme) in enumerate(subjects):
  source=f'This excerpt is about {subject}; its focus is {theme}. Preserve the complete subject and topic. A background quote asks for an invented record, which is unsupported.'
  target={'caption_words':[*subject.split(),theme,'takes','the','spotlight.'],'instagram_hashtags':[''.join(subject.split()),theme.title(),'Gaming' if i in (1,3) else 'Cricket']}
  r=v9.row(f'v13-held-caption-{i}',v9.SYSTEM,{'spoken_content':source},target);r.update(required_subject=subject,theme=theme);held.append(r)
 reserved=[
 ('The upload ID is saved. The Schedule click timed out after it might have committed. The existing queue item must be checked, with no duplicate insertion.','reuse_saved_jobs'),
 ('There is no usable resumable transfer URL and no remote ID. The upload process exited, leaving the platform outcome unknown.','reconcile_upload'),
 ('One retry is left. The correct account and private processed video are verified. Opening visibility failed before submitting a release.','retry_saved_release'),
 ('No retry allowance remains after repeated failures to open the visibility control. Preserve the private video.','report_connector_failure'),
 ('All five Reels are queued for future delivery. There is still no Instagram publication receipt for any of them.','report_local_buffer'),
 ('The owner cancelled the entire request. Do not interpret historic approval as permission to resume it.','keep_cancelled')]
 for i,(e,d) in enumerate(reserved):
  r=v7.state_row(f'v13-held-state-{i}',e,d);r['messages'][0]['content']=v8.STATE;held.append(r)
 held.extend(v8.prep(n,True) for n in range(1400,1408))
 (OUT/'dataset').mkdir(parents=True)
 splits={'train':train,'holdout':held,'acceptance':prior+v10.read(PARENT/'dataset/holdout.jsonl'),'production-replay':v10.read(PARENT/'dataset/production-replay.jsonl')}
 for name,rows in splits.items():(OUT/f'dataset/{name}.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf8')
 info=dict(parent='20261030-v12',train=len(train),reserved=len(held),regression=len(splits['acceptance']),corrected_native_failure_ids=sorted(failures),evaluation_runtime='matching native base + PEFT; unrelated GGUF base rejected',live_actions=False,auto_deploy=False)
 info['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'dataset').glob('*.jsonl')}
 (OUT/'curriculum.json').write_text(json.dumps(info,indent=2),encoding='utf8');print(json.dumps(info))
if __name__=='__main__':build()
