"""The agent's brain: a local LLM that answers in JSON. No cloud inference.

Prefers the Ollama thinking model (qwen3:8b knows far more famous people, brands and history than
a 4B model) and falls back to the bundled llama.cpp Qwen that B-roll and Smart Zoom already use."""
import hashlib
from hinglish_cut.ollama_gpu import post as gpu_ollama_post
import json
from pathlib import Path

import requests

OLLAMA_URL = 'http://127.0.0.1:11434'


def check_response(response, model):
    if response.status_code < 400:return
    # Ollama's explanation is essential for diagnosis. Never expose the whole
    # request/history or silently accept a failed inference as a tool plan.
    try:detail=str(response.json().get('error') or '')
    except (ValueError,AttributeError):detail=''
    detail=' '.join(detail.split())[:700]
    raise RuntimeError(f'The local model {model} rejected this request (HTTP {response.status_code})'+
                       (': '+detail if detail else '. No tool action was started.'))


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
        from hinglish_cut.model_preferences import resolve_model
        model = resolve_model(root, 'planning_model', model, 'qwen3:8b')
        self.root = Path(root)
        self.model, self.url, self.progress = model, url.rstrip('/'), progress
        self.name = f'Ollama {model}'
        self.cache = Path(root) / 'cache' / 'visuals' / 'brain'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.trust_env = False
        from hinglish_cut.model_preferences import preferences
        from hinglish_cut.publishing_native import selected
        if selected(preferences(root),{'model':model}):
            self.name=f'Native trained {model}'
            return
        try:
            names = ollama_models(self.session, self.url, tries=1, timeout=3)
        except RuntimeError:
            from hinglish_cut.local_runtime import ensure
            if not ensure(root, self.session, self.url):
                self.session.close()
                raise
            names = ollama_models(self.session, self.url)
        if model not in names and model + ':latest' not in names:
            raise RuntimeError(f'Ollama is missing {model} (run: ollama pull {model})')

    def json(self, system, data, schema, max_tokens=2400, think=None):
        from hinglish_aigen.direct import image_planning_context
        system,data=image_planning_context(self.root,system,data,schema,self.name)
        from hinglish_cut.model_preferences import preferences
        local = preferences(self.root)
        if think is None:
            think=bool(local.get('planning_model')==self.model and local.get('planning_think'))
        from hinglish_niche.profiles import inject
        system, data = inject(system, data, root=self.root)
        spec = {'v': 1, 'model': self.model, 'system': system, 'data': data, 'schema': schema, 'think': think}
        from hinglish_cut.feature_context import limits, configure as feature_context, record as record_context
        feature = getattr(self, 'context_feature', None)
        context_limits = limits(self.root, feature) if isinstance(feature, str) else None
        if context_limits and vars(self).get('request_guard') is None:
            spec['feature_context'] = [feature, *context_limits]
        key = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        file = self.cache / f'{key}.json'
        self.last_cache_file = file
        required=schema.get('required',[])
        def complete(answer):
            return isinstance(answer,dict) and all(k in answer for k in required)
        incomplete_cache=False
        if file.exists() and getattr(self,'cache_enabled',True):
            try:cached=json.loads(file.read_text(encoding='utf-8'))
            except (ValueError,OSError):cached={}
            if complete(cached):
                self.last_usage={'cache_hit':True}
                return cached
            incomplete_cache=True
        body = {'model': self.model, 'stream': False, 'think': think, 'format': schema,
                # thinking is capped so a CPU-only laptop still finishes in minutes, not hours
                'options': {'temperature': .2, 'seed': 7, 'num_ctx': 12288,
                            'num_predict': max_tokens + (3000 if think else 0)},
                'messages': [{'role': 'system', 'content': system},
                             {'role': 'user', 'content': json.dumps(data, ensure_ascii=False,separators=(',',':'))}]}
        import time
        from hinglish_cut.model_preferences import configure_request
        request_guard = vars(self).get('request_guard')
        if request_guard is not None:
            request_guard.configure(body)
        else:
            configure_request(self.root, body)
            self.last_context_budget = feature_context(self.root, body, feature)
            record_context(self.root, self.last_context_budget)
        if incomplete_cache and think:
            body.update(think=False)
            body['options']['num_predict']=max_tokens
        attempts=getattr(self,'request_attempts',3)
        streaming=getattr(self,'reply_progress',None) if set(required)=={'reply'} and not body['think'] else None
        timeout = getattr(self,'request_timeout',3600)
        if context_limits: timeout = max(timeout, 3600)
        # A publishing selection retry can bypass the chat-template PEG parser
        # while retaining the exact model, system/user context and JSON schema.
        # This is only selected after a recorded decoder failure, not a new model.
        generate_recovery = (set(required) == {'shorts'} and
            self.model.startswith('storylens-publishing:') and isinstance(data, dict) and
            'peg-native format' in str(data.get('previous_format_error', '')))
        endpoint = self.url + ('/api/generate' if generate_recovery else '/api/chat')
        wire_body = body
        if generate_recovery:
            wire_body = {k:v for k,v in body.items() if k != 'messages'}
            wire_body.update(system=body['messages'][0]['content'], prompt=body['messages'][1]['content'])
            # Avoid the failing schema decoder, but enforce that SAME schema
            # locally before accepting or caching any model answer.
            wire_body['format'] = 'json'
            wire_body['system'] += '\nReturn only one JSON object satisfying this exact schema: ' + json.dumps(schema)
        for attempt in range(attempts):
            streaming_options={'on_content':streaming} if callable(streaming) else {}
            response = gpu_ollama_post(self.root, self.session, endpoint, json=wire_body, timeout=timeout, **streaming_options)
            if response.status_code>=500 and 'peg-native format' in response.text:
                # A structured-output decoder failure is not a transient GPU
                # outage. Replaying it three times only hides the real error.
                break
            if response.status_code < 500 or attempt == attempts-1:
                break
            # Ollama's GPU runner can crash on small cards (it restarts itself): wait and ask again
            self.progress(f'  The Ollama model stopped unexpectedly; retrying ({attempt + 1}/2)')
            time.sleep(8 * (attempt + 1))
        check_response(response,self.model)
        self.last_usage={'cache_hit':False,'context_limit':body['options']['num_ctx'],
            'transport':'generate_schema_recovery' if generate_recovery else 'chat',
            'input_tokens':response.json().get('prompt_eval_count'),
            'output_tokens':response.json().get('eval_count')}
        message = response.json().get('message', {})
        if generate_recovery: message = {'content': response.json().get('response', '')}
        answer = json.loads(message.get('content') or '{}')
        if generate_recovery:
            from jsonschema import validate
            from jsonschema.exceptions import ValidationError
            try:
                validate(answer, schema)
            except ValidationError as error:
                feedback = 'At ' + '/'.join(map(str,error.absolute_path)) + ': ' + error.message
                self.progress('Correcting the local model output: ' + feedback[:180])
                corrected = dict(wire_body)
                corrected['prompt'] = wire_body['prompt'] + '\nYour previous JSON: ' + json.dumps(answer) + '\nFix this validation error: ' + feedback + '\nReturn the entire corrected JSON object; keep all required fields.'
                response = gpu_ollama_post(self.root,self.session,endpoint,json=corrected,timeout=timeout)
                check_response(response,self.model)
                answer = json.loads(response.json().get('response') or '{}')
                validate(answer, schema)
                self.last_usage.update(validation_feedback=feedback,validation_recovery=True,
                    output_tokens=response.json().get('eval_count'))
        if not complete(answer) and body['think']:
            self.progress('  The local model returned no complete tool answer; retrying once with bounded JSON output')
            body.update(think=False)
            body['options']['num_predict']=max_tokens
            response=gpu_ollama_post(self.root, self.session, self.url+'/api/chat',json=body,timeout=timeout)
            check_response(response,self.model)
            message=response.json().get('message',{})
            answer=json.loads(message.get('content') or '{}')
        if not complete(answer):
            raise RuntimeError('The local model did not return the required structured answer. No empty result was accepted; retry the request.')
        if body['think'] and message.get('thinking'):
            answer['_thinking'] = message['thinking'][:6000]
        if getattr(self,'cache_enabled',True):
            from hinglish_clean.detection import write_json
            write_json(file,answer)
        return answer

    def close(self):
        self.session.close()


class LocalBrain:
    """The bundled llama.cpp Qwen (same model B-roll uses); `think` is ignored, schemas carry a reasoning field."""

    def __init__(self, root, threads=4):
        self.root = Path(root)
        from hinglish_broll.llm import LocalLLM
        self.llm = LocalLLM(root, threads=threads)
        self.name = 'local Qwen'

    def json(self, system, data, schema, max_tokens=2400, think=False):
        from hinglish_aigen.direct import image_planning_context
        system,data=image_planning_context(self.root,system,data,schema,self.name)
        return self.llm.json(system, data, schema, max_tokens=max_tokens)

    def close(self):
        self.llm.close()


def open_brain(root, choice='auto', model='qwen3:8b', threads=4, progress=print):
    from hinglish_cut.model_preferences import preferences
    gpu_required = preferences(root).get('require_cuda_inference') is True
    if gpu_required and choice not in ('auto', 'ollama'):
        raise RuntimeError('GPU inference is required. Choose the configured local Ollama model; the unverified CPU fallback is disabled.')
    if choice in ('auto', 'ollama'):
        try:
            return OllamaBrain(root, model, progress=progress)
        except RuntimeError as error:
            if gpu_required:
                raise RuntimeError(f'GPU inference is required. {error}. Restore the local Ollama runtime and retry; CPU fallback is disabled.') from error
            if choice == 'ollama':
                raise RuntimeError(f'{error}. Start the Ollama app or choose the built-in brain.') from error
            progress(f'  {error}; using the built-in local model instead')
    return LocalBrain(root, threads)
