"""CLIP text/image embeddings for matching footage to what is being said. Runs locally."""
from pathlib import Path

import numpy as np


WEIGHTS = ('model.safetensors', 'pytorch_model.bin')


def model_folder(name, root, offline=False):
    """Local snapshot with config + one weights file (safetensors preferred, else PyTorch .bin)."""
    from hinglish_cut.model_storage import configure, selected_path
    configure(root)
    name=selected_path(root,name)
    if Path(name).is_dir():
        return str(Path(name))
    from huggingface_hub import list_repo_files, snapshot_download
    cache = str(Path(root) / 'models')

    def complete(folder):
        return any((Path(folder) / w).is_file() for w in WEIGHTS)

    try:
        folder = snapshot_download(name, cache_dir=cache, local_files_only=True,
                                   allow_patterns=['*.json', '*.txt', *WEIGHTS])
        if complete(folder):
            return folder
    except Exception:
        pass
    if offline:
        raise FileNotFoundError(f'The visual model {name} is not downloaded yet')
    files = set(list_repo_files(name))
    weights = next((w for w in WEIGHTS if w in files), None)
    if not weights:
        raise FileNotFoundError(f'{name} has no PyTorch weights')
    return snapshot_download(name, cache_dir=cache, allow_patterns=['*.json', '*.txt', weights])


class Vision:
    def __init__(self, name, root, device='cpu', threads=4):
        # Closing the HTTP client does not unload the planner. Release it before
        # importing CUDA/PyTorch libraries, not after their memory is committed.
        if device=='cuda':
            from hinglish_cut.model_preferences import release_ollama
            release_ollama(root)
        import torch
        from transformers import CLIPModel, CLIPProcessor
        if device == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('NVIDIA CUDA vision inference is unavailable; CPU fallback is disabled')
        from hinglish_cut.model_storage import role
        selected=role(root,'broll_vision')
        self.multimodal=bool(selected and name in ('openai/clip-vit-base-patch32',selected['repo'],selected['path']))
        self.vector_cache=Path(root)/'cache/broll/image-vectors'
        self.vector_cache.mkdir(parents=True,exist_ok=True)
        import hashlib,json
        source=Path(selected['path']) if self.multimodal else Path(model_folder(name,root))
        revision=[(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(source.iterdir())
                  if p.suffix in ('.json','.safetensors','.bin')]
        self.vector_signature=hashlib.sha256(json.dumps(['v1',str(source),device,revision]).encode()).hexdigest()
        if self.multimodal:
            from .vl_embedding import load_encoder
            self.torch=torch
            self.device=device
            torch.set_num_threads(threads)
            self.model,self.processor=load_encoder(selected['path'],self.device)
            return
        self.torch = torch
        torch.set_num_threads(threads)
        self.device = device
        folder = str(source)
        self.model = CLIPModel.from_pretrained(folder).to(self.device).eval()
        if self.device == 'cuda':
            self.model = self.model.half()
        self.processor = CLIPProcessor.from_pretrained(folder)

    def _normalize(self, features):
        features = features.float().cpu().numpy()
        return features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-8)

    def texts(self, texts, batch=32):
        if self.multimodal:
            from .vl_embedding import encode
            return encode(self.model,self.processor,self.device,texts=texts)
        out = []
        with self.torch.no_grad():
            for i in range(0, len(texts), batch):
                inputs = self.processor(text=texts[i:i + batch], return_tensors='pt', padding=True,
                                        truncation=True, max_length=77).to(self.device)
                out.append(self._normalize(self.model.get_text_features(**inputs)))
        return np.concatenate(out) if out else np.zeros((0, self.model.config.projection_dim), np.float32)

    def images(self, images, batch=16):
        if self.multimodal:
            from .vl_embedding import encode
            return encode(self.model,self.processor,self.device,images=images)
        out = []
        with self.torch.no_grad():
            for i in range(0, len(images), batch):
                inputs = self.processor(images=[im.convert('RGB') for im in images[i:i + batch]],
                                        return_tensors='pt').to(self.device)
                pixels = inputs['pixel_values']
                if self.device == 'cuda':
                    pixels = pixels.half()
                out.append(self._normalize(self.model.get_image_features(pixel_values=pixels)))
        return np.concatenate(out) if out else np.zeros((0, self.model.config.projection_dim), np.float32)

    def close(self):
        self.model = None
        self.processor = None
        import gc
        gc.collect()
        if self.device == 'cuda':
            self.torch.cuda.empty_cache()
