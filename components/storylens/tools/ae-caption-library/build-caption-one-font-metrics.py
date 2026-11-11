"""Freeze the shipped Inter glyph ink/advances for deterministic caption packing."""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
import hashlib,json

root=Path(__file__).resolve().parents[2]
result={"version":1,"notes":"Unkerned glyph ink with tracking; native AE measured ink remains the final width guard.","fonts":{}}
for role,name in [('bold','Inter-Bold.otf'),('support','Inter-Medium.otf')]:
    source=root/'hinglish_captions/fonts'/name
    font=TTFont(source);glyphset=font.getGlyphSet();glyphs={}
    for code,glyphname in font.getBestCmap().items():
        pen=BoundsPen(glyphset);glyphset[glyphname].draw(pen)
        bounds=pen.bounds or (0,0,0,0)
        glyphs[str(code)]=[font['hmtx'][glyphname][0],bounds[0],bounds[2]]
    result['fonts'][role]={'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'units_per_em':font['head'].unitsPerEm,'glyphs':glyphs}
destination=root/'editor_plugins/caption-patterns/inter-ink-metrics.json'
destination.write_text(json.dumps(result,separators=(',',':'))+'\n',encoding='utf8')
print(destination.name, destination.stat().st_size, 'bytes')
