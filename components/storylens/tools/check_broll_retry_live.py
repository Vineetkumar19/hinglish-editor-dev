"""One explicit normal-app saved-progress continuation; never auto-submit twice."""
from pathlib import Path
import hashlib
import json
import time
from urllib.request import urlopen
from tools.check_editor_panel_live import api

ROOT=Path(__file__).resolve().parents[1]
RECEIPT=ROOT/'output/plugin-validation/broll-retry-live-request.json'

def save(value):
    RECEIPT.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    if RECEIPT.exists():
        raise SystemExit('A continuation intent already exists. Inspect its outcome; do not resubmit.')
    previous=json.loads((ROOT/'output/plugin-validation/broll-local-runtime-request.json').read_text('utf-8'))
    payload=previous['request']
    source=Path(payload['input_path'])
    assert hashlib.sha256(source.read_bytes()).hexdigest()==previous['source_sha256']
    chats=api('/api/assistant/history')['chats'];photos=api('/api/photos/history')['jobs']
    assert not [x for x in chats if x['status'] in ('working','running','queued')]
    assert not [x for x in photos if x['status'] not in ('done','failed','cancelled','archived','interrupted')]
    import msvcrt
    with (ROOT/'cache/app/gpu-work.lock').open('r+b') as stream:
        msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
    def local(path):
        with urlopen('http://127.0.0.1:11434'+path,timeout=10) as response:return json.load(response)
    status=api('/api/jobs/7c03db6fbd88')
    assert status['status']=='failed'
    data={'request':payload,'source_sha256':previous['source_sha256'],'prior_job_id':status['id'],
          'prior_job_status':'failed','requested_at':time.time(),'submission_state':'intent_saved_not_submitted',
          'provider':{'endpoint':'http://127.0.0.1:11434','version':local('/api/version'),
                      'loaded_observation':local('/api/ps')},
          'installed_model_digests':[{k:m.get(k) for k in ('name','digest','size')} for m in local('/api/tags')['models']],
          'code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
              'hinglish_broll/keywords.py','hinglish_broll/producer_contract.py','hinglish_broll/candidate_manifest.py')},
          'interventions':['Codex submits identical authorized normal /api/jobs request, not assistant-chosen tool arguments.',
                           'Resume uses saved model plan/search/verdict/media lineage where valid; not fresh semantic acceptance.',
                           'One previous explicit operator choice washingmachine remains separate native test evidence.'],
          'assistant_dispatch_acceptance':False,'semantic_acceptance':False,'native_acceptance':False}
    save(data)
    job=api('/api/jobs',payload)
    data.update(job_id=job['id'],submitted_at=time.time(),submission_state='submitted',initial_status=job['status'])
    save(data)
    print(json.dumps({k:data[k] for k in ('job_id','prior_job_id','initial_status','submitted_at')}))

if __name__=='__main__':main()
