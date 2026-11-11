"""Correct source-bound categories for newly imported owner sound packs."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.sound_pack_categories import classify

LIBRARY = ROOT / 'library/owner-sound-packs'
SOURCE = Path(r'D:\Editing\Sound Packs')


def main():
    manifest = json.loads((LIBRARY / 'import-manifest.json').read_text(encoding='utf-8'))
    source_packs = {
        'Cinetools Cinematic Tension Horror',
        'W. A. Production What About Cinematic FX',
        'TRANSITION SOUND EFFECTS',
    }
    rows = [row for row in manifest['files']
            if Path(row['source']).is_relative_to(SOURCE)
            and Path(row['source']).relative_to(SOURCE).parts[0] in source_packs]
    if len(rows) != 605:
        raise RuntimeError(f'Expected 605 new hash-identified files, found {len(rows)}')
    transition = [row for row in rows if 'TRANSITION SOUND EFFECTS' in row['source']]
    by_name = {}
    for row in transition:
        by_name.setdefault(Path(row['source']).name, []).append(row)
    if len(by_name) != 114 or any(len(pair) != 2 for pair in by_name.values()):
        raise RuntimeError('Transition sample-rate pairs differ from the audited 114 cues')
    result = []
    for row in rows:
        source = Path(row['source'])
        target = Path(row['path'])
        relative = source.relative_to(SOURCE)
        kind, family = classify(relative)
        if kind != 'sfx' or not target.is_file():
            raise RuntimeError(f'Unexpected source or missing import: {source}')
        with target.open('rb') as stream:
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        if sha != row['sha256']:
            raise RuntimeError(f'Imported recording changed: {target}')
        sidecar = Path(str(target) + '.json')
        meta = json.loads(sidecar.read_text(encoding='utf-8'))
        meta['category'] = family
        meta['tags'] = list(relative.parts[:-1]) + [family, 'designed cinematic sound effect']
        meta['classification_basis'] = 'source pack folder and filename; acoustic audition pending'
        alternate = 'TRANSITION SOUND EFFECTS' in row['source'] and '96kHz' in row['source']
        if alternate:
            other = next(item for item in by_name[source.name] if '48kHz' in item['source'])
            meta['exclude_from_selection'] = True
            meta['format_alternate_of'] = other['path']
        else:
            meta['exclude_from_selection'] = False
            meta.pop('format_alternate_of', None)
        sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        result.append(dict(source=str(source), imported=str(target), sha256=sha,
                           category=family, selection_excluded=alternate,
                           basis='source folder and filename'))
    receipt = dict(source=str(SOURCE), files=result,
                   categories=dict(Counter(row['category'] for row in result)),
                   equivalent_format_alternates=sum(row['selection_excluded'] for row in result),
                   method='Source-bound label correction, not isolated listening or model-weight training')
    (LIBRARY / 'new-packs-2026-11-07-curation.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'curated': len(result), 'categories': receipt['categories']}))


if __name__ == '__main__':
    main()
