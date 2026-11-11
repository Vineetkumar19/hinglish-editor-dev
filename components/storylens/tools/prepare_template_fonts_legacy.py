"""Recover original legacy names from the official Google font archive and author downloads."""
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import quote
from prepare_template_fonts import ROOT, DEST, fetch
from template_font_audit import font_names

manifest_path = DEST / 'sources.json'
manifest = json.loads(manifest_path.read_text('utf-8'))
audit = json.loads((ROOT / 'output/template-fonts/audit-before.json').read_text('utf-8'))
wanted = set(audit['missing_candidates'])
errors = []


def register(path, url, license_path, **extra):
    for names in font_names(path):
        for ps in names.get('6', []):
            if ps in wanted and not any(r['postscript_name'] == ps for r in manifest['fonts']):
                manifest['fonts'].append(dict(source=str(path), postscript_name=ps, url=url, license=str(license_path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **extra))


for family, directory in [('alegreya', 'ofl'), ('opensans', 'apache'), ('raleway', 'ofl'), ('caveat', 'ofl'), ('sourcesanspro', 'ofl'), ('roboto', 'apache')]:
    try:
        commits = json.loads(fetch(f'https://api.github.com/repos/google/fonts/commits?path={directory}/{family}&until=2020-01-01T00:00:00Z&per_page=1'))
        if not commits:
            raise ValueError('No matching legacy commit')
        ref = commits[0]['sha']
        base = f'https://raw.githubusercontent.com/google/fonts/{ref}/{directory}/{family}/'
        metadata = fetch(base + 'METADATA.pb')
        target = DEST / ('legacy-' + family)
        target.mkdir(exist_ok=True)
        license_name = 'OFL.txt' if directory == 'ofl' else 'LICENSE.txt'
        (target / license_name).write_bytes(fetch(base + license_name))
        (target / 'METADATA.pb').write_bytes(metadata)
        for block in metadata.decode().split('fonts {')[1:]:
            ps = re.search(r'post_script_name: "([^"]+)"', block)
            filename = re.search(r'filename: "([^"]+)"', block)
            if not ps or ps[1] not in wanted or not filename:
                continue
            source = target / filename[1]
            url = base + quote(filename[1])
            source.write_bytes(fetch(url))
            register(source, url, target / license_name, legacy_commit=ref)
    except Exception as e:
        errors.append({'family': family, 'error': str(e)})

# These author pages explicitly label these exact two fonts as free for commercial use.
for slug in ['aa_typewriter', 'moms_typewriter']:
    try:
        url = 'https://dl.dafont.com/dl/?f=' + slug
        data = fetch(url)
        target = DEST / slug
        target.mkdir(exist_ok=True)
        archive = zipfile.ZipFile(io.BytesIO(data))
        page = 'https://www.dafont.com/' + slug.replace('_', '-') + '.font' if slug == 'aa_typewriter' else 'https://www.dafont.com/moms_typewriter.font'
        license_path = target / 'author-page.html'
        license_path.write_bytes(fetch(page))
        for member in archive.infolist():
            if member.is_dir():
                continue
            name = Path(member.filename).name
            if Path(name).suffix.lower() not in ('.ttf', '.otf', '.txt', '.pdf'):
                continue
            source = target / name
            source.write_bytes(archive.read(member))
            if source.suffix.lower() in ('.ttf', '.otf'):
                register(source, url, license_path, author_page=page)
    except Exception as e:
        errors.append({'family': slug, 'error': str(e)})

try:
    page = fetch('https://www.tinkov.info/gilroy.html').decode('utf-8', errors='replace')
    links = re.findall(r'href=[\"\x27]([^\"\x27]+\.zip)[\"\x27]', page)
    from urllib.parse import urljoin
    url = next(urljoin('https://www.tinkov.info/gilroy.html', link) for link in links if 'gilroy' in link.lower())
    target = DEST / 'gilroy'
    target.mkdir(exist_ok=True)
    (target / 'author-page.html').write_text(page, encoding='utf-8')
    archive = zipfile.ZipFile(io.BytesIO(fetch(url)))
    for member in archive.infolist():
        name = Path(member.filename).name
        if not member.is_dir() and not name.startswith('._') and '__MACOSX' not in member.filename and Path(name).suffix.lower() in ('.otf', '.ttf', '.pdf', '.txt'):
            source = target / name
            source.write_bytes(archive.read(member))
            if source.suffix.lower() in ('.otf', '.ttf'):
                register(source, url, target / 'author-page.html')
except Exception as e:
    errors.append({'family': 'gilroy', 'error': str(e)})

# The owner's package already includes these source fonts. Preserve their bytes.
for source in Path(audit['root']).rglob('*.OTF'):
    if source.is_file():
        register(source, 'Owner-provided template font asset', source.parent, owner_supplied=True)
manifest['legacy_download_errors'] = errors
manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'prepared': len(manifest['fonts']), 'errors': errors}, indent=2))
