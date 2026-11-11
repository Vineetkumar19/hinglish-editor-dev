"""Evaluate recorded user turns with local inference. No chat submission or execution."""
import json
from datetime import datetime
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    from hinglish_app.assistant_campaign import active_turns,context,plan_with_model,requested
    from hinglish_publish.service import Publisher
    from hinglish_publish.campaign import RecordedBrain,IST,save
    from hinglish_visuals.brain import open_brain
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_storage import configure
    configure(ROOT)
    snapshot=json.loads((ROOT/'cache/assistant/b4969419cc3f476f.json').read_text('utf-8'))
    users=[m['text'] for m in snapshot['messages'] if m['role']=='user']
    start=max(i for i,text in enumerate(users) if requested(text))
    turns=users[start:]
    readonly=SimpleNamespace(root=ROOT,state=SimpleNamespace(publisher=Publisher(ROOT)))
    folder=ROOT/'output/campaigns/dialogue-regression'
    folder.mkdir(parents=True,exist_ok=True)
    receipts=[]
    with gpu_lock(ROOT):
        brain=open_brain(ROOT,'ollama',progress=print)
        try:
            recorder=RecordedBrain(brain,folder)
            for end in range(1,len(turns)+1):
                active=active_turns({'messages':[{'role':'user','text':t} for t in turns[:end]]},turns[end-1])
                evidence=context(readonly,'\n'.join(active))
                answer=plan_with_model(recorder,active,evidence,datetime.now(IST).isoformat(),print)
                passed=(answer['action']=='prepare' and answer['targets']==['gaming']
                        and answer['clock']=='18:00' and answer['count']==7
                        and answer['max_seconds_exclusive']==60 and answer['source_topic']=='cricket'
                        and answer['first_date']=='2026-10-20' and answer['different_source']
                        and not answer['question'])
                receipts.append({'last_user_turn':active[-1],'model':brain.name,'answer':answer,'passed':passed})
                save(folder/'results.json',{'read_only':True,'live_chat_submitted':False,'cases':receipts})
                print(json.dumps(receipts[-1],ensure_ascii=False),flush=True)
        finally:
            brain.close()
    if not receipts or not all(r['passed'] for r in receipts):
        raise SystemExit('Local dialogue regression failed; no task was executed.')
