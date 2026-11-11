"""Read-only main-app activity check; never prints authentication tokens."""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/downloader-performance-20261103'
base = 'http://127.0.0.1:8765'
html = urllib.request.urlopen(base+'/downloader.html', timeout=5).read().decode()
token = re.search(r'data-token="([^"]+)"', html)[1]
def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(base+path,
        headers={'X-Hinglish-Token':token}), timeout=5))
jobs = get('/api/downloader/queue')['jobs']
chats = get('/api/assistant/history')
data = {'active_downloads':[{'id':j['id'],'status':j['status'],'stage':j.get('stage')} for j in jobs if j['status'] in ('running','queued')],
        'running_chats':[{'id':c.get('id'),'status':c.get('status'),'updated':c.get('updated')} for c in chats.get('chats',[]) if c.get('status')=='running']}
BASE.mkdir(parents=True, exist_ok=True)
(BASE/'preflight.json').write_text(json.dumps(data, indent=2))
print(json.dumps(data))
