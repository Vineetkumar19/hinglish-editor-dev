"""Install the exact bundled caption fonts for the current Windows user.

Run without arguments to inspect. --install explicitly registers verified copies;
existing font files and Windows' own fonts are never replaced or removed.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import time


ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / 'hinglish_captions/fonts'


def names(path):
    data = path.read_bytes()
    count = struct.unpack_from('>H', data, 4)[0]
    for i in range(count):
        tag, _, offset, _ = struct.unpack_from('>4sIII', data, 12 + i * 16)
        if tag == b'name':
            _, records, strings = struct.unpack_from('>HHH', data, offset)
            result = {}
            for j in range(records):
                platform, encoding, language, name, size, start = struct.unpack_from('>HHHHHH', data, offset + 6 + j * 12)
                if name not in (1, 2, 4, 6, 16, 17) or platform not in (0, 3):
                    continue
                value = data[offset + strings + start:offset + strings + start + size].decode('utf-16-be')
                if name not in result or language == 1033:
                    result[name] = value
            return result
    raise ValueError(f'The font has no readable name table: {path.name}')


def install(apply=False):
    if os.name != 'nt':
        raise RuntimeError('Font installation is available on Windows only.')
    import winreg
    sources = json.loads((FONTS / 'sources.json').read_text('utf-8'))
    target = Path(os.environ['LOCALAPPDATA']) / 'Microsoft/Windows/Fonts'
    rows = []
    for path in sorted(FONTS.iterdir()):
        if path.suffix.lower() not in ('.otf', '.ttf'):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sources[path.name]['sha256']:
            raise ValueError(f'{path.name} differs from the caption design source. Restore the verified bundled font before installing.')
        title = names(path)[4]
        # Adobe enumerates the standard per-user font directory and face names.
        # Keep a unique filename, but register the real full face name.
        value_name = f'{title} ({"OpenType" if path.suffix == ".otf" else "TrueType"})'
        dest = target / ('Storylens-' + path.name)
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise ValueError(f'A different font already exists at {dest}. It was kept; choose another installation folder.')
        rows.append({'source': str(path), 'path': str(dest), 'name': title,
                     'registry_value': value_name, 'sha256': digest})
    receipt = {'installed': False, 'fonts': rows, 'time': time.time()}
    if apply:
        target.mkdir(parents=True, exist_ok=True)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
            for row in rows:
                try:
                    old, _ = winreg.QueryValueEx(key, row['registry_value'])
                except FileNotFoundError:
                    old = None
                if old is not None and str(old).casefold() != row['path'].casefold():
                    raise ValueError(f"The existing registration for {row['name']} was kept. Review it before installing a different version.")
            for row in rows:
                if not Path(row['path']).exists():
                    shutil.copy2(row['source'], row['path'])
                winreg.SetValueEx(key, row['registry_value'], 0, winreg.REG_SZ, row['path'])
                loaded = ctypes.windll.gdi32.AddFontResourceExW(row['path'], 0, None)
                if not loaded:
                    raise RuntimeError(f"Windows saved {row['name']} but could not activate it. Restart the editor or sign in again, then retry.")
                row['faces_loaded'] = loaded
        result = ctypes.c_size_t()
        ctypes.windll.user32.SendMessageTimeoutW(0xffff, 0x001D, 0, 0, 2, 3000, ctypes.byref(result))
        receipt['installed'] = True
        dest = ROOT / 'output/editor-handoffs/caption-font-installation.json'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    print(json.dumps(install(parser.parse_args().install), indent=2))
