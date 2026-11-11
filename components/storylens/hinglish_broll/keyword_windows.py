"""Bound long review planning to small speech windows with job-local checkpoints.

This is a planning checkpoint, never a footage approval or a model-output cache
shared between projects. Original word times remain authoritative.
"""
from dataclasses import asdict, replace
import hashlib
import json
import math
import time

from .placement import Moment, Slot
from .recovery import read_json, write_json

VERSION = 1
MAX_WORDS = 180
MAX_CHARS = 1800
MAX_SECONDS = 60


def speech_windows(words):
    """Cover every source word exactly once; preserve original word objects."""
    batch, size = [], 0
    for word in words:
        text_size = len(word.text) + 1
        if batch and (len(batch) >= MAX_WORDS or size + text_size > MAX_CHARS
                      or word.end - batch[0].start > MAX_SECONDS):
            yield batch
            batch, size = [], 0
        batch.append(word)
        size += text_size
    if batch:
        yield batch


def _budgets(windows, requested):
    if not requested:
        return [max(1, min(12, math.ceil(len(w) / 12))) for w in windows]
    total = sum(map(len, windows))
    exact = [requested * len(w) / total for w in windows]
    budgets = [math.floor(v) for v in exact]
    for i in sorted(range(len(windows)), key=lambda i: exact[i] - budgets[i], reverse=True)[:requested-sum(budgets)]:
        budgets[i] += 1
    return budgets


def discover_bounded(llm, phrases, words, summary, count=0, brief='', progress=print,
                     *, checkpoint=None, discover=None):
    from .keywords import discover as ordinary_discover
    discover = discover or ordinary_discover
    windows = list(speech_windows(words))
    if not windows:
        return []
    budgets = _budgets(windows, count)
    # Bind this job's partial plan to its complete original speech and settings.
    # No completed window is reused after a model/profile/input change.
    from pathlib import Path
    model_config = Path(__file__).resolve().parents[1] / 'config.models.local.json'
    binding = {'version': VERSION, 'summary': summary, 'brief': brief, 'count': count,
               'limits': [MAX_WORDS, MAX_CHARS, MAX_SECONDS],
               'implementation': hashlib.sha256(Path(__file__).read_bytes() +
                   Path(__file__).with_name('keywords.py').read_bytes()).hexdigest(),
               'model_config': hashlib.sha256(model_config.read_bytes()).hexdigest() if model_config.is_file() else None,
               'model': getattr(llm, 'model', None),
               'words': [{'text': w.text, 'start': w.start, 'end': w.end} for w in words],
               'phrases': [asdict(p) for p in phrases]}
    fingerprint = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    saved = read_json(checkpoint, {}) if checkpoint else {}
    if saved.get('fingerprint') != fingerprint:
        saved = {'version': VERSION, 'fingerprint': fingerprint, 'windows': {}}
    result = []
    for i, (batch, budget) in enumerate(zip(windows, budgets)):
        if not budget:
            continue
        key = str(i)
        if key in saved['windows']:
            progress(f'Using saved keyword window {i+1}/{len(windows)}')
            rows = saved['windows'][key]['slots']
            result.extend(Slot(moment=Moment(**r['moment']), **{k:v for k,v in r.items() if k!='moment'}) for r in rows)
            continue
        start, end = batch[0].start, batch[-1].end
        local_phrases = []
        for phrase in phrases:
            local = [w for w in batch if w.end > phrase.start and w.start < phrase.end]
            if local:
                local_phrases.append(replace(phrase, start=local[0].start, end=local[-1].end,
                                             text=' '.join(w.text for w in local)))
        progress(f'Planning keywords {i+1}/{len(windows)} · {start:.1f}–{end:.1f}s')
        began = time.monotonic()
        slots = discover(llm, local_phrases, batch, summary, budget, brief, progress)
        if len(slots) > budget:
            # Keep coverage across this window when the model exceeds its
            # requested count, rather than retaining only its opening terms.
            slots = [slots[min(len(slots)-1, math.floor((n+.5)*len(slots)/budget))]
                     for n in range(budget)]
        # Store only after a whole window finishes; a failed window cannot erase
        # earlier completed windows or masquerade as an empty successful plan.
        saved['windows'][key] = {'start': start, 'end': end,
                                 'elapsed_seconds': time.monotonic()-began,
                                 'slots': [asdict(s) for s in slots]}
        if checkpoint:
            write_json(checkpoint, saved)
        result.extend(slots)
    return sorted(result, key=lambda s: (s.start, s.end))
