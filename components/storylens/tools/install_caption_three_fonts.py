"""Install only the Caption 3 reference fonts; keep other registrations."""
from pathlib import Path
import ctypes,hashlib,json,os,shutil,time
import winreg
from fontTools.ttLib import TTFont
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'hinglish_captions/fonts/caption-three'

def install():
    manifest=json.loads((FOLDER/'sources.json').read_text('utf8'));target=Path(os.environ['LOCALAPPDATA'])/'Microsoft/Windows/Fonts'
    receipt_path=ROOT/'output/editor-handoffs/caption-font-installation.json'
    try:receipt=json.loads(receipt_path.read_text('utf8'))
    except (OSError,ValueError):receipt={'fonts':[]}
    pending=[]
    for name,entry in manifest.items():
        source=FOLDER/name;digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if digest!=entry['sha256']:raise ValueError('The Caption 3 font differs from its verified source; it was kept without installation.')
        with TTFont(source) as f:title=f['name'].getDebugName(4)
        destination=target/('Storylens-'+name);value=title+' (TrueType)'
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()!=digest:raise ValueError('A different font already exists at the destination; it was kept.')
        pending.append(dict(source=str(source),path=str(destination),name=title,registry_value=value,sha256=digest))
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
        for row in pending:
            try:old,_=winreg.QueryValueEx(key,row['registry_value'])
            except FileNotFoundError:old=None
            if old is not None and str(old).casefold()!=row['path'].casefold():raise ValueError('A different font registration was kept; review it before installing this face.')
        target.mkdir(parents=True,exist_ok=True)
        for row in pending:
            if not Path(row['path']).exists():shutil.copy2(row['source'],row['path'])
            winreg.SetValueEx(key,row['registry_value'],0,winreg.REG_SZ,row['path'])
            row['faces_loaded']=ctypes.windll.gdi32.AddFontResourceExW(row['path'],0,None)
            if not row['faces_loaded']:raise RuntimeError('The font was saved but Windows did not activate it. Restart the editor before retrying.')
    oldrows={str(Path(row['source']).resolve()).casefold():row for row in receipt['fonts']}
    oldrows.update({str(Path(row['source']).resolve()).casefold():row for row in pending})
    receipt.update(installed=True,fonts=list(oldrows.values()),time=time.time());receipt_path.parent.mkdir(parents=True,exist_ok=True);receipt_path.write_text(json.dumps(receipt,indent=2))
    result=ctypes.c_size_t();ctypes.windll.user32.SendMessageTimeoutW(0xffff,0x001D,0,0,2,3000,ctypes.byref(result))
    print('Installed the Caption 3 fonts; preserved all previous font receipts.')
if __name__=='__main__':install()
