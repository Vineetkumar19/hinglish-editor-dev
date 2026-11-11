"""Explicit owner publishing defaults, separate from model-generated choices."""
import json
from pathlib import Path


def declarations(root):
    path=Path(root)/'config.workflow.local.json'
    if not path.is_file():return {}
    settings=json.loads(path.read_text('utf-8')).get('publishing_defaults',{})
    return {key:settings[key] for key in ('made_for_kids','synthetic_media')
            if type(settings.get(key)) is bool}


def apply(root,review):
    defaults=declarations(root)
    # A declaration already recorded for this review remains authoritative.
    for key,value in defaults.items():review.setdefault(key,value)
    review['declaration_defaults_saved']=len(defaults)==2
    return review
