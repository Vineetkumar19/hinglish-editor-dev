"""Sanitize the static Sites publication, which has no billing database."""
import json
import zipfile
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def main():
    dest=ROOT/'sites/hinglish-editor';manifest=json.loads((dest/'.openai/hosting.json').read_text(encoding='utf-8-sig'))
    if not manifest.get('project_id'):raise SystemExit('Register and persist the site identity first.')
    with zipfile.ZipFile(ROOT/'output/saas/STORYLENS_PUBLIC_WEBSITE.zip') as archive:
        for name in archive.namelist():
            path=(dest/'dist'/name).resolve()
            if not path.is_relative_to((dest/'dist').resolve()):raise SystemExit('Invalid public archive path.')
            content=archive.read(name)
            if name.endswith('.html'):
                text=content.decode('utf-8')
                for route in ('account','tour','policies','app','support','reviews'):
                    text=re.sub(r'(["\'])/'+route+r'(?=["\'?#])',r'\1/'+route+'.html',text)
                content=text.encode('utf-8')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    (dest/'.gitignore').write_text('node_modules/\n.openai/cache/\n.openai/tmp/\n.env\n',encoding='utf-8')
    (dest/'README.md').write_text('Public marketing site and read-only tour. No accounts, secret keys, billing database, editor engines, models or customer uploads are included. The complete subscription backend is prepared separately in the owner project.\n',encoding='utf-8')
    print('Public site prepared; 2 editions, no customer data collection or payments.')


if __name__=='__main__':main()
