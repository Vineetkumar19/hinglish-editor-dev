"""Optional per-computer Ollama choices; explicit per-feature models take priority."""
import json
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar

_publishing_budget = ContextVar('publishing_model_memory_budget', default=False)
_uploading_context = ContextVar('uploading_model_context', default=False)


@contextmanager
def uploading_context():
    """Full installed native context for the uploading feature only."""
    token = _uploading_context.set(True)
    try:
        yield
    finally:
        _uploading_context.reset(token)


@contextmanager
def publishing_memory_budget():
    """Scope a conservative GPU/context budget to this publishing task only."""
    token = _publishing_budget.set(True)
    try:
        yield
    finally:
        _publishing_budget.reset(token)


def preferences(root):
    path = Path(root) / 'config.models.local.json'
    data = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    if not isinstance(data, dict):
        raise ValueError('Local model preferences must be a JSON object')
    from .model_storage import role
    for name,keys in {'planner':('planning_model','vision_model'),'vision':('vision_model',),
                      'meaning':('meaning_model',),'embedding':('embedding_model',)}.items():
        selected=role(root,name)
        if selected:
            data.update({key:selected['ollama_model'] for key in keys})
    return data


def resolve_model(root, role, requested, legacy_default):
    if requested != legacy_default:
        return requested
    name = preferences(root).get(role, requested)
    if not isinstance(name, str) or not name.strip() or name.endswith(':cloud'):
        raise ValueError('Choose a nonempty local Ollama model name')
    return name


def preferred_device(root):
    device = preferences(root).get('device', 'cpu')
    if device not in ('cpu', 'cuda'):
        raise ValueError('Local device must be cpu or cuda')
    return device


def configure_request(root, body):
    """Bound context memory without dropping any messages or changing embeddings."""
    from .creative_memory import configure as creative_context
    creative_context(root, body)
    data = preferences(root)
    if not data:
        return body
    options = dict(body.get('options', {}))
    cap = data.get('context_limit', 8192)
    if type(cap) is not int or not 2048 <= cap <= 32768:
        raise ValueError('context_limit must be between 2048 and 32768')
    options['num_ctx'] = min(options.get('num_ctx', cap), cap)
    if _publishing_budget.get() and body.get('messages'):
        # The caller has already injected complete creator guidance. Size that
        # exact payload; never remove messages to make a smaller cache fit.
        payload = {'messages': body['messages'], 'format': body.get('format', {})}
        required = (len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))+2)//3
        required += options.get('num_predict', 1000) + 512
        if required > cap:
            raise ValueError('The publishing model input exceeds its configured context. The request and full saved guidance are preserved; no upload started.')
        options['num_ctx'] = min(cap, max(4096, ((required+1023)//1024)*1024))
        # Keep the selected 14B local model while leaving GPU cache/compute
        # headroom on the owner's laptop. This is not a global model change.
        options['num_gpu'] = 28
    if _uploading_context.get() and data.get('publishing_context_limit'):
        upload_cap = data['publishing_context_limit']
        if type(upload_cap) is not int or not 2048 <= upload_cap <= 1048576:
            raise ValueError('Choose a valid installed native publishing context limit.')
        if body.get('model') != data.get('publishing_context_model'):
            raise ValueError('The uploading context belongs to another model. Verify this model’s native context before changing it.')
        options['num_ctx'] = upload_cap
    # A machine-level CUDA choice takes priority over the older Publisher cap.
    # -1 lets Ollama place as many layers as the available VRAM can hold.
    # Keep context sizing above: GPU allocation must not drop saved guidance.
    if data.get('device') == 'cuda' and 'ollama_num_gpu' in data:
        layers = data['ollama_num_gpu']
        if type(layers) is not int or layers < -1 or layers == 0:
            raise ValueError('Choose automatic GPU allocation (-1) or a positive GPU layer count.')
        options['num_gpu'] = layers
    body['options'] = options
    body['keep_alive'] = data.get('keep_alive', '30s')
    # Newer multimodal Qwen models can think by default. Pixel checks require
    # their short schema answer, and already-explicit planning choices are kept.
    body.setdefault('think', False)
    return body


def release_ollama(root, keep=None):
    """Free this project's idle Ollama models before another CUDA engine starts."""
    data = preferences(root)
    if not data.get('release_ollama_before_cuda', False):
        return
    names = {data.get('planning_model'), data.get('vision_model'), data.get('embedding_model'),
             data.get('meaning_model'), 'qwen3:8b', 'qwen3-embedding:0.6b', 'storylens-meaning:4b'}
    try:
        import requests
        with requests.Session() as session:
            session.trust_env = False
            loaded = session.get('http://127.0.0.1:11434/api/ps', timeout=5).json().get('models', [])
            for model in loaded:
                if model.get('name') in names and model.get('name') != keep:
                    response = session.post('http://127.0.0.1:11434/api/generate',
                                            json={'model': model['name'], 'keep_alive': 0}, timeout=60)
                    response.raise_for_status()
    except (requests.RequestException, ValueError):
        # Ollama is optional for the speech and bundled llama.cpp engines.
        pass
