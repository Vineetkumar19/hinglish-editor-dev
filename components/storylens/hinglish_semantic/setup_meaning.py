"""Install the pinned CPU meaning runtime and quantized model, on request."""
import hashlib
import json
from pathlib import Path
import zipfile


JUDGE_REPO = 'unsloth/Qwen3-4B-Instruct-2507-GGUF'
JUDGE_REVISION = 'a06e946bb6b655725eafa393f4a9745d460374c9'
JUDGE_FILE = 'Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
RUNTIME_TAG = 'b11011'
RUNTIME_SHA256 = '54511f3fec3273715725736197dfb7abefbb97932656c90104fb2a0d09e21a94'


def prepare(root):
    from hinglish_cut.model_storage import role, configure
    configure(root)
    if role(root,'meaning'):
        require(root)
        return
    import requests
    from huggingface_hub import hf_hub_download
    root = Path(root).resolve()
    manifest_file = root / 'models/meaning-upgrade.json'
    data = json.loads(manifest_file.read_text(encoding='utf-8')) if manifest_file.exists() else {}
    print('Preparing local meaning model (about 2.5 GB; downloads resume).', flush=True)
    judge = hf_hub_download(JUDGE_REPO, JUDGE_FILE, revision=JUDGE_REVISION, cache_dir=str(root / 'models'))
    data.update(judge_path=judge, judge_revision=JUDGE_REVISION, judge_repo=JUDGE_REPO)
    runtime = root / 'tools/llama/runtime.json'
    installed = json.loads(runtime.read_text(encoding='utf-8')) if runtime.exists() else {}
    if installed.get('runtime_version') != RUNTIME_TAG or not Path(installed.get('server_path', '')).is_file():
        response = requests.get('https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/' + RUNTIME_TAG, timeout=60)
        response.raise_for_status()
        asset = next(a for a in response.json()['assets'] if 'win-cpu-x64' in a['name'] and a['name'].endswith('.zip'))
        folder = root / 'tools/llama' / RUNTIME_TAG
        folder.mkdir(parents=True, exist_ok=True)
        archive = folder / asset['name']
        if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != RUNTIME_SHA256:
            with requests.get(asset['browser_download_url'], stream=True, timeout=120) as r:
                r.raise_for_status()
                with archive.open('wb') as f:
                    for block in r.iter_content(1024 * 1024): f.write(block)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != RUNTIME_SHA256:
            raise ValueError('Meaning runtime checksum failed; installation stopped')
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not (folder / name).resolve().is_relative_to(folder.resolve()): raise ValueError('Unsafe archive path')
            z.extractall(folder)
        server = next(folder.rglob('llama-server.exe'))
        installed = {'runtime_version': RUNTIME_TAG, 'server_path': str(server), 'runtime_sha256': RUNTIME_SHA256}
        runtime.write_text(json.dumps(installed, indent=2), encoding='utf-8')
    data.update(installed)
    manifest_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print('Local meaning model ready.', flush=True)


def require(root):
    root = Path(root)
    file = root / 'models/meaning-upgrade.json'
    if not file.exists(): raise ValueError('Run Download Phase 2 Models.bat once for the new meaning model.')
    data = json.loads(file.read_text(encoding='utf-8'))
    import os
    from hinglish_cut.model_storage import role
    selected=role(root,'meaning')
    if os.environ.get('STORYLENS_MODEL_SELECTION') and selected:
        data.update(judge_path=str(Path(selected['path'])/selected['weight_file']),
            judge_repo=selected['repo'],judge_revision=selected['revision'],
            backend='ollama',ollama_model=selected['ollama_model'],native_api=True)
    for key in ('judge_path', 'server_path'):
        if key not in data or not Path(data[key]).is_file():
            raise ValueError('Missing local meaning model/runtime. Run Download Phase 2 Models.bat once.')
    from hinglish_cut.model_storage import role
    selected = role(root,'meaning')
    expected = selected.get('revision',JUDGE_REVISION)
    if selected and (data.get('judge_repo')!=selected['repo'] or
        Path(data['judge_path']).resolve()!=(Path(selected['path'])/selected['weight_file']).resolve()):
        raise ValueError('Meaning manifest does not match the selected model')
    if data.get('judge_revision') != expected or data.get('runtime_version') != RUNTIME_TAG:
        raise ValueError('Meaning model/runtime revision changed. Run Download Phase 2 Models.bat to restore the tested versions.')
    return data


def load_manifest(root):
    """Shared identity for independent-ASR transcript caches."""
    root=Path(root)
    path=root/'models/meaning-upgrade.json'
    if not path.is_file(): path=root/'models/meaning-models.json'
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    from hinglish_cut.model_storage import role
    selected=role(root,'independent_asr')
    if selected:
        data.update(speech_path=selected['path'],speech_revision=selected['revision'])
    if not data.get('speech_revision') or not (Path(data.get('speech_path',''))/'model.bin').is_file():
        raise ValueError('The independent speech model is missing')
    return data
