"""Extract the downloaded portable CUDA DLLs into this project only."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'tools/cuda-reference-runtime'
files=[]
for wheel in sorted((BASE/'wheels').glob('*.whl')):
 with zipfile.ZipFile(wheel) as archive:
  for item in archive.infolist():
   if not item.filename.lower().endswith('.dll'):continue
   target=BASE/'bin'/Path(item.filename).name
   target.parent.mkdir(parents=True,exist_ok=True)
   with archive.open(item) as source,target.open('wb') as out:
    while chunk:=source.read(1024*1024):out.write(chunk)
   files.append({'name':target.name,'bytes':target.stat().st_size,'package':wheel.name})
(BASE/'manifest.json').write_text(json.dumps({'scope':'Portable project-local CUDA DLLs; no system installation.','files':files},indent=2)+'\n')
print('Extracted',len(files),'project-local CUDA DLLs',flush=True)
