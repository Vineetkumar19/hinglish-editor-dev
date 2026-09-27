"""The agent's brain: a local LLM that answers in JSON. No cloud inference.

Prefers the Ollama thinking model (qwen3:8b knows far more famous people, brands and history than
a 4B model) and falls back to the bundled llama.cpp Qwen that B-roll and Smart Zoom already use."""
import hashlib
import json
from pathlib import Path

import requests

OLLAMA_URL = 'http://127.0.0.1:11434'


def ollama_models(session, url, tries=3, timeout=20):
    """Installed Ollama models. Patient on purpose: while a model is thinking on the CPU, Ollama can take
    many seconds to answer, and a short timeout wrongly reported "not running"."""
    import time
    last = None
    for n in range(tries):
        try:
            return {m['name'] for m in session.get(url + '/api/tags', timeout=timeout).json().get('models', [])}
        except (requests.RequestException, ValueError) as error:
            last = error
            time.sleep(2 * (n + 1))
    raise RuntimeError('Ollama is not running (start the Ollama app)') from last


class OllamaBrain:
    def __init__(self, root, model, url=OLLAMA_URL, progress=print):
        self.model, self.url, self.progress = model, url.rstrip('/'), progress
        self.name = f'Ollama {model}'
        self.cache = Path(root) / 'cache' / 'visuals' / 'brain'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.trust_env = False
        names = ollama_models(self.session, self.url)
        if model not in names and model + ':latest' not in names:
            raise RuntimeError(f'Ollama is missing {model} (run: ollama pull {model})')

    def json(self, system, data, schema, max_tokens=2400, think=False):
        spec = {'v': 1, 'model': self.model, 'system': system, 'data': data, 'schema': schema, 'think': think}
        key = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        file = self.cache / f'{key}.json'
        if file.exists():
            return json.loads(file.read_text(encoding='utf-8'))
        body = {'model': self.model, 'stream': False, 'think': think, 'format': schema,
                # thinking is capped so a CPU-only laptop still finishes in minutes, not hours
                'options': {'temperature': .2, 'seed': 7, 'num_ctx': 12288,
                            'num_predict': max_tokens + (3000 if think else 0)},
                'messages': [{'role': 'system', 'content': system},
                             {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}]}
        response = self.session.post(self.url + '/api/chat', json=body, timeout=3600)
        response.raise_for_status()
        message = response.json().get('message', {})
        answer = json.loads(message.get('content') or '{}')
        if think and message.get('thinking'):
            answer['_thinking'] = message['thinking'][:6000]
        file.write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding='utf-8')
        return answer

    def close(self):
        self.session.close()


class LocalBrain:
    """The bundled llama.cpp Qwen (same model B-roll uses); `think` is ignored, schemas carry a reasoning field."""

    def __init__(self, root, threads=4):
        from hinglish_broll.llm import LocalLLM
        self.llm = LocalLLM(root, threads=threads)
        self.name = 'local Qwen (llama.cpp)'

    def json(self, system, data, schema, max_tokens=2400, think=False):
        return self.llm.json(system, data, schema, max_tokens=max_tokens)

    def close(self):
        self.llm.close()


def open_brain(root, choice='auto', model='qwen3:8b', threads=4, progress=print):
    if choice in ('auto', 'ollama'):
        try:
            return OllamaBrain(root, model, progress=progress)
        except RuntimeError as error:
            if choice == 'ollama':
                raise RuntimeError(f'{error}. Start the Ollama app or choose the built-in brain.') from error
            progress(f'  {error}; using the built-in local model instead')
    return LocalBrain(root, threads)
