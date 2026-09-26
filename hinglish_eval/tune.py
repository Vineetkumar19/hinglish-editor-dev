"""Corrections from the quality check for the next attempt of a feature.

The runner writes them to a JSON file and passes its path in HINGLISH_EVAL_TUNE; the features read
numbers (e.g. sound.effect_gain_db) and plain-English feedback for their AI model from it. Without the
variable every value is the neutral default, so features behave exactly as before."""
import json
import os

ENV = 'HINGLISH_EVAL_TUNE'
_cache = None


def _data():
    global _cache
    if _cache is None:
        path = os.environ.get(ENV)
        try:
            with open(path, encoding='utf-8') as f:
                _cache = json.load(f)
        except (TypeError, OSError, ValueError):
            _cache = {}
    return _cache


def value(feature, key, default):
    return _data().get(feature, {}).get(key, default)


def feedback(feature):
    """Problems the output check found last time, told to the model so it does better this time."""
    return list(_data().get(feature, {}).get('feedback', []))


def attempt():
    return int(_data().get('attempt', 1))
