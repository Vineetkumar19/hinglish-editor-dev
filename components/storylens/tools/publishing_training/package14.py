"""Package and independently check the exact v14 export; no platform actions."""
import os,sys,json,subprocess,hashlib,time,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/publishing-training/20261031-v14'
Q8=Path('C:/Ai Models/training/publishing-v14-export/publishing-v14-Q8_0.gguf')
Q4=OUT/'publishing-v14-Q4_K_M.gguf'
MODEL='storylens-publishing:14b-v14'

def main():
    from tools.publishing_training.base_identity_check import compare
    status=json.loads((OUT/'export-status.json').read_text())
    assert status['stage']=='exported_q8' and status['merged_tensors']==160
    assert status['complete']==443 and Q8.stat().st_size==status['bytes']
    identity=compare(Q8)
    assert all(r['exact_equal'] for r in identity), 'Matching-base identity check failed'
    (OUT/'export-base-identity.json').write_text(json.dumps(identity,indent=2))
    if Q4.exists():raise RuntimeError('Preserve existing quantized export; explicit continuation required')
    with (OUT/'quantize-v14.log').open('w',encoding='utf8') as log:
        subprocess.run([str(ROOT/'tools/llama/b11011/llama-quantize.exe'),'--allow-requantize',str(Q8),str(Q4),'Q4_K_M','2'],stdout=log,stderr=subprocess.STDOUT,check=True)
    assert Q4.stat().st_size>8_000_000_000
    identity=compare(Q4)
    assert all(r['exact_equal'] for r in identity)
    with Q4.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    # Remove only this newly generated, verified disposable conversion intermediate.
    assert Q8.resolve().parent==Path('C:/Ai Models/training/publishing-v14-export').resolve()
    Q8.unlink()
    modelfile=OUT/'Modelfile-v14'
    modelfile.write_text(f'FROM "{Q4.as_posix()}"\nPARAMETER num_ctx 40960\nPARAMETER num_gpu 41\n',encoding='utf8')
    with (OUT/'register-v14.log').open('w',encoding='utf8') as log:
        subprocess.run(['ollama','create',MODEL,'-f',str(modelfile)],stdout=log,stderr=subprocess.STDOUT,check=True)
    import requests
    session=requests.Session();session.trust_env=False
    response=session.post('http://127.0.0.1:11434/api/show',json={'model':MODEL},timeout=30);response.raise_for_status();show=response.json()
    assert show['model_info']['qwen3.context_length']==40960
    (OUT/'ollama-show-v14.json').write_text(json.dumps(show,indent=2))
    from tools.publishing_training import evaluate,revision9
    evaluate.OUT=OUT;score=revision9.scoring(evaluate.score)
    cases=[]
    for split in ['holdout','production-replay']:
        cases += [dict(json.loads(s),test_split=split) for s in (OUT/f'dataset/{split}.jsonl').read_text('utf8').splitlines()]
    seen={}
    for s in (OUT/'dataset/acceptance.jsonl').read_text('utf8').splitlines():
        r=json.loads(s);family=r['family']
        if family!='instagram_copy' and seen.get(family,0)<4:
            cases.append(dict(r,test_split='regression'));seen[family]=seen.get(family,0)+1
    results=[]
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import release_ollama
    with gpu_lock(ROOT):
        release_ollama(ROOT)
        for row in cases:
            body={'model':MODEL,'messages':row['messages'][:-1],'stream':False,'think':False,
                  'keep_alive':'30s','options':{'temperature':0,'seed':3407,'num_predict':700,'num_ctx':8192,'num_gpu':41,'num_thread':2}}
            started=time.monotonic()
            response=session.post('http://127.0.0.1:11434/api/chat',json=body,timeout=600);response.raise_for_status();data=response.json()
            content=data['message']['content']
            try:answer=json.loads(content)
            except ValueError:answer=None
            results.append({'id':row['id'],'split':row['test_split'],'content':content,'passed':bool(score(row,answer)),'elapsed':time.monotonic()-started,'done_reason':data.get('done_reason')})
            (OUT/'packaged-v14-checks.json').write_text(json.dumps(results,indent=2),encoding='utf8')
            print(json.dumps({'checked':len(results),'total':len(cases),'passed':sum(x['passed'] for x in results)}),flush=True)
        release_ollama(ROOT)
    receipt={'model':MODEL,'sha256':digest,'base_identity':identity,'checked':len(results),'passed':sum(x['passed'] for x in results),'serving_config_changed':False,'new_posts':0}
    (OUT/'packaging-v14.json').write_text(json.dumps(receipt,indent=2))
    if any(not x['passed'] for x in results):raise RuntimeError('Packaged-model checks failed; candidate not activated')
    blob=Path('C:/Ai Models/ollama/blobs')/('sha256-'+digest)
    with blob.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest
    # Installed Ollama blob is verified; avoid retaining a second 9 GB copy on A:.
    assert Q4.resolve().parent==OUT.resolve()
    Q4.unlink()
    print('Packaged v14 checks passed; ready for scoped activation.',flush=True)

if __name__=='__main__':main()
