"""Bounded, model-specific text embeddings for the selected local Qwen encoder."""
from hinglish_cut.ollama_gpu import post as gpu_ollama_post
import numpy as np
import requests


class OllamaEmbeddings:
    def __init__(self, root, model, dimensions=4096, timeout=900):
        self.root, self.model, self.dimensions = root, model, dimensions
        self.session = requests.Session()
        self.session.trust_env = False
        self.url = 'http://127.0.0.1:11434'
        self.timeout = timeout

    def encode(self, texts, query=False, progress=lambda _: None, manage_residency=True):
        from . import gpu_lock as slot
        if not hasattr(slot,'child_environment'):
            raise RuntimeError('Finish the current job and reload Storylens to activate the GPU policy safely. No CPU fallback was started.')
        with slot.gpu_lock(self.root):
            return self._encode(texts,query,progress,manage_residency)

    def _encode(self, texts, query=False, progress=lambda _: None, manage_residency=True):
        from .model_preferences import release_ollama
        if manage_residency:
            release_ollama(self.root)
        result = []
        try:
            for start in range(0, len(texts), 4):
                batch = texts[start:start + 4]
                if query:
                    batch = ['Instruct: Given a search query, retrieve relevant passages.\nQuery: ' + text for text in batch]
                response = gpu_ollama_post(self.root, self.session, self.url + '/api/embed', json={
                    'model': self.model, 'input': batch, 'truncate': False,
                    'keep_alive': '30s', 'options': {'num_ctx': 4096, 'use_mmap': True}}, timeout=self.timeout)
                response.raise_for_status()
                rows = response.json()['embeddings']
                if len(rows) != len(batch):
                    raise ValueError('The embedding runtime returned an incomplete batch')
                vectors = np.asarray(rows, dtype=np.float32)
                if vectors.shape != (len(batch), self.dimensions) or not np.isfinite(vectors).all():
                    raise ValueError('The selected embedding model returned invalid vectors')
                vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)
                result.extend(vectors)
                progress(f'  Meaning index: {min(start + 4, len(texts))}/{len(texts)} sections')
            return np.asarray(result, np.float32).reshape((-1, self.dimensions))
        finally:
            if manage_residency:
                self.unload()

    def unload(self):
        try:
            self.session.post(self.url + '/api/generate', json={'model': self.model, 'keep_alive': 0}, timeout=60)
        except requests.RequestException:
            pass

    def close(self):
        self.unload()
        self.session.close()
