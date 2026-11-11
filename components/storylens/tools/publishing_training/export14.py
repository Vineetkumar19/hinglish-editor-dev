"""Export v14 from its exact saved NF4 base, one tensor at a time.

No network, inference, activation or publishing. Final quantization/acceptance
is a separate step. Source weights and all earlier candidates are immutable.
"""
import os, sys, json, time, logging, hashlib, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/publishing-training/20261031-v14'
BASE = Path('C:/Ai Models/training/sound-qwen3-14b/base')
DEST = Path('C:/Ai Models/training/publishing-v14-export/publishing-v14-Q8_0.gguf')
CONVERTER = ROOT / 'tools/sound_training/export-source/llama.cpp-b11011'
sys.path[:0] = [str(ROOT), str(CONVERTER), str(CONVERTER/'gguf-py')]
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')

def main():
    import torch
    from safetensors import safe_open
    from bitsandbytes.functional import QuantState, dequantize_4bit
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.model_preferences import release_ollama
    import gguf
    from conversion import ModelBase, ModelType, get_model_class
    logging.basicConfig(level=logging.INFO)
    torch.set_num_threads(2)
    index = json.loads((BASE/'model.safetensors.index.json').read_text())['weight_map']
    adapter_path = OUT/'adapter/adapter_model.safetensors'
    with safe_open(str(adapter_path), framework='pt', device='cpu') as f:
        adapter = {k:f.get_tensor(k) for k in f.keys()}
    config = json.loads((OUT/'adapter/adapter_config.json').read_text())
    scale = config['lora_alpha']/config['r']
    weights = [k for k in index if k.endswith('.weight')]
    receipt = dict(stage='waiting_for_gpu', complete=0, total=len(weights),
                   adapter_sha256=hashlib.sha256(adapter_path.read_bytes()).hexdigest(),
                   base=str(BASE), output=str(DEST), merged_tensors=0)
    def save():
        (OUT/'export-status.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    # Keep the two mappings open; never retain a tensor backed by a closed map.
    from contextlib import ExitStack
    stack=ExitStack()
    shards={p:stack.enter_context(safe_open(str(BASE/p),framework='pt',device='cpu')) for p in set(index.values())}
    def load(name):
        return shards[index[name]].get_tensor(name).clone()
    original_quantize=gguf.quants.quantize
    def bounded_quantize(data,qtype):
        import numpy as np
        if qtype!=gguf.GGMLQuantizationType.Q8_0 or data.size<1048576:
            return original_quantize(data,qtype)
        shape=gguf.quant_shape_to_byte_shape(data.shape,qtype)
        result=np.empty(shape,dtype=np.uint8)
        source=data.reshape(-1,data.shape[-1]);target=result.reshape(-1,shape[-1])
        rows=max(1,1048576//data.shape[-1])
        for start in range(0,len(source),rows):
            target[start:start+rows]=original_quantize(source[start:start+rows],qtype)
        return result
    gguf.quants.quantize=bounded_quantize
    def tensors(self):
        for i,name in enumerate(weights):
            value=load(name)
            if name+'.quant_state.bitsandbytes__nf4' in index:
                state={k[len(name)+1:]:load(k) for k in index if k.startswith(name+'.')}
                qs=QuantState.from_dict(state,device=torch.device('cuda'))
                value=dequantize_4bit(value.to('cuda'),quant_state=qs)
            prefix='base_model.model.'+name[:-len('.weight')]
            a=adapter.get(prefix+'.lora_A.weight')
            if a is not None:
                b=adapter[prefix+'.lora_B.weight']
                # Match PEFT's BF16 merged storage, with FP32 delta accumulation.
                value=(value.float()+scale*(b.to(value.device).float()@a.to(value.device).float())).to(value.dtype)
                receipt['merged_tensors']+=1
            result=value.cpu()
            del value
            receipt.update(stage='exporting',complete=i+1,current_tensor=name)
            save()
            yield name,result
            del result
    ModelBase.index_tensors=lambda self,**kw:{name:None for name in weights}
    ModelBase.get_tensors=tensors
    ModelBase.dequant_model=lambda self: None
    with gpu_lock(ROOT):
        release_ollama(ROOT)
        DEST.parent.mkdir(parents=True,exist_ok=True)
        if DEST.exists():raise RuntimeError('Existing export preserved; choose an explicit reviewed continuation')
        scratch=OUT/'export-temp';scratch.mkdir(exist_ok=True)
        tempfile.tempdir=str(scratch)
        hp=json.loads((BASE/'config.json').read_text());hp.pop('quantization_config',None)
        model_class=get_model_class('Qwen3ForCausalLM',mmproj=False)
        model=model_class(BASE,gguf.LlamaFileType.MOSTLY_Q8_0,DEST,hparams=hp,
                          use_temp_file=True,eager=True,model_name='Storylens Publishing v14')
        started=time.monotonic()
        model.write()
        if receipt['merged_tensors']!=160:raise RuntimeError('Expected all 160 trained attention matrices merged')
        receipt.update(stage='exported_q8',elapsed_seconds=time.monotonic()-started,bytes=DEST.stat().st_size)
        save()
        print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
