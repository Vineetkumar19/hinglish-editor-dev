"""Download the selected non-generative upgrades to the user-selected C: model store.

Only data files are downloaded. Existing models are not deleted or activated here.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
STORE = Path(r'C:\Ai Models')
STATE = ROOT / 'downloads/model-upgrade-c-drive.json'
LOCK = threading.Lock()
SPECS = [
    ('planner', 'unsloth/Qwen3.5-9B-GGUF', ['Qwen3.5-9B-Q6_K.gguf', 'mmproj-BF16.gguf']),
    ('meaning', 'Qwen/Qwen3-14B-GGUF', ['Qwen3-14B-Q4_K_M.gguf']),
    ('embedding', 'Qwen/Qwen3-Embedding-8B-GGUF', ['Qwen3-Embedding-8B-Q6_K.gguf']),
    ('asr', 'Oriserve/Whisper-Hindi2Hinglish-Prime', None),
    ('independent_asr', 'Systran/faster-whisper-large-v3', ['model.bin']),
    ('broll_vision', 'Qwen/Qwen3-VL-Embedding-2B', None),
]


def save(state):
    with LOCK:
        temporary = STATE.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
        temporary.replace(STATE)


def configure():
    STORE.mkdir(parents=True, exist_ok=True)
    for name, relative in {'HF_HOME': 'cache/huggingface', 'HF_HUB_CACHE': 'cache/huggingface/hub',
                           'TORCH_HOME': 'cache/torch', 'U2NET_HOME': 'rembg',
                           'OLLAMA_MODELS': 'ollama', 'MODELSCOPE_CACHE': 'cache/modelscope'}.items():
        os.environ[name] = str(STORE / relative)
    os.environ.update(HF_HUB_DISABLE_XET='1', HF_HUB_DOWNLOAD_TIMEOUT='60',
                      HF_HUB_DISABLE_SYMLINKS_WARNING='1')


def main():
    configure()
    from huggingface_hub import HfApi, snapshot_download
    from ranged_download import patch_huggingface, ranged_get
    from urllib.request import Request, urlopen
    patch_huggingface(STORE)
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'storage_root': str(STORE), 'models': {}}
    for row in state['models'].values():
        if row.get('status') == 'failed':
            row.update(status='queued')
            row.pop('error', None)
    save(state)
    api = HfApi()

    def download(spec):
        role, repo, weights = spec
        row = state['models'].setdefault(role, {})
        # Preserve an existing resumable speech download until the dedicated
        # candidate's full editing check explicitly replaces its selection.
        if role=='asr' and row.get('repo'):
            repo=row['repo']
        try:
            for attempt in range(5):
                try:
                    info = api.model_info(repo, revision=row.get('revision') or 'main', files_metadata=True)
                    break
                except Exception:
                    if attempt == 4:
                        raise
                    time.sleep(min(2**attempt, 12))
            metadata = [f.rfilename for f in info.siblings if '/' not in f.rfilename and
                        f.rfilename.endswith(('.json', '.txt', '.model', '.jinja', '.tiktoken'))]
            selected = (weights if weights is not None else [f.rfilename for f in info.siblings if
                        '/' not in f.rfilename and f.rfilename.endswith('.safetensors')]) + metadata
            selected = sorted(set(selected))
            available = {f.rfilename: f for f in info.siblings}
            if not set(selected) <= available.keys():
                raise ValueError('The pinned model does not contain the expected weight files')
            destination = STORE / 'huggingface' / repo.replace('/', '--')
            row.update(repo=repo, revision=info.sha, path=str(destination), files=selected,
                       selected_bytes=sum(available[n].size or 0 for n in selected), status='downloading')
            save(state)
            print(f'{role}: {repo}, {row["selected_bytes"]/2**30:.2f} GiB -> {destination}', flush=True)
            for attempt in range(5):
                try:
                    snapshot_download(repo, revision=info.sha, allow_patterns=selected,
                                      local_dir=str(destination), max_workers=2)
                    # The hub may return a partial local directory after a network
                    # failure. Retry that case just like an interrupted transfer.
                    for name in selected:
                        file = destination / name
                        if not file.is_file() or file.stat().st_size != available[name].size:
                            raise IOError('Incomplete model file: ' + name)
                    break
                except Exception as error:
                    if attempt == 4:
                        raise
                    print(f'{role}: resuming after {type(error).__name__}: {error}', flush=True)
                    time.sleep(min(2**attempt, 12))
            verified = []
            for name in selected:
                file = destination / name
                if not file.is_file() or file.stat().st_size != available[name].size:
                    raise ValueError('Missing or wrong-size model file: ' + name)
                lfs = available[name].lfs
                digest = lfs.get('sha256') if isinstance(lfs, dict) else getattr(lfs, 'sha256', None)
                if digest:
                    with file.open('rb') as stream:
                        if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                            raise ValueError('Model checksum mismatch: ' + name)
                    verified.append({'file': name, 'sha256': digest})
            row.update(status='downloaded', verified=verified)
            save(state)
            print(f'{role}: DOWNLOAD_AND_SHA256_COMPLETE', flush=True)
        except Exception as error:
            row.update(status='failed', error=f'{type(error).__name__}: {error}')
            save(state)
            raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(download, SPECS))
    # rembg's full ONNX model, using the upstream package's specified MD5.
    path = STORE / 'rembg/models/birefnet-general/birefnet-general.onnx'
    path.parent.mkdir(parents=True, exist_ok=True)
    url = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-epoch_244.onnx'
    partial = path.with_suffix('.onnx.incomplete')
    expected_md5 = '7a35a0141cbbc80de11d9c9a28f52697'
    if not path.exists():
        with urlopen(Request(url, method='HEAD'), timeout=60) as response:
            size = int(response.headers['Content-Length'])
        with partial.open('r+b' if partial.exists() else 'w+b') as stream:
            resume = stream.seek(0, 2)
            ranged_get(url, stream, size, resume, workers=16, download_root=STORE)
        with partial.open('rb') as stream:
            if hashlib.file_digest(stream, 'md5').hexdigest() != expected_md5:
                raise ValueError('Full BiRefNet checksum mismatch')
        partial.replace(path)
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'md5').hexdigest() != expected_md5:
            raise ValueError('Full BiRefNet checksum mismatch')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    state['models']['cutout'] = dict(status='downloaded', path=str(path), selected_bytes=path.stat().st_size,
                                      verified=[{'sha256': digest, 'md5': expected_md5}], source=url)
    state['status'] = 'downloads_verified_integration_pending'
    save(state)
    print('ALL_C_DRIVE_UPGRADE_DOWNLOADS_VERIFIED', flush=True)


if __name__ == '__main__':
    main()
