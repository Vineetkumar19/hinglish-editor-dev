"""Resolve with pip, then prefetch its exact hashed artifacts with resumable ranges."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

from ranged_download import ranged_get
import ranged_download

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse-report', action='store_true')
    args = parser.parse_args()
    report = ROOT / 'downloads/laptop-dependency-report.json'
    if not args.reuse_report:
        subprocess.run([sys.executable, '-E', '-m', 'pip', 'install', '--dry-run', '--report', str(report),
            '-r', 'requirements.txt', '-r', 'requirements-saas.txt', '-r', 'requirements-publish.txt',
            'diffusers>=0.36', 'accelerate>=1.10', 'sentencepiece', 'protobuf', 'ftfy', 'imageio'],
            cwd=ROOT, check=True)
    data = json.loads(report.read_text(encoding='utf-8'))
    rows = data['install']
    # pip's report omits already installed dependencies. The separate generation
    # venv still needs Torch's small base packages, so cache their exact versions too.
    from pip._vendor.packaging.tags import sys_tags
    from pip._vendor.packaging.utils import parse_wheel_filename
    ranks = {tag: index for index, tag in enumerate(sys_tags())}
    names = {row['metadata']['name'].lower().replace('_', '-') for row in rows}
    for name in ('filelock', 'typing_extensions', 'sympy', 'networkx', 'jinja2', 'fsspec', 'setuptools', 'mpmath', 'MarkupSafe'):
        if name.lower().replace('_', '-') in names:
            continue
        version = importlib.metadata.version(name)
        with urlopen('https://pypi.org/pypi/' + quote(name) + '/' + quote(version) + '/json', timeout=45) as response:
            release = json.load(response)
        candidates = []
        for item in release['urls']:
            if not item['filename'].endswith('.whl'):
                continue
            tags = parse_wheel_filename(item['filename'])[3]
            supported = [ranks[tag] for tag in tags if tag in ranks]
            if supported:
                candidates.append((min(supported), item))
        item = min(candidates, key=lambda value: value[0])[1]
        rows.append({'metadata': {'name': name, 'version': version},
            'download_info': {'url': item['url'], 'archive_info': {'hashes': {'sha256': item['digests']['sha256']}}}})
    report.write_text(json.dumps(data, indent=2), encoding='utf-8')
    constraints = '\n'.join(sorted(row['metadata']['name'] + '==' + row['metadata']['version'] for row in rows)) + '\n'
    (ROOT / 'downloads/laptop-resolved-constraints.txt').write_text(constraints, encoding='utf-8')
    ranged_download.CHUNK = 1024 * 1024

    def fetch(row):
        info = row['download_info']
        url = info['url']
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname not in ('files.pythonhosted.org', 'download.pytorch.org'):
            raise ValueError('Unexpected package source in pip report: ' + str(parsed.hostname))
        sha = info['archive_info']['hashes']['sha256']
        name = unquote(parsed.path.rsplit('/', 1)[-1])
        target = ROOT / 'downloads/wheels' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            with target.open('rb') as source:
                if hashlib.file_digest(source, 'sha256').hexdigest() == sha:
                    return
        with urlopen(Request(url, method='HEAD'), timeout=45) as response:
            size = int(response.headers['Content-Length'])
        partial = target.with_suffix(target.suffix + '.incomplete')
        resume = partial.stat().st_size if partial.is_file() else 0
        with partial.open('r+b' if partial.exists() else 'w+b') as stream:
            ranged_get(url, stream, size, resume, workers=4, expected_sha256=sha)
        partial.replace(target)
        print('Verified package: ' + name, flush=True)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(fetch, rows))
    (ROOT / 'downloads/laptop-wheels-ready.txt').write_text(str(len(rows)), encoding='utf-8')
    print(f'All {len(rows)} resolved package artifacts are verified in downloads/wheels.', flush=True)


if __name__ == '__main__':
    main()
