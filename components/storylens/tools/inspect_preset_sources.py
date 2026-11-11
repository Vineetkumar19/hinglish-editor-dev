"""Offline read-only AEP inventory. Names are structural evidence, not native rendering."""
from pathlib import Path
import struct,json,hashlib,re
from template_font_audit import extract_aep_fonts
BASE=Path('D:/Editing/Cinematics AE templates');OUT=Path(__file__).resolve().parents[1]/'output/preset-library-evidence'
def inspect(project):
 b=project.read_bytes();order='>' if b[:4]==b'RIFX' else '<';items=[];errors=[]
 def chunks(start,end):
  at=start
  while at+8<=end:
   tag=b[at:at+4];size=struct.unpack_from(order+'I',b,at+4)[0];stop=at+8+size
   if stop>end:errors.append({'offset':at,'message':'chunk exceeds parent'});return
   yield tag,at+8,stop
   at=stop+(size&1)
 def walk(start,end,folders=(),depth=0):
  if depth>32:return
  for tag,s,e in chunks(start,end):
   if tag!=b'LIST':continue
   kind=b[s:s+4]
   if kind==b'Item':
    children=list(chunks(s+4,e));names=[b[a:z].decode('utf8',errors='replace').rstrip('\0') for t,a,z in children if t==b'Utf8'];name=names[0] if names else ''
    itemkind='comp' if any(t==b'cdta' for t,a,z in children) else 'folder' if any(t==b'LIST' and b[a:a+4] in [b'Fold',b'Sfdr'] for t,a,z in children) else 'footage'
    layers=[]
    if itemkind=='comp':
     for t,a,z in children:
      if t==b'LIST' and b[a:a+4] in [b'Layr',b'DLay',b'SLay']:
       lc=list(chunks(a+4,z));ln=[b[x:y].decode('utf8',errors='replace').rstrip('\0') for k,x,y in lc if k==b'Utf8'];layers.extend(ln)
    items.append({'name':name,'kind':itemkind,'folders':list(folders),'layer_names':layers})
    for t,a,z in children:
     if t==b'LIST' and b[a:a+4] in [b'Fold',b'Sfdr']:walk(a+4,z,folders+(name,),depth+1)
   elif kind in [b'Fold',b'Sfdr']:walk(s+4,e,folders,depth+1)
 walk(12,min(len(b),struct.unpack_from(order+'I',b,4)[0]+8))
 return {'project':str(project),'category':project.relative_to(BASE).parts[0],'size':len(b),'sha256':hashlib.sha256(b).hexdigest(),'format':b[:4].decode('ascii',errors='replace'),'items':items,'font_candidates':extract_aep_fonts(b),'parse_errors':errors,'native_verified':False}
if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True);rows=[]
 for p in sorted(BASE.rglob('*')):
  if p.is_file() and p.suffix.lower() in ['.aep','.aepx','.aet'] and not p.name.startswith('.') and '__MACOSX' not in p.parts and 'Auto-Save' not in p.parts:rows.append(inspect(p))
 (OUT/'source-project-review.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf8')
 print(json.dumps([{'category':r['category'],'project':Path(r['project']).name,'comps':[i['name'] for i in r['items'] if i['kind']=='comp'],'parse_errors':len(r['parse_errors'])} for r in rows],ensure_ascii=True,indent=2))
