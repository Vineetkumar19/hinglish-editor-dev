"""Record reviewed local thumbnail exports after both authorized tasks pass."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--visual-review-passed',action='store_true')
    assert parser.parse_args().visual_review_passed,'Inspect the three exports before recording visual review'
    assert read(Path(r'C:\Ai Models\logs\model-upgrade-completion.json'))['status']=='complete'
    assert read(ROOT/'output/validation/new-laptop/localhost-upgrade-checks.json')['passed']
    proof=ROOT/'output/validation/new-laptop/thumbnail-upgrade-inference.json'
    data=read(proof);assert data['passed']
    card=read(ROOT/'library/thumbnail-styles/mumbai-indians-2020/style.json')
    for source in card['sources']:
        with Path(source['path']).open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest()==source['sha256']
    data.update(visual_review_pending=False,visual_review_passed=True,
        visual_review_notes='All three final PNGs inspected: player imagery present, faces visible, readable headlines and distinct backgrounds/layouts; bottom cutout edges refined.',
        original_references_unchanged=True,
        comparison=str(Path(data['folder'])/'three-options-wide.jpg'))
    data['final_sha256']={file:hashlib.sha256(Path(file).read_bytes()).hexdigest() for file in data['images']}
    proof.write_text(json.dumps(data,indent=2),encoding='utf-8')
    report=Path(data['gallery']);page=report.read_text(encoding='utf-8')
    if 'Official IPL' not in page:
        page+='<p>Story facts: <a href="'+html.escape(data['fact_source'],quote=True)+'">Official IPL 2020 final match report</a></p>'
        report.write_text(page,encoding='utf-8')
    print('MODEL_SETUP_AND_THUMBNAIL_VISUAL_REVIEW_PASSED')
    print('C_FREE_GiB',round(shutil.disk_usage(r'C:\Ai Models').free/2**30,1))


if __name__=='__main__':main()
