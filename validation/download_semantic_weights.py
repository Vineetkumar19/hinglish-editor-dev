"""Resume the official Qwen weights when the hub's standard download stalls."""
import hashlib
import os
from pathlib import Path
import shutil
import time
import requests

root = Path(__file__).resolve().parents[1]
repo = root / 'models' / 'models--Qwen--Qwen2.5-1.5B-Instruct'
revision = (repo / 'refs' / 'main').read_text().strip()
url = f'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/resolve/{revision}/model.safetensors'
sha = 'dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee'
expected_size = 3087467144
part = repo / 'blobs' / (sha + '.semantic-partial')
final = repo / 'blobs' / sha
if not final.exists():
    for attempt in range(5):
        start = part.stat().st_size if part.exists() else 0
        try:
            headers = {'Range': f'bytes={start}-'} if start else {}
            # A fresh public URL avoids a stale cached signed CDN redirect.
            with requests.get(url, params={'download': 'true', 'request': str(time.time_ns())},
                              headers=headers, stream=True, timeout=(20, 45)) as response:
                response.raise_for_status()
                if response.status_code == 206:
                    if not response.headers.get('Content-Range', '').startswith(f'bytes {start}-'):
                        raise ValueError('Server returned a different byte range')
                else:
                    start = 0
                with part.open('ab' if start else 'wb') as output:
                    written = start
                    last = time.monotonic()
                    for chunk in response.iter_content(2 * 1024 * 1024):
                        output.write(chunk)
                        written += len(chunk)
                        if time.monotonic() - last > 5:
                            output.flush()
                            print(f'Qwen: {written / 1e9:.2f} / {expected_size / 1e9:.2f} GB', flush=True)
                            last = time.monotonic()
            if part.stat().st_size != expected_size:
                raise ValueError('Incomplete weights; will resume')
            break
        except (requests.RequestException, ValueError) as error:
            print(f'Download attempt {attempt + 1}: {error}', flush=True)
            if attempt == 4: raise
    print('Checking weight checksum', flush=True)
    h = hashlib.sha256()
    with part.open('rb') as stream:
        while block := stream.read(8 * 1024 * 1024): h.update(block)
    if h.hexdigest() != sha:
        raise ValueError('Weights did not match the official SHA-256')
    part.replace(final)
target = repo / 'snapshots' / revision / 'model.safetensors'
if not target.exists():
    try: os.link(final, target)
    except OSError: shutil.copyfile(final, target)
print('Qwen local weights verified and installed.', flush=True)
