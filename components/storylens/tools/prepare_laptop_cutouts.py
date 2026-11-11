"""Resume official rembg weights and verify the package's published checksums."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

import ranged_download
from ranged_download import ROOT, ranged_get

MODELS = (
    ('birefnet-general-lite', 'BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx', '4fab47adc4ff364be1713e97b7e66334'),
    ('isnet-general-use', 'isnet-general-use.onnx', 'fc16ebd8b0c10d971d3513d564d01e29'),
)


def main():
    import sys
    sys.path.insert(0,str(ROOT))
    from hinglish_cut.model_storage import configure,role
    configure(ROOT)
    selected=role(ROOT,'cutout')
    if selected:
        path=Path(selected['path'])
        with path.open('rb') as source:
            if hashlib.file_digest(source,'md5').hexdigest()!='7a35a0141cbbc80de11d9c9a28f52697':
                raise ValueError('Upgraded cutout checksum mismatch')
        print('Full BiRefNet already installed and verified.',flush=True)
        return
    ranged_download.CHUNK = 256 * 1024
    receipts = []
    for name, asset, expected in MODELS:
        url = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/' + asset
        target = ROOT / 'models/rembg/models' / name / (name + '.onnx')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            with target.open('rb') as source:
                valid = hashlib.file_digest(source, 'md5').hexdigest() == expected
        else:
            valid = False
        if not valid:
            partial = target.with_suffix('.onnx.incomplete')
            if target.exists():
                if partial.exists():
                    raise RuntimeError('Both an invalid model and a partial exist; inspect before replacing either.')
                target.replace(partial)
            with urlopen(Request(url, method='HEAD'), timeout=45) as response:
                size = int(response.headers['Content-Length'])
            resume = partial.stat().st_size if partial.exists() else 0
            with partial.open('r+b' if partial.exists() else 'w+b') as stream:
                ranged_get(url, stream, size, resume)
            with partial.open('rb') as source:
                actual = hashlib.file_digest(source, 'md5').hexdigest()
            if actual != expected:
                raise ValueError('rembg checksum mismatch for ' + name)
            partial.replace(target)
        with target.open('rb') as source:
            sha = hashlib.file_digest(source, 'sha256').hexdigest()
        receipts.append(dict(model=name, path=str(target), url=url, md5=expected, sha256=sha, bytes=target.stat().st_size))
        print('Verified ' + name, flush=True)
    (ROOT / 'output/validation/new-laptop/cutout-downloads.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
