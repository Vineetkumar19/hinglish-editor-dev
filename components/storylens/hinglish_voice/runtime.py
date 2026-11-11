"""Run the pinned VoiceStudio model in its own interpreter, freeing memory on exit."""
import json
import os
from pathlib import Path
import subprocess


def settings(root):
    return {
        'source': str(Path(root)/'tools/voicestudio-runtime/source'),
        'python': str(Path(root)/'tools/voicestudio-runtime/venv/Scripts/python.exe'),
        'model': str(Path(root)/'models/voicestudio/OmniVoice'),
    }


def ready(root):
    config = settings(root)
    model = Path(config['model'])
    return (Path(config['python']).is_file() and
            (Path(config['source'])/'omnivoice/models/omnivoice.py').is_file() and
            (model/'config.json').is_file() and
            (model/'tokenizer.json').is_file() and
            any(model.glob('*.safetensors')) and
            (model/'audio_tokenizer/config.json').is_file() and
            (model/'audio_tokenizer/preprocessor_config.json').is_file() and
            any((model/'audio_tokenizer').glob('*.safetensors')))


def synthesize(request, destination, log):
    root = Path(request['root'])
    if not ready(root):
        raise RuntimeError('Voiceover setup: install the isolated VoiceStudio runtime and local OmniVoice model before generating.')
    config = settings(root)
    from .pronunciation import prepare
    spoken, reference = prepare(root,request,Path(destination).parent)
    from hinglish_cut.model_preferences import release_ollama
    release_ollama(root)
    task = Path(destination).with_suffix('.request.json')
    task.write_text(json.dumps({**request, **config, 'spoken_script':spoken, 'spoken_reference':reference, 'output':str(destination)}, ensure_ascii=False), 'utf-8')
    env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false', PYTHONUTF8='1')
    with Path(log).open('w', encoding='utf-8') as stream:
        completed = subprocess.run([config['python'], str(Path(__file__).with_name('worker.py')), str(task)],
                                   cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if completed.returncode:
        details = Path(log).read_text('utf-8', errors='replace')[-14000:]
        raise RuntimeError('Voiceover generation: local synthesis stopped. '+details)
