"""Read-only local-model replay of the failed campaign request. Never renders/posts."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    from hinglish_app.server import AppState
    from hinglish_app.assistant_campaign import interpret
    from hinglish_cut.model_storage import configure
    configure(ROOT)
    prior=json.loads((ROOT/'cache/assistant/b4969419cc3f476f.json').read_text('utf-8'))
    text=next(m['text'] for m in reversed(prior['messages']) if m['role']=='user')
    state=AppState(ROOT)
    assistant=state.assistant
    session=assistant.create()['id']
    assistant._update(session,profile='cricket')
    result,evidence=interpret(assistant,session,text,print)
    receipt={'session':session,'request':text,'model':assistant.snapshot(session)['brain'],
             'plan':result,'folder_evidence':evidence['folders'],'side_effects':'none; interpret only'}
    target=ROOT/'output/campaigns/chat-routing-local-model-proof.json'
    target.write_text(json.dumps(receipt,indent=2,ensure_ascii=False),'utf-8')
    print(json.dumps(receipt,indent=2,ensure_ascii=False))
