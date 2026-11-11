"""Bounded, read-only readiness probes; configuration is owned by the operator."""
from __future__ import annotations

import errno
import json
from pathlib import Path
import shutil
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config
from .workflow_contracts import digest

REMEDIES = {
    'unverified': 'Model response has not been tested. Use an explicitly authorized, resource-admitted probe.',
    'configuration': 'Correct the named configuration and recheck.',
    'dns': 'Check the named hostname and resolver; recheck DNS separately from HTTP.',
    'authentication': 'Reconnect the named account, then recheck. No credentials were changed.',
    'rate_limit': 'Wait for the provider cooldown before rechecking.',
    'permission': 'Review the actual failing operation and OS error; no protection was disabled.',
    'dependency': 'Start or configure the required dependency, then recheck the original task.',
    'transient': 'Retry this read-only probe with bounded backoff.',
    'disk': 'Free space on the configured work volume, then recheck.',
    'busy_port': 'Identify the listener and expected service before changing a port.',
    'worker_crash': 'Inspect the last checkpoint and reconcile any uncertain external action.',
    'tls': 'Repair certificate/trust configuration; certificate validation remains enabled.',
}


class ProbeNotPerformed(ValueError):
    pass


def classify(exc):
    if isinstance(exc, ProbeNotPerformed):
        return 'unverified'
    code = getattr(exc, 'winerror', None) or getattr(exc, 'errno', None)
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return 'authentication'
        if exc.code == 429:
            return 'rate_limit'
        return 'transient' if exc.code >= 500 else 'configuration'
    if isinstance(exc, urllib.error.URLError):
        return classify(exc.reason)
    if isinstance(exc, socket.gaierror) or code == 11001:
        return 'dns'
    if isinstance(exc, ssl.SSLError):
        return 'tls'
    if isinstance(exc, PermissionError) or code in (errno.EACCES, 10013):
        return 'permission'
    if code in (errno.EADDRINUSE, 10048):
        return 'busy_port'
    if code == errno.ENOSPC:
        return 'disk'
    if isinstance(exc, (ConnectionRefusedError, FileNotFoundError)) or code == 10061:
        return 'dependency'
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return 'transient'
    return 'configuration'


def inventory():
    path = Path(config.get('SUITE_HEALTH_CONFIG', str(config.profiles_dir() / 'workflow_health.json')))
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        return data['probes'][:30]
    return [{'id': 'workspace-disk', 'kind': 'disk', 'path': str(config.data_dir()),
             'minimum_bytes': 256 * 1024 * 1024, 'workflows': ['all']},
            {'id': 'ollama-service', 'kind': 'http',
             'url': str(config.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')).rstrip('/') + '/api/tags',
             'workflows': ['community', 'sponsorship', 'video_client', 'fullstack_sales', 'job_hunter', 'saas_sales']},
            {'id': 'configured-model', 'kind': 'model', 'workflows': ['existing model workflows']},
            {'id': 'loopback-dns', 'kind': 'dns', 'host': 'localhost', 'workflows': ['all']},
            {'id': 'cortana-runtime', 'kind': 'integration',
             'integration': 'cortana', 'workflows': ['system_health', 'client_delivery']},
            {'id': 'storylens-service', 'kind': 'http',
             'url': config.get('STORYLENS_HEALTH_URL', 'http://127.0.0.1:8765/api/health'), 'workflows': ['client_delivery', 'content_release']},
            {'id': 'cortana-diagnostics', 'kind': 'integration', 'integration': 'cortana', 'workflows': ['system_health']},
            {'id': 'storylens-handoff', 'kind': 'integration', 'integration': 'storylens', 'workflows': ['client_delivery', 'content_release']}]


def probe(spec):
    kind = spec['kind']
    if kind == 'disk':
        free = shutil.disk_usage(spec['path']).free
        if free < int(spec.get('minimum_bytes', 256 * 1024 * 1024)):
            raise OSError(errno.ENOSPC, 'Insufficient workspace storage')
        return {'free_bytes': free}
    if kind == 'dns':
        addresses = socket.getaddrinfo(spec['host'], None)
        return {'address_count': len(addresses)}
    if kind == 'tcp':
        with socket.create_connection((spec['host'], int(spec['port'])), timeout=3):
            return {'reachable_port': int(spec['port'])}
    if kind == 'bind':
        if spec.get('host', '127.0.0.1') not in ('127.0.0.1', '::1'):
            raise ValueError('Bind probes are loopback only')
        with socket.socket() as sock:
            sock.bind((spec.get('host', '127.0.0.1'), int(spec['port'])))
            return {'available_port': int(spec['port'])}
    if kind == 'http':
        url = urllib.parse.urlsplit(spec['url'])
        if url.scheme not in ('http', 'https') or url.username or url.password or url.query:
            raise ValueError('Health endpoints must have no embedded credentials or query')
        if url.scheme == 'http' and url.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('Remote health endpoints require TLS')
        with urllib.request.urlopen(spec['url'], timeout=4) as response:
            response.read(1024)
            return {'http_status': response.status, 'tls_verified': url.scheme == 'https'}
    if kind == 'model':
        # A reachable /api/tags is not a completed model response. Never launch
        # GPU inference opportunistically during a lightweight health check.
        raise ProbeNotPerformed('Model response not checked: an explicit resource-admitted probe is required')
    if kind == 'model_receipt':
        path = Path(spec['path'])
        age = time.time() - path.stat().st_mtime
        saved = json.loads(path.read_text(encoding='utf-8'))
        brain = saved.get('result',{}).get('brain',{})
        if age > spec.get('max_age_seconds',86400) or saved.get('state') != 'waiting_for_review' or not brain.get('fresh_model_response'):
            raise ProbeNotPerformed('Recorded model response is absent, failed or too old; run an explicit planning probe')
        return {'engine':saved['engine'],'model':brain['model'], 'response_verified':True,
            'checked_at':path.stat().st_mtime, 'age_seconds':round(age), 'fresh_call_in_this_probe':False,
            'evidence_ref':str(path)}
    if kind == 'integration':
        from .workflow_broker import IntegrationClient
        return IntegrationClient(spec['integration']).capabilities()
    raise ValueError('Unsupported configured probe kind')


def run_health(store, probes=None, retry_budget=1, runtime_seconds=60, guard=None):
    checks = []
    deadline = time.monotonic() + runtime_seconds
    for spec in (inventory() if probes is None else probes):
        if guard:
            guard()
        if time.monotonic() >= deadline:
            checks.append({'id': spec['id'], 'operation': spec['kind'], 'ok': False,
                'classification': 'dependency', 'detail': 'Readiness runtime budget exhausted before this probe',
                'next_action': 'Recheck with a narrower probe inventory or a larger explicit budget'})
            break
        attempts = 0
        started = time.monotonic()
        while True:
            attempts += 1
            try:
                facts = probe(spec)
                result = {'id': spec['id'], 'operation': spec['kind'], 'ok': True, 'facts': facts,
                          'classification': 'healthy', 'next_action': ''}
                store.kv_set('health_last_success', spec['id'], {'at': time.time(), 'facts': facts})
                break
            except Exception as exc:
                category = classify(exc)
                if category == 'transient' and attempts <= min(int(retry_budget), 2):
                    time.sleep(min(.25 * 2 ** (attempts - 1), 1))
                    continue
                from .workflow_broker import IntegrationUnavailable
                cause = exc.reason if isinstance(exc, urllib.error.URLError) and not isinstance(exc, urllib.error.HTTPError) else exc
                result = {'id': spec['id'], 'operation': spec['kind'], 'ok': False,
                          'classification': category, 'error_type': type(exc).__name__,
                          'cause_type': type(cause).__name__,
                          'os_error': getattr(cause, 'winerror', None) or getattr(cause, 'errno', None),
                          'http_status': getattr(exc, 'code', None),
                          'detail': str(exc)[:300] if isinstance(exc, (ValueError, IntegrationUnavailable)) else type(cause).__name__,
                          'next_action': REMEDIES[category]}
                break
        result.update(workflows=spec.get('workflows', []), attempts=attempts,
                      elapsed_ms=round((time.monotonic() - started) * 1000),
                      last_success=store.kv_get('health_last_success', spec['id']))
        checks.append(result)
    # Stale heartbeats never get called completed. No automatic replay of writes.
    for row in store.query("SELECT thread_id,agent,updated_at FROM threads WHERE status IN ('ok','running') AND updated_at<?", (time.time() - 900,)):
        checks.append({'id': row['thread_id'], 'operation': 'checkpoint_heartbeat', 'ok': False,
            'classification': 'worker_crash', 'detail': 'Stale checkpoint; worker liveness unverified',
            'workflows': [row['agent']], 'next_action': REMEDIES['worker_crash']})
    failed = [c for c in checks if not c['ok']]
    signature = digest([(c['id'], c['classification']) for c in failed])
    last = store.kv_get('health_incidents', signature, {})
    if failed and time.time() - last.get('last_reported', 0) > 900:
        store.event('health_incident', 'system_health', '', signature=signature,
                    affected_checks=[c['id'] for c in failed])
        store.kv_set('health_incidents', signature, {'last_reported': time.time()})
    return {'type': 'HealthReport', 'checked_at': time.time(), 'checks': checks,
            'ready': not failed, 'recovery_proposals': [
                {'type': 'RecoveryProposal', 'check': c['id'], 'action': c['next_action'],
                 'automatic': c['classification'] == 'transient', 'attempts': c.get('attempts', 0)} for c in failed],
            'model_profile': config.get('LLM_MODEL', config.get('OLLAMA_MODEL', 'not configured')),
            'scope': 'Readiness only; original task recovery requires its own verified outcome.'}
