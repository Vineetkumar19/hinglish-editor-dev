"""Copy only audio from owner packs; keep source paths, hashes and all originals."""
import hashlib,json,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hinglish_sound.library import AUDIO_EXTENSIONS,scan
from tools.sound_pack_categories import classify
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(r'D:\Editing\Sound Packs')
DEST=ROOT/'library/owner-sound-packs'
DEST.mkdir(parents=True,exist_ok=True)

existing={}
for parent in (ROOT/'library/sfx-pro',ROOT/'library/sound-online',ROOT/'library/music',DEST):
    for sidecar in parent.rglob('*.json'):
        try:
            d=json.loads(sidecar.read_text('utf-8-sig'))
            if d.get('sha256'):existing.setdefault(d['sha256'],[]).append(str(sidecar)[:-5])
        except (OSError,ValueError,AttributeError):pass
rows=[]
sources=(SOURCE,DEST/'extracted')
files=sorted(p for base in sources for p in base.rglob('*') if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and not p.name.startswith('._'))
for i,path in enumerate(files,1):
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    base=next(b for b in sources if path.is_relative_to(b))
    relative=path.relative_to(base)
    kind,cat=classify(relative)
    if digest in existing:
        previous=next((p for p in existing[digest] if Path(p).is_relative_to(DEST/kind)),
                      existing[digest][0])
        rows.append(dict(source=str(path),sha256=digest,path=previous,duplicate=True));continue
    target=DEST/kind/cat/(digest[:12]+'-'+path.name)
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(path,target)
    meta=dict(name=path.stem,tags=list(relative.parts[:-1])+[cat],
      source_url=str(path),license='Owner-supplied pack; retain the original pack licence',sha256=digest)
    Path(str(target)+'.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf-8')
    existing.setdefault(digest,[]).append(str(target))
    rows.append(dict(source=str(path),path=str(target),sha256=digest,kind=kind,category=cat,duplicate=False))
    if i%100==0:print(f'Imported {i}/{len(files)}',flush=True)
(DEST/'import-manifest.json').write_text(json.dumps(dict(source=str(SOURCE),files=rows),ensure_ascii=False,indent=2),'utf-8')
for kind in ('sfx','music'):
    assets=scan(DEST/kind,kind,ROOT/'cache/sound',progress=lambda x:print(x,flush=True))
    print(kind,len(assets),flush=True)
print(json.dumps(dict(found=len(files),unique=sum(not r['duplicate'] for r in rows),duplicates=sum(r['duplicate'] for r in rows))),flush=True)
