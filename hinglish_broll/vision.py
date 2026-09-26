"""CLIP text/image embeddings for matching footage to what is being said. Runs locally."""
from pathlib import Path

import numpy as np


WEIGHTS = ('model.safetensors', 'pytorch_model.bin')


def model_folder(name, root, offline=False):
    """Local snapshot with config + one weights file (safetensors preferred, else PyTorch .bin)."""
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
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch
        torch.set_num_threads(threads)
        self.device = 'cuda' if device == 'cuda' and torch.cuda.is_available() else 'cpu'
        folder = model_folder(name, root)
        self.model = CLIPModel.from_pretrained(folder).to(self.device).eval()
        if self.device == 'cuda':
            self.model = self.model.half()
        self.processor = CLIPProcessor.from_pretrained(folder)

    def _normalize(self, features):
        features = features.float().cpu().numpy()
        return features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-8)

    def texts(self, texts, batch=32):
        out = []
        with self.torch.no_grad():
            for i in range(0, len(texts), batch):
                inputs = self.processor(text=texts[i:i + batch], return_tensors='pt', padding=True,
                                        truncation=True, max_length=77).to(self.device)
                out.append(self._normalize(self.model.get_text_features(**inputs)))
        return np.concatenate(out) if out else np.zeros((0, self.model.config.projection_dim), np.float32)

    def images(self, images, batch=16):
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
        if self.device == 'cuda':
            self.torch.cuda.empty_cache()
