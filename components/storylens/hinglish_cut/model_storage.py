"""Per-machine model data location and explicitly validated upgrade selections."""
import json
import os
from pathlib import Path


def configuration(root):
    path = Path(os.environ.get('STORYLENS_MODEL_SELECTION') or (Path(root) / 'config.model_storage.local.json'))
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}


def role(root, name):
    data = configuration(root)
    return data.get('roles', {}).get(name, {}) if data.get('active') else {}


def signature(root):
    data = configuration(root)
    return json.dumps(data.get('roles', {}) if data.get('active') else {}, sort_keys=True)


def configure(root):
    data = configuration(root)
    if not data.get('root'):
        return
    folder = Path(data['root'])
    for key, relative in {'HF_HOME': 'cache/huggingface', 'HF_HUB_CACHE': 'cache/huggingface/hub',
                          'TORCH_HOME': 'cache/torch', 'MODELSCOPE_CACHE': 'cache/modelscope',
                          'U2NET_HOME': 'rembg', 'OLLAMA_MODELS': 'ollama',
                          'CUDA_CACHE_PATH':'cache/cuda','TRITON_CACHE_DIR':'cache/triton'}.items():
        os.environ[key] = str(folder / relative)
    if not role(root,'cutout'):
        os.environ['U2NET_HOME']=str(folder/'editor-models/rembg')


def selected_path(root, name):
    data = configuration(root)
    return data.get('aliases', {}).get(name, name) if data.get('active') else name
