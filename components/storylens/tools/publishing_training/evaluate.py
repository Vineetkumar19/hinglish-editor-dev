"""Real base/adapter inference on held-out cases; no platform actions."""
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.publishing_training.curriculum import OUT, LESSONS
BASE=Path('C:/Ai Models/ollama/blobs/sha256-500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0')
DATASET='holdout'
PREFIX=''
REPAIR_COPY=False
PRODUCTION_RECOVERY=False
CONTEXT_SIZE=4096
COMPARE_BASE=True

def save(name,value):
    (OUT/(PREFIX+name)).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf8')

def schema(family, row=None):
    if row and row.get('response_schema'):return row['response_schema']
    string={'type':'string'}
    strings={'type':'array','items':string}
    fields=({'profile':string,'video':string,'thumbnail':string,'count':{'type':'integer'},'long_release':string,'shorts_release':string,'steps':strings}
            if family=='plan' else {'decision':{'type':'string','enum':sorted({r[2] for r in LESSONS})},'message':string} if family=='state'
            else {'title':string,'description':string,'tags':strings,'caption_words':strings,'instagram_hashtags':strings})
    return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}

def score(row,answer):
    target=json.loads(row['messages'][-1]['content'])
    if not isinstance(answer,dict) or set(answer)!=set(target):return False
    if row['family'] in ('plan','preparation'):return answer==target
    if row['family']=='state':
        if OUT.name in {'20261030-v7','20261030-v8'}:return answer==target
        valid=answer['decision']==target['decision'] and bool(answer['message'].strip())
        if OUT.name=='20261030-v6' and answer['decision'] in {'retry_saved_release','report_local_buffer','reuse_saved_jobs'}:
            # A correct enum with contradictory prose is not a passing answer.
            clauses=re.split(r'[.;!]',answer['message'].lower())
            for clause in clauses:
                if re.search(r'\b(?:create|start|send|make)\b.*\b(?:upload|queue)\b',clause) and not re.search(r'\b(?:not|never|no|without)\b',clause):return False
        return valid
    from hinglish_publish.prepare_post_source import instagram_from_words
    from hinglish_publish import metadata
    try:
        caption=instagram_from_words(answer)
        metadata.validate({**answer,'instagram_caption':caption})
        if OUT.name in {'20261030-v5','20261030-v6'}:
            words=answer.get('caption_words',[])
            if not words or words[-1].lower().strip('.,!?') in {'in','for','with','and','the','a','an','of','to','or'}:return False
            if re.search(r'no (?:dates|scores|records|outcomes|statistics)|not (?:mentioned|stated|provided)',answer['description'],re.I):return False
        team=target['tags'][0]
        return (team.lower() in (answer['title']+' '+answer['description']).lower()
            and 3<=len(re.findall(r'#[A-Za-z][A-Za-z0-9_]*',answer['description']))<=5
            and not re.search(r'https?://|\b(?:record|champion|trophies|202\d)\b',caption,re.I))
    except (ValueError,TypeError,KeyError):return False

def main():
    from tools.sound_training import export_adapter
    status=json.loads((OUT/'status.json').read_text())
    if status['stage']!='adapter_trained_awaiting_review':raise RuntimeError('Wait for actual training completion')
    from tools.publishing_training.base_identity_check import compare
    identity=compare(BASE)
    save('base-compatibility.json',dict(sampled_normalizations=identity,full_weight_identity_verified=False))
    if any(not item['exact_equal'] for item in identity):
        raise RuntimeError('The evaluation GGUF has different normalization weights from the training base. Do not apply this LoRA blindly. Evaluate on the matching native base or a verified compatible export.')
    export_adapter.OUT=OUT;export_adapter.main()
    import requests
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import release_ollama
    cases=[json.loads(line) for line in (OUT/f'dataset/{DATASET}.jsonl').read_text('utf8').splitlines()]
    results=[];endpoint='http://127.0.0.1:18932'
    session=requests.Session();session.trust_env=False
    key=secrets.token_urlsafe(24);session.headers['Authorization']='Bearer '+key
    save('evaluation-status.json',dict(stage='waiting_for_shared_gpu_slot',cases=len(cases)))
    with gpu_lock(ROOT):
        release_ollama(ROOT)
        with socket.socket() as check:check.bind(('127.0.0.1',18932))
        exe=ROOT/'tools/sound_training/llama-gpu-runtime/llama-server.exe'
        env=dict(os.environ);env['PATH']='C:/Ai Models/runtimes/sound-training/Lib/site-packages/torch/lib'+os.pathsep+env.get('PATH','')
        cmd=[str(exe),'-m',str(BASE),'--lora',str(OUT/'adapter.gguf'),'--host','127.0.0.1','--port','18932',
             '--api-key',key,'-ngl','99','-c',str(CONTEXT_SIZE),'-np','1','-t','2','-tb','2','-fa','on','-ctk','q8_0','-ctv','q8_0',
             '--reasoning-budget','0','--no-webui']
        with (OUT/'evaluation-server.log').open('w',encoding='utf8') as log:
            proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                started=time.monotonic()
                while True:
                    if proc.poll() is not None:raise RuntimeError('Isolated evaluation server exited')
                    try:
                        if session.get(endpoint+'/health',timeout=2).status_code==200:break
                    except requests.RequestException:pass
                    if time.monotonic()-started>180:raise RuntimeError('Evaluation server not ready')
                    time.sleep(1)
                response=session.get(endpoint+'/lora-adapters',timeout=10);response.raise_for_status()
                save('loaded-adapters.json',response.json());identity=response.json()[0]['id']
                for row in cases:
                    result=dict(id=row['id'],family=row['family'])
                    for label,scale in ([('base',0.0),('adapter',1.0)] if COMPARE_BASE else [('adapter',1.0)]):
                        update=session.post(endpoint+'/lora-adapters',json=[dict(id=identity,scale=scale)],timeout=10);update.raise_for_status()
                        request=dict(messages=row['messages'][:-1],temperature=0,seed=3407,max_tokens=700,cache_prompt=False,
                            chat_template_kwargs={'enable_thinking':False},
                            response_format={'type':'json_schema','json_schema':{'name':'publishing_decision','strict':True,'schema':schema(row['family'],row)}})
                        response=session.post(endpoint+'/v1/chat/completions',json=request,timeout=150);response.raise_for_status();data=response.json()
                        choice=data['choices'][0];content=choice['message'].get('content','')
                        try:parsed=json.loads(content)
                        except ValueError:parsed=None
                        result[label]=dict(passed=choice.get('finish_reason')=='stop' and score(row,parsed),content=content,
                            finish_reason=choice.get('finish_reason'),usage=data.get('usage'),timings=data.get('timings'))
                        result[label]['first_pass']=result[label]['passed']
                        if REPAIR_COPY and row['family']=='paired_copy' and not result[label]['passed']:
                            result[label]['first_content']=content
                            result[label]['repair_attempts']=[]
                            for _ in range(2):
                                from hinglish_publish.prepare_post_source import instagram_from_words
                                try:
                                    instagram_from_words(parsed or {})
                                    correction='Revise only the rejected copy: stay within the supplied subject, keep a complete caption under 11 words and 3-5 separate hashtags. Do not include diagnostic prose.'
                                except (ValueError,TypeError,AttributeError) as error:correction=str(error)
                                original=json.loads(row['messages'][1]['content'])
                                repair_data={**original,'correction':correction,'rejected_draft':parsed}
                                repair_request={**request,'messages':[row['messages'][0],dict(role='user',content=json.dumps(repair_data))]}
                                response=session.post(endpoint+'/v1/chat/completions',json=repair_request,timeout=150);response.raise_for_status()
                                repaired=response.json();choice=repaired['choices'][0];content=choice['message'].get('content','')
                                try:parsed=json.loads(content)
                                except ValueError:parsed=None
                                passed=choice.get('finish_reason')=='stop' and score(row,parsed)
                                result[label]['repair_attempts'].append(dict(content=content,passed=passed,correction=correction,usage=repaired.get('usage')))
                                result[label].update(content=content,passed=passed)
                                if passed:break
                        if PRODUCTION_RECOVERY and row['family']=='paired_copy' and not result[label]['passed']:
                            from hinglish_publish.prepare_post_source import recover_instagram
                            original=json.loads(row['messages'][1]['content'])
                            result[label]['first_content']=content
                            calls=[]
                            class RecoveryBrain:
                                name='isolated-publishing-evaluation'
                                def json(self,system,payload,spec,**options):
                                    args={**request,'max_tokens':options.get('max_tokens',700),
                                        'messages':[dict(role='system',content=system),dict(role='user',content=json.dumps(payload))],
                                        'response_format':{'type':'json_schema','json_schema':{'name':'caption_recovery','strict':True,'schema':spec}}}
                                    reply=session.post(endpoint+'/v1/chat/completions',json=args,timeout=150);reply.raise_for_status()
                                    body=reply.json();text=body['choices'][0]['message'].get('content','')
                                    calls.append(dict(system=system,input=payload,content=text,usage=body.get('usage')))
                                    return json.loads(text)
                            try:
                                repaired=recover_instagram(RecoveryBrain(),parsed or {},original.get('spoken_content',''),
                                    {'profile':original.get('profile')},{},lambda _:None)
                                words=repaired['instagram_caption'].split('\n\n')[0].split()
                                parsed={**(parsed or {}),'caption_words':words,'instagram_hashtags':repaired['tags']}
                                result[label].update(content=json.dumps(parsed),passed=score(row,parsed))
                            except (ValueError,TypeError,KeyError) as error:
                                result[label]['recovery_error']=str(error)
                            result[label]['production_recovery']=dict(function='hinglish_publish.prepare_post_source.recover_instagram',calls=calls)
                    results.append(result);save('heldout-comparison.json',results)
                    save('evaluation-status.json',dict(stage='evaluating',complete=len(results),total=len(cases)))
                summary=dict(total=len(results),base_compared=COMPARE_BASE,
                    base_passed=sum(r['base']['passed'] for r in results) if COMPARE_BASE else None,
                    adapter_passed=sum(r['adapter']['passed'] for r in results),
                    base_first_passed=sum(r['base']['first_pass'] for r in results) if COMPARE_BASE else None,
                    adapter_first_passed=sum(r['adapter']['first_pass'] for r in results),
                    bounded_copy_repair=REPAIR_COPY,
                    production_caption_recovery=PRODUCTION_RECOVERY,
                    regressions=[r['id'] for r in results if COMPARE_BASE and r['base']['passed'] and not r['adapter']['passed']],
                    adapter_failures=[r['id'] for r in results if not r['adapter']['passed']],
                    live_platform_acceptance=False,serving_model_changed=False)
                summary['decision_gate_passed']=summary['adapter_passed']==summary['total'] and not summary['regressions']
                save('evaluation-summary.json',summary);save('evaluation-status.json',dict(stage='complete',**summary));print(json.dumps(summary))
            finally:
                if proc.poll() is None:proc.terminate();proc.wait(timeout=30)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='20261030-v1')
    parser.add_argument('--dataset',choices=['holdout','acceptance'],default='holdout')
    parser.add_argument('--repair-copy',action='store_true')
    parser.add_argument('--production-caption-recovery',action='store_true')
    args=parser.parse_args();home=ROOT/'output/publishing-training';OUT=(home/args.run).resolve()
    if OUT.parent!=home.resolve():raise ValueError('Use a direct publishing-training run folder')
    DATASET=args.dataset;PREFIX='' if DATASET=='holdout' else 'acceptance-'
    REPAIR_COPY=args.repair_copy
    if REPAIR_COPY:PREFIX='repair-'+PREFIX
    PRODUCTION_RECOVERY=args.production_caption_recovery
    if PRODUCTION_RECOVERY:
        if REPAIR_COPY:raise ValueError('Choose one recovery evaluation mode')
        PREFIX='production-recovery-'+PREFIX
    main()
