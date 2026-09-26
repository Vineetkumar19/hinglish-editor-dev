"""Download a local ASR and quantized meaning judge; no media is uploaded."""
from pathlib import Path
import hashlib
import json
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor

os.environ['HF_HUB_DISABLE_XET'] = '1'
import requests
from huggingface_hub import HfApi, snapshot_download, hf_hub_download

ROOT = Path(__file__).resolve().parents[1]

def models():
    api = HfApi()
    repo = 'dropbox-dash/faster-whisper-large-v3-turbo'
    info = api.model_info(repo)
    print('Downloading speech model', repo, info.sha, flush=True)
    speech = snapshot_download(repo, revision=info.sha, cache_dir=str(ROOT / 'models'),
                               allow_patterns=['*.json', '*.txt', '*.bin'], max_workers=2)
    partial = {'speech_path': speech, 'speech_revision': Path(speech).name}
    (ROOT / 'models/meaning-models.json').write_text(json.dumps(partial, indent=2), encoding='utf-8')
    repo = 'unsloth/Qwen3-4B-Instruct-2507-GGUF'
    info = api.model_info(repo)
    filename = next(f.rfilename for f in info.siblings if f.rfilename.endswith('Q4_K_M.gguf'))
    print('Downloading meaning model', filename, info.sha, flush=True)
    judge = hf_hub_download(repo, filename, revision=info.sha, cache_dir=str(ROOT / 'models'))
    result = {**partial, 'judge_path': judge, 'judge_revision': info.sha, 'judge_repo': repo}
    (ROOT / 'models/meaning-models.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result

def runtime():
    response = requests.get('https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20', timeout=60)
    response.raise_for_status()
    releases = response.json()
    matches = []
    for release in releases:
        matches = [a for a in release['assets'] if ('win-cpu-x64' in a['name'] or 'win-avx2-x64' in a['name']) and a['name'].endswith('.zip')]
        if matches: break
    if not matches:
        raise ValueError('CPU runtime asset unavailable: ' + ', '.join(a['name'] for a in release['assets']))
    asset = matches[0]
    dest = ROOT / 'tools' / 'llama' / release['tag_name']
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / asset['name']
    print('Downloading official llama.cpp', asset['name'], flush=True)
    with requests.get(asset['browser_download_url'], stream=True, timeout=120) as download:
        download.raise_for_status()
        with archive.open('wb') as output:
            for chunk in download.iter_content(1024 * 1024): output.write(chunk)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    expected = asset.get('digest')
    if expected and expected != 'sha256:' + digest: raise ValueError('Runtime checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not (dest / name).resolve().is_relative_to(dest.resolve()): raise ValueError('Unsafe archive path')
        z.extractall(dest)
    server = next(dest.rglob('llama-server.exe'))
    result = {'runtime_version': release['tag_name'], 'server_path': str(server), 'runtime_sha256': digest}
    (ROOT / 'tools/llama/runtime.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result

if __name__ == '__main__':
    import sys
    if '--models-only' in sys.argv:
        manifest = models()
        runtime_file = ROOT / 'tools/llama/runtime.json'
        if runtime_file.exists(): manifest.update(json.loads(runtime_file.read_text(encoding='utf-8')))
        (ROOT / 'models/meaning-upgrade.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        raise SystemExit(0)
    if '--runtime-only' in sys.argv:
        print(json.dumps(runtime(), indent=2), flush=True)
        raise SystemExit(0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(models), pool.submit(runtime)
        manifest = {**a.result(), **b.result()}
    (ROOT / 'models' / 'meaning-upgrade.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Ready:', ROOT / 'models' / 'meaning-upgrade.json', flush=True)
