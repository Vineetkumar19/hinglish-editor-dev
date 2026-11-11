"""Read-only project media-path candidates; native AE remains the final authority."""
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
LIBRARY=Path('D:/Editing/AE documentry style editing templates/LatestTemplete')
OUT=ROOT/'output/template-fonts/library-recheck'
MEDIA={'.jpg','.jpeg','.png','.psd','.ai','.eps','.mov','.mp4','.m4v','.avi','.wav','.mp3','.aif','.aiff','.tif','.tiff','.exr','.dpx','.tga','.bmp','.gif','.webm','.mxf'}

def references(data):
    # Anchor at drive/root prefixes and bound length. Never scan every possible
    # printable substring of large embedded AEP data (quadratic on long runs).
    paths=set()
    for match in re.finditer(rb'(?:[A-Za-z]:[\\/]|/Users/|/Volumes/)[^\x00\r\n]{1,2048}',data):
        path=match.group().decode('utf8',errors='replace').strip()
        if Path(path.replace('\\','/')).suffix.lower() in MEDIA:paths.add(path)
    return sorted(paths)

def run():
    files=[]
    for folder,dirs,names in os.walk(LIBRARY,followlinks=False):
        dirs[:]=[d for d in dirs if not Path(folder,d).is_junction() and not Path(folder,d).is_symlink()]
        files.extend(Path(folder,name) for name in names)
    index={}
    for file in files:
        if file.suffix.lower() in MEDIA:index.setdefault(file.name.casefold(),[]).append(file)
    projects=[]
    for project in files:
        if project.suffix.lower() not in ('.aep','.aepx','.aet'):continue
        package=project.relative_to(LIBRARY).parts[0];rows=[]
        for original in references(project.read_bytes()):
            parts=original.replace('\\','/').casefold().split('/')
            candidates=[p for p in index.get(parts[-1],[]) if p.relative_to(LIBRARY).parts[0]==package]
            ranked=[]
            for file in candidates:
                own=file.as_posix().casefold().split('/');score=0
                while score<min(len(own),len(parts)) and own[-1-score]==parts[-1-score]:score+=1
                ranked.append((score,file))
            best=max((score for score,_ in ranked),default=0)
            choices=[str(p) for score,p in ranked if score==best]
            rows.append({'original':original,'status':'available_in_package' if len(choices)==1 else 'ambiguous' if choices else 'not_in_package','candidates':choices})
        projects.append({'project':str(project),'references':rows})
    report={'note':'Offline path candidates may include unused or proxy references and cannot prove current native footage is missing. Original projects unchanged.',
            'projects':projects,'asset_files':sum(len(v) for v in index.values())}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'media-audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),'utf8')
    rows=[row for p in projects for row in p['references']]
    print(json.dumps({'projects':len(projects),'asset_files':report['asset_files'],'path_candidates':len(rows),
                      'available_in_package':sum(r['status']=='available_in_package' for r in rows),
                      'ambiguous':sum(r['status']=='ambiguous' for r in rows),'not_in_package':sum(r['status']=='not_in_package' for r in rows)}))

if __name__=='__main__':run()
