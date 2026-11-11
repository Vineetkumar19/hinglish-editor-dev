"""Run/resume the saved Vineet style analysis locally, one stage at a time."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = ROOT / 'output/reference-analysis/cricket-documentaries'


def main(skip_scan=False):
    from tools.analyze_documentary_reference import facts
    profile = json.loads((ROOT / 'library/creator-profiles/beneath-documentary-edit.json').read_text(encoding='utf-8'))
    folder = Path(profile['source_folder'])
    original = json.loads((BASE / 'inventory.json').read_text(encoding='utf-8'))
    slugs = {str(Path(i['path']).resolve()).casefold(): i['slug'] for i in original}
    occupied = set(slugs.values())
    inventory = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}:
            continue
        key = str(path.resolve()).casefold()
        slug = slugs.get(key)
        if slug is None:
            import re
            stem = re.sub(r'[^a-z0-9]+', '-', path.stem.lower()).strip('-') or 'reference'
            slug = stem
            suffix = 2
            while slug in occupied:
                slug = f'{stem}-{suffix}'
                suffix += 1
            occupied.add(slug)
        source = facts(path)
        inventory.append({'name': path.name, 'slug': slug, 'path': str(path),
                          'seconds': source['seconds'], 'duration': source['seconds'], 'bytes': source['bytes']})
    if not inventory:
        raise ValueError('No reference videos were found in the saved Vineet folder.')
    # Additional videos need reviewed chapter notes; numeric/local-model analysis
    # still works when no human/assistant review has yet been performed.
    for item in inventory:
        target = BASE / item['slug']
        target.mkdir(exist_ok=True)
        notes = target / 'review-notes.json'
        if not notes.exists():
            notes.write_text(json.dumps({'source': item['name'], 'chapters': [], 'visual_review': {},
                'coverage_limit': 'No reviewed chapter notes yet; automatic measurements and local-model candidates only.'}, indent=2), encoding='utf-8')
    (BASE / 'inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    stages = [] if skip_scan else [('Native-frame and complete audio measurements',
                                   ['tools/analyze_crick_edit_dna.py', '--base', str(BASE), '--speech'])]
    stages += [('Offline scene, voice and sound interpretation', ['tools/classify_crick_edit_dna.py', '--base', str(BASE)]),
               ('Local style/vector memory and review', ['tools/build_vineet_editing_dna.py'])]
    began = time.time()
    progress = {'style': 'vineet documentry edit', 'status': 'running', 'sources': len(inventory), 'started': began}
    path = BASE / 'dna-learning-progress.json'
    try:
        for stage, args in stages:
            progress.update(stage=stage, elapsed_seconds=time.time() - began)
            path.write_text(json.dumps(progress, indent=2), encoding='utf-8')
            print(stage, flush=True)
            # Explicit pipes keep nested worker progress visible on Windows,
            # including when CREATE_NO_WINDOW is used by a desktop launcher.
            child = subprocess.Popen([sys.executable, '-u', *args], cwd=ROOT,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding='utf-8', errors='replace',
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for line in child.stdout:
                print(line, end='', flush=True)
            if child.wait():
                raise subprocess.CalledProcessError(child.returncode, child.args)
        progress.update(status='complete', elapsed_seconds=time.time() - began,
                        report=str(BASE / 'dna-report.html'))
    except BaseException as error:
        progress.update(status='failed', error=str(error), elapsed_seconds=time.time() - began)
        raise
    finally:
        path.write_text(json.dumps(progress, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--interpret-and-index', action='store_true', help='Continue after completed source measurements.')
    args = parser.parse_args()
    main(args.interpret_and_index)
