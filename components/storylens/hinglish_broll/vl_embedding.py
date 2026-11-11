"""Local Qwen multimodal embeddings using reviewed, installed Transformers code.

Uses the official model's system/user format and last non-padding-token pooling.
No remote Python code, video downloads, or model-generated instructions execute.
"""
import gc
import sys
import threading
from contextlib import contextmanager,nullcontext
import numpy as np

_WEIGHT_READER_LOCK=threading.RLock()


@contextmanager
def sequential_reader(module):
    """Use safetensors' supported pread backend for this isolated model load.

    Windows fault traces pointed into Torch storage slicing of lazy mapped
    weights. Keep the same weights/dtype/device, but read the requested tensor
    through the library's bounded file reader. Restore the alias on every exit.
    No installed package or another process is changed.
    """
    with _WEIGHT_READER_LOCK:
        original=module.safe_open
        def read(*args,**kwargs):
            kwargs['backend']='pread'
            return original(*args,**kwargs)
        module.safe_open=read
        try:yield
        finally:module.safe_open=original


@contextmanager
def windows_reader():
    from transformers import modeling_utils
    with sequential_reader(modeling_utils):yield


def load_pretrained(encoder, path, device, torch):
    """Stream local weights to their final device; avoid load-on-CPU then .to()."""
    target='cuda:0' if device=='cuda' else device
    with windows_reader() if sys.platform=='win32' else nullcontext():
        return encoder.from_pretrained(str(path),local_files_only=True,
            dtype=torch.bfloat16 if device.startswith('cuda') else torch.float32,
            device_map={'':target}).eval()


def load_encoder(path, device):
    import torch
    from transformers.models.qwen3_vl.modeling_qwen3_vl import Qwen3VLModel, Qwen3VLPreTrainedModel
    from transformers import AutoProcessor

    class Encoder(Qwen3VLPreTrainedModel):
        _checkpoint_conversion_mapping = {}

        def __init__(self, config):
            super().__init__(config)
            self.model=Qwen3VLModel(config)
            self.post_init()

        def forward(self, **inputs):
            return self.model(**inputs)

    model=load_pretrained(Encoder,path,device,torch)
    model.config.projection_dim=model.config.text_config.hidden_size
    processor=AutoProcessor.from_pretrained(str(path),local_files_only=True,padding_side='right',
        min_pixels=4*32*32,max_pixels=256*256)
    return model,processor


def encode(model,processor,device,texts=None,images=None):
    import torch
    count=len(texts) if texts is not None else len(images)
    results=[]
    for start in range(0,count,2):
        chunk=range(start,min(count,start+2))
        conversations=[]
        pictures=[]
        for index in chunk:
            content=[]
            if images is not None:
                picture=images[index].convert('RGB').copy()
                picture.thumbnail((256,256))
                content.append({'type':'image','image':picture})
                pictures.append(picture)
            if texts is not None:
                content.append({'type':'text','text':texts[index]})
            conversations.append([
                {'role':'system','content':[{'type':'text','text':"Represent the user's input."}]},
                {'role':'user','content':content}])
        prompts=processor.apply_chat_template(conversations,tokenize=False,add_generation_prompt=True)
        inputs=processor(text=prompts,images=pictures or None,padding=True,return_tensors='pt')
        if inputs['input_ids'].shape[1]>4096:
            raise ValueError('Visual search text is too long; split it into shorter descriptions')
        inputs={key:value.to(device) for key,value in inputs.items()}
        with torch.inference_mode():
            hidden=model(**inputs,use_cache=False).last_hidden_state
            mask=inputs['attention_mask']
            last=mask.shape[1]-mask.flip(1).argmax(1)-1
            pooled=hidden[torch.arange(hidden.shape[0],device=hidden.device),last]
            vectors=torch.nn.functional.normalize(pooled.float(),dim=-1).cpu().numpy()
        results.append(vectors)
        del hidden,inputs,pooled
    return np.concatenate(results) if results else np.zeros((0,model.config.projection_dim),np.float32)
