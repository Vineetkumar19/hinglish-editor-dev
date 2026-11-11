from pathlib import Path
import requests,re,json
W=Path(__file__).parent;url='http://127.0.0.1:8879';page=requests.get(url,timeout=5).text;token=json.loads(re.search(r'const TOKEN=("[^"]+")',page).group(1));h={'X-Inbox-Token':token};state=requests.get(url+'/api/state').json();cfg=state['config'];assert not cfg['gpt_enabled'] and not cfg['enabled']
r=requests.post(url+'/api/gpt',headers=h,json={});assert r.status_code==400
changed={**cfg,'mode':'manual','event':'India vs New Zealand','gpt_enabled':False,'enabled':False};r=requests.post(url+'/api/config',headers=h,json=changed);assert r.status_code==200,r.text
assert requests.get(url+'/api/state').json()['config']['event']=='India vs New Zealand'
requests.post(url+'/api/config',headers=h,json=cfg).raise_for_status()
x=next(i for i in state['items']if i['platform']=='Reddit' and i['media_url']);r=requests.post(url+'/api/download',headers=h,json={'id':x['id']},timeout=35);image=r.json();export={}
if r.status_code==200:
 requests.post(url+'/api/review',headers=h,json={'id':x['id'],'review':'keep'}).raise_for_status()
 try:export=requests.post(url+'/api/export',headers=h,json={}).json()
 finally:requests.post(url+'/api/review',headers=h,json={'id':x['id'],'review':x['review']}).raise_for_status()
 (Path(export['folder'])/'VALIDATION-NOTE.txt').write_text('Temporary technical keep/download/export check; original review state restored. Not owner creative approval.',encoding='utf8')
receipt={'candidate_count':len(state['items']),'gpt_off':True,'feeds_off':True,'gpt_run_rejected_while_off':True,'manual_focus_saved_and_restored':True,'real_source_image_download':image,'export_test':export,'gpt_live_research_executed':False,'browser_ui':'Controls rendered/saved in Chrome; screenshot retained. Chrome connector later disconnected; no further UI actions attempted.'}
(W/'validation.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt,indent=2))
