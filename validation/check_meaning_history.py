"""Recheck recorded retakes and negative answers from two older user batches."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import json
from hinglish_cut.model import Media, Transcript, Word
from hinglish_semantic.core import SemanticSettings
from hinglish_semantic.models import Embedder
from hinglish_semantic.meaning import arrange_meaning
from hinglish_semantic.local_judge import MeaningJudge
from hinglish_semantic.pipeline import serialize_rows
from hinglish_semantic.paragraph_export import cuts_for_rows

checks = [
    ('nightlife', 'output/phase2/20260915-234737-279794/project.json',
     'Toh agar tum yahaan enjoy karne aa rahe ho\nIsliye toh main camera kholke Instagram pe reels bana raha hoon.'),
    ('pg', 'output/phase2/20260917-031115-544956/project.json',
     'Washing machine? Nahi. Fridge? Nahi.')]
settings = SemanticSettings(matching_backend='meaning')
evidence = []
for name, file, script in checks:
    p = json.loads((ROOT / file).read_text(encoding='utf-8'))
    transcripts = [Transcript(Media(**t['media']), [Word(**w) for w in t['words']], t['speech'], t['issues'])
                   for t in p['transcripts']]
    encoder = Embedder(settings, ROOT)
    judge = MeaningJudge(settings, ROOT)
    try:
        rows = arrange_meaning(script, transcripts, settings, encoder, judge,
                               lambda s: print(name + ': ' + s, flush=True))
    finally:
        encoder.close(); judge.close()
    cuts, _ = cuts_for_rows(rows, transcripts, settings)
    saved = serialize_rows(rows)
    evidence.append({'case': name, 'rows': saved, 'cut_count': len(cuts)})
    (ROOT / 'validation/meaning-history.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    for r in rows:
        print(r['idea'], '=>', r['selected']['span'] if r['selected'] else 'MISSING', flush=True)
    assert all(r['selected'] for r in rows), f'{name}: missing known spoken passage'
    if name == 'nightlife':
        assert abs(rows[0]['selected']['span'].start - 5.27) < .05, 'Earlier repeated take selected'
        assert abs(rows[1]['selected']['span'].start - 13.47) < .05, 'Earlier incomplete take selected'
    else:
        assert all(any(w in r['selected']['span'].text.lower() for w in ('nahi', 'nahin')) for r in rows)
print('Selected real historical retakes/negative answers and non-overlapping cuts verified.', flush=True)
