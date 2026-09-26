"""Record independent recognition evidence for the active, unmodified inputs."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dataclasses import asdict
import json
from hinglish_semantic.core import SemanticSettings
from hinglish_semantic.pipeline import inputs
from hinglish_semantic.analysis import analyze_sources

manifest = json.loads((ROOT / 'models/meaning-models.json').read_text())
manifest.update(json.loads((ROOT / 'tools/llama/runtime.json').read_text()))
(ROOT / 'models/meaning-upgrade.json').write_text(json.dumps(manifest, indent=2))
paths, fmt = inputs(ROOT, 'assemble')
settings = SemanticSettings(speech_backend='turbo', matching_backend='meaning')
transcripts, wavs, errors = analyze_sources(paths, ROOT, settings, lambda s: print(s, flush=True))
dest = ROOT / 'validation/meaning-active-analysis.json'
dest.write_text(json.dumps({'transcripts': [asdict(t) for t in transcripts],
                           'audio_paths': {k: str(v) for k, v in wavs.items()},
                           'errors': errors, 'format': fmt}, indent=2), encoding='utf-8')
for t in transcripts:
    print(t.media.id, ' '.join(w.text for w in t.words), flush=True)
print('Saved:', dest, errors, flush=True)
