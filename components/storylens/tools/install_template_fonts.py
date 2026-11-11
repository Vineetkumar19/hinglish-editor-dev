"""Register verified template font files per user, without replacing existing fonts."""
import argparse
import ctypes
import hashlib
import json
import os
import shutil
from pathlib import Path
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]


def prepare_plan(manifest, target):
    rows = []
    seen = set()
    for entry in manifest['fonts']:
        source = Path(entry['source'])
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != entry['sha256']:
            raise ValueError('The font source changed. Restore the verified download before installing.')
        with TTFont(source) as font:
            ps = font['name'].getDebugName(6)
            title = font['name'].getDebugName(4)
        if ps != entry['postscript_name']:
            raise ValueError('The downloaded font identity does not match the installation plan.')
        if ps in seen:
            continue
        seen.add(ps)
        destination = target / ('StorylensTemplate-' + ps + source.suffix.lower())
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError('An existing font file was kept. Its content differs from this download.')
        rows.append(dict(entry, path=str(destination), title=title, registry_value=title + (' (OpenType)' if source.suffix.lower() == '.otf' else ' (TrueType)')))
    return rows


def install(apply=False, manifest_path=None, receipt_path=None):
    manifest = json.loads((Path(manifest_path) if manifest_path else ROOT / 'library/template-fonts/sources.json').read_text('utf-8'))
    target = Path(os.environ['LOCALAPPDATA']) / 'Microsoft/Windows/Fonts'
    rows = prepare_plan(manifest, target)
    receipt = {'installed': False, 'fonts': rows, 'skipped_existing_registrations': []}
    if not apply:
        return receipt
    import winreg
    target.mkdir(parents=True, exist_ok=True)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
        for row in rows:
            try:
                old, _ = winreg.QueryValueEx(key, row['registry_value'])
            except FileNotFoundError:
                old = None
            if old is not None and str(old).casefold() != row['path'].casefold():
                row['existing_registration'] = str(old)
                row['status'] = 'existing registration preserved'
                receipt['skipped_existing_registrations'].append(row['postscript_name'])
                # Activate the existing file if it is the same face; no registry edits.
                existing = Path(str(old))
                if not existing.is_absolute():
                    existing = Path(os.environ['WINDIR']) / 'Fonts' / existing
                if existing.is_file():
                    with TTFont(existing) as font:
                        exact = font['name'].getDebugName(6) == row['postscript_name']
                    if exact:
                        row['existing_faces_loaded'] = ctypes.windll.gdi32.AddFontResourceExW(str(existing), 0, None)
                continue
            destination = Path(row['path'])
            if not destination.exists():
                shutil.copy2(row['source'], destination)
            winreg.SetValueEx(key, row['registry_value'], 0, winreg.REG_SZ, str(destination))
            row['faces_loaded'] = ctypes.windll.gdi32.AddFontResourceExW(str(destination), 0, None)
            row['status'] = 'installed' if row['faces_loaded'] else 'saved; activation needs editor restart'
    result = ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(0xffff, 0x001D, 0, 0, 2, 3000, ctypes.byref(result))
    receipt['installed'] = True
    output=Path(receipt_path) if receipt_path else ROOT / 'output/template-fonts/install-receipt.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--receipt',type=Path)
    args=parser.parse_args()
    result = install(args.install,args.manifest,args.receipt)
    print(json.dumps({'installed': result['installed'], 'fonts': len(result['fonts']), 'registered': sum(row.get('status') == 'installed' for row in result['fonts']), 'existing_preserved': result['skipped_existing_registrations']}))
