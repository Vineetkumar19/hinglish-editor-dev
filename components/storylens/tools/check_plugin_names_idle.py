from pathlib import Path
import json,urllib.request,urllib.error
root=Path(__file__).resolve().parents[1];base='http://127.0.0.1:8765';out=root/'output/plugin-folder-names'
def get(path,token=None):
    request=urllib.request.Request(base+path,headers={'X-Hinglish-Token':token} if token else {})
    with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)
token=get('/api/bridge')['token'];terminal={'done','complete','completed','failed','cancelled','canceled','interrupted','archived','needs_review','idle','stopped'};active={};counts={}
for kind,path,key in [('photos','/api/photos/history','jobs'),('downloads','/api/downloader/history','jobs'),('chats','/api/assistant/history','chats')]:
    rows=get(path,token)[key];active[kind]=[{'id':r.get('id'),'status':r.get('status')} for r in rows if r.get('status') not in terminal];counts[kind]=len(rows)
active['editing']=[];count=0
for folder in (root/'cache/app/jobs').iterdir():
    if not folder.is_dir():continue
    try:row=get('/api/jobs/'+folder.name,token)
    except urllib.error.HTTPError as error:
        if error.code==404:continue
        raise
    count+=1
    if row.get('status') not in terminal:active['editing'].append({'id':folder.name,'status':row.get('status')})
counts['editing']=count
(out/'idle-before-reload.json').write_text(json.dumps({'active':active,'checked_counts':counts},indent=2))
if any(active.values()):raise SystemExit('Active Storylens work found. No reload allowed.')
print('Storylens idle; no active photo/download/chat/editing jobs.')
