"""Official remaining family downloads; never change PostScript identity."""
from pathlib import Path
import urllib.request,urllib.parse,json,hashlib,zipfile,io
from fontTools.ttLib import TTFont
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'library/cinematic-text-fonts';rows=[];errors=[]
required=set(json.loads((ROOT/'output/cinematic-text-evidence/font-audit.json').read_text('utf8'))['required_candidates'])
def get(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Storylens-font-setup'}),timeout=25).read()
def record(p,url,lic):
    with TTFont(p) as f:ps=f['name'].getDebugName(6)
    if ps in required:rows.append({'source':str(p),'postscript_name':ps,'url':url,'license':str(lic),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
try:
    repo='dharmatype/Bebas-Neue';tree=json.loads(get(f'https://api.github.com/repos/{repo}/git/trees/master?recursive=1'));folder=DEST/'bebas-original';folder.mkdir(exist_ok=True);license=folder/'OFL.txt';license.write_bytes(get(f'https://raw.githubusercontent.com/{repo}/master/OFL.txt'))
    candidates=[r['path'] for r in tree['tree'] if r['path'].lower().endswith(('.ttf','.otf')) and ('bold' in r['path'].lower() or 'book' in r['path'].lower())]
    for name in candidates:
        url=f'https://raw.githubusercontent.com/{repo}/master/'+urllib.parse.quote(name);p=folder/Path(name).name;p.write_bytes(get(url));record(p,url,license)
    print('Bebas upstream candidates:',candidates,flush=True)
except Exception as e:errors.append({'font':'Bebas Neue','error':str(e)})
try:
    url='https://api.fontshare.com/v2/fonts/download/clash-grotesk';data=get(url);folder=DEST/'clash-grotesk';folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        license=folder/'Fontshare-license.txt';licenses=[];fonts=[]
        for info in archive.infolist():
            if info.file_size>8*1024*1024 or info.is_dir():continue
            if info.filename.lower().endswith('.txt') and ('license' in info.filename.lower() or 'licence' in info.filename.lower()):licenses.append(archive.read(info).decode('utf8','replace'))
            if Path(info.filename).name=='ClashGrotesk-Regular.otf':
                p=folder/Path(info.filename).name;p.write_bytes(archive.read(info));fonts.append(p)
        if not licenses:raise ValueError('Official download lacks the font licence; installation withheld.')
        license.write_text('\n\n'.join(licenses),'utf8')
        for p in fonts:record(p,url,license)
except Exception as e:errors.append({'font':'Clash Grotesk','error':str(e)})
(DEST/'remaining-source-supplement.json').write_text(json.dumps({'fonts':rows,'errors':errors},indent=2),'utf8');print(json.dumps({'fonts':[r['postscript_name'] for r in rows],'errors':errors}))
