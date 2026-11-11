"""Versioned manual SOURCE banks. No download, inference, rendering or host calls.

Selections use slot indices: omitted preserves a saved manual choice, None means
unreviewed, '' explicitly means no visual, and a media ID selects an offered image.
Exporting or resolving a choice never inserts it into an editor.
"""
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

from .recovery import profile_source

SCHEMA = 'storylens.smart_visuals.source_bank'
VERSION = 1


def choice_target(project):
    target = project.get('options_per_moment', 5)
    if type(target) is not int or target not in (2, 5):
        raise ValueError('Choose two long-form or five short-form visual options.')
    return target


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _identity(value):
    return _hash(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8'))[:24]


def _source_choice(folder, option, entity, bank_id, *, manual=False):
    from PIL import Image
    if not isinstance(option, dict) or not isinstance(option.get('id'), str) or not option['id']:
        raise ValueError('This choice has no saved media identity.')
    if option.get('kind') != 'image':
        raise ValueError('This source bank accepts images. Keep B-roll video choices separate.')
    if option.get('entity', entity['key']) != entity['key'] or option.get('qid', entity.get('qid')) != entity.get('qid'):
        raise ValueError('This choice belongs to a different saved subject.')
    evaluation = option.get('evaluation') or {}
    if manual:
        from .manual_web import manual_choice
        if not manual_choice({'search_method':'website','review_policy':'human'},option):
            raise ValueError('This manual choice needs its original file-validation and unreviewed status.')
    elif evaluation.get('passed') is not True:
        raise ValueError('This choice has not passed its saved local visual check.')
    profile = (evaluation.get('checks') or {}).get('profile_source')
    if profile and not profile_source(profile):
        raise ValueError('This choice needs its identity reference rechecked.')
    relative = option.get('asset')
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('This choice needs a source file inside its saved project.')
    path = (folder / relative).resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise ValueError('This choice source is missing or outside its saved project.')
    if option.get('path') and Path(option['path']).resolve() != path:
        raise ValueError('This choice source does not match its saved file binding.')
    raw = path.read_bytes()
    if manual and option.get('file_sha256') != _hash(raw):
        raise ValueError('This manual source changed after download. Reopen its saved review.')
    with Image.open(path) as image:
        if image.format not in ('PNG', 'JPEG', 'WEBP', 'GIF', 'BMP', 'TIFF'):
            raise ValueError('This choice is not a supported source image.')
        dimensions = list(image.size)
        mime = Image.MIME.get(image.format, 'application/octet-stream')
        fingerprint = _hash(image.convert('RGBA').resize((96, 96)).tobytes())
    stored = option.get('sha256')
    if stored and stored != fingerprint:
        raise ValueError('This image no longer matches its saved visual fingerprint.')
    return {'asset_id': _identity([bank_id, option['id']]), 'media_id': option['id'],
        'kind': 'image', 'title': option.get('title', ''),
        'file': {'path': str(path), 'relative_path': relative, 'sha256': _hash(raw),
                 'bytes': len(raw), 'mime': mime, 'dimensions': dimensions},
        'image_fingerprint': {'algorithm': 'sha256-rgba-resize-96x96',
                              'value': fingerprint, 'saved_value': stored},
        'source': {key: option.get(key) for key in ('source', 'url', 'page_url', 'author',
            'license', 'license_url', 'official', 'nonfree', 'text')},
        'verification': {'saved_evaluation': evaluation,
                         'check_context': option.get('check_context'),
                         **({'method':'website','vision_checked':False,'requires_human_review':True} if manual else {}),
                         'new_visual_review': False}}


def build_source_bank(project_file, selections=None):
    """Read existing raw files; retain every bank and never modify saved choices.

    Unusable choices remain listed as unavailable. Selecting one fails the whole
    request before a manifest is written. Byte hashes bind future host handoffs;
    the older project's image sha256 field is a normalized pixel fingerprint.
    """
    file = Path(project_file).resolve()
    raw = file.read_bytes()
    project = json.loads(raw)
    if project.get('review_options') is not True:
        raise ValueError('Open a manual Smart Visuals choice project for source-bank export.')
    target = choice_target(project)
    timeline = project['timeline']
    try:
        fps = Fraction(str(timeline['fps']))
        duration = float(timeline['duration'])
        if fps <= 0 or not math.isfinite(duration) or duration <= 0:
            raise ValueError()
    except (ValueError, ZeroDivisionError, TypeError, KeyError):
        raise ValueError('This project needs valid saved timing before exporting its sources.') from None
    if selections is not None and not isinstance(selections, dict):
        raise ValueError('Choose visuals by their saved slot and media identity.')
    requested = {}
    for index, value in (selections or {}).items():
        if isinstance(index, bool) or not str(index).isdigit() or str(int(index)) in requested:
            raise ValueError('This visual choice has an invalid or repeated slot.')
        if value is not None and not isinstance(value, str):
            raise ValueError('Choose a saved visual, No visual, or leave it unreviewed.')
        requested[str(int(index))] = value
    banks = []
    seen_slots = set()
    namespace = _identity({key: timeline.get(key) for key in ('name', 'fps', 'width', 'height', 'duration')})
    for slot in project['slots']:
        index = slot.get('index')
        if type(index) is not int or index < 0 or index in seen_slots:
            raise ValueError('This project has an invalid or repeated visual slot.')
        seen_slots.add(index)
        key = slot.get('entity')
        entity = project.get('entities', {}).get(key)
        if not entity or entity.get('key') != key:
            raise ValueError('This visual slot has no matching saved subject identity.')
        start, end = float(slot['start']), float(slot['end'])
        if not all(math.isfinite(v) for v in (start, end)) or not 0 <= start < end <= duration:
            raise ValueError('This visual slot falls outside the saved timeline.')
        start_frame, end_frame = round(Fraction(str(start)) * fps), round(Fraction(str(end)) * fps)
        if end_frame <= start_frame:
            raise ValueError('This visual slot has no duration at the saved frame rate.')
        bank_id = _identity([namespace, index, key, entity.get('qid'), slot.get('reference_type')])
        choices, unavailable, media_ids = [], [], set()
        for option in slot.get('options', []):
            media_id = option.get('id') if isinstance(option, dict) else None
            if media_id in media_ids:
                raise ValueError('This visual bank has repeated media identities. Reopen the saved choices.')
            media_ids.add(media_id)
            try:
                choices.append(_source_choice(file.parent, option, entity, bank_id,
                    manual=project.get('search_method')=='website' and project.get('review_policy')=='human'))
            except (ValueError, OSError, SyntaxError, TypeError) as error:
                unavailable.append({'media_id': media_id, 'reason': str(error)})
        saved = slot.get('chosen') or {}
        wanted = requested.get(str(index), saved.get('id'))
        if wanted is None:
            selection = {'state': 'unreviewed', 'asset_id': None}
        elif wanted == '':
            selection = {'state': 'no_visual', 'asset_id': None}
        else:
            selected = next((o for o in choices if o['media_id'] == wanted), None)
            if selected is None:
                raise ValueError('The selected visual is unavailable or is not offered for this subject. Choose again; saved progress is kept.')
            selection = {'state': 'selected', 'asset_id': selected['asset_id']}
        banks.append({'bank_id': bank_id, 'slot_index': index, 'entity': entity,
            'reference_type': slot.get('reference_type', 'identity'),
            'spoken_text': slot.get('text', ''), 'requested_visual': slot.get('visual', ''),
            'evidence_terms': slot.get('evidence_terms', []), 'queries': slot.get('queries', []),
            'anchor': {'start_seconds': start, 'end_seconds': end, 'start_frame': start_frame,
                       'end_frame': end_frame, 'fps': str(fps)},
            'target': target, 'shortfall': max(0, target - len(choices)),
            'availability': 'no_match' if not choices else ('ready' if len(choices) >= target else 'partial'),
            'selection': selection, 'choices': choices, 'unavailable_choices': unavailable,
            'legacy_presentation': slot.get('display')})
    if set(requested) - {str(i) for i in seen_slots}:
        raise ValueError('A selected visual refers to a slot outside this project.')
    return {'schema': SCHEMA, 'version': VERSION, 'feature': 'smart_visuals',
        'source_project': {'path': str(file), 'sha256': _hash(raw)},
        'timeline': timeline, 'options_per_moment': target,
        'lineage': {'saved_planning_model': project.get('brain'),
                    **({'search_method':'website','review_policy':'human','vision_checked':False}
                       if project.get('search_method')=='website' and project.get('review_policy')=='human' else {}),
                    'saved_research_state': project.get('research_state'),
                    'new_model_inference': False, 'new_visual_review': False,
                    'selection_policy': 'saved manual selection or explicit user choice only'},
        'auto_insert': False, 'manual_choice_required': True,
        'handoff': {'presentation': 'plain_source', 'renderer': None,
                    'add_text': False, 'add_card': False, 'motion': 'host_owned'},
        'banks': banks}


def export_source_bank(project_file, target, selections=None):
    """Write a NEW source manifest. Never overwrite a prior result or source."""
    target = Path(target)
    if target.exists():
        raise FileExistsError('Keep the existing result. Choose a new source-bank filename.')
    manifest = build_source_bank(project_file, selections)
    with target.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def selected_source_assets(manifest, project_file):
    """Validate binding again and return selected RAW images, never rendered cards.

    This is the suite-owned adapter hook, not a native insertion implementation.
    Changed bytes/project/identity/timing/schema invalidate a previously exported
    manifest. No visual or unreviewed banks return no placement instructions.
    """
    if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA or type(manifest.get('version')) is not int or manifest['version'] != VERSION:
        raise ValueError('Re-export this Smart Visuals source bank with a supported version.')
    requested = {}
    try:
        for bank in manifest['banks']:
            index = str(bank['slot_index'])
            if index in requested:
                raise ValueError()
            selection = bank['selection']
            if selection['state'] == 'selected':
                requested[index] = next(o['media_id'] for o in bank['choices'] if o['asset_id'] == selection['asset_id'])
            elif selection['state'] in ('unreviewed', 'no_visual') and selection['asset_id'] is None:
                requested[index] = None if selection['state'] == 'unreviewed' else ''
            else:
                raise ValueError()
        current = build_source_bank(project_file, requested)
    except (ValueError, KeyError, TypeError, OSError, StopIteration):
        raise ValueError('This source bank no longer matches its saved project or files. Re-export it; original progress is kept.') from None
    if current != manifest:
        raise ValueError('This source bank has changed identity, timing or source bindings. Re-export it; original progress is kept.')
    selected = []
    for bank in current['banks']:
        if bank['selection']['state'] != 'selected':
            continue
        choice = next(o for o in bank['choices'] if o['asset_id'] == bank['selection']['asset_id'])
        selected.append({'bank_id': bank['bank_id'], 'asset_id': choice['asset_id'],
            'media_id': choice['media_id'], 'entity': bank['entity'],
            'path': choice['file']['path'], 'sha256': choice['file']['sha256'],
            'source': choice['source'], 'anchor': bank['anchor'],
            'reference_type': bank['reference_type'], 'verification': choice['verification'],
            'image_fingerprint': choice['image_fingerprint'],
            'source_project': current['source_project'],
            'presentation': 'plain_source', 'add_text': False, 'add_card': False,
            'auto_insert': False})
    return selected
