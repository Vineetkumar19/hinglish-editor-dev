"""First bounded experiment family: labelled video-metadata retrieval.

Runs two built-in scorers on the same held-out queries. Does not import remote
code, install packages, read credentials or claim to benchmark video embeddings.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import platform
import re
import time
import tracemalloc

from .workflow_contracts import canonical, digest, require_fields
from .workflow_store import file_hash


def tokens(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def run_experiment(task, ledger, output_root):
    data = task['input']
    require_fields(data, ('question', 'source_ref', 'license', 'dataset'))
    ref = ledger.verify_artifacts([data['dataset']])[0]
    out = Path(output_root) / task['task_id'] / str(task['revision'])
    checkpoint = out / 'completed-measurement.json'
    def register_result(saved):
        refs = []
        for name, expected in saved['file_hashes'].items():
            path = out / name
            if path.parent != out or file_hash(path) != expected:
                raise ValueError('Experiment checkpoint artifact changed; create a new task revision')
            refs.append(ledger.register_artifact(path, project='agents', revision=str(task['revision']),
                evidence=[data['source_ref'], ref['content_hash']], artifact_id=task['task_id'] + '-' + name))
        return {**saved['result'], 'artifacts': refs}
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding='utf-8'))
        if saved['input_hash'] != digest(data) or saved['implementation_hash'] != file_hash(Path(__file__)):
            raise ValueError('Experiment inputs or implementation changed; create a new task revision')
        return register_result(saved)
    if Path(ref['locator']).stat().st_size > 2_000_000:
        raise ValueError('Dataset exceeds the bounded 2 MB intake limit')
    dataset = json.loads(Path(ref['locator']).read_text(encoding='utf-8'))
    require_fields(dataset, ('clips', 'queries', 'provenance'))
    if not 1 <= len(dataset['clips']) <= 1000 or not 1 <= len(dataset['queries']) <= 100:
        raise ValueError('Experiment limit: 1–1000 clips and 1–100 held-out queries')
    ids = [c['id'] for c in dataset['clips']]
    if len(ids) != len(set(ids)):
        raise ValueError('Clip IDs must be unique')
    for c in dataset['clips']:
        require_fields(c, ('id', 'text', 'source_ref'))
    for q in dataset['queries']:
        require_fields(q, ('id', 'text', 'relevant_ids', 'split'))
        if q['split'] != 'held_out' or not q['relevant_ids'] or not set(q['relevant_ids']) <= set(ids):
            raise ValueError('Every query needs held-out labels referring to the same dataset')
    budgets = task['envelope']['budgets']
    limit = budgets['runtime_seconds']
    if limit <= 0 or budgets['storage_bytes'] < 20_000:
        raise ValueError('Experiment needs positive runtime and at least 20 KB storage')
    started = time.monotonic()
    documents = {c['id']: Counter(tokens(c['text'])) for c in dataset['clips']}
    df = Counter(w for words in documents.values() for w in words)
    idf = {w: math.log((1 + len(documents)) / (1 + n)) + 1 for w, n in df.items()}
    n = min(5, len(ids))
    results = {}
    tracemalloc.start()
    try:
        for method in ('overlap', 'tfidf_cosine'):
            rows, t0 = [], time.monotonic()
            for query in dataset['queries']:
                if time.monotonic() - started > limit:
                    raise TimeoutError('Experiment runtime budget exceeded')
                if ledger.get(task['task_id'])['state'] == 'cancelled' or ledger.get(task['task_id'])['paused']:
                    raise ValueError('Experiment stopped by task control')
                q = Counter(tokens(query['text']))
                def score(words):
                    if method == 'overlap':
                        return float(len(set(q) & set(words)))
                    numerator = sum(q[w] * words[w] * idf.get(w, 1) ** 2 for w in q)
                    a = sum((v * idf.get(w, 1)) ** 2 for w, v in q.items())
                    b = sum((v * idf.get(w, 1)) ** 2 for w, v in words.items())
                    return numerator / math.sqrt(a * b) if a * b else 0.0
                ranked = sorted(ids, key=lambda cid: (-score(documents[cid]), cid))
                positions = [i + 1 for i, cid in enumerate(ranked) if cid in query['relevant_ids']]
                rows.append({'query_id': query['id'], 'top_ids': ranked[:n],
                    'reciprocal_rank': 1 / min(positions),
                    'recall_at_k': len(set(ranked[:n]) & set(query['relevant_ids'])) / len(set(query['relevant_ids']))})
            results[method] = {'queries': rows, 'mrr': sum(r['reciprocal_rank'] for r in rows) / len(rows),
                'recall_at_k': sum(r['recall_at_k'] for r in rows) / len(rows), 'k': n,
                'elapsed_seconds': time.monotonic() - t0}
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    improved = results['tfidf_cosine']['mrr'] > results['overlap']['mrr']
    manifest = {'contract_version': 1, 'question': data['question'], 'source_ref': data['source_ref'],
        'license': data['license'], 'dataset_hash': ref['content_hash'],
        'implementation_hash': file_hash(Path(__file__)), 'python': platform.python_version(),
        'methods': ['overlap', 'tfidf_cosine'], 'seed': None, 'deterministic': True,
        'metric_tolerance': 1e-12, 'runtime_tolerance': 'timings vary; no fixed throughput claim',
        'peak_python_allocation_bytes': peak, 'peak_rss': None, 'peak_vram': None,
        'memory_limit_note': 'Allocation measurement is not process RSS or GPU memory',
        'verdict': 'investigate further' if improved else 'reject',
        'scope': 'Metadata retrieval only; no embedding model or video-content inference.',
        'integration_change': 'None applied; any StoryLens change requires a separate review'}
    files = {'experiment.json': manifest, 'environment-lock.json': {'python': platform.python_version(),
             'dependencies': 'Python standard library', 'implementation_hash': manifest['implementation_hash']},
             'dataset-manifest.json': dataset, 'baseline-results.json': results['overlap'],
             'candidate-results.json': results['tfidf_cosine'],
             'failure-samples.json': [r for r in results['tfidf_cosine']['queries'] if r['reciprocal_rank'] < 1]}
    encoded = {name: canonical(body).encode('utf-8') for name, body in files.items()}
    if sum(map(len, encoded.values())) > budgets['storage_bytes']:
        raise ValueError('Experiment output exceeds storage budget')
    out.mkdir(parents=True, exist_ok=True)
    for name, body in encoded.items():
        path = out / name
        path.write_bytes(body)
    saved = {'input_hash': digest(data), 'implementation_hash': manifest['implementation_hash'],
        'file_hashes': {name: file_hash(out / name) for name in encoded},
        'result': {'manifest': manifest, 'baseline': results['overlap'], 'candidate': results['tfidf_cosine'], 'reproduce_input': data}}
    # Commit measured outputs before artifact registration. A restart midway
    # through registration reuses the exact timing/memory measurements and bytes.
    pending = checkpoint.with_suffix('.tmp')
    pending.write_text(canonical(saved), encoding='utf-8')
    pending.replace(checkpoint)
    return register_result(saved)
