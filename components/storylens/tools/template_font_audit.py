"""Read-only AEP font-reference inventory; binary results are candidates, not native usage proof."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from fontTools.ttLib import TTFont, TTCollection


def decode_literal(raw):
    out = bytearray()
    i = 0
    escapes = {ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('b'): 8, ord('f'): 12}
    while i < len(raw):
        c = raw[i]
        i += 1
        if c != 92 or i == len(raw):
            out.append(c)
            continue
        c = raw[i]
        i += 1
        if 48 <= c <= 55:
            digits = bytes([c])
            while i < len(raw) and len(digits) < 3 and 48 <= raw[i] <= 55:
                digits += bytes([raw[i]])
                i += 1
            out.append(int(digits, 8) & 255)
        elif c in (10, 13):
            if c == 13 and i < len(raw) and raw[i] == 10:
                i += 1
        else:
            out.append(escapes.get(c, c))
    return bytes(out)


def extract_aep_fonts(data, errors=None):
    found = set()
    pattern = rb'/CoolTypeFont\s*/0\s*<<\s*/0\s*\(((?:\\.|[^\\)])*)\)'
    for match in re.finditer(pattern, data, re.S):
        raw = decode_literal(match[1])
        try:
            name = raw[2:].decode('utf-16-be', errors='strict') if raw.startswith(b'\xfe\xff') else raw.decode('utf-8', errors='strict')
        except UnicodeDecodeError as error:
            if errors is not None:errors.append({'offset':match.start(),'error':str(error)})
            continue
        if name and name != 'AdobeInvisFont':
            found.add(name)
    return sorted(found, key=str.casefold)


def font_names(path):
    fonts = TTCollection(path, lazy=True).fonts if path.suffix.lower() in ('.ttc', '.otc') else [TTFont(path, lazy=True)]
    result = []
    for font in fonts:
        names = {}
        for row in font['name'].names:
            if row.nameID in (1, 2, 4, 6, 16, 17):
                try:
                    names.setdefault(str(row.nameID), set()).add(row.toUnicode())
                except UnicodeError:
                    pass
        result.append({key: sorted(value) for key, value in names.items()})
        font.close()
    return result


def inventory(root, font_roots):
    projects, refs, errors, fonts = [], {}, [], []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in ('.aep', '.aepx', '.aet') or p.name.startswith('._'):
            continue
        b = p.read_bytes()
        font_errors=[]
        names = extract_aep_fonts(b,font_errors)
        errors.extend({'path':str(p),**error} for error in font_errors)
        row = {'path': str(p), 'sha256': hashlib.sha256(b).hexdigest(), 'fonts': names, 'binary_candidate_scan': True}
        projects.append(row)
        for name in names:
            refs.setdefault(name, []).append(str(p.relative_to(root)))
    for base in font_roots:
        if not base.exists():
            continue
        for p in base.rglob('*'):
            if p.suffix.lower() not in ('.ttf', '.otf', '.ttc', '.otc'):
                continue
            try:
                for names in font_names(p):
                    fonts.append({'path': str(p), 'names': names})
            except Exception as e:
                errors.append({'path': str(p), 'error': str(e)})
    installed = {name for f in fonts for name in f['names'].get('6', [])}
    return {'root': str(root), 'projects': projects, 'references': refs, 'installed_fonts': fonts,
            'missing_candidates': sorted(set(refs) - installed, key=str.casefold),
            'font_read_errors': errors, 'note': 'Binary tables include fallback/unused references; verify current project with AE usedFonts. Original AEPs unchanged.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--font-root', action='append', type=Path, default=[])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = inventory(args.root, args.font_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'projects': len(result['projects']), 'font_candidates': len(result['references']), 'missing_candidates': result['missing_candidates'], 'no_font_table': sum(not p['fonts'] for p in result['projects'])}))
