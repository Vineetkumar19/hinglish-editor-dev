"""Resume the models supported by Storylens and repair relocated manifests.

Downloads weights/data only; never enables trust_remote_code or downloads reference media.
Use --bootstrap-site with the preserved old venv only while the new env is installing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def relocate(root):
    """Update only known model/runtime manifests, keeping their original contents."""
    for relative in ('models/meaning-upgrade.json', 'models/meaning-models.json', 'tools/llama/runtime.json'):
        path = root / relative
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        changed = False
        for key in ('speech_path', 'judge_path', 'server_path'):
            old = data.get(key)
            if not old or Path(old).exists():
                continue
            normalized = old.replace('\\', '/')
            for marker in ('/models/', '/tools/'):
                if marker not in normalized:
                    continue
                candidate = (root / (marker.strip('/') + '/' + normalized.split(marker, 1)[1])).resolve()
                if candidate.is_relative_to(root) and candidate.exists():
                    data[key] = str(candidate)
                    changed = True
                    break
        if changed:
            backup = path.with_suffix(path.suffix + '.before-laptop-migration')
            if not backup.exists():
                shutil.copy2(path, backup)
            write_json(path, data)
            print('Relocated ' + relative, flush=True)


def prepare_image_template(root, destination):
    """Use the official corrected template without changing the BF16 tokenizer vocabulary."""
    from huggingface_hub import hf_hub_download
    revision = 'f332072aa78be7aecdf3ee76d5c247082da564a6'
    source = Path(hf_hub_download('Tongyi-MAI/Z-Image-Turbo',
        filename='tokenizer/tokenizer_config.json', revision=revision,
        local_dir=str(root / 'downloads/tokenizer-correction')))
    corrected = json.loads(source.read_text(encoding='utf-8'))
    baseline = json.loads((destination / 'tokenizer/tokenizer_config.json').read_text(encoding='utf-8'))
    ignored = {'chat_template', 'extra_special_tokens'}
    if any(baseline.get(k) != corrected.get(k) for k in baseline.keys() | corrected.keys() if k not in ignored):
        raise ValueError('Official template correction changes tokenizer settings')
    if corrected.get('extra_special_tokens') not in (None, {}, []):
        raise ValueError('Unexpected extra special tokens in template correction')
    template = corrected.get('chat_template')
    if not isinstance(template, str) or not template:
        raise ValueError('Official tokenizer correction has no chat template')
    target = destination / 'tokenizer/chat_template.jinja'
    target.write_text(template, encoding='utf-8')
    receipt = {'revision': revision, 'source': str(source),
               'sha256': hashlib.sha256(template.encode('utf-8')).hexdigest()}
    write_json(root / 'output/validation/new-laptop/image-tokenizer-template.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--bootstrap-site', type=Path)
    parser.add_argument('--group', choices=('core', 'generation', 'all'), default='all')
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0,str(root))
    from hinglish_cut.model_storage import configure,role
    configure(root)
    if args.bootstrap_site:
        sys.path.insert(0, str(args.bootstrap_site.resolve()))
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '60')
    from huggingface_hub import HfApi, snapshot_download
    from ranged_download import patch_huggingface
    patch_huggingface()

    models = root / 'models'
    state_file = root / 'downloads/laptop-model-downloads.json'
    state = json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {'models': {}}
    specs = []
    if args.group in ('core', 'all'):
        specs += [
            ('Oriserve/Whisper-Hindi2Hinglish-Swift', None, 'Roman Hinglish speech'),
            ('MahmoudAshraf/mms-300m-1130-forced-aligner', None, 'Word alignment'),
            ('intfloat/multilingual-e5-small', None, 'Existing documentary/semantic retrieval index'),
            ('openai/clip-vit-base-patch32', None, 'B-roll image/text ranking'),
            ('laion/larger_clap_general', None, 'Sound/music audio/text ranking'),
            ('Qwen/Qwen2.5-1.5B-Instruct', None, 'Legacy Transformers evaluator compatibility'),
            ('dropbox-dash/faster-whisper-large-v3-turbo', '0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf', 'Independent multilingual speech'),
            ('unsloth/Qwen3-4B-Instruct-2507-GGUF', 'a06e946bb6b655725eafa393f4a9745d460374c9', 'Pinned semantic/B-roll fallback'),
        ]
    if args.group in ('generation', 'all'):
        specs += [
            ('Tongyi-MAI/Z-Image-Turbo', '367372dab44eb24c5908d1f6d867b66123cb390d', 'AI image/first-frame generation (official BF16 variant)'),
            ('Wan-AI/Wan2.2-TI2V-5B-Diffusers', None, 'AI video generation'),
        ]
    api = HfApi()
    for repo, pinned_revision, role in specs:
        from hinglish_cut.model_storage import role as selected_role
        if selected_role(root,'planner') and repo in {
            'Oriserve/Whisper-Hindi2Hinglish-Swift','intfloat/multilingual-e5-small',
            'openai/clip-vit-base-patch32','Qwen/Qwen2.5-1.5B-Instruct',
            'dropbox-dash/faster-whisper-large-v3-turbo','unsloth/Qwen3-4B-Instruct-2507-GGUF'}:
            print('Retired model already replaced: '+repo,flush=True)
            continue
        print(f'Preparing {repo}: {role}', flush=True)
        entry = state['models'].setdefault(repo, {})
        try:
            info = api.model_info(repo, revision=pinned_revision or entry.get('revision') or 'main', files_metadata=True)
            revision = info.sha
            names = [item.rfilename for item in info.siblings]
            generation = repo.startswith(('Tongyi-MAI/', 'Wan-AI/'))
            if repo.endswith('-GGUF'):
                selected = ['Qwen3-4B-Instruct-2507-Q4_K_M.gguf']
            elif generation:
                bf16 = repo == 'Tongyi-MAI/Z-Image-Turbo'
                selected = [n for n in names if n.endswith(('.json', '.txt', '.model', '.tiktoken', '.jinja'))
                            or (n.endswith('.safetensors') and (not bf16 or '.bf16' in n))]
                if bf16:
                    # Keep only the indexes matching the selected variant; the
                    # standard indexes reference FP32 shards we do not download.
                    selected = [n for n in selected if not n.endswith('.safetensors.index.json')]
            else:
                root_names = [n for n in names if '/' not in n]
                has_safe = any(n.endswith('.safetensors') for n in root_names)
                selected = [n for n in root_names if n.endswith(('.json', '.txt', '.model', '.tiktoken', '.jinja'))
                            or (n.endswith('.safetensors') if has_safe else n.endswith('.bin'))]
            total = sum(f.size or 0 for f in info.siblings if f.rfilename in selected)
            destination = root / 'tools/aigen/install/models' / repo.replace('/', '--') if generation else None
            entry.update(role=role, revision=revision, selected_bytes=total, status='downloading')
            if generation:
                entry['variant'] = 'bf16' if repo == 'Tongyi-MAI/Z-Image-Turbo' else None
            write_json(state_file, state)
            print(f'  Selected {len(selected)} files, {total / 2**30:.2f} GiB; revision {revision}', flush=True)
            kwargs = {'repo_id': repo, 'revision': revision, 'allow_patterns': selected, 'max_workers': 4}
            kwargs.update({'local_dir': str(destination)} if generation else {'cache_dir': str(models)})
            for attempt in range(4):
                try:
                    folder = Path(snapshot_download(**kwargs))
                    if any(not (folder / n).is_file() for n in selected):
                        raise RuntimeError('Selected model files are missing')
                    break
                except Exception as error:
                    if attempt == 3:
                        raise
                    print(f'  Retry {attempt + 1}: {type(error).__name__}: {error}', flush=True)
                    time.sleep(2 ** (attempt + 1))
            if repo == 'Tongyi-MAI/Z-Image-Turbo':
                entry['tokenizer_template'] = prepare_image_template(root, folder)
            entry.update(status='downloaded', path=str(folder), files=len(selected))
            verified = 0
            for item in info.siblings:
                if item.rfilename not in selected:
                    continue
                lfs = getattr(item, 'lfs', None)
                expected_hash = getattr(lfs, 'sha256', None)
                if isinstance(lfs, dict):
                    expected_hash = lfs.get('sha256')
                if expected_hash:
                    with (folder / item.rfilename).open('rb') as source:
                        actual_hash = hashlib.file_digest(source, 'sha256').hexdigest()
                    if actual_hash != expected_hash:
                        raise ValueError('Model weight checksum mismatch: ' + item.rfilename)
                    verified += 1
            entry['verified_weight_files'] = verified
            if not generation:
                reference = models / ('models--' + repo.replace('/', '--')) / 'refs/main'
                reference.parent.mkdir(parents=True, exist_ok=True)
                reference.write_text(revision, encoding='utf-8')
            write_json(state_file, state)
            print('  Complete: ' + str(folder), flush=True)
            relocate(root)
        except Exception as error:
            entry.update(status='failed', error=f'{type(error).__name__}: {error}')
            write_json(state_file, state)
            raise
    relocate(root)
    if args.group in ('generation', 'all'):
        config = root / 'config.aigen.local.json'
        data = json.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
        backup = config.with_suffix('.json.before-laptop-migration')
        if config.exists() and not backup.exists():
            shutil.copy2(config, backup)
        data.update(install=str(root / 'tools/aigen/install'), gpu='NVIDIA GeForce RTX 5070 Ti Laptop GPU', vram_gb=12)
        write_json(config, data)
    print('All selected model downloads completed. Inference validation is a separate step.', flush=True)


if __name__ == '__main__':
    main()
