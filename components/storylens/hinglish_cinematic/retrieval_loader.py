"""Bounded sequential loading of the unchanged installed BF16 retrieval weights."""
from pathlib import Path
import json,struct,math,gc

def load_encoder_streaming(path,progress=lambda *args:None,stop=None):
    import torch
    from accelerate import init_empty_weights
    from accelerate.utils import set_module_tensor_to_device
    from transformers import AutoConfig,AutoProcessor
    from transformers.models.qwen3_vl.modeling_qwen3_vl import Qwen3VLModel,Qwen3VLPreTrainedModel
    path=Path(path);file=path/'model.safetensors'
    class Encoder(Qwen3VLPreTrainedModel):
        _checkpoint_conversion_mapping={}
        def __init__(self,config):
            super().__init__(config);self.model=Qwen3VLModel(config);self.post_init()
        def forward(self,**inputs):return self.model(**inputs)
    config=AutoConfig.from_pretrained(str(path),local_files_only=True)
    config._attn_implementation='sdpa'
    with init_empty_weights(include_buffers=False):model=Encoder(config)
    try:
        with file.open('rb') as stream:
            header_size=struct.unpack('<Q',stream.read(8))[0]
            if not 1<=header_size<=16*1024*1024:raise ValueError('Invalid retrieval weight header size.')
            header=json.loads(stream.read(header_size));header.pop('__metadata__',None)
            expected=model.state_dict()
            if set(header)!=set(expected):raise ValueError('Retrieval weight names do not exactly match the installed architecture.')
            for index,(name,entry) in enumerate(header.items(),1):
                if stop is not None and stop.is_set():raise InterruptedError('Retrieval load stopped.')
                a,b=entry['data_offsets'];shape=entry['shape']
                if entry['dtype']!='BF16' or list(expected[name].shape)!=shape or b-a!=math.prod(shape)*2 or not 0<=a<b<=file.stat().st_size-8-header_size:
                    raise ValueError('Retrieval tensor type, shape or offset mismatch: '+name)
                stream.seek(8+header_size+a);raw=bytearray(b-a)
                if stream.readinto(raw)!=b-a:raise ValueError('Truncated retrieval tensor: '+name)
                tensor=torch.frombuffer(raw,dtype=torch.bfloat16).reshape(shape)
                set_module_tensor_to_device(model,name,'cuda:0',value=tensor,dtype=torch.bfloat16,clear_cache=False)
                del tensor,raw
                if index%40==0:progress(f'Loaded retrieval tensors {index}/{len(header)}',6)
            del expected
        if any(t.device.type=='meta' for t in list(model.parameters())+list(model.buffers())):raise ValueError('Retrieval model has unloaded tensors.')
        model.to('cuda:0');model.eval();model.config.projection_dim=model.config.text_config.hidden_size
        processor=AutoProcessor.from_pretrained(str(path),local_files_only=True,padding_side='right',min_pixels=4*32*32,max_pixels=256*256)
        return model,processor
    except BaseException:
        del model;gc.collect();torch.cuda.empty_cache();raise
