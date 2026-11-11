"""Prepare freely redistributable caption fonts inside the package, not Windows."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'hinglish_captions/fonts'
FILES = {
    'Roboto-Black.ttf': 'https://raw.githubusercontent.com/googlefonts/roboto-2/main/src/hinted/Roboto-Black.ttf',
    'Roboto-Regular.ttf': 'https://raw.githubusercontent.com/googlefonts/roboto-2/main/src/hinted/Roboto-Regular.ttf',
    'Roboto-LICENSE.txt': 'https://raw.githubusercontent.com/googlefonts/roboto-2/main/LICENSE',
    'GreatVibes-Regular.ttf': 'https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/GreatVibes-Regular.ttf',
    'GreatVibes-OFL.txt': 'https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/OFL.txt',
    'DancingScript-Regular.ttf': 'https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf',
    'DancingScript-OFL.txt': 'https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/OFL.txt',
}


def main():
    from PIL import ImageFont
    FOLDER.mkdir(parents=True, exist_ok=True)
    receipt = {}
    for name, url in FILES.items():
        path = FOLDER / name
        if not path.is_file():
            with urlopen(url, timeout=60) as response:
                data = response.read()
            if name.endswith('.ttf') and data[:4] not in (b'\x00\x01\x00\x00', b'OTTO', b'true'):
                raise ValueError('Invalid font download: ' + name)
            path.write_bytes(data)
        data = path.read_bytes()
        receipt[name] = {'source': url, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        if name.endswith('.ttf'):
            receipt[name]['font_name'] = ImageFont.truetype(str(path), 32).getname()
        print('Ready: ' + name, flush=True)
    (FOLDER / 'sources.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
