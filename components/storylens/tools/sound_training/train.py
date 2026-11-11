"""Isolated, local QLoRA knowledge pilot. Never updates live Storylens settings."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/sound-training/20261030-qwen3-14b'
BASE=Path('C:/Ai Models/training/sound-qwen3-14b/base')
DEFAULTS=dict(per_device_train_batch_size=1,gradient_accumulation_steps=8,
              num_train_epochs=2,learning_rate=5e-5,max_seq_length=1024,
              lora_rank=8,lora_alpha=16,full_finetuning=False,auto_deploy=False)
GENERATION_TOKENS=384
EVALUATION_LIMIT=8

def configure(output,epochs=1,learning_rate=1e-5):
    global OUT
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'output/sound-training').resolve()):
        raise ValueError('Training outputs must remain in output/sound-training')
    if type(epochs) not in (int,float) or not math.isfinite(epochs) or not 0<epochs<=2:
        raise ValueError('Choose a bounded positive training epoch count, at most two')
    if type(learning_rate) not in (int,float) or not math.isfinite(learning_rate) or not 0<learning_rate<=5e-5:
        raise ValueError('Learning rate is outside the conservative training bound')
    OUT=output;DEFAULTS.update(num_train_epochs=epochs,learning_rate=learning_rate)

def encode_record(row,tokenizer,maximum):
    messages=row['messages']
    if len(messages)<2 or messages[-1]['role']!='assistant' or not messages[-1]['content'].strip():
        raise ValueError('A nonempty assistant training target is required')
    prefix=tokenizer.apply_chat_template(messages[:-1],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    prompt_ids=tokenizer.encode(prefix,add_special_tokens=False)
    target_ids=tokenizer.encode(messages[-1]['content']+tokenizer.eos_token,add_special_tokens=False)
    ids=prompt_ids+target_ids
    if len(ids)>maximum:raise ValueError(f'Example {row["id"]} has {len(ids)} tokens; refused silent truncation at {maximum}')
    return {'input_ids':ids,'attention_mask':[1]*len(ids),'labels':[-100]*len(prompt_ids)+target_ids}

def validate_split(train,evals):
    if not train or not evals:raise ValueError('Both training and evaluation are required')
    ti={x['id'] for x in train};ei={x['id'] for x in evals}
    if len(ti)!=len(train) or len(ei)!=len(evals) or ti&ei:raise ValueError('Duplicate/overlapping example IDs')
    tp={x['messages'][-2]['content'] for x in train}
    if any(x['messages'][-2]['content'] in tp for x in evals):raise ValueError('Evaluation prompt leaked into training')

def checked_loss(value):
    if not math.isfinite(float(value)):raise ValueError('Training/evaluation loss is not finite')
    return float(value)

def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/name;tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str),encoding='utf-8');tmp.replace(path)

def status(stage,**extra):
    d=dict(stage=stage,updated_unix=time.time(),model='Qwen3-14B',original_model_unchanged=True,
           auto_deploy=False,**extra)
    save('status.json',d);print(json.dumps(d,default=str),flush=True)

def run(mode,initial_adapter=None):
    os.environ.update(HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',WANDB_DISABLED='true',
                      TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                      UNSLOTH_DISABLE_STATISTICS='1')
    os.environ['TRITON_CACHE_DIR']=str(OUT/'triton-cache')
    os.environ['TORCHINDUCTOR_CACHE_DIR']=str(OUT/'torch-cache')
    os.environ['UNSLOTH_TEMP_LOCATION']=str(OUT/'unsloth-cache')
    sys.path.insert(0,str(ROOT))
    parent_receipt=None
    if initial_adapter:
        from tools.sound_training.continuation import validate_parent
        parent_receipt=validate_parent(initial_adapter,OUT,BASE,DEFAULTS['lora_rank'],DEFAULTS['lora_alpha'])
        save('parent-adapter.json',parent_receipt)
    from hinglish_cut.gpu_lock import gpu_lock
    status('waiting_for_shared_gpu_slot',mode=mode)
    with gpu_lock(ROOT):
        status('checking_isolated_training_runtime',mode=mode)
        from unsloth import FastLanguageModel
        import torch
        from transformers import AutoTokenizer,DataCollatorForSeq2Seq,Trainer,TrainingArguments,TrainerCallback
        from datasets import Dataset
        torch.set_num_threads(2)
        torch.manual_seed(3407)
        info={p:importlib.metadata.version(p) for p in ('torch','transformers','unsloth','unsloth_zoo','peft','bitsandbytes','trl','datasets')}
        info.update(gpu=torch.cuda.get_device_name(0),cuda_available=torch.cuda.is_available(),
                    gpu_memory=list(torch.cuda.mem_get_info()),python=sys.version)
        save('runtime.json',info)
        if mode=='inspect':status('runtime_import_verified',**info);return
        tokenizer=AutoTokenizer.from_pretrained(str(BASE),local_files_only=True,trust_remote_code=False)
        data=OUT/'dataset'
        train=[json.loads(x) for x in (data/'train.jsonl').read_text(encoding='utf-8').splitlines()]
        ev=[json.loads(x) for x in (data/'holdout.jsonl').read_text(encoding='utf-8').splitlines()]
        validate_split(train,ev)
        encoded=[encode_record(r,tokenizer,DEFAULTS['max_seq_length']) for r in train]
        enc_ev=[encode_record(r,tokenizer,DEFAULTS['max_seq_length']) for r in ev]
        save('tokenization.json',{'train_examples':len(train),'holdout_examples':len(ev),
             'max_tokens':max(len(r['input_ids']) for r in encoded+enc_ev),
             'train_tokens':sum(len(r['input_ids']) for r in encoded),
             'target_tokens':sum(sum(t!=-100 for t in r['labels']) for r in encoded),
             'truncated_examples':0,'prompt_masked':True})
        if mode=='tokenize':status('tokenization_verified');return
        required=['model-00001-of-00002.safetensors','model-00002-of-00002.safetensors']
        expected=[4996841286,4931923327]
        for name,size in zip(required,expected):
            if not (BASE/name).is_file() or (BASE/name).stat().st_size!=size:raise RuntimeError('Pinned training weights are not fully downloaded: '+name)
        if (OUT/'adapter/adapter_model.safetensors').exists():raise RuntimeError('An adapter already exists. Evaluate/resume explicitly; never overwrite it automatically.')
        status('loading_training_base',config=DEFAULTS)
        started=time.monotonic()
        model,tokenizer=FastLanguageModel.from_pretrained(model_name=str(BASE),max_seq_length=DEFAULTS['max_seq_length'],
             dtype=torch.bfloat16,load_in_4bit=True,full_finetuning=False,device_map={'':0},
             local_files_only=True,trust_remote_code=False)
        model=FastLanguageModel.get_peft_model(model,r=DEFAULTS['lora_rank'],
             target_modules=['q_proj','k_proj','v_proj','o_proj'],lora_alpha=DEFAULTS['lora_alpha'],
             lora_dropout=0,bias='none',use_gradient_checkpointing='unsloth',random_state=3407,
             use_rslora=False,loftq_config=None)
        if initial_adapter:
            from tools.sound_training.continuation import load_parent
            parent_receipt['verified_loaded_tensors']=load_parent(model,initial_adapter)
            save('parent-adapter.json',parent_receipt)
        params={name:p for name,p in model.named_parameters() if p.requires_grad}
        if not params or any('lora_' not in name for name in params):raise RuntimeError('Refused training beyond adapter parameters')
        tracked_name=next(name for name in params if 'lora_B' in name)
        initial=params[tracked_name].detach().float().cpu().clone()
        class Progress(TrainerCallback):
            def on_log(self,args,state,control,logs=None,**kwargs):
                if logs and 'loss' in logs:checked_loss(logs['loss'])
                phase='evaluating' if logs and 'eval_loss' in logs else 'training'
                status(phase,step=state.global_step,total_steps=state.max_steps,epoch=state.epoch,logs=logs or {},elapsed_seconds=time.monotonic()-started)
            def on_step_end(self,args,state,control,**kwargs):
                if (OUT/'STOP').exists():control.should_training_stop=True;control.should_save=True
        args=TrainingArguments(output_dir=str(OUT/'checkpoints'),
             per_device_train_batch_size=1,per_device_eval_batch_size=1,
             gradient_accumulation_steps=DEFAULTS['gradient_accumulation_steps'],
             num_train_epochs=DEFAULTS['num_train_epochs'],learning_rate=DEFAULTS['learning_rate'],
             warmup_ratio=0.05,lr_scheduler_type='linear',optim='adamw_torch',bf16=True,fp16=False,
             logging_steps=1,save_strategy='epoch',save_total_limit=2,eval_strategy='no',
             report_to='none',seed=3407,dataloader_num_workers=0,dataloader_pin_memory=False,
             remove_unused_columns=False,max_grad_norm=1.0,weight_decay=0.01)
        trainer=Trainer(model=model,args=args,train_dataset=Dataset.from_list(encoded),
             eval_dataset=Dataset.from_list(enc_ev),data_collator=DataCollatorForSeq2Seq(tokenizer,padding=True,label_pad_token_id=-100),
             processing_class=tokenizer,callbacks=[Progress()])
        status('evaluating_parent_adapter' if initial_adapter else 'evaluating_untrained_adapter',trainable_parameters=sum(p.numel() for p in params.values()))
        before=trainer.evaluate();checked_loss(before['eval_loss']);save('eval-before.json',before)
        status('training_started',config=DEFAULTS)
        result=trainer.train()
        checked_loss(result.training_loss)
        after=trainer.evaluate();checked_loss(after['eval_loss']);save('eval-after.json',after)
        delta=float((params[tracked_name].detach().float().cpu()-initial).abs().max())
        if delta<=0:raise RuntimeError('No change detected in tracked adapter weights')
        adapter=OUT/'adapter';model.save_pretrained(str(adapter));tokenizer.save_pretrained(str(adapter))
        receipts=dict(optimizer_steps=trainer.state.global_step,epochs=trainer.state.epoch,
            config=dict(DEFAULTS),dataset_sha256=hashlib.sha256((data/'train.jsonl').read_bytes()).hexdigest(),
            training_metrics=result.metrics,eval_before=before,eval_after=after,
            tracked_parameter=tracked_name,max_weight_delta=delta,
            elapsed_seconds=time.monotonic()-started,base_repo='unsloth/Qwen3-14B-bnb-4bit',
            base_revision='b455922269e4678c84f854fe38a6993d73614a1e',
            halted_by_owner=(OUT/'STOP').exists(),auto_deployed=False,
            audio_quality_verified=False,application_verified=False)
        receipts['parent_adapter']=parent_receipt
        save('training-receipt.json',receipts)
        # Compare a few genuinely held-out decisions, not just loss.
        FastLanguageModel.for_inference(model)
        generation=[]
        for row in ev[:EVALUATION_LIMIT]:
            prompt=tokenizer.apply_chat_template(row['messages'][:-1],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            inputs=tokenizer(prompt,return_tensors='pt').to('cuda')
            pair={}
            for label,disabled in [('base',True),('adapter',False)]:
                from contextlib import nullcontext
                with model.disable_adapter() if disabled else nullcontext():
                    with torch.inference_mode():answer=model.generate(**inputs,max_new_tokens=GENERATION_TOKENS,do_sample=False,use_cache=True)
                pair[label]=tokenizer.decode(answer[0][inputs.input_ids.shape[1]:],skip_special_tokens=True)
                pair[label+'_token_count']=int(answer.shape[1]-inputs.input_ids.shape[1])
                pair[label+'_hit_token_limit']=pair[label+'_token_count']>=GENERATION_TOKENS
            generation.append(dict(id=row['id'],question=row['messages'][-2]['content'],rubric=row['rubric'],**pair))
            save('heldout-comparison.json',generation)
        status('adapter_trained_awaiting_review',**receipts)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['inspect','tokenize','train'],default='inspect')
    parser.add_argument('--output-dir');parser.add_argument('--epochs',type=float,default=1)
    parser.add_argument('--learning-rate',type=float,default=1e-5)
    parser.add_argument('--initial-adapter',help='Continue a compatible saved adapter in a separate output folder')
    args=parser.parse_args();mode=args.mode
    if args.output_dir:configure(args.output_dir,args.epochs,args.learning_rate)
    try:run(mode,initial_adapter=args.initial_adapter)
    except BaseException as e:
        status('stopped_with_error',error_type=type(e).__name__,error=str(e),mode=mode)
        raise
