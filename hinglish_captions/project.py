from dataclasses import asdict
from pathlib import Path
import json

from hinglish_cut.model import Media
from hinglish_cut.xml_export import canvas_for

from .core import CaptionCue, CaptionWord, retime_cue_text
from .renderer import render_overlay
from .report import write_report
from .styles import FONT_CHOICES, TEMPLATES, template
from .subtitles import write_ass, write_srt
from .xml_export import export_caption_xml


def cues_to_data(cues):
    return [{'start': cue.start, 'end': cue.end,
             'words': [{'text': word.text, 'start': word.start, 'end': word.end}
                       for word in cue.words]} for cue in cues]


def cues_from_data(rows):
    return [CaptionCue(tuple(CaptionWord(str(word['text']), float(word['start']), float(word['end']))
                             for word in row['words']), float(row['start']), float(row['end']))
            for row in rows]


def write_project(path, media, cues, style, output_format, source_relative, spelling_changes=None,
                  reference_script='', font_id='template', position=.70, size_scale=1.0):
    width, height = canvas_for(None if output_format == 'source' else output_format, media)
    data = {
        'version': 1,
        'media': asdict(media),
        'source_relative': source_relative,
        'cues': cues_to_data(cues),
        'style': style,
        'font': font_id,
        'position': position,
        'size': size_scale,
        'output_format': output_format,
        'width': width,
        'height': height,
        'reference_script': reference_script,
        'spelling_changes': spelling_changes or [],
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data


def rebuild_project(project_path, changes, progress=print):
    project_path = Path(project_path)
    folder = project_path.parent
    data = json.loads(project_path.read_text(encoding='utf-8'))
    style_name = str(changes.get('style', data.get('style', 'flash_cut')))
    font_id = str(changes.get('font', data.get('font', 'template')))
    output_format = str(changes.get('output_format', data.get('output_format', 'source')))
    if style_name not in TEMPLATES:
        raise ValueError('Unknown caption template')
    if font_id not in FONT_CHOICES:
        raise ValueError('Unknown caption font')
    if output_format not in ('source', 'instagram_vertical', 'square', 'youtube_horizontal'):
        raise ValueError('Unknown video format')
    position = min(.92, max(.10, float(changes.get('position', data.get('position', .70)))))
    size_scale = min(1.8, max(.55, float(changes.get('size', data.get('size', 1.0)))))
    cues = cues_from_data(data['cues'])
    texts = changes.get('texts')
    if texts is not None:
        if not isinstance(texts, list) or len(texts) != len(cues):
            raise ValueError('Caption edit count does not match this project')
        cues = [retime_cue_text(cue, str(text)[:500]) for cue, text in zip(cues, texts)]
    media = Media(**data['media'])
    width, height = canvas_for(None if output_format == 'source' else output_format, media)
    overlay = folder / 'media' / 'premium-captions.mov'
    xml = folder / 'CAPTIONED_SEQUENCE.xml'
    render_overlay(overlay, cues, width, height, media.duration, media.rate, style_name, progress,
                   font_id, position, size_scale)
    export_caption_xml(xml, media, overlay, None if output_format == 'source' else output_format, width, height)
    write_srt(folder / 'captions.srt', cues)
    write_ass(folder / 'captions.ass', cues, style_name, width, height,
              font_id, position, size_scale)
    (folder / 'transcript.txt').write_text(' '.join(cue.text for cue in cues), encoding='utf-8')
    data.update(cues=cues_to_data(cues), style=style_name, font=font_id, position=position,
                size=size_scale, output_format=output_format, width=width, height=height)
    project_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    files = [('Open Premiere / Resolve XML', xml.name), ('Editable SRT', 'captions.srt'),
             ('Styled ASS', 'captions.ass'), ('Roman Hinglish transcript', 'transcript.txt')]
    write_report(folder / 'report.html', Path(media.path).name, data['source_relative'], cues,
                 style_name, files, data)
    return {'report': str((folder / 'report.html').resolve()), 'xml': str(xml.resolve()),
            'style': template(style_name)['name'], 'cues': len(cues)}
