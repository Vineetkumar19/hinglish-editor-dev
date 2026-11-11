"""Activate the already installed, documented Match Cut font without changing font names."""
from pathlib import Path
import ctypes,hashlib,json,sys,winreg
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
from template_font_audit import font_names
out=root/'output/effects-library-evidence'
audit=json.loads((out/'font-audit.json').read_text(encoding='utf8'))
font=Path(audit['installed']['Inter-Bold'])
assert font.is_file() and any('Inter-Bold' in row.get('6',[]) for row in font_names(font))
registered=[]
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
    for i in range(winreg.QueryInfoKey(key)[1]):
        name,value,_=winreg.EnumValue(key,i)
        if str(value).casefold()==str(font).casefold():registered.append(name)
assert registered, 'Inter Bold is present but not registered for the current Windows user.'
gdi=ctypes.WinDLL('gdi32',use_last_error=True)
gdi.AddFontResourceExW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_void_p]
gdi.AddFontResourceExW.restype=ctypes.c_int
faces=gdi.AddFontResourceExW(str(font),0,None)
if faces:
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.SendNotifyMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
    notified=bool(user.SendNotifyMessageW(0xffff,0x001d,0,0))
else:notified=False
receipt={'documented_required_font':'Inter-Bold','source_document':'D:/Editing/Cinematics AE templates/Effects templates/match-cut-intro-64791012/Project File/Tutorial/Read me.txt','font_path':str(font),'sha256':hashlib.sha256(font.read_bytes()).hexdigest(),'windows_registry_names':registered,'already_installed':True,'session_faces_activated':faces,'font_change_broadcast':notified,'exact_postscript_name_verified':True,'native_ae_recognition':'Pending owner check; Windows registration and broadcast do not prove AE used-font recognition.','unresolved_binary_candidates':audit['missing_candidates'],'candidate_limit':'MojitoWeb and Myriad-Roman occur in internal dictionaries; the pack documentation requests Inter only. Actual usage is unverified, so no replacements or unlicensed font downloads were performed.'}
(out/'font-activation.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
print(json.dumps({'documented_font':'Inter-Bold','already_installed':True,'session_faces_activated':faces,'font_change_broadcast':notified,'native_ae_recognition':'owner check pending'}))
