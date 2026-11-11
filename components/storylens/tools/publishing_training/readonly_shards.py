"""Read-only, file-backed CPU safetensors access for Windows low-RAM loading.

Avoids committing a writable copy of each complete 5 GB input shard. Tensor
bytes, names, shapes and dtypes are read directly from the immutable source.
"""
import json,struct
from pathlib import Path

class ReadOnlyShard:
    def __init__(self,path):
        self.path=Path(path)
        with self.path.open('rb') as f:
            size=struct.unpack('<Q',f.read(8))[0]
            self.header=json.loads(f.read(size));self.offset=8+size
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def keys(self):return [k for k in self.header if k!='__metadata__']
    def metadata(self):return self.header.get('__metadata__',{})
    def get_tensor(self,name):
        import numpy as np,torch
        d=self.header[name];dtype=d['dtype']
        table={'BF16':('uint16',torch.bfloat16),'F16':('float16',torch.float16),'F32':('float32',torch.float32),'F64':('float64',torch.float64),'U8':('uint8',torch.uint8),'I8':('int8',torch.int8),'I16':('int16',torch.int16),'I32':('int32',torch.int32),'I64':('int64',torch.int64),'BOOL':('bool',torch.bool)}
        npdtype,tdtype=table[dtype]
        value=np.memmap(self.path,dtype=npdtype,mode='r',offset=self.offset+d['data_offsets'][0],shape=tuple(d['shape']))
        return torch.from_numpy(value).view(tdtype)
    def get_slice(self,name):
        parent=self
        class Slice:
            def get_shape(self):return parent.header[name]['shape']
            def get_dtype(self):return parent.header[name]['dtype']
            def __getitem__(self,key):return parent.get_tensor(name)[key]
        return Slice()

def install(base):
    import transformers.modeling_utils as module
    original=module.safe_open;base=Path(base).resolve()
    def safe_open(filename,*args,**kwargs):
        framework=kwargs.get('framework',args[0] if args else None)
        device=kwargs.get('device',args[1] if len(args)>1 else 'cpu')
        if framework=='pt' and device in ('cpu',None) and Path(filename).resolve().is_relative_to(base):
            return ReadOnlyShard(filename)
        return original(filename,*args,**kwargs)
    module.safe_open=safe_open
