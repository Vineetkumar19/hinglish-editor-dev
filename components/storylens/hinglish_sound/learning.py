"""Your taste, learned locally: every Save & remix records which sounds you kept and which you removed.

- a file you removed in two different videos (and never kept) is not used again; saving the same
  video again only updates that video's choices (it is never counted twice)
- your recent keeps/removals are given to the AI director as examples of your style
Nothing is uploaded and no model weights change; delete cache/learning/sound-preferences.json to reset."""
import json
from pathlib import Path

FILE = Path('cache') / 'learning' / 'sound-preferences.json'
MAX_EXAMPLES = 60


def load(root):
    file = Path(root) / FILE
    if file.exists():
        try:
            return json.loads(file.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'files': {}, 'examples': []}


def save(root, data):
    file = Path(root) / FILE
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def counts(data):
    """{path: {'kept': videos, 'removed': videos}}: one vote per video (plus counts saved by older versions)."""
    out = {p: dict(n) for p, n in data.get('files', {}).items()}
    for choices in data.get('videos', {}).values():
        for path, verdict in choices.items():
            out.setdefault(path, {'kept': 0, 'removed': 0})[verdict] += 1
    return out


def banned(data):
    return {path for path, n in counts(data).items() if n.get('removed', 0) >= 2 and not n.get('kept', 0)}


def record(root, cues, kept_indices, video=''):
    """cues: ALL the sounds proposed for one video; kept_indices: the ones you kept; video: which video
    (its plan file). Saving the same video again replaces its earlier choices. Only AI-chosen sounds
    teach taste."""
    data = load(root)
    data.setdefault('videos', {})
    kept_indices = set(kept_indices)
    video = str(video) or f'video-{len(data["videos"]) + 1}'
    choices = {}
    data['examples'] = [e for e in data.get('examples', []) if e.get('video') != video]
    for i, cue in enumerate(cues):
        verdict = 'kept' if i in kept_indices else 'removed'
        if choices.get(cue['path']) != 'kept':                 # the same file used twice: kept wins
            choices[cue['path']] = verdict
        if cue.get('source') == 'ai':
            data['examples'].append({'line': cue.get('line', ''), 'word': cue.get('word', ''),
                                     'trigger': cue.get('trigger', ''), 'type': cue['category'],
                                     'sound': cue.get('sound', ''), 'emotion': cue.get('emotion', ''),
                                     'verdict': verdict, 'video': video})
    data['videos'][video] = choices
    data['examples'] = data['examples'][-MAX_EXAMPLES:]
    save(root, data)
    return data


def taste(data, limit=10):
    """A short block for the director: what this creator kept and removed before."""
    examples = data.get('examples', [])[-limit * 2:]
    kept = [e for e in examples if e['verdict'] == 'kept'][-limit:]
    removed = [e for e in examples if e['verdict'] == 'removed'][-limit:]
    if not kept and not removed:
        return ''
    row = lambda e: f'- "{e["line"][:70]}" -> {e["type"]} ({e["sound"][:40]}) on "{e["word"]}"' + \
        (f' [{e["emotion"]}]' if e.get('emotion') else '')
    text = "\nTHIS CREATOR'S TASTE (from their own past edits; follow it):"
    if kept:
        text += '\nThey KEPT sounds like:\n' + '\n'.join(row(e) for e in kept)
    if removed:
        text += '\nThey REMOVED sounds like (avoid similar choices):\n' + '\n'.join(row(e) for e in removed)
    return text
