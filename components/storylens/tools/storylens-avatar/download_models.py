from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib, os, re, time
import requests

BASE = Path('tools/storylens-avatar/models')
FILES = [
    ('musetalk/musetalkV15/unet_fp16.safetensors',
     'https://huggingface.co/AEmotionStudio/musetalk-models/resolve/201c8f343b8a81249cd8e09d3b13d3b5f407e7fa/musetalkV15/unet_fp16.safetensors',
     1699979016, '7e1db0be4cbbe9630150ec5e424a351f50c7517e555ab0f7db7695f0c9d2c31f'),
    ('vae/diffusion_pytorch_model.safetensors',
     'https://huggingface.co/stabilityai/sd-vae-ft-mse/resolve/31f26fdeee1355a5c34592e401dd41e45d25a493/diffusion_pytorch_model.safetensors',
     None, 'a1d993488569e928462932c8c38a0760b874d166399b14414135bd9c42df5815'),
]
CHUNK = 8 * 1024 * 1024

def fetch_part(url, path, start, end):
    wanted = end - start + 1
    if path.is_file() and path.stat().st_size == wanted:
        return wanted
    for attempt in range(3):
        try:
            with requests.get(url, headers={'Range': f'bytes={start}-{end}'}, stream=True, timeout=(12,20)) as response:
                expected_range = f'bytes {start}-{end}/'
                if response.status_code != 206 or not response.headers.get('Content-Range','').startswith(expected_range):
                    raise RuntimeError(f'Unexpected range HTTP {response.status_code}')
                with path.open('wb') as output:
                    for piece in response.iter_content(512*1024):
                        output.write(piece)
                if path.stat().st_size != wanted:
                    raise RuntimeError('Incomplete range')
                return wanted
        except (OSError, requests.RequestException, RuntimeError):
            if attempt == 2:
                raise
    raise AssertionError('unreachable')

def fetch_model(item):
    relative,url,size,checksum = item
    path=BASE/relative
    if path.is_file():
        with path.open('rb') as file:
            if hashlib.file_digest(file,'sha256').hexdigest()==checksum:
                print(path.name,'already verified',flush=True)
                return
    with requests.get(url,headers={'Range':'bytes=0-0'},stream=True,timeout=(10,20)) as response:
        assert response.status_code==206,response.status_code
        actual_size=int(response.headers['Content-Range'].split('/')[-1])
        assert size is None or size==actual_size
    size=actual_size
    folder=path.parent/(path.name+'.ranges')
    folder.mkdir(exist_ok=True)
    parts=[(folder/f'{i:05d}.part',start,min(size,start+CHUNK)-1) for i,start in enumerate(range(0,size,CHUNK))]
    done=0
    start_time=time.monotonic()
    progress=start_time
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures=[pool.submit(fetch_part,url,*part) for part in parts]
        for future in as_completed(futures):
            done+=future.result()
            if time.monotonic()-progress>=12:
                print(path.name,round(done/2**20),'/',round(size/2**20),'MiB',round(done/max(1,time.monotonic()-start_time)/2**20,2),'MiB/s',flush=True)
                progress=time.monotonic()
    assembled=path.with_suffix(path.suffix+'.assembled')
    sha=hashlib.sha256()
    with assembled.open('wb') as out:
        for part,_,_ in parts:
            data=part.read_bytes()
            sha.update(data)
            out.write(data)
    assert assembled.stat().st_size==size and sha.hexdigest()==checksum,'Checksum mismatch'
    os.replace(assembled,path)
    for part,_,_ in parts:
        part.unlink()
    folder.rmdir()
    print(path.name,'SHA-256 verified',size,flush=True)

for item in reversed(FILES):
    fetch_model(item)
