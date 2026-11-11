"""Named, isolated documentary reference sets and their saved animation settings."""
import copy
import json
from pathlib import Path

SETS = {
    'beneath-documentary-edit': 'vineet documentry edit',
    'crick-edit-editing-style': 'cricAddict',
}
ANIMATIONS = [
    {'id': 'road-travel', 'name': 'Road Timeline', 'archive_style': 'map', 'archive_variant': 0,
     'description': 'Camera travels right; previous photos leave left, next photos enter right; drawn road and depth parallax.'},
    {'id': 'horizontal-reel', 'name': 'Aligned Film Reel', 'archive_style': 'slate', 'archive_variant': 1,
     'description': 'Equal film windows and perforations advance together; source photos fit without stretching.'},
    {'id': 'cinema', 'name': 'Centred Photo Reveal', 'archive_style': 'night', 'archive_variant': 0,
     'description': 'One central photograph replaces another through aperture reveals and focus dissolves.'},
    {'id': 'hinged-triptych', 'name': 'Hinged Glass Panels', 'archive_style': 'glass', 'archive_variant': 0,
     'description': 'Three fixed glass panels open on separate hinges.'},
    {'id': 'turning-album', 'name': 'Turning Photo Album', 'archive_style': 'album', 'archive_variant': 0,
     'description': 'Photographs turn with album pages; the next photo is revealed underneath.'},
]


def reference(root, key='beneath-documentary-edit'):
    if key not in SETS:
        raise ValueError('Choose a saved documentary editing style.')
    folder = Path(root) / 'library' / 'creator-profiles'
    path = folder / (key + '.json')
    if not path.is_file() and key == 'beneath-documentary-edit':
        path = folder / 'cricket-documentary.json'  # Older installations and saved jobs.
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def catalogue(root):
    result = []
    for key, name in SETS.items():
        memory = reference(root, key)
        if memory:
            result.append({'id': key, 'name': name, 'status': memory.get('analysis_status', 'pending'),
                           'animations': copy.deepcopy(memory.get('animation_settings', [])),
                           'patterns': [{'id': p['id'], 'name': p['name'], 'description': p['application']}
                                        for p in memory.get('learned_patterns', [])],
                           'coverage': copy.deepcopy(memory.get('coverage_summary', {})),
                           'source_folder': memory.get('source_folder', '')})
    return result


def apply_style_settings(root, style, scene):
    """Selecting an animation card changes the actual layout, not just its palette."""
    if scene.get('template') != 'archive_board' or not str(style).startswith('card:'):
        return
    from hinglish_motion.style import card
    notes = card(root, style[5:]).notes
    defaults = notes.get('archive_defaults')
    if not defaults and notes.get('documentary_set') == 'beneath-documentary-edit':
        choices = {a['id']: a for a in ANIMATIONS}
        data = scene.get('data', {})
        selected = data.get('archive_composition')
        if selected not in choices:
            selected = {'map': 'road-travel', 'slate': 'horizontal-reel', 'glass': 'hinged-triptych',
                        'album': 'turning-album'}.get(data.get('archive_style'), 'cinema')
        setting = choices[selected]
        defaults = {k: setting[k] for k in ('archive_style', 'archive_variant')}
        defaults.update(archive_composition=selected, archive_grade='colour')
    if defaults:
        scene.setdefault('data', {}).update(copy.deepcopy(defaults))
