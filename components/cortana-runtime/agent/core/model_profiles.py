"""Explicit model choice with admission, probes, and no silent escalation."""
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import httpx
import psutil
from core import local_store as store
from core.config import settings, ROOT_DIR
from core.tasks import check_cancelled

_lock = threading.RLock()
_gpu_options = {}


class ModelAdmissionError(ValueError):
    """The shared machine cannot admit the requested model right now."""


PROFILES = {
    'local_9b_q4': {'tag': 'cortana-local:9b-q4', 'source': 'qwen3.5:9b-q4_K_M', 'size': '9', 'quant': 'Q4'},
    'local_14b_q4': {'tag': 'cortana-local:14b-q4', 'source': 'storylens-meaning:14b', 'size': '14', 'quant': 'Q4'},
    'local_vision': {'tag': 'cortana-local:vision', 'source': 'qwen3-vl:8b-instruct-q4_K_M', 'size': '8', 'quant': 'Q4'},
}


def _client(timeout=120):
    return httpx.Client(base_url=settings.ollama_host, timeout=timeout, trust_env=False)


def inventory():
    with _client() as client:
        tags = client.get('/api/tags'); tags.raise_for_status()
        running = client.get('/api/ps'); running.raise_for_status()
        version = client.get('/api/version'); version.raise_for_status()
    installed = {m['name']: m for m in tags.json()['models']}
    return {'profiles': {name: {**profile, 'installed': profile['tag'] in installed,
                'metadata': installed.get(profile['tag']), 'source_installed': profile.get('source') in installed}
            for name, profile in PROFILES.items()}, 'loaded': running.json().get('models', []),
            'runtime_version': version.json(), 'selected_model': settings.ollama_model,
            'available_ram_bytes': psutil.virtual_memory().available, 'cloud_enabled': False}


def _free_gpu_mib():
    binary = shutil.which('nvidia-smi')
    if not binary:
        return 0
    try:
        result = subprocess.run([binary, '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, check=True, timeout=2,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        # Only the single NVIDIA GPU configuration has been measured.
        return int(result.stdout.strip())
    except (ValueError, OSError, subprocess.SubprocessError):
        return 0


def admit(target, client, *, voice_pair=False):
    check_cancelled()
    response = client.get('/api/ps'); response.raise_for_status()
    owned = {p['tag'] for p in PROFILES.values()} | {'cortana-local:9b','cortana-local:embedding'}
    loaded = response.json().get('models', [])
    foreign = [m['name'] for m in loaded if m['name'] not in owned]
    if foreign:
        raise ModelAdmissionError('Waiting for other local model workloads to finish. Cortana will not unload them: ' + ', '.join(foreign))
    # This owner-controlled flag can be used by another task without killing work.
    if (ROOT_DIR / 'memory' / 'pause_model_work').exists():
        raise ModelAdmissionError('Model work is paused for the shared GPU. Local file/workspace commands remain available.')
    resident = any(m['name'] == target for m in loaded)
    if target == 'cortana-speech':
        from core import stt
        resident = stt.gpu_model_loaded()
    if not resident and psutil.virtual_memory().available < 1024 ** 3:
        raise ModelAdmissionError('Less than 1 GiB RAM is available. Save/close other work before loading a model.')
    keep = {target}
    if voice_pair and target == 'cortana-speech':
        from core import stt
        tag = PROFILES['local_9b_q4']['tag']
        ready = next((m for m in loaded if m['name'] == tag and m.get('size') == m.get('size_vram')), None)
        if ready and _free_gpu_mib() >= (768 if stt.gpu_model_loaded() else 2600):
            keep.add(tag)
    for model in loaded:
        if model['name'] not in keep:
            client.post('/api/generate', json={'model': model['name'], 'keep_alive': 0}).raise_for_status()
    return loaded


def initialize_selection():
    try:
        selected = store.get('model_selection', 'current')['profile']
    except ValueError:
        selected = 'local_9b_q4'
    settings.ollama_model = PROFILES[selected]['tag']
    settings.ollama_vision_model = PROFILES['local_vision']['tag']
    settings.ollama_num_ctx = 4096
    # The broker retains the lease until owned warm weights are released.
    settings.ollama_keep_alive = '75s'


def reviewed_license(tag, metadata, details):
    if details.get('license'):
        return details['license']
    path=ROOT_DIR/'config/model-provenance.json'
    if not path.exists():
        return None
    record=json.loads(path.read_text(encoding='utf-8')).get(tag,{})
    if (record.get('manifest_digest')==metadata.get('digest') and record.get('weight_sha256')
            and 'sha256-'+record['weight_sha256'] in details.get('modelfile','')):
        return record['license']+'; '+record['license_source']+'; source revision '+record['source_revision']
    return None


def _observe_residency(stop, samples, target):
    with httpx.Client(base_url=settings.ollama_host,timeout=3,trust_env=False) as client:
        while not stop.is_set():
            try:
                response=client.get('/api/ps'); response.raise_for_status()
                match=next((model for model in response.json().get('models',[]) if model['name']==target),None)
                if match:
                    samples.append({'at':time.time(),'available_ram_bytes':psutil.virtual_memory().available,
                        **{key:match.get(key) for key in ('name','digest','size','size_vram','context_length')}})
                    del samples[:-120]
            except (httpx.HTTPError,ValueError):
                pass
            stop.wait(.25)


def switch_profile(profile):
    if profile not in {'local_9b_q4', 'local_14b_q4'}:
        raise ValueError('Choose local_9b_q4 or local_14b_q4. Cloud remains disabled.')
    from core.resource_broker import gpu_slot
    with gpu_slot(), _lock, _client() as client:
        info = inventory()
        wanted = info['profiles'][profile]
        if not wanted['installed']:
            raise ValueError(f"{wanted['tag']} is not installed. No model choice was changed.")
        detail = client.post('/api/show', json={'model': wanted['tag']}); detail.raise_for_status()
        detail = detail.json()
        metadata = detail.get('details', {})
        if not metadata.get('parameter_size', '').startswith(wanted['size']) or not metadata.get('quantization_level', '').startswith('Q4'):
            raise ValueError('Installed model size/quantization does not match the requested profile.')
        license_text=reviewed_license(wanted['tag'],wanted['metadata'],detail)
        if 'tools' not in detail.get('capabilities', []) or not license_text:
            raise ValueError('Model tool support or license metadata is missing; profile admission is incomplete.')
        old = settings.ollama_model
        transaction = store.put('model_switch', {'from': old, 'to': wanted['tag'], 'state': 'checkpointed'})
        start = time.monotonic()
        observations, stopped = [], threading.Event()
        observer = None
        try:
            admit(wanted['tag'], client)
            gpu_options = prepare_inference(wanted['tag'])
            check_cancelled()
            observer = threading.Thread(target=_observe_residency,args=(stopped,observations,wanted['tag']),daemon=True)
            observer.start()
            probe = client.post('/api/chat', json={'model': wanted['tag'], 'stream': False, 'think': False,
                'keep_alive': 0, 'options': {'num_ctx': 4096, 'num_predict': 80, 'temperature': 0, **gpu_options},
                'messages': [{'role': 'user', 'content': 'Call capability_probe with value exactly cortana_probe. Do not answer in prose.'}],
                'tools': [{'type':'function','function':{'name':'capability_probe','description':'Non-executing probe.',
                    'parameters':{'type':'object','properties':{'value':{'type':'string'}},'required':['value']}}}]})
            probe.raise_for_status()
            stopped.set(); observer.join(timeout=4)
            calls = probe.json().get('message', {}).get('tool_calls', [])
            function = calls[0].get('function', {}) if len(calls) == 1 else {}
            if function.get('name') != 'capability_probe' or function.get('arguments') != {'value':'cortana_probe'}:
                raise ValueError('The exact tool-call capability probe failed.')
            check_cancelled()
            transaction.update(state='completed', elapsed_seconds=time.monotonic()-start,
                digest=wanted['metadata']['digest'], quantization=metadata['quantization_level'],
                license=license_text[:1000], loaded_after_release=inventory()['loaded'],
                load_duration_ns=probe.json().get('load_duration'), eval_duration_ns=probe.json().get('eval_duration'),
                residency_observations=observations, residency_status='observed' if observations else 'not_observed',
                probe='exact tool call passed')
            check_cancelled()
            with store.connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                store.put_in_transaction(conn, 'model_selection', {'profile': profile, 'tag': wanted['tag']}, 'current')
                transaction = store.put_in_transaction(conn, 'model_switch', transaction, transaction['id'], transaction['revision'])
            settings.ollama_model = wanted['tag']
        except BaseException as exc:
            transaction.update(state='failed', error=str(exc)[:400], previous_profile=old,
                note='Previous choice retained; it may need reloading. No automatic fallback was performed.')
            store.put('model_switch', transaction, transaction['id'], transaction['revision'])
            raise
        finally:
            stopped.set()
            if observer:
                observer.join(timeout=4)
        return transaction


def prepare_inference(target):
    with _lock, _client(timeout=2 if target == 'cortana-speech' else 120) as client:
        voice_pair = (settings.stt_device == 'cuda' and
                      settings.stt_model_size == settings.stt_wake_model_size == 'large-v3-turbo' and
                      settings.ollama_model == PROFILES['local_9b_q4']['tag'])
        loaded = admit(target, client, voice_pair=voice_pair)
        if target == 'cortana-speech':
            return {}
        # One reasoning/vision runner at a time. Keep the speech specialist
        # resident beside 9B only when measured headroom supports the pair.
        from core import stt
        if stt.gpu_model_loaded():
            is_9b = target == PROFILES['local_9b_q4']['tag']
            already_loaded = any(m['name'] == target and m.get('size') == m.get('size_vram') for m in loaded)
            if not (voice_pair and is_9b and _free_gpu_mib() >= (768 if already_loaded else 6400)):
                stt._release_gpu_models()
        if target == PROFILES['local_14b_q4']['tag']:
            # The explicitly selected 14B profile may use partial CPU offload.
            return {'num_batch':64}
        if target not in _gpu_options:
            response = client.post('/api/show', json={'model':target})
            response.raise_for_status()
            info = response.json().get('model_info', {})
            blocks = info.get(str(info.get('general.architecture')) + '.block_count')
            if type(blocks) is not int or not 1 <= blocks <= 256:
                raise ValueError('Cannot verify the selected model GPU layers. No CPU fallback was started.')
            _gpu_options[target] = {'num_gpu':blocks + 1, 'num_batch':64}
        return dict(_gpu_options[target])


async def ensure_gpu_residency(client, model, options, keep_alive):
    """Prove placement before generating a potentially long spoken answer."""
    async def resident():
        response = await client.get(settings.ollama_host + '/api/ps', timeout=5)
        response.raise_for_status()
        return next((row for row in response.json().get('models', [])
                     if row.get('name') == model), None)

    row = await resident()
    if not row or row.get('context_length') != options['num_ctx']:
        response = await client.post(settings.ollama_host + '/api/chat', json={
            'model':model, 'messages':[], 'stream':False, 'think':False,
            'keep_alive':keep_alive, 'options':options}, timeout=settings.ollama_timeout_seconds)
        response.raise_for_status()
        row = await resident()
    total, vram = (row or {}).get('size'), (row or {}).get('size_vram')
    partial_allowed = model == PROFILES['local_14b_q4']['tag']
    if (type(total) is not int or type(vram) is not int or total <= 0 or vram <= 0
            or (vram < total and not partial_allowed)):
        raise ValueError('The selected model is not fully in VRAM. Cortana stopped before answering on CPU; retry when GPU memory is free.')
    from core.performance import record
    record('residency', model=model, total_bytes=total, vram_bytes=vram,
           context=options['num_ctx'], full_gpu=vram >= total)
    return row
