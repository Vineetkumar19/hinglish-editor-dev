"""Activate checked publishing v14 and send exactly one normal assistant prompt."""
import json,time,shutil,pathlib,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'output/dc-five-v14-test'
MODEL='storylens-publishing:14b-v14-native'

def main():
    proof=json.loads((ROOT/'output/publishing-training/20261031-v14/native-provider-verification.json').read_text())
    assert proof['model']==MODEL and proof['checked']>=9 and proof['checked']==proof['passed']
    marker=OUT/'submission.json'
    if marker.exists():raise RuntimeError('Existing submission marker preserved; no second request sent')
    assert pathlib.Path('E:/documentry edit/final videos/final videos/Dc.mp4').is_file()
    bridge=json.loads((ROOT/'cache/app/bridge.json').read_text('utf-8-sig'))
    def call(ep,payload=None):
        req=urllib.request.Request(bridge['url']+ep,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Hinglish-Token':bridge['token']})
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
    config=ROOT/'config.models.local.json'
    shutil.copy2(config,OUT/'config.models.before-dc-v14.json')
    before=json.loads(config.read_text('utf-8-sig'));after=dict(before)
    after.update(publishing_model=MODEL,publishing_context_model=MODEL,
        publishing_context_basis='Exact native training base config: max_position_embeddings=40960; unmerged v14 adapter verified through native provider.',
        publishing_native_runtime={'enabled':True,'model':MODEL,'base':'C:/Ai Models/training/sound-qwen3-14b/base',
          'adapter':str(ROOT/'output/publishing-training/20261031-v14/adapter'),
          'python':'C:/Ai Models/runtimes/sound-training/Scripts/python.exe'})
    tmp=config.with_suffix('.json.v14-tmp');tmp.write_text(json.dumps(after,indent=2),encoding='utf8');tmp.replace(config)
    assert all(after[k]==v for k,v in before.items() if k not in ('publishing_model','publishing_context_model','publishing_context_basis','publishing_native_runtime'))
    session=call('/api/assistant/session',{})['id']
    prompt='Schedule long on 2026-11-01 at 19:00 IST on my cricket YouTube: "E:\\documentry edit\\final videos\\final videos\\Dc.mp4". Extract 5 Shorts; Shorts daily after the existing queue. Instagram every 1 minute for this test. No thumbnail.'
    record={'session':session,'model':MODEL,'prompt':prompt,'attempted_at':time.time(),'send_attempts':1,'url':bridge['url']+'/?chat='+session,'submitted':False,'submission_method':'normal assistant message endpoint; browser control unavailable'}
    marker.write_text(json.dumps(record,indent=2),encoding='utf8')
    # Do not repeat this call if its remote outcome becomes uncertain.
    response=call('/api/assistant/message',{'session':session,'profile':'cricket','message':prompt,'attachments':[]})
    record.update(submitted=True,response=response)
    marker.write_text(json.dumps(record,indent=2),encoding='utf8')
    request=json.loads((OUT/'request.json').read_text());request.update(state='submitted',submitted=True,session=session,model=MODEL)
    (OUT/'request.json').write_text(json.dumps(request,indent=2),encoding='utf8')
    print(json.dumps({'session':session,'url':record['url'],'submitted':True,'model':MODEL}),flush=True)

if __name__=='__main__':main()
