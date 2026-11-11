from pathlib import Path
import json,hashlib
from fontTools.ttLib import TTFont
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'library/cinematic-text-fonts';OUT=ROOT/'output/cinematic-text-evidence';audit=json.loads((OUT/'font-audit.json').read_text('utf8'));fonts={}
for name in ['sources.json','exact-source-supplement.json','remaining-source-supplement.json']:
    p=DEST/name
    if p.is_file():
        for row in json.loads(p.read_text('utf8')).get('fonts',[]):
            source=Path(row['source'])
            with TTFont(source) as f:ps=f['name'].getDebugName(6)
            if ps!=row['postscript_name']:raise ValueError('Font name changed: '+str(source))
            row['sha256']=hashlib.sha256(source.read_bytes()).hexdigest();fonts[ps]=row
missing=sorted(set(audit['required_candidates'])-set(fonts)-set(audit['installed']))
plan={'fonts':list(fonts.values()),'unresolved_candidates':missing,'font_reference_count':len(audit['required_candidates']),'note':'Legacy/fallback references are listed conservatively; actual missing scene fonts are checked natively before inserting.'}
(DEST/'install-plan.json').write_text(json.dumps(plan,indent=2),'utf8');print(json.dumps({'fonts_ready':len(fonts),'unresolved_candidates':missing}))
