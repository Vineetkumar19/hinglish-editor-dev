"""Run the real caption worker on a copied failed request, without touching AE."""
import argparse,json,sys,time,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from hinglish_app.caption_native_timing import execute
from hinglish_app.caption_persistence import save
p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
if len(a.source)!=32 or any(c not in '0123456789abcdef' for c in a.source):raise ValueError('Invalid source request')
original=root/'output/captions/ae-speech'/a.source
key=uuid.uuid4().hex;folder=original.parent/key;folder.mkdir()
request=json.loads((original/'request.json').read_text('utf8'));save(folder/'request.json',request)
evidence=root/'output/caption-recording-recovery-20261029';evidence.mkdir(exist_ok=True)
receipt={'source_job':a.source,'test_job':key,'ae_untouched':True,'started':time.time(),'status':'running'}
save(evidence/'latest-check.json',receipt);print(json.dumps(receipt),flush=True);begin=time.monotonic()
try:
    execute(root,key)
    project=json.loads((folder/'caption-project.json').read_text('utf8'))
    receipt.update(status='complete',seconds=time.monotonic()-begin,transcription=project['transcription'])
except Exception as error:
    receipt.update(status='failed',seconds=time.monotonic()-begin,error=str(error))
    save(folder/'status.json',{'id':key,'status':'failed','stage':'Speech timing stopped','error':{'details':str(error)}})
    raise
finally:
    save(evidence/'latest-check.json',receipt);save(evidence/(key+'.json'),receipt);print(json.dumps(receipt),flush=True)
