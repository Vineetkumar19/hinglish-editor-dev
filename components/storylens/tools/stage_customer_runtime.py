"""Create an isolated compilation tree, excluding owner data and merchant secrets."""
import argparse
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse
from hinglish_license.crypto import decode

ROOT=Path(__file__).resolve().parents[1]


def stage(destination,origin,public_key):
    destination=Path(destination).resolve()
    if not destination.is_relative_to((ROOT/'output/saas/build').resolve()) or destination.exists():
        raise ValueError('Use a new build directory inside output/saas/build. Existing files are preserved.')
    uri=urlparse(origin)
    if uri.scheme!='https' or not uri.hostname or uri.hostname.endswith('.example') or uri.path or uri.query or uri.fragment or uri.username:
        raise ValueError('Use the real production license server HTTPS origin.')
    decode(public_key,32);destination.mkdir(parents=True)
    copied=[]
    for folder in ROOT.glob('hinglish_*'):
        if not folder.is_dir() or folder.name=='hinglish_saas':continue
        for file in folder.rglob('*'):
            if not file.is_file() or file.suffix.lower() not in ('.py','.js','.jsx','.html','.css','.svg','.ttf','.otf','.woff','.woff2','.txt'):continue
            if '__pycache__' in file.parts:continue
            relative=file.relative_to(ROOT);target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(file,target);copied.append(relative.as_posix())
    shutil.copytree(ROOT/'editor_plugins/release',destination/'editor_plugins/release')
    (destination/'hinglish_license/release_config.py').write_text('SERVER_ORIGIN = '+repr(origin)+'\nPUBLIC_KEY = '+repr(public_key)+'\n',encoding='utf-8')
    (destination/'build-provenance.json').write_text(json.dumps({'server_origin':origin,'public_key':public_key,
             'owner_media':False,'merchant_secrets':False,'models':False,'source_files':copied},indent=2),encoding='utf-8')
    return destination


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--origin',required=True);parser.add_argument('--public-key',required=True)
    args=parser.parse_args();print(stage(args.destination,args.origin,args.public_key))


if __name__=='__main__':main()
