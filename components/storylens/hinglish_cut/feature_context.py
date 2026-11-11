"""Explicit feature budgets. Never change an untagged/publishing request.

Token counts cover the final messages and schema, with separate framing and
output reserves. No source, creator instructions or saved history is deleted.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from hinglish_publish.prepare_post_budget import ContextBudgetError as BaseBudgetError, ModelTokens


class ContextBudgetError(BaseBudgetError):
    def __init__(self, message):
        super().__init__('Feature context: '+message)


def policy(root):
    path = Path(root)/'config.context.local.json'
    if not path.is_file(): return {}
    value = json.loads(path.read_text('utf-8-sig'))
    if not isinstance(value, dict) or value.get('version') != 1:
        raise ContextBudgetError('The feature context configuration is invalid. Restore its saved configuration before retrying.')
    return value


def limits(root, feature, kind='text'):
    data = policy(root)
    if not isinstance(feature, str) or not feature or feature in data.get('deferred_features', []): return None
    row = data.get('features', {}).get(feature)
    if row is None: return None
    if kind not in ('text', 'vision') or kind not in row:
        raise ContextBudgetError(f'The {feature} feature does not use a {kind} model. Keep its configured text-only workflow.')
    base, maximum = row[kind], row.get(kind+'_max', row[kind])
    verified = data.get('model_limits', {}).get(kind, 0)
    if any(type(v) is not int for v in (base, maximum, verified)) or not 2048 <= base <= maximum <= verified:
        raise ContextBudgetError('This context exceeds the verified model configuration. Configure and validate YaRN separately before enabling an extended window.')
    model = row.get(kind+'_model',data.get('models', {}).get(kind))
    if not isinstance(model, str) or not model or model.endswith(':cloud'):
        raise ContextBudgetError('Choose the verified local model for this feature context.')
    return base, maximum, model


@lru_cache(maxsize=8)
def token_counter(root, model):
    return ModelTokens(root, model)


def configure(root, body, feature, *, kind='text', counter=None):
    selected = limits(root, feature, kind)
    if selected is None: return None
    base, maximum, model = selected
    if str(body.get('model', '')).removesuffix(':latest') != model.removesuffix(':latest'):
        raise ContextBudgetError('This feature context belongs to another model. Verify the selected model before retrying.')
    options = body.setdefault('options', {})
    output = options.get('num_predict')
    if type(output) is not int or not 0 < output < base:
        raise ContextBudgetError('Reserve a positive reply budget below the feature context limit.')
    receipt = {'feature': feature, 'model': model, 'kind': kind, 'context_limit': base,
               'output_reserved': output, 'framing_reserved': 512}
    if kind == 'vision':
        # Base64 length is NOT image token count. Keep the bounded frame batches;
        # report runtime prompt usage instead of inventing an exact image count.
        receipt['count_basis'] = 'vision capacity; image token usage measured by runtime'
    else:
        if any(m.get('images') for m in body.get('messages', [])):
            raise ContextBudgetError('Image input cannot be sent through this text-only feature context.')
        serialized = json.dumps({'messages': body.get('messages', []), 'format': body.get('format', {})},
                                ensure_ascii=False, separators=(',', ':'))
        count = counter or token_counter(str(Path(root).resolve()), model)
        tokens = count(serialized)
        if type(tokens) is not int or tokens < 0:
            raise ContextBudgetError('The local model token count is invalid; no inference was sent.')
        total = tokens + output + 512
        cap = base if total <= base else maximum
        if policy(root).get('features',{}).get(feature,{}).get('adaptive_context') is True:
            cap=min(maximum,max(base,((total+2047)//2048)*2048))
        receipt.update(input_tokens=tokens, total_reserved=total, context_limit=cap,
            payload_sha256=hashlib.sha256(serialized.encode()).hexdigest(),
            count_basis='selected-model tokens of complete messages+schema; separate framing allowance')
        if total > cap:
            raise ContextBudgetError(f'This {feature} step needs {total:,} tokens including its reply, beyond its {cap:,}-token context. '
                'Source and full creator guidance are preserved. Process the remaining source in overlapping sections; no oversized inference was sent.')
    options['num_ctx'] = receipt['context_limit']
    return receipt


def bind(brain, feature):
    """Tag an owned planner; injected test/third-party planners keep their API."""
    brain.context_feature = feature
    return brain


def history_options(root):
    return {'exchanges': 20, 'text_limit': None} if limits(root, 'assistant') else {}


def record(root, receipt):
    if receipt:
        from hinglish_app.durable_json import write
        path = Path(root)/'cache/app/context-budgets'/f"{receipt['feature']}-{receipt['kind']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, receipt)
