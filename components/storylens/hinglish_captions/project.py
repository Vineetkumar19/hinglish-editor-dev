from dataclasses import asdict
from pathlib import Path
import json

from hinglish_cut.model import Media
from hinglish_cut.xml_export import canvas_for

from .core import CaptionCue, CaptionWord, build_cues, retime_cue_text
from .renderer import WORD_COLOR_CHOICES, render_overlay
from .report import write_report
from .styles import FONT_CHOICES, TEMPLATES, template
from .subtitles import write_ass, write_srt
from .xml_export import export_caption_xml


def caption_export_capabilities():
    from .caption_two import profile
    from .caption_three import LAYOUT_REVISION
    return {'revision': 2, 'reference_layout_revision': 2, 'template_pattern_revision':1,'demo_backgrounds': ['black', 'white'],
            'caption_two_motion': profile()['motion'], 'caption_three_layout_revision': LAYOUT_REVISION}


def cues_to_data(cues):
    return [{'start': cue.start, 'end': cue.end, 'template_source':cue.template_source or cue.text,
             'template_slot':cue.template_slot if cue.template_slot>=0 else index,
             'words': [{'text': word.text, 'start': word.start, 'end': word.end}
                       for word in cue.words]} for index,cue in enumerate(cues)]


def cues_from_data(rows):
    return [CaptionCue(tuple(CaptionWord(str(word['text']), float(word['start']), float(word['end']))
                             for word in row['words']), float(row['start']), float(row['end']),
                     row.get('template_source') or ' '.join(str(w['text']) for w in row['words']),int(row.get('template_slot',index)))
            for index,row in enumerate(rows)]


def write_project(path, media, cues, style, output_format, source_relative, spelling_changes=None,
                  reference_script='', font_id='template', position=None, size_scale=1.0,
                  word_colors=None):
    width, height = canvas_for(None if output_format == 'source' else output_format, media)
    if position is None:position=template(style)['default_position']
    data = {
        'version': 2,
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
        'word_colors': word_colors or [[None] * len(cue.words) for cue in cues],
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data


def rebuild_project(project_path, changes, progress=print):
    project_path = Path(project_path)
    folder = project_path.parent
    data = json.loads(project_path.read_text(encoding='utf-8'))
    project_only = changes.get('save_project_only') is True
    style_name = str(changes.get('style', data.get('style', 'caption_1')))
    font_id = str(changes.get('font', data.get('font', 'template')))
    output_format = str(changes.get('output_format', data.get('output_format', 'source')))
    if style_name not in TEMPLATES:
        raise ValueError('Unknown caption template')
    if font_id not in FONT_CHOICES:
        raise ValueError('Unknown caption font')
    if output_format not in ('source', 'instagram_vertical', 'square', 'youtube_horizontal'):
        raise ValueError('Unknown video format')
    demo_background = changes.get('demo_background', data.get('demo_background'))
    if demo_background is not None:
        if not data.get('demo') or demo_background not in ('black', 'white'):
            raise ValueError('Choose a black or white background for a demo project.')
    from .editing import apply_timings,layouts_for,number
    position=number(changes.get('position',data.get('position',.7)),'vertical position',0,1)
    size_scale=number(changes.get('size',data.get('size',1)),'caption size',.08,4)
    visibility=changes.get('word_visibility',data.get('word_visibility','phrase'))
    if visibility not in ('phrase','spoken','styled_spoken'):raise ValueError('Choose phrase or spoken-word visibility')
    cues = cues_from_data(data['cues'])
    texts = changes.get('texts')
    if texts is not None:
        if not isinstance(texts, list) or len(texts) != len(cues):
            raise ValueError('Caption edit count does not match this project')
        cues = [retime_cue_text(cue, str(text)[:500]) for cue, text in zip(cues, texts)]
    cues=apply_timings(cues,changes.get('timings'),float(data['media']['duration']))
    explicit_layouts=changes.get('cue_layouts',data.get('cue_layouts'))
    layouts=layouts_for(cues,explicit_layouts,position,size_scale)
    if template(style_name).get('layout'):
        for layout in layouts:layout['size']=size_scale
    raw_colors = changes.get('word_colors', data.get('word_colors'))
    if raw_colors is None:
        raw_colors = [[None] * len(cue.words) for cue in cues]
    if not isinstance(raw_colors, list) or len(raw_colors) != len(cues):
        raise ValueError('Word color edit count does not match this project')
    flat_colors = []
    for cue, values in zip(cues, raw_colors):
        if not isinstance(values, list):
            raise ValueError('Word colors must be selected per caption word')
        row = list(values[:len(cue.words)]) + [None] * max(0, len(cue.words) - len(values))
        for value in row:
            normalized = value.upper() if isinstance(value, str) else None
            flat_colors.append(normalized if normalized in WORD_COLOR_CHOICES else None)
    # Enforce the same readable caption rule for old projects and manual edits.
    # Character length can make a frame break at four words; no frame can exceed five.
    if not data.get('demo') and data.get('caption_content') != 'lyrics' and 'timings' not in changes and explicit_layouts is None:
        originals=cues
        cues = build_cues([word for cue in cues for word in cue.words],
                         max_words=template(style_name).get('max_words',5),
                         max_chars=52 if style_name=='caption_1' else 34, max_seconds=2.8)
        from .template_patterns import bind_patterns
        cues=bind_patterns(cues,originals)
        layouts=layouts_for(cues,None,position,size_scale)
    if not project_only and style_name=='caption_1':
        from .caption_one import paginate_cue
        pages=[(page,dict(layout)) for cue,layout in zip(cues,layouts)
               for page in paginate_cue(cue,font_id)]
        cues=[page for page,_ in pages];layouts=[layout for _,layout in pages]
    elif not project_only and style_name in ('cinematic_mixed_draft','cinematic_clean_draft'):
        from .cinematic_reference import pages as cinematic_pages
        cw,ch=canvas_for(None if output_format=='source' else output_format,Media(**data['media']))
        pages=[(page,dict(layout)) for cue,layout in zip(cues,layouts) for page in cinematic_pages(cue,cw,ch)]
        cues=[page for page,_ in pages];layouts=[layout for _,layout in pages]
    elif not project_only and style_name in ('caption_2','caption_3','caption_4','caption_5'):
        if style_name=='caption_2':
            from .caption_two import paginate_cue
        elif style_name=='caption_5':
            from .caption_five import paginate_cue
        elif style_name=='caption_4':
            from .caption_four import paginate_cue
        else:
            from .caption_three import paginate_cue
        pages=[(page,dict(layout)) for cue,layout in zip(cues,layouts) for page in paginate_cue(cue,font_id)]
        cues=[page for page,_ in pages];layouts=[layout for _,layout in pages]
    word_colors, cursor = [], 0
    for cue in cues:
        word_colors.append(flat_colors[cursor:cursor + len(cue.words)])
        cursor += len(cue.words)
    media = Media(**data['media'])
    if demo_background is not None and not project_only:
        from dataclasses import replace
        from .demo import ensure_solid_demo_background
        source = ensure_solid_demo_background(folder, folder / data['source_relative'], demo_background)
        media = replace(media, path=str(source.resolve()))
        data.update(media=asdict(media), source_relative=source.relative_to(folder).as_posix(),
                    demo_background=demo_background)
    width, height = canvas_for(None if output_format == 'source' else output_format, media)
    if project_only:
        changed=any(data.get(key)!=value for key,value in {
            'cues':cues_to_data(cues),'style':style_name,'font':font_id,
            'position':position,'size':size_scale,'output_format':output_format,
            'width':width,'height':height,'word_colors':word_colors,
            'cue_layouts':layouts,'word_visibility':visibility}.items())
        data.update(cues=cues_to_data(cues), style=style_name, font=font_id,
                    position=position, size=size_scale, output_format=output_format,
                    width=width, height=height, word_colors=word_colors,
                    cue_layouts=layouts, word_visibility=visibility, version=3,
                    preview_stale=bool(data.get('preview_stale') or changed))
        # Save the editable design without rendering video or acquiring the GPU.
        project_path.with_suffix('.previous.json').write_text(project_path.read_text('utf-8'), encoding='utf-8')
        temporary=project_path.with_suffix('.saving.json')
        temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(project_path)
        write_report(folder/'report.html',Path(media.path).name,data['source_relative'],cues,
                     style_name,[],data)
        return {'saved':True,'project':data,'video':None}
    overlay = folder / 'media' / 'premium-captions.mov'
    xml = folder / 'CAPTIONED_SEQUENCE.xml'
    from hinglish_cut.compute_policy import heavy_device
    device=heavy_device(Path(__file__).resolve().parents[1],data.get('transcription',{}).get('device','cpu'))
    if device == 'cuda':
        # Keep requested edits reviewable even when the selected format is unsupported.
        pending=dict(data,cues=cues_to_data(cues),style=style_name,font=font_id,position=position,
                     size=size_scale,output_format=output_format,width=width,height=height,
                     word_colors=word_colors,cue_layouts=layouts,word_visibility=visibility)
        (folder/'gpu-export-pending.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf8')
    render_overlay(overlay, cues, width, height, media.duration, media.rate, style_name, progress,
                   font_id, position, size_scale, word_colors,cue_layouts=layouts,word_visibility=visibility,device=device)
    export_caption_xml(xml, media, overlay, None if output_format == 'source' else output_format, width, height)
    write_srt(folder / 'captions.srt', cues,visibility)
    write_ass(folder / 'captions.ass', cues, style_name, width, height,
              font_id, position, size_scale,word_visibility=visibility,cue_layouts=layouts)
    (folder / 'transcript.txt').write_text(' '.join(cue.text for cue in cues), encoding='utf-8')
    data.update(preview_stale=False,cues=cues_to_data(cues), style=style_name, font=font_id, position=position,
                size=size_scale, output_format=output_format, width=width, height=height,
                word_colors=word_colors, cue_layouts=layouts,word_visibility=visibility,version=3)
    preview = folder / 'captioned-preview.mp4'
    if preview.exists() or changes.get('export_video'):
        from .export_video import render_captioned_video
        device = data.get('transcription', {}).get('device', 'cpu')
        background_options = {'demo_background': demo_background} if demo_background is not None else {}
        data['video_encoder'] = render_captioned_video(folder / data['source_relative'], overlay, preview, device, **background_options)
    project_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    files = [('Open Premiere / Resolve XML', xml.name), ('Editable SRT', 'captions.srt'),
             ('Styled ASS', 'captions.ass'), ('Roman Hinglish transcript', 'transcript.txt')]
    if preview.exists():files.append(('Captioned MP4',preview.name))
    write_report(folder / 'report.html', Path(media.path).name, data['source_relative'], cues,
                 style_name, files, data)
    return {'report': str((folder / 'report.html').resolve()), 'xml': str(xml.resolve()),'video':str(preview.resolve()) if preview.exists() else None,
            'style': template(style_name)['name'], 'cues': len(cues)}
