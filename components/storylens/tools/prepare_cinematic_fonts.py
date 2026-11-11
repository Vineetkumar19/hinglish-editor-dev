"""Download official OFL fonts and prepare an exact-identity per-user install plan."""
from pathlib import Path
import concurrent.futures,hashlib,json,re,urllib.request
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/cinematic-text-evidence';DEST=ROOT/'library/cinematic-text-fonts';DEST.mkdir(parents=True,exist_ok=True)
audit=json.loads((OUT/'font-audit.json').read_text('utf8'));required=set(audit['required_candidates']);found={};errors=[]
previous=json.loads((ROOT/'library/template-fonts/sources.json').read_text('utf8'))
for row in previous.get('fonts',[]):
    if row['postscript_name'] in required and Path(row['source']).is_file():found[row['postscript_name']]=row
def inspect(p,url=None,license=None):
    try:
        with TTFont(p) as f:ps=f['name'].getDebugName(6)
        if ps in required:found[ps]={'source':str(p),'postscript_name':ps,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':url or 'existing-local-font','license':str(license or '')}
    except Exception as e:errors.append({'file':str(p),'error':str(e)})
for base in [ROOT/'library/template-fonts',DEST]:
    for p in base.rglob('*'):
        if p.suffix.lower() in ['.ttf','.otf'] and not p.name.startswith('._'):inspect(p)
families=['anton','cinzeldecorative','instrumentserif','outfit','barlowcondensed','bigshoulderstext','bricolagegrotesque','cormorant','hahmlet','italianno','jura','librecaslondisplay','metalmania','michroma','montecarlo','montserrat','poppins','ptserif','racingsansone','sixcaps','tirodevanagarihindi','tirodevanagarimarathi','viga']
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Storylens-local-font-setup'});return urllib.request.urlopen(req,timeout=25).read()
def family(name):
    base='https://raw.githubusercontent.com/google/fonts/main/ofl/'+name+'/';folder=DEST/name;folder.mkdir(exist_ok=True)
    try:
        meta=(folder/'METADATA.pb').read_text('utf8') if (folder/'METADATA.pb').is_file() else get(base+'METADATA.pb').decode();(folder/'METADATA.pb').write_text(meta,'utf8');license=folder/'OFL.txt';
        if not license.is_file():license.write_bytes(get(base+'OFL.txt'))
        rows=[]
        for filename in sorted(set(re.findall(r'filename: "([^"]+)"',meta))):
            p=folder/filename
            if not p.is_file():p.write_bytes(get(base+urllib.parse.quote(filename)))
            rows.append((p,base+urllib.parse.quote(filename),license))
        return rows
    except Exception as e:return {'family':name,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for result in pool.map(family,families):
        if isinstance(result,dict):errors.append(result);continue
        for p,url,license in result:
            inspect(p,url,license)
            with TTFont(p) as variable:
                if 'fvar' not in variable:continue
                for instance in variable['fvar'].instances:
                    # Only original named instances; never relabel a different design to satisfy AE.
                    try:
                        coordinates={axis.axisTag:axis.defaultValue for axis in variable['fvar'].axes};coordinates.update(instance.coordinates)
                        static=instantiateVariableFont(variable,coordinates,inplace=False,updateFontNames=True)
                        ps=static['name'].getDebugName(6)
                        if ps in required and ps not in found:
                            output=p.parent/(ps+'.ttf');static.save(output);inspect(output,url,license);found[ps]['named_instance_coordinates']=dict(instance.coordinates)
                        static.close()
                    except Exception as e:errors.append({'font':p.name,'error':str(e)})
manifest={'fonts':list(found.values()),'required_candidates':sorted(required),'unresolved':sorted(required-set(found)-set(audit['installed'])),'sources':'Official google/fonts OFL files plus previously verified local owner font files; no substitute aliases','errors':errors}
(DEST/'sources.json').write_text(json.dumps(manifest,indent=2),'utf8');print(json.dumps({'ready':len(found),'unresolved':manifest['unresolved'],'errors':errors}))
