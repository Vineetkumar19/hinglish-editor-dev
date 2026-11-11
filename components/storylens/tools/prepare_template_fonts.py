"""Download only requested open-source font families, retaining their source and license."""
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import quote
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from template_font_audit import font_names

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'library/template-fonts'
FAMILIES = ['abhayalibre', 'alegreya', 'bebasneue', 'caveat', 'forum', 'gothica1', 'kanit', 'lato', 'montserrat', 'opensans', 'poppins', 'ptserif', 'rajdhani', 'raleway', 'roboto', 'robotocondensed', 'satisfy', 'secularone', 'sourcesanspro']


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Storylens-Font-Inventory/1.0'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()


def prepare_family(family, wanted):
    rows = []
    target = DEST / family
    target.mkdir(parents=True, exist_ok=True)
    errors = []
    for license_dir in ('ofl', 'apache'):
        base = f'https://raw.githubusercontent.com/google/fonts/main/{license_dir}/{family}/'
        try:
            metadata = fetch(base + 'METADATA.pb')
            license_name = 'OFL.txt' if license_dir == 'ofl' else 'LICENSE.txt'
            license_data = fetch(base + license_name)
            break
        except Exception as e:
            errors.append(str(e))
    else:
        return {'family': family, 'error': errors}
    (target / 'METADATA.pb').write_bytes(metadata)
    (target / license_name).write_bytes(license_data)
    filenames = sorted(set(re.findall(r'filename: "([^"]+)"', metadata.decode())))
    for name in filenames:
        try:
            url = base + quote(name)
            source = target / name
            if not source.exists():
                source.write_bytes(fetch(url))
            with TTFont(source) as font:
                if 'fvar' in font:
                    # Only official named instances. Preserve the actual instance names.
                    for instance in font['fvar'].instances:
                        axes = {axis.axisTag: instance.coordinates.get(axis.axisTag, axis.defaultValue) for axis in font['fvar'].axes}
                        static = instantiateVariableFont(font, axes, inplace=False, updateFontNames=True)
                        ps = static['name'].getDebugName(6)
                        if ps not in wanted:
                            continue
                        output = target / (ps + '.ttf')
                        static.save(output)
                        rows.append({'source': str(output), 'postscript_name': ps, 'url': url, 'license': str(target / license_name), 'axes': axes, 'derived_named_instance': True})
                else:
                    ps = font['name'].getDebugName(6)
                    if ps in wanted:
                        rows.append({'source': str(source), 'postscript_name': ps, 'url': url, 'license': str(target / license_name)})
        except Exception as e:
            errors.append(name + ': ' + str(e))
    for row in rows:
        row['sha256'] = hashlib.sha256(Path(row['source']).read_bytes()).hexdigest()
    return {'family': family, 'fonts': rows, 'errors': errors}


if __name__ == '__main__':
    audit = json.loads((ROOT / 'output/template-fonts/audit-before.json').read_text('utf-8'))
    wanted = set(audit['missing_candidates'])
    # Native usage can include fonts that are not retained in binary fallback tables.
    native = json.loads((ROOT / 'output/template-fonts/native-fonts.json').read_text('utf-8-sig'))
    wanted.update(f['postScriptName'] for f in native['used'] if f['isSubstitute'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda family: prepare_family(family, wanted), FAMILIES))
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {'families': results, 'fonts': [row for result in results for row in result.get('fonts', [])]}
    (DEST / 'sources.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'prepared_faces': len(manifest['fonts']), 'families': [{k: v for k, v in result.items() if k != 'fonts'} for result in results]}, indent=2))
