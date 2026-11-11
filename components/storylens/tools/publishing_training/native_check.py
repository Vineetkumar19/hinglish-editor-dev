"""Compare saved adapter behavior in its original training runtime; no actions."""
import os,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',WANDB_DISABLED='true',UNSLOTH_DISABLE_STATISTICS='1')
OUT=ROOT/'output/publishing-training/20261030-v11'
DATASET='production-replay'
BASE=Path('C:/Ai Models/training/sound-qwen3-14b/base')
from hinglish_cut.gpu_lock import gpu_lock
from hinglish_cut.model_preferences import release_ollama

def main():
 with gpu_lock(ROOT):
  release_ollama(ROOT)
  from unsloth import FastLanguageModel
  import torch
  from tools.sound_training.continuation import load_parent
  torch.set_num_threads(2)
  model,tokenizer=FastLanguageModel.from_pretrained(model_name=str(BASE),max_seq_length=8192,dtype=torch.bfloat16,load_in_4bit=True,device_map={'':0},local_files_only=True,trust_remote_code=False)
  model=FastLanguageModel.get_peft_model(model,r=8,target_modules=['q_proj','k_proj','v_proj','o_proj'],lora_alpha=16,lora_dropout=0,bias='none',use_gradient_checkpointing='unsloth',random_state=3407,use_rslora=False,loftq_config=None)
  loaded=load_parent(model,OUT/'adapter');FastLanguageModel.for_inference(model)
  from tools.publishing_training import revision9,evaluate
  evaluate.OUT=OUT
  score=revision9.scoring(evaluate.score)
  splits=['holdout','acceptance','production-replay'] if DATASET=='review' else [DATASET]
  rows=[dict(json.loads(s),evaluation_split=split) for split in splits for s in (OUT/f'dataset/{split}.jsonl').read_text('utf8').splitlines()]
  result=[]
  for row in rows:
   prompt=tokenizer.apply_chat_template(row['messages'][:-1],tokenize=False,add_generation_prompt=True,enable_thinking=False)
   inputs=tokenizer(prompt,return_tensors='pt').to('cuda');started=time.monotonic()
   with torch.inference_mode():output=model.generate(**inputs,max_new_tokens=700,do_sample=False,use_cache=True)
   text=tokenizer.decode(output[0][inputs.input_ids.shape[1]:],skip_special_tokens=True)
   try:parsed=json.loads(text)
   except ValueError:parsed=None
   result.append(dict(id=row['id'],split=row['evaluation_split'],content=text,passed=score(row,parsed),elapsed_seconds=time.monotonic()-started,input_tokens=int(inputs.input_ids.shape[1]),output_tokens=int(output.shape[1]-inputs.input_ids.shape[1]),loaded_adapter_tensors=loaded))
   (OUT/f'native-{DATASET}.json').write_text(json.dumps(result,indent=2),encoding='utf8')
   status=dict(complete=len(result),total=len(rows),passed=sum(r['passed'] for r in result),runtime='native training base + adapter, no JSON grammar',live_actions=False)
   status['splits']={s:dict(complete=sum(r['split']==s for r in result),total=sum(r['evaluation_split']==s for r in rows),passed=sum(r['split']==s and r['passed'] for r in result)) for s in splits}
   (OUT/f'native-{DATASET}-status.json').write_text(json.dumps(status,indent=2),encoding='utf8')
   print(json.dumps(status),flush=True)
if __name__=='__main__':main()
