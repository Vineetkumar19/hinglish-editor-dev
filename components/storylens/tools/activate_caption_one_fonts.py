"""Activate unchanged bundled Caption 1 fonts for this login session.

Windows user font registrations remain installed; this handles Adobe sessions
which have not loaded those faces yet. No admin writes, downloads or renaming.
"""
import argparse,ctypes,hashlib,json
from pathlib import Path

def activate(root,load,notify,*,caption_two=False,caption_three=False,caption_six=False):
    source=Path(root)/'hinglish_captions/fonts';
    if caption_three:source=source/'caption-three'
    manifest=json.loads((source/'sources.json').read_text('utf8'));rows=[]
    names=('StorylensCircleSans-SemiBold.ttf','PlayfairDisplay-BoldItalic.ttf','InterDisplay-SemiBoldItalic.ttf') if caption_six else ('CaptionThree-BoldItalic.ttf','CaptionThree-RegularItalic.ttf','CaptionThree-Playful.ttf') if caption_three else ('Inter-Bold.otf','Inter-Medium.otf')+(('StorylensInterCaption-Regular.ttf',) if caption_two else ())
    for name in names:
        path=source/name;digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=manifest[name]['sha256']:raise ValueError('Restore the verified bundled '+name+' font before generating captions.')
        rows.append({'path':str(path.resolve()),'sha256':digest})
    for row in rows:
        row['faces_loaded']=load(row['path'])
        if not row['faces_loaded']:raise ValueError('Windows could not activate '+Path(row['path']).name+'. Its saved font file is kept.')
    notify()
    return {'activated':True,'fonts':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--caption-two',action='store_true');parser.add_argument('--caption-three',action='store_true');parser.add_argument('--caption-six',action='store_true');args=parser.parse_args()
    gdi=ctypes.WinDLL('gdi32',use_last_error=True);gdi.AddFontResourceExW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_void_p];gdi.AddFontResourceExW.restype=ctypes.c_int
    user=ctypes.WinDLL('user32',use_last_error=True);user.SendNotifyMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
    result=activate(args.root,lambda p:gdi.AddFontResourceExW(p,0,None),lambda:user.SendNotifyMessageW(0xffff,0x001d,0,0),caption_two=args.caption_two,caption_three=args.caption_three,caption_six=args.caption_six)
    print(json.dumps(result))
