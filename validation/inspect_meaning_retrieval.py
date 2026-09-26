import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import json
from dataclasses import asdict
from hinglish_cut.model import Media, Transcript, Word
from hinglish_semantic.core import SemanticSettings
from hinglish_semantic.models import Embedder
from hinglish_semantic.meaning import meaning_units, retrieve_phrases

project = json.loads((ROOT / 'output/phase2/20260917-090817-355252/project.json').read_text(encoding='utf-8'))
transcripts = [Transcript(Media(**t['media']), [Word(**w) for w in t['words']], t['speech'], t['issues'])
               for t in project['transcripts']]
settings = SemanticSettings(matching_backend='meaning')
units = meaning_units((ROOT / 'input/phase2/script.txt').read_text(encoding='utf-8-sig'))
encoder = Embedder(settings, ROOT)
try:
    pools = retrieve_phrases(units, transcripts, settings, encoder)
finally:
    encoder.close()
rows = [{**u, 'candidates': [{**c, 'span': asdict(c['span'])} for c in p]} for u,p in zip(units,pools)]
(ROOT / 'validation/meaning-retrieval.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
for row in rows:
    print(row['index'], row['idea'], flush=True)
    for c in row['candidates']:
        print('  ', c['span']['id'], c['span']['text'], flush=True)
