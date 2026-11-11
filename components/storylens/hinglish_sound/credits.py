"""Carry source licences and attribution into the exported soundtrack folder."""
import json
from pathlib import Path


def write(folder, sections, cues):
    rows = []
    paths = dict.fromkeys([s['path'] for s in sections] + [c.path for c in cues])
    for path in paths:
        sidecar = Path(str(path) + '.json')
        if not sidecar.is_file():
            rows.append({'file': Path(path).name, 'source': path, 'licence': 'Owner-supplied; no licence metadata'})
            continue
        try:
            data = json.loads(sidecar.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict):
                raise ValueError('Expected source metadata object')
        except (OSError, ValueError):
            rows.append({'file': Path(path).name, 'source': str(path),
                         'licence': 'Source metadata could not be read; check the original licence.'})
            continue
        rows.append({'file': Path(path).name, 'source': data.get('source_url') or data.get('url') or path,
                     'licence': data.get('license') or data.get('licence') or '',
                     'author': data.get('author') or data.get('username') or '',
                     'credit': data.get('attribution') or '', 'name': data.get('name', ''),
                     'changes': 'Excerpted, mixed, faded and level-adjusted for this video.'})
    Path(folder, 'sound-sources.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    Path(folder, 'CREDITS.txt').write_text('\n\n'.join('\n'.join(filter(None,
        [r.get('credit') or r.get('name') or r['file'], r.get('author'), r['source'], r['licence'], r.get('changes')]))
        for r in rows), encoding='utf-8')
    return rows
