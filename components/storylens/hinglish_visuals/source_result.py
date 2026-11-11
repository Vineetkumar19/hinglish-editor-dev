"""Feature-owned production result/decision hooks for plain SOURCE banks.

Immutable manifests retain prior decisions. Only the new active pointer changes;
the project, source assets, legacy selections and rendered exports stay intact.
The suite must authenticate/serialize requests before calling this local API.
"""
import hashlib
import json
import re
import threading
from pathlib import Path

from hinglish_clean.detection import write_json
from .source_bank import build_source_bank, selected_source_assets

_lock = threading.RLock()
REQUEST_TYPE = 'smart_visuals.source_bank.select'


def _descriptor(project_file, path, manifest, digest):
    return {'state': 'available', 'schema': manifest['schema'], 'version': manifest['version'],
        'project_path': str(project_file), 'source_project_sha256': manifest['source_project']['sha256'],
        'manifest_path': str(path), 'manifest_relative': path.relative_to(project_file.parent).as_posix(),
        'manifest_sha256': digest, 'options_per_moment': manifest['options_per_moment'],
        'selected_count': sum(b['selection']['state'] == 'selected' for b in manifest['banks']),
        'auto_insert': False, 'native_acceptance': False}


def _publish(project_file, manifest):
    # Revalidate before making the pointer visible. This is bookkeeping, not a
    # model judgment or native acceptance receipt.
    selected_source_assets(manifest, project_file)
    raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    folder = project_file.parent / 'source-banks'
    folder.mkdir(exist_ok=True)
    path = folder / f'source-bank-v1-{digest}.json'
    try:
        with path.open('xb') as stream:
            stream.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError('The saved source-bank snapshot changed. Keep the original and prepare a fresh review.') from None
    write_json(folder / 'active.json', {'manifest': path.name, 'sha256': digest})
    return _descriptor(project_file, path, manifest, digest)


def _active(project_file):
    folder = project_file.parent / 'source-banks'
    pointer = json.loads((folder / 'active.json').read_text('utf-8'))
    name = pointer.get('manifest', '')
    if not isinstance(name, str) or not re.fullmatch(r'source-bank-v1-[a-f0-9]{64}\.json', name):
        raise ValueError('The saved source-bank pointer is invalid. Prepare a fresh review.')
    path = (folder / name).resolve()
    if not path.is_relative_to(folder.resolve()):
        raise ValueError('The saved source-bank snapshot is outside this project.')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if pointer.get('sha256') != digest or name != f'source-bank-v1-{digest}.json':
        raise ValueError('The saved source-bank snapshot changed. Prepare a fresh review.')
    manifest = json.loads(raw)
    selected_source_assets(manifest, project_file)
    return _descriptor(project_file, path, manifest, digest), manifest


def ensure_source_result(project_file):
    """Ordinary completed review/result entry: emit once, then reopen decisions.

    Incomplete banks are valid results; collecting is not. A stale active bank
    is reported rather than silently dropping user decisions or relabelling it.
    """
    file = Path(project_file).resolve()
    with _lock:
        project = json.loads(file.read_text('utf-8'))
        if project.get('collecting'):
            raise ValueError('Visual research is still running. Finished sources and choices are kept.')
        if (file.parent / 'source-banks' / 'active.json').exists():
            return _active(file)[0]
        return _publish(file, build_source_bank(file))


def apply_source_request(payload):
    """Apply actual review decisions only; no source or model decisions are made.

    Payload comes from storylensVisualsSourceBank.request() after ordinary user
    clicks. This API opens no network listener; the suite owns transport/auth,
    outer cross-process serialization, and subsequent host insertion.
    """
    if not isinstance(payload, dict) or payload.get('type') != REQUEST_TYPE or type(payload.get('version')) is not int or payload['version'] != 1:
        raise ValueError('Use a supported Smart Visuals source-selection request.')
    if not isinstance(payload.get('choices'), dict):
        raise ValueError('Choose the visuals in the saved review before preparing source assets.')
    file = Path(payload['project_path']).resolve()
    with _lock:
        current = ensure_source_result(file)
        if payload.get('base_manifest_sha256') != current['manifest_sha256'] or Path(payload.get('base_manifest', '')).resolve() != Path(current['manifest_path']):
            raise ValueError('This review changed after it was opened. Reopen the latest choices; saved decisions are kept.')
        _, prior = _active(file)
        choices = {}
        for bank in prior['banks']:
            selection = bank['selection']
            if selection['state'] == 'selected':
                choices[str(bank['slot_index'])] = next(o['media_id'] for o in bank['choices'] if o['asset_id'] == selection['asset_id'])
            else:
                choices[str(bank['slot_index'])] = '' if selection['state'] == 'no_visual' else None
        choices.update(payload['choices'])
        manifest = build_source_bank(file, choices)
        # A request cannot advance the snapshot baseline after a model/project
        # change while retaining a decision from the older state.
        if manifest['source_project'] != prior['source_project']:
            raise ValueError('The source or saved model lineage changed. Reopen a fresh review before choosing.')
        result = _publish(file, manifest)
        result['selected_sources'] = selected_source_assets(manifest, file)
        return result
