"""Content-verified, copy-only consolidation. No Adobe/project execution."""
import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

DEFAULT_ROOT = Path(r'D:\Editing\AE documentry style editing templates')
PROJECTS = {'.aep', '.aepx', '.aet'}
MEDIA = {'.png', '.jpg', '.jpeg', '.psd', '.psb', '.ai', '.eps', '.exr', '.tif', '.tiff', '.tga', '.bmp', '.gif', '.webp', '.mp4', '.mov', '.avi', '.mxf', '.m4v', '.flv', '.wav', '.mp3', '.aif', '.aiff', '.otf', '.ttf'}
SKIP = {'__macosx', 'adobe after effects auto-save', 'auto-save', '.git'}


def eligible(p):
    return not any(part.lower() in SKIP or part.startswith('.') for part in p.parts) and p.name.lower() not in {'thumbs.db', '.ds_store'}


def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def within(p, root):
    return p == root or root in p.parents


def package_root(project, root, destination):
    folder = project.parent
    # Preserve sibling media when the project lives inside a conventional AE folder.
    while folder.parent not in {root, destination} and re.fullmatch(r'(?:ae|after\s*effects|project(?:\s*files?)?)', folder.name, re.I):
        if any(child.is_dir() and re.search(r'footage|assets|media|images|prerender', child.name, re.I) for child in folder.iterdir()):
            break
        folder = folder.parent
    return folder


def plan(root=DEFAULT_ROOT, cache_file=None, progress=None):
    root = Path(root).resolve(strict=True)
    destination = root / 'LatestUniqueTemplete'
    if destination.is_symlink():
        raise ValueError('The destination must be a local folder.')
    files = []
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if eligible(Path(d)) and not (Path(base) / d).is_symlink()]
        for name in names:
            p = Path(base) / name
            if eligible(p.relative_to(root)) and not p.is_symlink():
                files.append(p)
    cache = {}
    if cache_file and Path(cache_file).exists():
        cache = json.loads(Path(cache_file).read_text(encoding='utf-8'))
    hashed = 0

    def hashed_file(p):
        nonlocal hashed
        stat = p.stat()
        key = str(p)
        item = cache.get(key)
        if not item or item['size'] != stat.st_size or item['mtime_ns'] != stat.st_mtime_ns:
            item = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'sha256': digest(p)}
            cache[key] = item
            hashed += 1
            if progress and hashed % 100 == 0:
                progress({'hashed_files': hashed, 'current': str(p)})
        return item['sha256']

    projects = [p for p in files if p.suffix.lower() in PROJECTS]
    roots = {p: package_root(p, root, destination) for p in projects}
    package_files = {}
    asset_sets = {}
    for base in set(roots.values()):
        # Loose root projects must not absorb a sibling template's whole package.
        foreign = {b for b in roots.values() if b != base and within(b, base)}
        prefix = str(base) + os.sep
        foreign_prefixes = tuple(str(b) + os.sep for b in foreign)
        owned = [p for p in files if str(p).startswith(prefix) and (not foreign_prefixes or not str(p).startswith(foreign_prefixes))]
        package_files[base] = owned
        asset_sets[base] = {hashed_file(p) for p in owned if p.suffix.lower() in MEDIA and not re.search(r'tutorial|how.to.use|video.help|guide', p.name, re.I)}
    groups = {}
    for p in projects:
        groups.setdefault(hashed_file(p), []).append(p)
    missing = []
    requests = {}
    for fingerprint, copies in groups.items():
        saved = [p for p in copies if within(p, destination)]
        outside = [p for p in copies if not within(p, destination)]
        covered = [asset_sets[roots[p]] for p in saved]
        # Prefer the most complete source; subsets of that source are duplicates.
        outside.sort(key=lambda p: (-len(asset_sets[roots[p]]), str(p).lower()))
        if not saved:
            missing.append({'sha256': fingerprint, 'sources': [str(p) for p in outside]})
        for p in outside:
            assets = asset_sets[roots[p]]
            if saved and any(assets <= previous for previous in covered):
                continue
            reason = 'missing_project' if not covered else 'different_assets'
            requests.setdefault(roots[p], {'reason': reason, 'project_hashes': []})['project_hashes'].append(fingerprint)
            covered.append(assets)
            saved.append(p)
    packages = []
    for source, info in sorted(requests.items(), key=lambda r: str(r[0]).lower()):
        source_projects = [p for p in projects if roots[p] == source]
        name = source.name
        if re.search(r'issue.not.checked|^(?:after\s*effects|project|ae)$', name, re.I):
            name = source_projects[0].stem
        target = destination / name
        if target.exists() or any(Path(x['destination']) == target for x in packages):
            target = destination / (name + ' - ' + hashlib.sha256(str(source).encode()).hexdigest()[:8])
        entries = []
        for p in package_files[source]:
            if p.suffix.lower() in {'.zip', '.rar', '.7z'}:
                continue
            st = p.stat()
            entries.append({'relative': str(p.relative_to(source)), 'size': st.st_size, 'sha256': hashed_file(p)})
        packages.append({'source': str(source), 'destination': str(target), **info, 'files': entries, 'bytes': sum(x['size'] for x in entries)})
    if cache_file:
        Path(cache_file).write_text(json.dumps(cache), encoding='utf-8')
    return {'root': str(root), 'destination': str(destination), 'project_files': len(projects), 'unique_projects': len(groups), 'missing_projects': missing, 'packages': packages, 'copy_bytes': sum(x['bytes'] for x in packages)}


def apply(prepared):
    root = Path(prepared['root']).resolve(strict=True)
    destination = (root / 'LatestUniqueTemplete').resolve()
    if Path(prepared['destination']).resolve() != destination or not within(destination, root):
        raise ValueError('Invalid destination.')
    # Validate every source and destination before making the first copy.
    for package in prepared['packages']:
        source = Path(package['source']).resolve(strict=True)
        target = Path(package['destination']).resolve()
        if not within(source, root) or within(source, destination) or target.parent != destination or target.exists():
            raise ValueError('The source or destination changed. Rebuild the copy plan.')
        for entry in package['files']:
            p = source / entry['relative']
            if not within(p.resolve(strict=True), source) or p.is_symlink() or digest(p) != entry['sha256']:
                raise ValueError('A source file changed. Rebuild the copy plan.')
            if not within((target / entry['relative']).resolve(), target):
                raise ValueError('Invalid destination path.')
    destination.mkdir(exist_ok=True)
    receipts = []
    for package in prepared['packages']:
        source, target = Path(package['source']), Path(package['destination'])
        target.mkdir()
        for entry in package['files']:
            original, copied = source / entry['relative'], target / entry['relative']
            copied.parent.mkdir(parents=True, exist_ok=True)
            with original.open('rb') as inp, copied.open('xb') as output:
                shutil.copyfileobj(inp, output, 1024 * 1024)
            if digest(copied) != entry['sha256']:
                raise ValueError('Copied file verification failed: ' + str(copied))
            shutil.copystat(original, copied)
        receipts.append({'source': str(source), 'destination': str(target), 'files_verified': len(package['files']), 'reason': package['reason']})
    return {'copied_packages': len(receipts), 'packages': receipts, 'originals_preserved': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'output/documentary-library-evidence')
    parser.add_argument('--apply', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.apply:
        result = apply(json.loads(args.apply.read_text(encoding='utf-8')))
        (args.output / 'copy-receipt.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    else:
        result = plan(args.root, args.output / 'content-hash-cache.json', lambda r: print(json.dumps(r), flush=True))
        (args.output / 'copy-plan.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in {'packages', 'missing_projects'}}, indent=2))
