"""Recover original statics only from official upstream or Google font history."""
from pathlib import Path
import urllib.request,urllib.parse,json,re,hashlib
from fontTools.ttLib import TTFont
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'library/cinematic-text-fonts';audit=json.loads((ROOT/'output/cinematic-text-evidence/font-audit.json').read_text('utf8'));required=set(audit['required_candidates']);rows=[];errors=[]
def get(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Storylens-font-setup'}),timeout=30).read()
def save(url,family,filename,license_url):
    folder=DEST/family;folder.mkdir(exist_ok=True);p=folder/filename;p.write_bytes(get(url));lic=folder/'OFL.txt';lic.write_bytes(get(license_url))
    with TTFont(p) as f:ps=f['name'].getDebugName(6)
    if ps not in required:raise ValueError('Different internal font identity: '+ps)
    rows.append({'source':str(p),'postscript_name':ps,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':url,'license':str(lic)})
for repo,ref,folder,family in [('ateliertriay/bricolage','main','fonts/ttf','bricolage-original'),('CatharsisFonts/Cormorant','master','precompiled','cormorant-original')]:
    try:
        tree=json.loads(get(f'https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1'))
        candidates=[x['path'] for x in tree['tree'] if x['path'].lower().endswith(('.ttf','.otf')) and Path(x['path']).stem in required]
        seen=set()
        for file in sorted(candidates,key=lambda p:(0 if folder in p else 1,len(p))):
            name=Path(file).name
            if name in seen:continue
            seen.add(name);save(f'https://raw.githubusercontent.com/{repo}/{ref}/'+urllib.parse.quote(file),family,name,f'https://raw.githubusercontent.com/{repo}/{ref}/OFL.txt')
    except Exception as e:errors.append({'repo':repo,'error':str(e)})
try:save('https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-BoldItalic.ttf','montserrat-original','Montserrat-BoldItalic.ttf','https://raw.githubusercontent.com/JulietaUla/Montserrat/master/OFL.txt')
except Exception as e:errors.append({'font':'Montserrat-BoldItalic','error':str(e)})
(DEST/'exact-source-supplement.json').write_text(json.dumps({'fonts':rows,'errors':errors},indent=2),'utf8');print(json.dumps({'fonts':[r['postscript_name'] for r in rows],'errors':errors}))
