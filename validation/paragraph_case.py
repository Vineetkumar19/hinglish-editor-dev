"""Inspect the user's failed 13-source case; no fabricated transcripts."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hinglish_cut.model import Media, Word, Transcript
from hinglish_semantic.core import SemanticSettings
from hinglish_semantic.coverage import arrange_paragraphs
from hinglish_semantic.pipeline import serialize_rows

root = Path(__file__).resolve().parents[1]
project = json.loads((root / 'output/phase2/20260910-235544-082290/project.json').read_text())
transcripts = [Transcript(Media(**t['media']), [Word(**w) for w in t['words']], t['speech'], t['issues'])
               for t in project['transcripts']]
rows = arrange_paragraphs((root / 'input/phase2/script.txt').read_text(encoding='utf-8-sig'), transcripts,
                          SemanticSettings(), progress=lambda x: None)
for row in rows:
    c = row['selected']
    print(f"P{row['paragraph_index']+1}.{row['index']+1} {row['idea']}")
    if c:
        s = c['span']
        print(f"  source {c['source_order']+1} {s.start:.2f}-{s.end:.2f}: {s.text} (score {c['score']:.2f})")
    else:
        print('  MISSING')
        for c in row['alternatives'][:3]:
            print(f"    {c['span'].text}: {c['evidence']} {c['issues']}")
    print('  ', row['issues'])
(root / 'validation/paragraph-case-decisions.json').write_text(json.dumps(serialize_rows(rows), indent=2), encoding='utf-8')
