"""The thinking model (Ollama, local) and the embedding model for the sound library vector index."""
import hashlib
import json
from pathlib import Path

import numpy as np
import requests

OLLAMA_URL = 'http://127.0.0.1:11434'
THINK_MODEL = 'qwen3:8b'                 # reasons step by step before answering
EMBED_MODEL = 'qwen3-embedding:0.6b'     # multilingual text embeddings for the vector index


def compact_sound_request(body):
    """Per-call fallback only: preserve creator/evidence; saved memory is never edited."""
    import copy
    result=copy.deepcopy(body)
    markers=('[Storylens sound reference study]','[Storylens creative reference memory]',
             '[Storylens ReelMimic reference]')
    def prose(text):
        for marker in markers:
            pos=text.find(marker)
            if pos<0:continue
            start=text.find('{',pos+len(marker))
            if start<0:continue
            try:_,length=json.JSONDecoder().raw_decode(text[start:])
            except ValueError:continue
            text=text[:pos]+text[start+length:]
        return text
    optional={'reference_study','script_led_examples','documentary_sound_examples'}
    def trim(value):
        if isinstance(value,dict):
            return {k:(v if k=='creator_profile' else trim(v)) for k,v in value.items() if k not in optional}
        if isinstance(value,list):return [trim(v) for v in value]
        return value
    for message in result.get('messages',[]):
        if message.get('role')=='system':message['content']=prose(message['content'])
        elif message.get('role')=='user':
            try:message['content']=json.dumps(trim(json.loads(message['content'])),ensure_ascii=False)
            except (ValueError,TypeError):pass
    return result


def fit_sound_request(body):
    """Fit ephemeral context before HTTP; keep source evidence and the full profile."""
    import copy
    result=copy.deepcopy(body)
    cap=int(result.get('options',{}).get('num_ctx',12288))
    requested=int(result.get('options',{}).get('num_predict',6000))
    def estimate(value):
        payload=[value.get('messages',[]),value.get('format',{})]
        return (len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8'))+2)//3+128
    tokens=estimate(result)
    if tokens+requested+256>cap:
        result=compact_sound_request(result)
        tokens=estimate(result)
    if tokens>cap-512:
        raise ValueError('Sound planning contains too much required information for the local model. '
                         'Your source and full creator instructions are kept. Use a shorter video or a model with a larger context.')
    # Ollama can roll its context during generation. Preserve the requested
    # structured-answer budget; a small leftover window can truncate valid JSON.
    return result,result.get('messages')!=body.get('messages')


class Brain:
    def __init__(self, root, model=THINK_MODEL, embed_model=EMBED_MODEL, url=OLLAMA_URL, progress=print):
        from hinglish_cut.model_preferences import resolve_model
        model = resolve_model(root, 'planning_model', model, THINK_MODEL)
        embed_model = resolve_model(root, 'embedding_model', embed_model, EMBED_MODEL)
        self.root = Path(root)
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
        from hinglish_cut.model_preferences import preferences
        think=bool(think and preferences(self.root).get('planning_think',True))
        from hinglish_niche.profiles import inject
        system, data = inject(system, data, root=self.root)
        from .reference_memory import inject as sound_reference_context
        system = sound_reference_context(system, data, self.root, feature='sound')
        spec = {'v': 2, 'model': self.model, 'system': system, 'data': data, 'schema': schema, 'think': think}
        from hinglish_cut.feature_context import limits, configure as feature_context, record as record_context
        context_limits=limits(self.root,'sound')
        if context_limits:spec['feature_context']=context_limits
        key = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        file = self.cache / f'{key}.json'
        if file.exists():
            return json.loads(file.read_text(encoding='utf-8'))
        self.progress(f'  {label} (local {self.model}; this can take a few minutes on CPU)')
        body = {'model': self.model, 'stream': False, 'think': think, 'format': schema,
                'options': {'temperature': .3, 'seed': 7, 'num_ctx': 12288, 'num_predict': max_tokens},
                'messages': [{'role': 'system', 'content': system},
                             {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}]}
        from hinglish_cut.model_preferences import configure_request
        configure_request(self.root, body)
        if context_limits:
            # Apply the owner-approved optional-prose fallback before allocating
            # a larger RAM-offloaded context. Required source/profile stays intact.
            body['options']['num_ctx']=context_limits[0]
            try:
                body,compacted=fit_sound_request(body)
            except ValueError:
                reduced=compact_sound_request(body)
                compacted=reduced.get('messages')!=body.get('messages')
                body=reduced
            self.last_context_budget=feature_context(self.root,body,'sound')
            record_context(self.root,self.last_context_budget)
        else:
            body,compacted=fit_sound_request(body)
        if compacted:self.progress('Preparing a smaller planning request; your source and full creator instructions are kept.')
        response = self.session.post(self.url + '/api/chat', json=body, timeout=3600)
        from hinglish_visuals.brain import check_response
        if response.status_code==400:
            try:reason=str(response.json().get('error','')).casefold()
            except (ValueError,AttributeError):reason=''
            if 'context' in reason and ('exceed' in reason or 'too long' in reason):
                reduced=compact_sound_request(body)
                if reduced!=body:
                    self.progress('Preparing the local request with less optional reference text; your source and full creator instructions are kept.')
                    body=reduced;compacted=True
                    response=self.session.post(self.url+'/api/chat',json=body,timeout=3600)
        check_response(response,self.model)
        message = response.json().get('message', {})
        answer = json.loads(message.get('content') or '{}')
        answer['_thinking'] = (message.get('thinking') or '')[:6000]
        if compacted:answer['_request_context']='Optional retrieved prose omitted for this call; creator profile and evidence retained; saved knowledge unchanged'
        file.write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding='utf-8')
        return answer

    def embed(self, texts, batch=64):
        """Normalized embeddings, cached per text (the vector database of the library lives on these)."""
        from hinglish_cut.model_storage import role
        selected = role(self.root, 'embedding')
        if selected and self.embed_model == selected.get('ollama_model'):
            from hinglish_cut.ollama_embeddings import OllamaEmbeddings
            from hinglish_cut.upgrade_embeddings import StagedEmbeddings
            from hinglish_cut.model_storage import configuration
            from hinglish_cut.model_preferences import release_ollama
            store = Path(configuration(self.root).get('root', self.root))
            encoder = StagedEmbeddings(store/'cache/sound-description-embeddings.sqlite3',
                OllamaEmbeddings(self.root, self.embed_model), selected['revision'])
            try:
                release_ollama(self.root, keep=self.embed_model)
                return encoder.encode(texts)
            finally:
                encoder.close()
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
