"""The thinking model (Ollama, local) and the embedding model for the sound library vector index."""
import hashlib
import json
from pathlib import Path

import numpy as np
import requests

OLLAMA_URL = 'http://127.0.0.1:11434'
THINK_MODEL = 'qwen3:8b'                 # reasons step by step before answering
EMBED_MODEL = 'qwen3-embedding:0.6b'     # multilingual text embeddings for the vector index


class Brain:
    def __init__(self, root, model=THINK_MODEL, embed_model=EMBED_MODEL, url=OLLAMA_URL, progress=print):
        self.model, self.embed_model, self.url, self.progress = model, embed_model, url.rstrip('/'), progress
        self.cache = Path(root) / 'cache' / 'sound' / 'brain'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.trust_env = False
        from hinglish_visuals.brain import ollama_models
        names = ollama_models(self.session, self.url)
        missing = [m for m in (model, embed_model) if m not in names and m + ':latest' not in names]
        if missing:
            raise RuntimeError('Ollama is missing ' + ', '.join(missing) + '. Run: ollama pull ' + missing[0])

    def ask(self, system, data, schema, think=True, max_tokens=6000, label='Thinking'):
        """Structured answer (JSON schema). With think=True the model reasons first; its reasoning is kept."""
        spec = {'v': 2, 'model': self.model, 'system': system, 'data': data, 'schema': schema, 'think': think}
        key = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        file = self.cache / f'{key}.json'
        if file.exists():
            return json.loads(file.read_text(encoding='utf-8'))
        self.progress(f'  {label} (local {self.model}; this can take a few minutes on CPU)')
        body = {'model': self.model, 'stream': False, 'think': think, 'format': schema,
                'options': {'temperature': .3, 'seed': 7, 'num_ctx': 12288, 'num_predict': max_tokens},
                'messages': [{'role': 'system', 'content': system},
                             {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}]}
        response = self.session.post(self.url + '/api/chat', json=body, timeout=3600)
        response.raise_for_status()
        message = response.json().get('message', {})
        answer = json.loads(message.get('content') or '{}')
        answer['_thinking'] = (message.get('thinking') or '')[:6000]
        file.write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding='utf-8')
        return answer

    def embed(self, texts, batch=64):
        """Normalized embeddings, cached per text (the vector database of the library lives on these)."""
        out, todo = [None] * len(texts), []
        store = self.cache / 'embeddings'
        store.mkdir(exist_ok=True)
        keys = [hashlib.sha1((self.embed_model + '\n' + t).encode('utf-8')).hexdigest() for t in texts]
        for i, key in enumerate(keys):
            file = store / f'{key}.npy'
            if file.exists():
                out[i] = np.load(file)
            else:
                todo.append(i)
        for start in range(0, len(todo), batch):
            chunk = todo[start:start + batch]
            response = self.session.post(self.url + '/api/embed', json={'model': self.embed_model,
                                         'input': [texts[i] for i in chunk]}, timeout=600)
            response.raise_for_status()
            for i, vector in zip(chunk, response.json()['embeddings']):
                v = np.asarray(vector, np.float32)
                v /= max(np.linalg.norm(v), 1e-9)
                np.save(store / f'{keys[i]}.npy', v)
                out[i] = v
        return np.stack(out) if out else np.zeros((0, 1024), np.float32)
