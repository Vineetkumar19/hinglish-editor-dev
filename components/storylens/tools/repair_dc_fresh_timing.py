"""Migrate this test's unsubmitted slots from its exact original owner request.

No uploads, browser actions, authorizations, or new jobs are created here.
Run again only to cover this flow's later-created Instagram buffer records.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from hinglish_publish.store import Store
from hinglish_publish.workflow_timing import parse_request
from hinglish_app.durable_json import write

ROOT = Path(__file__).resolve().parents[1]
SESSION = '9e79565cba2a4f05'
FLOW = '7e037afcfd2243f1a895b69cf6f7bc26'


def main():
    session=json.loads((ROOT/'cache/assistant'/f'{SESSION}.json').read_text())
    flow=json.loads((ROOT/'output/publisher-prepare-post/workflows'/f'{FLOW}.json').read_text())
    assert session['upload_workflow']['id']==FLOW and flow['assistant_plan']['session']==SESSION
    original=next(m for m in session['messages'] if m['id']==flow['assistant_plan']['message_id'] and m['role']=='user')
    timing=parse_request(original['text'])
    assert timing=={'long_at':'2026-11-01T19:00:00+05:30','instagram_interval':60}
    receipt=ROOT/'output/dc-five-v8-fresh-test/timing-repair.json'
    saved=json.loads(receipt.read_text()) if receipt.exists() else {'session':SESSION,'flow':FLOW,'timing':timing,'changes':[]}
    store=Store(ROOT)
    for key in flow['jobs'].get('long',[]):
        job=store.get(key)
        assert job['prepare_post_id']==flow['preparations']['long'] and job['fingerprint']==flow['source']['sha256']
        assert job['account_id']==flow['intent']['accounts']['youtube'] and job['kind']=='long'
        due=datetime.fromisoformat(timing['long_at']).timestamp()
        if job['due']!=due:
            assert job['status'] in ('ready','uploading','uploaded_private') and not job.get('browser_schedule_id')
            assert not job.get('remote',{}).get('publish_at')
            store.change(key,expected_status=(job['status'],),due=due)
            store.event(key,'Timing parser repair: applied original owner-requested 1 November 2026 19:00 IST before schedule submission.')
            saved['changes'].append({'job':key,'before':job['due'],'after':due,'time':time.time()})
    keys=flow['jobs'].get('instagram',[])
    if keys and not saved.get('instagram_slots_applied'):
        assert len(keys)==5 and flow['intent']['count']==5
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=[store.decode(db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()) for key in keys]
            for job in rows:
                assert job['prepare_post_id']==flow['preparations']['shorts'] and job['platform']=='instagram'
                assert job['account_id']==flow['intent']['accounts']['instagram'] and job['profile']=='cricket'
                assert job['status'] in ('ready','scheduled') and not job.get('remote',{}).get('id') and not job.get('browser_task_id')
            start=time.time()
            for n,job in enumerate(rows,1):
                due=start+60*n
                db.execute('UPDATE jobs SET due=? WHERE id=?',(due,job['id']))
                db.execute('INSERT INTO events(created,job_id,message) VALUES(?,?,?)',(time.time(),job['id'],'Timing parser repair: original one-minute Instagram test interval restored before delivery.'))
                saved['changes'].append({'job':job['id'],'before':job['due'],'after':due,'time':time.time()})
            saved['instagram_slots_applied']=True
    saved['checked']=time.time();write(receipt,saved)
    print(json.dumps({'long_corrected':any(x['job'] in flow['jobs'].get('long',[]) for x in saved['changes']),'instagram_slots_applied':saved.get('instagram_slots_applied',False),'instagram_jobs_created':len(keys)}))


if __name__=='__main__':main()
