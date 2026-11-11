"""Isolated real llama.cpp inference comparison. Never changes serving settings.

Same compact instruction/schema for base and adapter; no reference answers sent.
This checks actual GGUF adapter loading, not a rendered sound mix.
"""
from pathlib import Path
import json,sys,time,subprocess,os,requests,socket,secrets,re
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
OUT=ROOT/'output/sound-training/20261030-revision2'
BASE=Path('C:/Ai Models/ollama/blobs/sha256-500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0')
FIELDS=('decision','timing','mix','uncertainty')
SCHEMA=dict(type='object',properties={k:dict(type='string') for k in FIELDS},required=list(FIELDS),additionalProperties=False)
def cuda_inventory_valid(text):return bool(re.search(r'CUDA\d+:.*NVIDIA',text,re.I))

def system_prompt(system):
    return system+' Return only JSON with '+', '.join(FIELDS)+'. Answer the requested question in at most 160 words total across the required fields. Do not list imagined observations. Use uncertainty for missing evidence.'

def variants(identity,compare_case_ids):
    return [('base',0.0),('adapter',1.0)] if compare_case_ids is None or identity in compare_case_ids else [('adapter',1.0)]
def request_body(system,question,identity,scale,reasoning_budget=0):
    if type(reasoning_budget) is not int or not 0<=reasoning_budget<=512:
        raise ValueError('Reasoning evaluation budget must be an integer from zero to 512')
    if reasoning_budget:system=system.replace('/no_think','')
    return dict(messages=[dict(role='system',content=system),dict(role='user',content=question)],
        temperature=0,seed=3407,max_tokens=384+reasoning_budget,cache_prompt=False,lora=[dict(id=identity,scale=scale)],
        chat_template_kwargs={'enable_thinking':bool(reasoning_budget)},
        response_format={'type':'json_schema','json_schema':{'name':'sound_decision','strict':True,'schema':SCHEMA}})
def check_response(response):
    choice=response['choices'][0];text=choice['message'].get('content','')
    try:parsed=json.loads(text)
    except (ValueError,TypeError):parsed=None
    complete=choice.get('finish_reason')=='stop' and isinstance(parsed,dict) and set(parsed)==set(FIELDS) and all(isinstance(v,str) and v.strip() for v in parsed.values())
    return dict(format_complete=bool(complete),finish_reason=choice.get('finish_reason'),text=text,parsed=parsed,
                usage=response.get('usage'),timings=response.get('timings'))
def save(name,data):(OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
def main(reasoning_budget=0,compare_case_ids=None,after_cases=None,context_tokens=4096):
    request_body('validation','validation',0,0,reasoning_budget)
    if type(context_tokens) is not int or not 2048<=context_tokens<=16384:raise ValueError('Use a bounded context for isolated inference')
    from revision import GATE,SYSTEM
    from hinglish_cut.gpu_lock import gpu_lock
    endpoint='http://127.0.0.1:18931';s=requests.Session();s.trust_env=False
    key=secrets.token_urlsafe(24);s.headers['Authorization']='Bearer '+key
    save('runtime-gate-status.json',dict(stage='waiting_for_shared_gpu_slot'))
    with gpu_lock(ROOT):
        from hinglish_cut.model_preferences import release_ollama
        release_ollama(ROOT)
        with socket.socket() as port_check:
            port_check.bind(('127.0.0.1',18931))
        executable=next((ROOT/'tools/sound_training/llama-gpu-runtime').rglob('llama-server.exe'))
        env=dict(os.environ);env['PATH']='C:/Ai Models/runtimes/sound-training/Lib/site-packages/torch/lib'+os.pathsep+env.get('PATH','')
        devices=subprocess.run([str(executable),'--list-devices'],env=env,capture_output=True,text=True,timeout=30)
        inventory=devices.stdout+devices.stderr
        save('runtime-device-inventory.json',dict(returncode=devices.returncode,output=inventory))
        if devices.returncode or not cuda_inventory_valid(inventory):raise RuntimeError('GPU backend unavailable; refused CPU model validation')
        command=[str(executable),'-m',str(BASE),'--lora',str(OUT/'adapter.gguf'),
          '--host','127.0.0.1','--port','18931','--api-key',key,'-ngl','99','-c',str(context_tokens),'-np','1','-t','2','-tb','2','-fa','on','-ctk','q8_0','-ctv','q8_0','--reasoning-budget',str(reasoning_budget),'--no-webui']
        with (OUT/'runtime-server.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            try:
                started=time.monotonic()
                while True:
                    if proc.poll() is not None:raise RuntimeError('Isolated inference server stopped; see runtime-server.log')
                    try:
                        r=s.get(endpoint+'/health',timeout=2)
                        if r.status_code==200:break
                    except requests.RequestException:pass
                    if time.monotonic()-started>180:raise RuntimeError('Isolated inference server did not become ready')
                    time.sleep(1)
                adapters=s.get(endpoint+'/lora-adapters',timeout=10);adapters.raise_for_status();save('runtime-adapters.json',adapters.json())
                identity=adapters.json()[0]['id'];results=[]
                for i,q,_,rubric in GATE:
                    row=dict(id=i,question=q,rubric=rubric)
                    for label,scale in variants(i,compare_case_ids):
                        r=s.post(endpoint+'/lora-adapters',json=[dict(id=identity,scale=scale)],timeout=10);r.raise_for_status()
                        system=system_prompt(SYSTEM)
                        r=s.post(endpoint+'/v1/chat/completions',json=request_body(system,q,identity,scale,reasoning_budget),timeout=120)
                        r.raise_for_status();row[label]=check_response(r.json())
                    results.append(row);save('runtime-gate-comparison.json',results)
                    save('runtime-gate-status.json',dict(stage='evaluating',completed=len(results),total=len(GATE)))
                if after_cases:after_cases(s,endpoint,identity)
                save('runtime-gate-status.json',dict(stage='awaiting_semantic_review',completed=len(results),total=len(GATE),
                     formats_complete=all(r[k]['format_complete'] for r in results for k in ('base','adapter') if k in r),
                     deployed=False,audio_mix_verified=False))
            finally:
                proc.terminate()
                try:proc.wait(timeout=15)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=15)
if __name__=='__main__':main()
