"""Save bounded, offline Earshot observations for the owner's 640 pack.

Acoustic model tags are evidence for retrieval, never literal source identity.
"""
import argparse
import json
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/reference-repositories/earshot'))
from earshot import api


def main(max_files=None):
    library = ROOT / 'library/owner-sound-packs'
    catalogue = json.loads((library / '640-cinematic-curation.json').read_text(encoding='utf-8'))
    receipt = library / '640-cinematic-acoustics.json'
    saved = json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {'files': {}}
    rows = catalogue['files'][:max_files] if max_files else catalogue['files']
    for index, row in enumerate(rows, 1):
        sha = row['sha256']
        if sha in saved['files']:
            continue
        try:
            with wave.open(row['imported'], 'rb') as wav:
                end = min(8.0, wav.getnframes() / wav.getframerate())
            result = api.describe(row['imported'], start=0, end=end)
            tags = [{k: tag.get(k) for k in ('term', 'category', 'z', 'verdict')}
                    for tag in result.get('top_tags', [])[:6]]
            saved['files'][sha] = {'title': row['title'], 'sample_window_seconds': [0, end],
                                    'top_tags': tags,
                                    'measurements': {k: result.get('measurements', {}).get(k)
                                                     for k in ('duration', 'lufs', 'onset_count', 'brightness_hz')},
                                    'status': 'estimated'}
        except Exception as exc:
            saved['files'][sha] = {'title': row['title'], 'status': 'failed', 'error_type': type(exc).__name__}
        if index % 5 == 0 or index == len(rows):
            receipt.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'acoustic samples {index}/{len(rows)}', flush=True)
    print(json.dumps({'sampled': len(saved['files']),
                      'failed': sum(r['status'] == 'failed' for r in saved['files'].values())}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-files', type=int)
    args = parser.parse_args()
    main(args.max_files)
