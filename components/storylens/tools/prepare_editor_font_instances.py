"""Create exact static faces from the bundled variable design font.

Use a distinct family so Adobe cannot resolve Inter v4 weights to the separate
Inter v3 font used by Caption 1. The original bundled fonts stay untouched.
"""
from pathlib import Path
import hashlib
import json
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT=Path(__file__).resolve().parents[1]
FONTS=ROOT/'hinglish_captions/fonts'


def prepare():
    manifest=json.loads((FONTS/'sources.json').read_text('utf-8'))
    # Caption 1 uses Inter v3 outlines. Adobe resolves the Inter family to the
    # separately installed v4 variable font, hiding the v3 static Bold face.
    # Give exact copies their own family; never replace or redraw the glyphs.
    for style in ('Bold','Medium'):
        original=FONTS/f'Inter-{style}.otf'
        digest=hashlib.sha256(original.read_bytes()).hexdigest()
        if manifest[original.name]['sha256']!=digest:
            raise ValueError('The Caption 1 design font differs from its verified source.')
        dest=FONTS/f'StorylensCaptionOne-{style}.otf'
        if dest.exists():continue
        family='Storylens Caption One';full=family+' '+style;face='StorylensCaptionOne-'+style
        with TTFont(original) as font:
            values={1:family if style=='Bold' else full,2:'Bold' if style=='Bold' else 'Regular',
                    3:full+' Storylens',4:full,6:face,16:family,17:style}
            for record in list(font['name'].names):
                if record.nameID in values:
                    font['name'].setName(values[record.nameID],record.nameID,record.platformID,record.platEncID,record.langID)
            for name,value in values.items():font['name'].setName(value,name,3,1,1033)
            cff=font['CFF '].cff;cff.fontNames=[face]
            cff.topDictIndex[0].FamilyName=family;cff.topDictIndex[0].FullName=full
            font.save(dest)
        manifest[dest.name]={'source':'Exact outlines and metrics of verified '+original.name+' with a distinct Adobe family',
            'source_sha256':digest,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
            'bytes':dest.stat().st_size,'font_name':[family,style]}
    source=FONTS/'Inter-Variable.ttf'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if manifest[source.name]['sha256']!=digest:
        raise ValueError('The Inter design source has changed. Restore its verified font before preparing editor faces.')
    for weight,style in ((300,'Light'),(400,'Regular'),(700,'Bold'),(900,'Black')):
        dest=FONTS/f'StorylensInterCaption-{style}.ttf'
        if dest.exists():continue
        with TTFont(source) as variable:
            axes={a.axisTag:(weight if a.axisTag=='wght' else a.defaultValue) for a in variable['fvar'].axes}
            font=instantiateVariableFont(variable,axes,inplace=False)
        family='Storylens Inter Caption';full=family+' '+style
        # Windows' legacy family slots only support Regular/Bold/Italic/Bold
        # Italic. Light and Black need distinct legacy families, while the
        # typographic family groups all four exact faces in modern editors.
        legacy=family if style in ('Regular','Bold') else full
        values={1:legacy,2:'Bold' if style=='Bold' else 'Regular',3:full+' Storylens',4:full,
                6:'StorylensInterCaption-'+style,16:family,17:style}
        for record in list(font['name'].names):
            if record.nameID in values:
                font['name'].setName(values[record.nameID],record.nameID,record.platformID,record.platEncID,record.langID)
        for name,value in values.items():
            font['name'].setName(value,name,3,1,1033)
            font['name'].setName(value,name,0,3,0)
        font['OS/2'].fsSelection=(font['OS/2'].fsSelection&~(1<<5|1<<6)) | (1<<5 if style=='Bold' else 1<<6)
        font['head'].macStyle=(font['head'].macStyle&~1) | (1 if style=='Bold' else 0)
        font.save(dest)
        manifest[dest.name]={'source':'Static instance of verified bundled Inter-Variable.ttf',
            'source_sha256':digest,'axes':axes,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
            'bytes':dest.stat().st_size,'font_name':[family,style]}
    (FONTS/'sources.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':prepare()
