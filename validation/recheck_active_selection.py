"""Confirm final default settings reuse cached meaning checks and the same edit."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import json
from hinglish_cut.model import Media, Transcript, Word
from hinglish_semantic.core import SemanticSettings
from hinglish_semantic.models import Embedder, require_models
from hinglish_semantic.local_judge import MeaningJudge
from hinglish_semantic.meaning import arrange_meaning
from hinglish_semantic.paragraph_export import cuts_for_rows, write_paragraph_page

out = Path(sys.argv[1]).resolve()
p = json.loads((out / 'project.json').read_text(encoding='utf-8'))
settings = SemanticSettings(**json.loads((ROOT / 'config.phase2.json').read_text(encoding='utf-8')))
require_models(ROOT, settings)
ts = [Transcript(Media(**t['media']), [Word(**w) for w in t['words']], t['speech'], t['issues']) for t in p['transcripts']]
text = '\n\n'.join(dict.fromkeys(r['paragraph_text'] for r in p['rows']))
encoder = Embedder(settings, ROOT)
judge = MeaningJudge(settings, ROOT)
try:
    rows = arrange_meaning(text, ts, settings, encoder, judge, lambda x: print(x, flush=True))
    runtime_started = judge.process is not None
finally:
    encoder.close(); judge.close()
ids = [r['selected']['span'].id if r['selected'] else None for r in rows]
assert ids == [r['selected_id'] for r in p['rows']], 'Final code changed the inspected selections'
cuts, _ = cuts_for_rows(rows, ts, settings)
from dataclasses import asdict
expected = json.loads((out / 'edit-decisions.json').read_text(encoding='utf-8'))['cuts']
assert [asdict(c) for c in cuts] == expected, 'Final code changed the rendered cuts'
report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
write_paragraph_page(out, report)
result = {'settings': 'normal Phase 2 defaults', 'selected_ranges_unchanged': True,
          'rendered_cuts_unchanged': True, 'cached_judgments_reused_without_server': not runtime_started}
(out / 'final-code-check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
