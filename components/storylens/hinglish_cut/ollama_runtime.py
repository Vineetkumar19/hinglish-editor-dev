"""Ollama's local OpenAI endpoint for the pinned GGUF semantic model."""
import requests

URL = 'http://127.0.0.1:11434'


def start(manifest):
    name = manifest.get('ollama_model')
    if not isinstance(name, str) or not name or name.endswith(':cloud'):
        raise ValueError('The semantic runtime requires a local Ollama model')
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(URL + '/api/tags', timeout=15)
        response.raise_for_status()
        if name not in {row['name'] for row in response.json().get('models', [])}:
            raise ValueError('The imported semantic model is missing from Ollama: ' + name)
    except Exception:
        session.close()
        raise
    return session, URL


def completion(manifest, body):
    body = dict(body)
    schema = body['response_format']['schema']
    body['model'] = manifest['ollama_model']
    body['response_format'] = {'type': 'json_schema', 'json_schema': {
        'name': 'storylens_result', 'strict': True, 'schema': schema}}
    return body


def close(session, manifest):
    if session is None:
        return
    try:
        session.post(URL + '/api/generate', json={'model': manifest['ollama_model'], 'keep_alive': 0}, timeout=60).raise_for_status()
    except requests.RequestException:
        pass
