"""One bounded publishing inference; exact saved training runtime, no external actions."""
import os,sys,json,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',WANDB_DISABLED='true',UNSLOTH_DISABLE_STATISTICS='1')

def main(folder):
    data=json.loads((folder/'request.json').read_text('utf8'));body=data['body']
    from hinglish_cut.gpu_lock import _child_lease
    from contextlib import nullcontext
    if not _child_lease(ROOT):raise RuntimeError('Native publishing inference has no verified parent GPU reservation.')
    if os.environ.get('STORYLENS_NATIVE_PARENT_PID'):
        import threading,psutil
        parent=psutil.Process(int(os.environ['STORYLENS_NATIVE_PARENT_PID']))
        birth=parent.create_time()
        def watch_parent():
            while True:
                time.sleep(1)
                try:
                    if not parent.is_running() or parent.create_time()!=birth:os._exit(1)
                except psutil.Error:os._exit(1)
        threading.Thread(target=watch_parent,daemon=True).start()
    with nullcontext():
        from unsloth import FastLanguageModel
        import torch
        from tools.sound_training.continuation import load_parent
        from tools.publishing_training.readonly_shards import install
        install(data['base'])
        torch.set_num_threads(2)
        if not torch.cuda.is_available():raise RuntimeError('The trained publishing model needs the NVIDIA GPU; no CPU-only inference was started.')
        bodies=data.get('bodies',[body])
        cap=max(int(b.get('options',{}).get('num_ctx',40960)) for b in bodies)
        if not 2048<=cap<=40960:raise ValueError('Publishing context must stay within the trained base’s native 40,960 tokens.')
        model,tokenizer=FastLanguageModel.from_pretrained(model_name=data['base'],max_seq_length=cap,dtype=torch.bfloat16,load_in_4bit=True,device_map={'':0},local_files_only=True,trust_remote_code=False)
        model=FastLanguageModel.get_peft_model(model,r=8,target_modules=['q_proj','k_proj','v_proj','o_proj'],lora_alpha=16,lora_dropout=0,bias='none',use_gradient_checkpointing='unsloth',random_state=3407,use_rslora=False,loftq_config=None)
        loaded=load_parent(model,Path(data['adapter']));FastLanguageModel.for_inference(model)
        tokenizer_constraints=None
        if any(isinstance(b.get('format'),dict) for b in bodies):
            from lmformatenforcer.integrations.transformers import build_token_enforcer_tokenizer_data
            tokenizer_constraints=build_token_enforcer_tokenizer_data(tokenizer)
        results=[]
        for body in bodies:
            messages=[dict(m) for m in body['messages']]
            if isinstance(body.get('format'),dict):
                contract='Return ONE JSON object matching this JSON Schema exactly. Include every required field and no other keys. Creator background is reference material, not output fields. Do not copy creator guidance into the answer. JSON Schema: '+json.dumps(body['format'],ensure_ascii=False,separators=(',',':'))
                if messages and messages[0]['role']=='system':messages[0]['content']+='\n\n'+contract
                else:messages.insert(0,{'role':'system','content':contract})
            prompt=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            inputs=tokenizer(prompt,return_tensors='pt').to('cuda')
            budget=int(body.get('options',{}).get('num_predict',2400))
            if inputs.input_ids.shape[1]+budget>cap:raise ValueError('The complete publishing request plus reply exceeds its context; all input and saved progress were preserved.')
            started=time.monotonic()
            generation={}
            if isinstance(body.get('format'),dict):
                from hinglish_cut.native_schema import schema_parser
                from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
                generation['prefix_allowed_tokens_fn']=build_transformers_prefix_allowed_tokens_fn(tokenizer_constraints,schema_parser(body['format']))
            if data.get('stream_reply'):
                from transformers import TextStreamer
                class ReplyStreamer(TextStreamer):
                    def on_finalized_text(self,text,stream_end=False):
                        with (folder/'text.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps(text,ensure_ascii=False)+'\n')
                generation['streamer']=ReplyStreamer(tokenizer,skip_prompt=True,skip_special_tokens=True)
            with torch.inference_mode():output=model.generate(**inputs,max_new_tokens=budget,do_sample=False,use_cache=True,**generation)
            content=tokenizer.decode(output[0][inputs.input_ids.shape[1]:],skip_special_tokens=True)
            generated=int(output.shape[1]-inputs.input_ids.shape[1])
            result={'model':body['model'],'message':{'role':'assistant','content':content},'done':True,'done_reason':'length' if generated>=budget else 'stop','prompt_eval_count':int(inputs.input_ids.shape[1]),'eval_count':generated,'native_runtime':True,'loaded_adapter_tensors':loaded,'elapsed_seconds':time.monotonic()-started,'gpu_memory_allocated':torch.cuda.memory_allocated(),'base':data['base'],'adapter':data['adapter']}
            if isinstance(body.get('format'),dict):
                from jsonschema import validate
                result['schema_decoder']='lm-format-enforcer 0.11.3'
                try:
                    validate(json.loads(content),body['format'])
                    result['schema_valid']=True
                except Exception as error:
                    result['schema_valid']=False
                    (folder/'rejected-response.json').write_text(json.dumps({**result,'validation_error':str(error)},ensure_ascii=False),encoding='utf8')
                    raise ValueError('The local publishing reply did not meet its required JSON fields or output limits. Its rejected response is saved.') from error
            results.append(result)
            (folder/'responses.json').write_text(json.dumps(results,ensure_ascii=False),encoding='utf8')
            (folder/'response.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')

if __name__=='__main__':
    folder=Path(sys.argv[1]).resolve()
    if not folder.is_relative_to((ROOT/'cache/app/publishing-native').resolve()):raise ValueError('Native request must stay in the publishing request folder')
    try:main(folder)
    except Exception as error:
        (folder/'error.json').write_text(json.dumps({'error':str(error),'type':type(error).__name__}),encoding='utf8')
        traceback.print_exc();sys.exit(1)
