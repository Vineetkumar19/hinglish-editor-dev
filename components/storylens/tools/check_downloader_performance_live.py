"""Small real main-app YouTube check; no full 4K transfer or native import."""
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/downloader-performance-20261103'
SAVED = BASE/'Saved video'; SAVED.mkdir(parents=True, exist_ok=True)
url = 'http://127.0.0.1:8765'
def call(path, payload=None, token=None):
    return json.load(urllib.request.urlopen(urllib.request.Request(url+path,
        data=json.dumps(payload).encode() if payload else None,
        headers={'Content-Type':'application/json', **({'X-Hinglish-Token':token} if token else {})}), timeout=20))
health = call('/api/health')
assert 'downloader_transfer_v2' in health['capabilities']
html = urllib.request.urlopen(url+'/downloader.html', timeout=5).read().decode()
token = re.search(r'data-token="([^"]+)"', html)[1]
job = call('/api/downloader/start', {'url':'https://youtu.be/R7UfRy2MDvo','quality':'720','mode':'video',
    'start_time':'0:01','end_time':'0:03','destination':str(SAVED),
    'submission_id':'downloader-performance-20261103-live'}, token)
print(json.dumps({'id':job['id'],'status':job['status']}), flush=True)
deadline = time.monotonic()+180
last = None
while job['status'] in ('queued','running') and time.monotonic()<deadline:
    time.sleep(1)
    job = call('/api/downloader/job?id='+job['id'], token=token)
    if job.get('stage') != last:
        print(json.dumps({'status':job['status'],'stage':job.get('stage')}), flush=True)
        last = job.get('stage')
(BASE/'main-live-result.json').write_text(json.dumps(job, indent=2))
assert job['status']=='complete', job.get('error')
assert abs(job['result']['assets']['video']['duration']-2)<.1
assert Path(job['result']['assets']['video']['saved_path']).is_file()
print(json.dumps({'status':job['status'],'timings':job.get('timings'),
                  'resolution':[job['result']['assets']['video']['width'],job['result']['assets']['video']['height']]}), flush=True)
