"""Read-only comparison of unquantized normalization weights; no model calls."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/sound_training/export-source/llama.cpp-b11011/gguf-py'))
from gguf import GGUFReader
from safetensors import safe_open
import numpy as np
BASE=Path('C:/Ai Models/training/sound-qwen3-14b/base')
def compare(gguf_path,base=BASE):
 index=json.loads((base/'model.safetensors.index.json').read_text())['weight_map']
 reader=GGUFReader(str(gguf_path));tensors={t.name:t for t in reader.tensors};results=[]
 for layer in (0,10,20,39):
  for hf,gg in [('input_layernorm','attn_norm'),('post_attention_layernorm','ffn_norm')]:
   name=f'model.layers.{layer}.{hf}.weight'
   with safe_open(str(base/index[name]),framework='pt',device='cpu') as f:a=f.get_tensor(name).float().numpy()
   tensor=tensors[f'blk.{layer}.{gg}.weight'];b=np.asarray(tensor.data,dtype=np.float32).reshape(-1)
   results.append(dict(layer=layer,name=hf,gguf_type=str(tensor.tensor_type),exact_equal=bool(np.array_equal(a,b)),max_absolute_difference=float(np.max(np.abs(a-b))),different_values=int(np.count_nonzero(a!=b))))
 return results

if __name__=='__main__':
 results=compare('C:/Ai Models/ollama/blobs/sha256-500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0')
 out=ROOT/'output/publishing-training/20261030-v12/base-identity-check.json'
 out.write_text(json.dumps(dict(comparison='Unquantized normalization tensors only; does not establish all base weights identical',results=results),indent=2),encoding='utf8')
 print(json.dumps(results))
