"""Editable word captions from saved, verified Caption Studio timings."""
import json
import math
from pathlib import Path
from hinglish_captions.subtitles import _srt_time


def words(project):
    duration=float(project['media']['duration']);rows=[]
    from hinglish_captions.styles import template,font_file
    from hinglish_captions.renderer import _font_path
    style_name=project.get('style','minimal');style=template(style_name)
    font=str(_font_path(font_file(project.get('font','template'),style_name)))
    for cue_index,cue in enumerate(project.get('cues',[])):
        for word_index,word in enumerate(cue.get('words',[])):
            text=str(word.get('text','')).strip()
            a=max(0,float(cue['start']),float(word['start']));b=min(duration,float(cue['end']),float(word['end']))
            if not text or not math.isfinite(a+b) or b<=a:continue
            layout=(project.get('cue_layouts') or [])[cue_index] if cue_index<len(project.get('cue_layouts') or []) else {'x':.5,'y':project.get('position',.7),'size':project.get('size',1)}
            colors=(project.get('word_colors') or [])
            color=colors[cue_index][word_index] if cue_index<len(colors) and word_index<len(colors[cue_index]) else None
            rows.append({'text':text.upper() if style.get('case')=='upper' else text,'start':a,'end':b,'layout':layout,'color':color or style['base'],'cue':cue_index,
                'font_path':font,'size_px':float(project.get('width',project['media'].get('width',720)))*.078*float(layout['size'])})
    if not rows:raise ValueError('No saved word timings are ready. Save & export your captions first, then prepare editable words.')
    return sorted(rows,key=lambda w:(w['start'],w['end']))


def srt(path,rows):
    lines=[]
    for i,row in enumerate(rows,1):
        a=round(row['start']*1000);b=max(a+1,round(row['end']*1000))
        lines.extend([str(i),f'{_srt_time(a/1000)} --> {_srt_time(b/1000)}',row['text'],''])
    Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')


def load(folder):
    paths=list(Path(folder).rglob('caption-project.json'))
    if not paths:raise ValueError('This edit has no saved caption words. Generate captions and save them in Caption Studio first.')
    return [(p,json.loads(p.read_text('utf-8'))) for p in sorted(paths)]


def export(folder,destination):
    """Separate clean picture and one timed subtitle per word; never double-burn."""
    from hinglish_cut.media import probe
    from hinglish_cut.model import Cut
    from hinglish_cut.xml_export import export_xml
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    items=[]
    for i,(file,project) in enumerate(load(folder),1):
        source=Path(project['media']['path'])
        if not source.is_file():
            source=file.parent/project.get('source_relative','missing-source')
        if not source.is_file():raise ValueError('The original caption video has moved. Relink it in Caption Studio and save before exporting editable words.')
        rows=words(project);subtitle=destination/f'WORDS-{i:03d}.srt';srt(subtitle,rows)
        manifest=destination/f'WORDS-{i:03d}.json';manifest.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        m=probe(source);xml=destination/f'CAPTION-BASE-{i:03d}.xml'
        export_xml(xml,[Cut(m.id,0,round(m.duration*float(m.rate)),0)],{m.id:m})
        items.append({'source':str(source.resolve()),'srt':str(subtitle.resolve()),'xml':str(xml.resolve()),'words':len(rows),'word_rows':rows})
    return items
