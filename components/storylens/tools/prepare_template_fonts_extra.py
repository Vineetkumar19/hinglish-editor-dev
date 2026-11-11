"""Download bounded publisher archives; extract only referenced desktop font identities."""
import io
import json
import hashlib
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


def register(source, url, license_path):
    for names in font_names(source):
        for ps in names.get('6', []):
            if ps in wanted and not any(r['postscript_name'] == ps for r in manifest['fonts']):
                manifest['fonts'].append(dict(source=str(source),postscript_name=ps,url=url,license=str(license_path),sha256=hashlib.sha256(source.read_bytes()).hexdigest()))


archives = [
 ('typodermic', 'https://typodermicfonts.com/assets/downloads/typodermic-free-fonts-2026i.zip'),
 ('bebas-neue-legacy', 'https://codeload.github.com/dharmatype/Bebas-Neue/zip/refs/heads/master'),
 ('bebas-original', 'https://codeload.github.com/dharmatype/Bebas/zip/refs/heads/master'),
 ('hack', 'https://codeload.github.com/source-foundry/Hack/zip/refs/heads/master'),
 ('metropolis', 'https://codeload.github.com/dw5/metropolis/zip/refs/heads/master'),
 ('another-typewriter', 'https://dl.dafont.com/dl/?f=another_typewriter')
]
for family, url in archives:
    try:
        target = DEST / family
        target.mkdir(exist_ok=True)
        archive = zipfile.ZipFile(io.BytesIO(fetch(url)))
        for member in archive.infolist():
            name = Path(member.filename).name
            if member.is_dir() or name.startswith('._') or '__MACOSX' in member.filename:
                continue
            ext = Path(name).suffix.lower()
            if ext in ('.otf', '.ttf'):
                data = archive.read(member)
                from fontTools.ttLib import TTFont
                with TTFont(io.BytesIO(data)) as f:
                    ps = f['name'].getDebugName(6)
                if ps not in wanted:
                    continue
                source = target / (ps + ext)
                if source.exists() and source.read_bytes() != data:
                    continue
                source.write_bytes(data)
                register(source, url, target)
            elif ext in ('.txt', '.md', '.pdf', '.html') and any(word in name.lower() for word in ('license','licence','eula','read','ofl','copy','dont')):
                # Keep license notices as data; never execute content from an archive.
                (target / name).write_bytes(archive.read(member))
        (target / 'download-source.txt').write_text(url, encoding='utf-8')
    except Exception as e:
        errors.append({'family':family,'error':str(e)})
manifest['extra_download_errors'] = errors
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'prepared':len(manifest['fonts']),'errors':errors},indent=2))
