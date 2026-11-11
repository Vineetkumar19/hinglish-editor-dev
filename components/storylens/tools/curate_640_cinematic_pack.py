"""Catalog the owner's 640 Cinematic pack without changing its audio bytes.

Roles are conservative title/folder estimates. They are search hints, not
listening approval or an instruction to place every sound on a timeline.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r'D:\Editing\Sound Packs\640CinematicSoundPack')
LIBRARY = ROOT / 'library/owner-sound-packs'
MUSIC_TITLES = {
    'running (percussion)', 'choices interlude', 'discovery (piano)',
    'epic drums', 'long strings cm', 'lonley desert interlude',
    'on a mission interlude', 'space interlude', 'suspence violins',
    'trailer all strings', 'trailer bass section', 'trailer brass section',
    'trailer choir', 'trailer harp', 'trailer intro (piano)',
    'trailer viola section', 'trailer violin section', 'viola solo',
    'violin chord', 'violin section', 'into the night chorus',
    'into the night', 'running bass',
}
ACOUSTIC_OVERRIDES = {
    'anxiety trip': ('impact', 'sub bass drop'),
    'bass run': ('impact', 'sub bass drop'),
    'blade runner': ('riser', 'rising sweep'),
}


def title(path):
    return path.stem.strip().casefold()


def effect_family(path):
    name = title(path)
    if name in ACOUSTIC_OVERRIDES:
        return ACOUSTIC_OVERRIDES[name][0]
    if re.search(r'ris(?:e|er)|swell|build', name):
        return 'riser'
    if re.search(r'hit|boom|thud|bang|drop', name):
        return 'impact'
    if re.search(r'woosh|whoosh|warp|pass(?:ing|er)', name):
        return 'whoosh'
    if re.search(r'feedback|transform bot', name):
        return 'glitch'
    if name == 'behind the door':
        return 'foley'
    if name == 'wind':
        return 'ambience'
    # The source is a designed cinematic pack. A vague title does not prove
    # a literal environmental recording, even when it says ocean or desert.
    return 'suspense'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def catalogue(apply=False):
    manifest = json.loads((LIBRARY / 'import-manifest.json').read_text(encoding='utf-8'))
    prior = {row['sha256']: row for row in manifest['files']
             if '640CinematicSoundPack' in row['source']}
    files = sorted(SOURCE.rglob('*.wav'))
    if len(files) != 102:
        raise RuntimeError(f'Expected the observed 102 WAVs; found {len(files)}')
    rows = []
    for path in files:
        sha = digest(path)
        previous = prior.get(sha)
        if not previous:
            raise RuntimeError(f'Unrecognized recording; do not silently reuse an old label: {path}')
        owned = Path(previous['path'].replace('A:\\', 'D:\\'))
        if not owned.is_file() or digest(owned) != sha:
            raise RuntimeError(f'Imported recording is absent or changed: {owned}')
        section = path.relative_to(SOURCE).parts[0]
        is_music = title(path) in MUSIC_TITLES
        category = 'music_candidate' if is_music else effect_family(path)
        rows.append(dict(source=str(path), imported=str(owned), sha256=sha,
                         title=path.stem.strip(), section=section,
                         role=category, audible_identity_verified=False,
                         evidence='Earshot first-eight-second acoustic estimate' if title(path) in ACOUSTIC_OVERRIDES
                                  else 'filename and pack section only'))
        if not apply:
            continue
        sidecar = Path(str(owned) + '.json')
        meta = json.loads(sidecar.read_text(encoding='utf-8'))
        meta.update(source_url=str(path), category='general' if is_music else category,
                    tags=[section, '640 Cinematic Sound Pack',
                          'instrumental score or stem candidate' if is_music else 'designed cinematic sound effect',
                          category] + ([ACOUSTIC_OVERRIDES[title(path)][1]]
                                       if title(path) in ACOUSTIC_OVERRIDES else []),
                    classification_basis=rows[-1]['evidence'] + '; full audition pending')
        sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        if is_music:
            target = LIBRARY / 'music/general' / owned.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                os.link(owned, target)  # same-volume hardlink: no second audio copy
            elif digest(target) != sha:
                raise RuntimeError(f'Music link conflicts with another recording: {target}')
            music_meta = dict(meta, category='general', tags=[section, '640 Cinematic Sound Pack',
                              'instrumental score or stem candidate'])
            Path(str(target) + '.json').write_text(json.dumps(music_meta, ensure_ascii=False, indent=2), encoding='utf-8')
            rows[-1]['music_path'] = str(target)
    receipt = dict(source=str(SOURCE), matched_existing=len(rows),
                   music_candidates=sum(r['role'] == 'music_candidate' for r in rows),
                   effect_families={family:sum(r['role'] == family for r in rows)
                                    for family in sorted({r['role'] for r in rows if r['role'] != 'music_candidate'})},
                   method='Hash match to existing import; title/section role hints; no full audio audition',
                   files=rows)
    if apply:
        (LIBRARY / '640-cinematic-curation.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    result = catalogue(args.apply)
    print(json.dumps({key: result[key] for key in ('matched_existing', 'music_candidates', 'effect_families')}))
