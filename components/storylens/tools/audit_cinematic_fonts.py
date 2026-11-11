"""Read-only reference/installed font inventory for the owner's text packs."""
from pathlib import Path
import json,os,hashlib
from template_font_audit import extract_aep_fonts,font_names
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'output/cinematic-text-evidence';out.mkdir(parents=True,exist_ok=True)
projects=[]
for p in Path('D:/Editing/Cinematics AE templates/Text templates').rglob('*.aep'):
    if p.name.startswith('._'):continue
    data=p.read_bytes();projects.append({'project':str(p),'sha256':hashlib.sha256(data).hexdigest(),'font_candidates':extract_aep_fonts(data)})
installed={};errors=[]
for folder in [Path(os.environ['WINDIR'])/'Fonts',Path(os.environ['LOCALAPPDATA'])/'Microsoft/Windows/Fonts',Path('C:/Program Files/Common Files/Adobe/Fonts')]:
    if not folder.exists():continue
    for p in folder.rglob('*'):
        if p.suffix.lower() not in ['.ttf','.otf','.ttc','.otc']:continue
        try:
            for names in font_names(p):
                for ps in names.get('6',[]):installed[ps]=str(p)
        except Exception as e:errors.append({'path':str(p),'error':str(e)})
required=sorted({n for p in projects for n in p['font_candidates']});missing=sorted(set(required)-installed.keys())
result={'projects':projects,'required_candidates':required,'installed':{k:installed[k] for k in required if k in installed},'missing_candidates':missing,'errors':errors,'note':'AEP font dictionaries include fallback/unused references. Native text usage and font appearance need owner AE validation.'}
(out/'font-audit.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps({'installed_matching':len(required)-len(missing),'missing_candidates':missing}))
