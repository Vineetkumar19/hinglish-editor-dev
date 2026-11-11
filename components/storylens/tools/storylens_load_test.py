"""Thirty authenticated fixture users against the real loopback/MySQL QA app."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import secrets
import statistics
import threading
import time
import requests
from hinglish_saas.store import Store
from hinglish_saas.security import digest

ROOT=Path(__file__).resolve().parents[1]
ORIGIN='http://127.0.0.1:8790'


def main():
    values=json.loads((ROOT/'output/storylens/qa-mysql/connection.private.json').read_text())
    store=Store(ROOT/'output/storylens/qa-mysql/app',values['database_url'])
    users=store.all("SELECT id FROM users WHERE email LIKE '%@example.test' AND email<>'operator@example.test' ORDER BY email LIMIT 30")
    if len(users)!=30:raise ValueError('Start the isolated --qa server with its 30 fixture customers first.')
    credentials=[]
    with store.connect(immediate=True) as db:
        for user in users:
            raw=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(raw),user['id'],csrf,time.time()+1200));credentials.append((raw,csrf))
    barrier=threading.Barrier(30)
    def run(index):
        raw,csrf=credentials[index];client=requests.Session();client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':csrf});client.cookies.set('he_session',raw)
        samples=[];errors=[];barrier.wait()
        for turn in range(20):
            started=time.perf_counter()
            try:
                if turn==2:
                    response=client.post(ORIGIN+'/api/reviews/mine',json={'display_name':'Load test fixture '+str(index),'rating':index%5+1,'title':'Synthetic capacity test','body':'This is an isolated automated load test review, not a genuine customer testimonial.'},timeout=20)
                else:response=client.get(ORIGIN+('/api/me','/api/reviews','/api/reviews/mine','/api/support/tickets')[turn%4],timeout=20)
                if response.status_code!=200:errors.append({'turn':turn,'status':response.status_code})
            except requests.RequestException:errors.append({'turn':turn,'status':'connection error'})
            samples.append((time.perf_counter()-started)*1000)
        client.close();return samples,errors
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=30) as pool:results=list(pool.map(run,range(30)))
    elapsed=time.perf_counter()-started;samples=sorted(x for result in results for x in result[0]);errors=[e for result in results for e in result[1]]
    with store.connect(immediate=True) as db:
        for raw,_ in credentials:db.execute('DELETE FROM sessions WHERE token=?',(digest(raw),))
    store.close()
    receipt={'database':'MySQL 8.0','concurrent_authenticated_customers':30,'requests':len(samples),'errors':errors,'elapsed_seconds':round(elapsed,2),'p50_ms':round(statistics.median(samples),1),'p95_ms':round(samples[int(len(samples)*.95)-1],1),'maximum_ms':round(max(samples),1),
        'scope':'Account, public review reads, private review reads, support ticket reads and concurrent review writes. Excludes GPU rendering and video uploads. Isolated synthetic records only.','passed':not errors}
    target=ROOT/'output/storylens/load-test.json';target.write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2))
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
