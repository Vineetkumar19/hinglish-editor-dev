import sys,subprocess,zipfile,json
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/sound-separation-runtime/packages'))
import py7zr
SOURCE=Path(r'D:\Editing\Sound Packs')
DEST=ROOT/'library/owner-sound-packs/extracted';DEST.mkdir(parents=True,exist_ok=True)
audio={'.wav','.mp3','.ogg','.flac','.m4a','.aif','.aiff','.aac'}
rows=[]
def checked(name,base):
    name=name.replace('\\','/')
    p=PurePosixPath(name)
    if p.is_absolute() or ':' in name or '..' in p.parts:raise ValueError('Unsafe archive path')
    target=(base/name).resolve()
    if not target.is_relative_to(base.resolve()):raise ValueError('Archive outside extraction folder')
    return target
for source in SOURCE.rglob('*'):
    if source.suffix.lower() not in {'.7z','.rar','.zip'}:continue
    target=DEST/source.stem;target.mkdir(exist_ok=True)
    try:
        if source.suffix=='.7z':
            with py7zr.SevenZipFile(source) as archive:
                names=archive.getnames()
                for name in names:checked(name,target)
                chosen=[n for n in names if Path(n).suffix.lower() in audio and not Path(n).name.startswith('._')]
                print('Extracting',source.name,len(chosen),'audio files',flush=True)
                archive.extract(path=target,targets=chosen)
        elif source.suffix=='.rar':
            tool=r'C:\Program Files\WinRAR\UnRAR.exe'
            r=subprocess.run([tool,'lb',str(source)],capture_output=True,text=True,check=True)
            for name in r.stdout.splitlines():checked(name,target)
            subprocess.run([tool,'x','-idq','-o-',str(source),str(target)+'\\'],check=True)
        else:
            with zipfile.ZipFile(source) as archive:
                for item in archive.infolist():
                    checked(item.filename,target)
                    if Path(item.filename).suffix.lower() in audio:archive.extract(item,target)
        rows.append(dict(source=str(source),status='extracted'))
    except Exception as error:
        rows.append(dict(source=str(source),status='failed',error=str(error)))
for source in list(DEST.rglob('*.zip')):
    target=source.with_suffix('');target.mkdir(exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        for item in archive.infolist():
            checked(item.filename,target)
            if Path(item.filename).suffix.lower() in audio and not Path(item.filename).name.startswith('._'):archive.extract(item,target)
(DEST/'archive-receipt.json').write_text(json.dumps(rows,indent=2),'utf-8')
print(json.dumps(rows),flush=True)
