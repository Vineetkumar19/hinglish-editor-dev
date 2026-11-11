"""Namespace the exact Inter SemiBold outlines to avoid Adobe family conflicts."""
from pathlib import Path
import json,hashlib
from fontTools.ttLib import TTFont

def prepare():
    fonts=Path(__file__).resolve().parents[1]/'hinglish_captions/fonts'
    source=fonts/'Inter-SemiBold.ttf';dest=fonts/'StorylensCircleSans-SemiBold.ttf'
    manifest=json.loads((fonts/'sources.json').read_text('utf-8'))
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest[source.name]['sha256']==digest
    family='Storylens Circle Sans SemiBold'
    values={1:family,2:'Regular',3:family+' Storylens',4:family,6:'StorylensCircleSans-SemiBold',16:family,17:'Regular'}
    with TTFont(source) as font:
        for record in list(font['name'].names):
            if record.nameID in values:font['name'].setName(values[record.nameID],record.nameID,record.platformID,record.platEncID,record.langID)
        for key,value in values.items():font['name'].setName(value,key,3,1,1033)
        font['OS/2'].fsSelection=(font['OS/2'].fsSelection&~(1<<5))|(1<<6)
        font['head'].macStyle&=~1
        font.save(dest)
    manifest[dest.name]={'source':'Exact outlines and metrics of verified Inter-SemiBold.ttf with distinct Adobe family','source_sha256':digest,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'font_name':[family,'Regular']}
    (fonts/'sources.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
    print(dest.name)

if __name__=='__main__':prepare()
