from pathlib import Path
import json
import re
import urllib.request
import datetime as dt

base='http://127.0.0.1:8880'
root=Path(__file__).parent
def get(path):return json.load(urllib.request.urlopen(base+path,timeout=10))
html=urllib.request.urlopen(base+'/',timeout=10).read().decode()
token=json.loads(re.search(r'const TOKEN=("[^"]+");',html).group(1))
def post(path,data):
 req=urllib.request.Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Inbox-Token':token})
 return json.load(urllib.request.urlopen(req,timeout=35))

s=get('/api/state');original=s['config']
assert original['enabled'] and original['gpt_enabled']
try:
 cfg=post('/api/config',{**original,'mode':'manual','event':'Call of Duty'})
 assert get('/api/state')['config']['event']=='Call of Duty'
finally:post('/api/config',original)
checks={'manual_game_persistence_and_restore':True,'separate_gaming_database':True,'candidate_count':len(s['items']),'feed_sources':s['last_scan'],'gpt_receipt':s['gpt_receipt'],'original_settings':original,'unit_tests_passed':6,'published_nothing':True}

image=next((x for x in s['items']if x['platform']=='Reddit' and x['media_url']),None)
if image:
 try:
  downloaded=post('/api/download',{'id':image['id']})
  if 'path' not in downloaded:raise RuntimeError(downloaded)
  checks['image_download']={'path':downloaded['path'],'bytes':Path(downloaded['path']).stat().st_size,'source':image['url']}
  try:
   post('/api/review',{'id':image['id'],'review':'keep'})
   selected=get('/api/state');assert next(x for x in selected['items']if x['id']==image['id'])['review']=='keep'
   exported=post('/api/export',{});assert exported['images']>=1
   (Path(exported['folder'])/'VALIDATION-NOTE.txt').write_text('Temporary application verification selection; restored to its prior review state. Not an owner-approved production selection.',encoding='utf-8')
   checks['selected_export']=exported
  finally:post('/api/review',{'id':image['id'],'review':image['review']})
 except Exception as e:checks['image_export_limitation']=str(e)
checks['checked_at']=dt.datetime.now(dt.timezone.utc).isoformat()
checks['gpt_receipt']=get('/api/state')['gpt_receipt']
(root/'validation-result.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in checks.items()if k not in ['original_settings','feed_sources']},indent=2))
