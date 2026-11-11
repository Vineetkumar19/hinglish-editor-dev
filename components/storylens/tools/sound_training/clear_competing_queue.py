"""One-shot owner-authorized cancellation of current competing app work.

Preserves outputs and all remote posts/schedules. No new publishing work starts.
"""
from pathlib import Path
import sys,json,sqlite3,time
from types import SimpleNamespace
import requests
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
def main():
    bridge=json.loads((ROOT/'cache/app/bridge.json').read_text(encoding='utf-8'))
    session=requests.Session();session.trust_env=False;session.headers['X-Hinglish-Token']=bridge['token']
    receipts={'authorization':'Owner requested clearing other queued GPU work for sound training, 30 October 2026','assistant_stops':[],'preparation_cancellations':[],'remote_posts_changed':False}
    for path in (ROOT/'cache/assistant').glob('*.json'):
        value=json.loads(path.read_text(encoding='utf-8'));phase=(value.get('pipeline') or {}).get('phase')
        if value.get('status') in ('planning','running','transcribing') or phase in ('waiting_retry','waiting_executor'):
            response=session.post(bridge['url']+'/api/assistant/stop',json={'session':value['id']},timeout=20)
            response.raise_for_status();result=response.json()
            receipts['assistant_stops'].append(dict(id=value['id'],status=result.get('status'),stop=result.get('stop')))
    from hinglish_publish.prepare_post import PreparePost
    engine=PreparePost(SimpleNamespace(root=ROOT))
    with engine.db() as db:active=[json.loads(row[0]) for row in db.execute('SELECT data FROM preparations')]
    for row in active:
        if row.get('status') not in ('working','queued','cancelling'):continue
        immediate=not any(row.get('jobs_by_platform',{}).values())
        result=engine.cancel(row['id'],row['profile'],immediate=immediate)
        receipts['preparation_cancellations'].append(dict(id=row['id'],profile=row['profile'],immediate=immediate,status=result['status']))
    receipts['time']=time.time()
    out=ROOT/'output/sound-training/20261030-revision2/queue-cancellation.json'
    out.write_text(json.dumps(receipts,indent=2),encoding='utf-8');print(json.dumps(receipts))
if __name__=='__main__':main()
