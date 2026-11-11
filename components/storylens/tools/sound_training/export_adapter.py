"""Export only LoRA A/B weights, with derived architecture-only base metadata.

The converter mistakes NF4 base metadata for adapter tensor quantization. Our
adapter tensors are floating point; no base tensor is converted or modified here.
"""
from pathlib import Path
import json,copy,subprocess,sys,hashlib
ROOT=Path(__file__).resolve().parents[2]
BASE=Path('C:/Ai Models/training/sound-qwen3-14b/base')
OUT=ROOT/'output/sound-training/20261030-revision2'
def adapter_base_config(source):
    if source.get('model_type')!='qwen3':raise ValueError('Only the verified Qwen3 architecture is supported')
    result=copy.deepcopy(source);result.pop('quantization_config',None);return result
def main():
    config=BASE/'config.json';folder=OUT/'export-architecture';folder.mkdir(exist_ok=True)
    (folder/'config.json').write_text(json.dumps(adapter_base_config(json.loads(config.read_text())),indent=2),encoding='utf-8')
    receipt=dict(original_config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
      transformation='Removed base NF4 quantization metadata only from derived adapter-converter architecture config. No model weights or training files modified.',base_config=str(config))
    (folder/'provenance.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    subprocess.run([sys.executable,str(ROOT/'tools/sound_training/export-source/llama.cpp-b11011/convert_lora_to_gguf.py'),
       '--base',str(folder),'--outtype','f16','--outfile',str(OUT/'adapter.gguf'),str(OUT/'adapter')],check=True)
if __name__=='__main__':main()
