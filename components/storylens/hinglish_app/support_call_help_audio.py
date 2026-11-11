"""Pre-rendered public product-guide speech, never call recordings/conversations.

Only explicit ``prepare`` writes the fixed documentation corpus. Runtime lookup
and combination are read-only and never synthesize or save a user's question.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from threading import Lock
from time import perf_counter
import wave

from . import support_call_speech as speech

_MAX_ROWS = 256
_MAX_TEXT = 900
_MAX_WAV = 3 * 1024 * 1024
_MAX_TOTAL = 128 * 1024 * 1024
_PREPARE_LOCK = Lock()
_IDENTITY_LOCK = Lock()
_identities = {}


def _directory(root):
    return Path(root).resolve() / 'cache' / 'app' / 'voice-help'


def _key(text, language):
    if language not in ('en', 'hi') or not isinstance(text, str) or not 0 < len(text) <= _MAX_TEXT:
        return None
    # File identity and synthesizer source changes invalidate the corpus. Large
    # ONNX bytes are not rehashed on the latency-sensitive runtime lookup path.
    voice = speech._voice_path(language)
    config = Path(str(voice) + '.json')
    implementation = Path(speech.__file__)
    try:
        signature = tuple((str(path), path.stat().st_size, path.stat().st_mtime_ns)
                          for path in (voice, config, implementation))
    except OSError:
        return None
    with _IDENTITY_LOCK:
        identity = _identities.get(signature)
        if identity is None:
            identity = sha256(json.dumps(signature).encode('utf-8')).hexdigest()
            _identities.clear()
            _identities[signature] = identity
    payload = json.dumps([language, text, identity], ensure_ascii=False, separators=(',', ':'))
    return sha256(payload.encode('utf-8')).hexdigest()


def _valid_wav(data):
    if not data or len(data) > _MAX_WAV:
        return False
    try:
        with wave.open(BytesIO(data), 'rb') as source:
            channels, width, rate, frames, compression, _ = source.getparams()
            if channels != 1 or width != 2 or not 8000 <= rate <= 48000 or compression != 'NONE' or not frames:
                return False
            return len(source.readframes(frames)) == frames * channels * width
    except (wave.Error, EOFError, OSError, ValueError):
        return False


def lookup(root, text, language):
    """Return a prepared exact public-guide WAV or None. Never writes/generates."""
    key = _key(text, language)
    if key is None:
        return None
    target = _directory(root) / ('help-' + key + '.wav')
    try:
        if target.stat().st_size > _MAX_WAV:
            return None
        data = target.read_bytes()
    except OSError:
        return None
    return data if _valid_wav(data) else None


def _atomic(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix='help-building-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _prune(directory, keep):
    # Only files owned by this module may be removed; never walk recursively.
    candidates = [p for p in directory.glob('help-*.wav')
                  if len(p.stem) == 69 and all(c in '0123456789abcdef' for c in p.stem[5:])]
    stale = [p for p in candidates if p.name not in keep]
    for path in stale:
        path.unlink(missing_ok=True)


def prepare(root, corpus):
    """Render a bounded fixed corpus: iterable[(text, language)] or mappings.

    Explicit maintenance operation, not a call-turn fallback. Callers supply the
    authored guide corpus only. Returns timing/status evidence without transcripts.
    """
    rows = []
    seen = set()
    for row in corpus:
        text, language = (row.get('text'), row.get('language')) if isinstance(row, dict) else row
        if language not in ('en', 'hi') or not isinstance(text, str) or not 0 < len(text) <= _MAX_TEXT:
            raise ValueError('Product-guide corpus rows require short English/Hindi text.')
        if (text, language) not in seen:
            seen.add((text, language))
            rows.append((text, language))
        if len(rows) > _MAX_ROWS:
            raise ValueError('Product-guide speech corpus exceeds its bounded size.')
    if not rows:
        raise ValueError('Product-guide speech corpus is empty.')
    started = perf_counter()
    result = {'requested': len(rows), 'prepared': 0, 'reused': 0, 'failed': [], 'rows': [], 'bytes': 0}
    with _PREPARE_LOCK:
        directory = _directory(root)
        directory.mkdir(parents=True, exist_ok=True)
        keep = set()
        for index, (text, language) in enumerate(rows):
            key = _key(text, language)
            if key is None:
                result['failed'].append({'index': index, 'language': language, 'reason': 'voice_unavailable'})
                continue
            filename = 'help-' + key + '.wav'
            turn = perf_counter()
            audio = lookup(root, text, language)
            reused = audio is not None
            try:
                if audio is None:
                    audio = speech.synthesize(root, text, language)
                    if not _valid_wav(audio):
                        raise ValueError('The generated product-guide audio is not a complete WAV.')
                if result['bytes'] + len(audio) > _MAX_TOTAL:
                    raise ValueError('Product-guide audio exceeds the cache byte budget.')
                if not reused:
                    _atomic(directory / filename, audio)
                result['bytes'] += len(audio)
                keep.add(filename)
                result['reused' if reused else 'prepared'] += 1
                result['rows'].append({'index': index, 'language': language, 'key': key,
                                       'reused': reused, 'ms': round((perf_counter() - turn) * 1000, 2),
                                       'bytes': len(audio)})
            except (OSError, ValueError, RuntimeError) as error:
                result['failed'].append({'index': index, 'language': language, 'reason': type(error).__name__})
        # Preserve the previous complete corpus if the rebuild was incomplete.
        if not result['failed']:
            _prune(directory, keep)
        result['total_ms'] = round((perf_counter() - started) * 1000, 2)
        result['ready'] = not result['failed'] and result['prepared'] + result['reused'] == len(rows)
        _atomic(directory / 'manifest.json', json.dumps(result, indent=2).encode('utf-8'))
    return result


def combine(root, pieces, language):
    """Join up to three exact prepared guide sentences in RAM; never saves."""
    pieces = tuple(pieces)
    if not 1 <= len(pieces) <= 3:
        return None
    clips = [lookup(root, text, language) for text in pieces]
    if any(clip is None for clip in clips):
        return None
    if len(clips) == 1:
        return clips[0]
    target = BytesIO()
    with wave.open(target, 'wb') as output:
        parameters = None
        for index, clip in enumerate(clips):
            with wave.open(BytesIO(clip), 'rb') as source:
                current = (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype())
                if parameters is None:
                    parameters = current
                    output.setparams(source.getparams())
                elif current != parameters:
                    return None
                if index:
                    output.writeframes(bytes(2 * round(source.getframerate() * 0.12)))
                output.writeframes(source.readframes(source.getnframes()))
    return target.getvalue()
