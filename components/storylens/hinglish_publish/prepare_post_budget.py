"""Scoped, offline model-token budgeting for Prepare/Post calls.

Count the final injected request envelope with the installed model vocabulary.
The count is exact for that serialized envelope, not Ollama's internal rendered
chat template; reserve additional framing headroom and the entire output budget.
No downloads, generation, model substitution or saved-guidance deletion.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from hinglish_app.durable_json import write


class ContextBudgetError(ValueError):
    pass


def model_file(model):
    name, separator, tag = model.rpartition(':')
    if not separator:name, tag = model, 'latest'
    parts = name.split('/')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', p) or p in ('.', '..') for p in [*parts, tag]):
        raise ContextBudgetError('The configured local model name cannot be resolved safely for token counting.')
    if len(parts) == 1:parts.insert(0, 'library')
    roots = [Path(os.environ['OLLAMA_MODELS'])] if os.environ.get('OLLAMA_MODELS') else []
    roots.append(Path.home()/'.ollama/models')
    for root in roots:
        for version, registry in (('manifests-v2', 'ollama.com'), ('manifests', 'registry.ollama.ai')):
            manifest = root/version/registry/Path(*parts)/tag
            if not manifest.is_file():continue
            data = json.loads(manifest.read_text('utf-8'))
            for layer in data.get('layers', []):
                digest = layer.get('digest', '')
                if layer.get('mediaType', '').endswith('.model') and re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
                    path = root/'blobs'/digest.replace(':', '-')
                    if path.is_file():return path.resolve()
    raise ContextBudgetError('The selected model’s local tokenizer is unavailable. Keep the saved stages and restore its installed model files; no model was downloaded or replaced.')


class ModelTokens:
    def __init__(self, root, model):
        from hinglish_cut.model_preferences import preferences
        native=preferences(root).get('publishing_native_runtime',{})
        self.native_tokenizer=None
        if native.get('enabled') and native.get('model')==model:
            from tokenizers import Tokenizer
            self.native_tokenizer=Tokenizer.from_file(str(Path(native['base'])/'tokenizer.json'))
            return
        self.executable = Path(root)/'tools/llama/b11011/llama-tokenize.exe'
        self.model = model_file(model)
        if not self.executable.is_file():
            raise ContextBudgetError('The local publishing token counter is unavailable. Restore the bundled tokenizer before retrying this saved stage.')

    @lru_cache(maxsize=48)
    def __call__(self, text):
        if self.native_tokenizer is not None:
            return len(self.native_tokenizer.encode(text,add_special_tokens=False).ids)
        result = subprocess.run([str(self.executable), '-m', str(self.model), '--stdin', '--ids', '--offline', '--no-bos'],
            input=text, encoding='utf-8', capture_output=True, timeout=30,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            ids = json.loads(result.stdout.strip())
            if result.returncode or not isinstance(ids, list) or any(type(i) is not int for i in ids):raise ValueError()
        except (ValueError, TypeError) as error:
            raise ContextBudgetError('The configured model’s token counter could not read this request. The source and full guidance are saved; no inference was sent.') from error
        return len(ids)


def request_budget(body, count, framing=512):
    """The caller supplies the actual, already injected/configured body."""
    payload = {'messages': body.get('messages', []), 'format': body.get('format', {})}
    serialized = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    input_tokens = count(serialized)
    output = body['options']['num_predict']
    cap = body['options']['num_ctx']
    if type(output) is not int or output < 1 or type(cap) is not int or cap < 1:
        raise ContextBudgetError('The publishing model needs a positive context and reply budget.')
    return {'input_tokens': input_tokens, 'output_reserved': output, 'framing_reserved': framing,
            'context_limit': cap, 'total_reserved': input_tokens+output+framing,
            'fits': input_tokens+output+framing <= cap,
            'payload_sha256': hashlib.sha256(serialized.encode()).hexdigest(),
            'count_basis': 'exact selected-model tokens of final messages+schema JSON; separate template/framing allowance'}


class PublishingBudget:
    def __init__(self, root, brain, folder, recorder, progress=lambda _: None, counter=None):
        self.root, self.brain, self.folder = Path(root), brain, Path(folder)
        (self.folder/'request-budgets').mkdir(parents=True, exist_ok=True)
        self.recorder, self.progress = recorder, progress
        self.counter = counter
        self.last = None
        self.preflight = None

    def count(self, text):
        if self.counter is None:self.counter = ModelTokens(self.root, self.brain.model)
        return self.counter(text)

    def configure(self, body, *, check=True):
        # Replace the legacy bytes/3 estimate only for this registered caller.
        # Preserve all messages, guidance and the normal GPU/memory policy.
        from hinglish_cut.model_preferences import configure_request, _publishing_budget, uploading_context
        token = _publishing_budget.set(False)
        try:
            with uploading_context():configure_request(self.root, body)
        finally:_publishing_budget.reset(token)
        if check:self(body)
        return body

    def preview(self, system, data, schema, options):
        from hinglish_aigen.direct import image_planning_context
        from hinglish_niche.profiles import inject
        from hinglish_cut.model_preferences import preferences
        system, data = image_planning_context(self.root, system, deepcopy(data), schema, self.brain.name)
        system, data = inject(system, data, root=self.root)
        policy = preferences(self.root)
        think = options.get('think')
        if think is None:think = bool(policy.get('planning_model') == self.brain.model and policy.get('planning_think'))
        body = {'model': self.brain.model, 'think': think, 'format': schema,
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(data, ensure_ascii=False, separators=(',', ':'))}],
                'options': {'num_ctx': 12288, 'num_predict': options.get('max_tokens', 2400)+(3000 if think else 0)}}
        self.configure(body, check=False)
        return request_budget(body, self.count)

    def __call__(self, body):
        self.last = request_budget(body, self.count)
        write(self.folder/'final-request-budget.json', self.last)
        write(self.folder/'request-budgets'/(self.last['payload_sha256']+'.json'), self.last)
        if not self.last['fits']:
            raise ContextBudgetError('This publishing step exceeds the selected model’s context after full creator guidance and reply space. Its source, guidance and completed stages are saved; no oversized inference was sent.')

    def prepare(self, system, data, schema, options):
        initial = self.preview(system, data, schema, options)
        self.preflight = initial
        write(self.folder/'request-budgets'/(initial['payload_sha256']+'.json'), initial)
        if initial['fits']:return data
        source_key = next((key for key in ('spoken_content', 'speech', 'transcript')
                           if isinstance(data, dict) and isinstance(data.get(key), str)), None)
        if source_key is None:
            raise ContextBudgetError('This step’s source and full guidance exceed the model context. Keep its saved inputs and split the unfinished step; no oversized inference was sent.')
        base = {**data, source_key: ''}
        if not self.preview(system, base, schema, options)['fits']:
            raise ContextBudgetError('The full creator guidance, schema and reply alone exceed this model’s context. They were kept unchanged; adjust the configured model/context before retrying.')
        from .prepare_post_source import source_quotes
        original = data[source_key]
        digest = hashlib.sha256(original.encode()).hexdigest()
        folder = self.folder/'budget-source'/digest
        folder.mkdir(parents=True, exist_ok=True)
        receipt = {'original_sha256': digest, 'original_budget': initial, 'rounds': [],
                   'full_guidance_preserved': True, 'method': 'hierarchical_verbatim_sentence_ids'}
        text = original
        for level in range(1, 5):
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]
            groups, group = [], []
            for sentence in sentences:
                if group and len(('\n'.join([*group, sentence])).encode()) > 4000:
                    groups.append('\n'.join(group));group = []
                group.append(sentence)
            if group:groups.append('\n'.join(group))
            reduced = []
            record = {'level': level, 'groups': []};receipt['rounds'].append(record)
            for number, group in enumerate(groups, 1):
                location = folder/f'round-{level}'
                location.mkdir(exist_ok=True)
                result = source_quotes(self.recorder, group, number, location, self.progress, max_sentences=2)
                reduced.extend(result['facts'])
                record['groups'].append({'number': number, 'source_sha256': result['source_sha256'],
                    'source_ids': result['source_ids'], 'artifact': str(location/f'source-context-v2-{number}.json')})
                write(folder/'reduction.json', receipt)
            smaller = '\n'.join(reduced)
            candidate = {**data, source_key: smaller}
            budget = self.preview(system, candidate, schema, options)
            record['budget'] = budget;write(folder/'reduction.json', receipt)
            if budget['fits']:
                self.preflight = budget
                return candidate
            if smaller == text:break
            text = smaller
        raise ContextBudgetError('The source could not be reduced enough within this step’s reply budget. Original speech, exact excerpt selections and full guidance are saved; retry the unfinished step with a shorter source or a suitable configured context.')
