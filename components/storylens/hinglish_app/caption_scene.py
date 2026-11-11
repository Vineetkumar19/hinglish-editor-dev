"""Editable word scenes from the existing Caption Studio design geometry."""
import math
from pathlib import Path
from fractions import Fraction


def build(project):
    """Use shared Caption 1 geometry or observe the selected renderer's words."""
    from hinglish_captions.styles import TEMPLATES
    style=project.get('style','minimal')
    if style not in TEMPLATES:
        raise ValueError('Choose one of the current Caption Studio styles, save it, then retry the editable import.')
    if style=='caption_1' and project.get('word_visibility','phrase')!='spoken':
        return caption_one(project)
    return rendered_scene(project)


def rendered_scene(project):
    from hinglish_captions import scene_capture
    from hinglish_captions.project import cues_from_data
    from hinglish_captions.renderer import draw_editor_caption
    from hinglish_captions.styles import template
    width,height=int(project['width']),int(project['height'])
    style=project.get('style','minimal');visibility=project.get('word_visibility','phrase')
    fps=min(30.,float(Fraction(str(project['media'].get('fps',30)))))
    duration=float(project['media']['duration']);result=[]
    for cue_index,cue in enumerate(cues_from_data(project['cues'])):
        layouts=project.get('cue_layouts') or []
        placement=layouts[cue_index] if cue_index<len(layouts) else {
            'x':.5,'y':project.get('position',template(style).get('default_position',.7)),
            'size':project.get('size',1)}
        colors=project.get('word_colors') or []
        cue_colors=colors[cue_index] if cue_index<len(colors) else []
        found={};first=max(0,math.floor(cue.start*fps));last=min(math.ceil(duration*fps),math.ceil(cue.end*fps))
        with scene_capture.capture():
            for frame in range(first,last):
                seconds=frame/fps+1e-7
                picture=draw_editor_caption(width,height,cue,seconds,style,project.get('font','template'),placement,visibility,cue_colors)
                for row in scene_capture.words(picture):
                    index=row['index']
                    if index is None:continue
                    key=(index,row.get('outline',False))
                    if key not in found:found[key]={'row':row,'frames':[]}
                    found[key]['frames'].append((seconds,row))
        for (index,outline),item in found.items():
            row=item['row'];frames=item['frames']
            start=max(0,cue.start,min(cue.words[index].start,frames[0][0]));end=min(duration,cue.end,frames[-1][0]+1/fps)
            if end<=start:continue
            path=Path(row['font_path'])
            if path.name=='Inter-Variable.ttf':
                face={300:'Light',400:'Regular',700:'Bold',900:'Black'}[row.get('weight') or 400]
                path=path.with_name(f'StorylensInterCaption-{face}.ttf')
                if not path.is_file():raise ValueError('The exact Inter editor weights are missing. Run tools/prepare_editor_font_instances.py and tools/install_caption_fonts.py --install, then retry.')
            animation=[{'time':max(0,t-start),'x':r['x'],'y':r['y'],'alpha':r['alpha'],'sx':r['sx'],'sy':r['sy'],'blur':r.get('blur',0)} for t,r in frames]
            if animation[0]['time']>1e-6:
                animation.insert(0,dict(animation[0],time=0,alpha=0))
            result.append({'text':row['text'],'font_path':str(path),'size_px':row['size_px'],
                'tracking':row['tracking'],'color':row['color'],'gradient':row['gradient'],
                'stroke_width':row.get('stroke_width',0),'stroke_color':row.get('stroke_color'),
                'outline':outline,'cue':cue_index,'slot':index+(len(cue.words) if outline else 0),
                'start':start,'end':end,'animation':animation,'design':style})
        # Full-sized word masks are cached only to accelerate one composition.
        # Release them before the next cue to keep this laptop's RAM bounded.
        for module_name in ('caption_one','caption_two','caption_three','caption_four','caption_five'):
            import sys
            module=sys.modules.get('hinglish_captions.'+module_name)
            if module:
                for name in ('glyph_mask','text_asset','glyph','selection_tile'):
                    method=getattr(module,name,None)
                    if hasattr(method,'cache_clear'):method.cache_clear()
    if not result:
        raise ValueError('No visible caption words were found. Check the saved word timings and save the caption project, then retry.')
    return sorted(result,key=lambda r:(r['start'],r['slot']))


def caption_one(project):
    from hinglish_captions.caption_one import layout, paginate_cue, motion_for, motion_state, text_metrics, profile
    from hinglish_captions.project import cues_from_data
    width, height = int(project['width']), int(project['height'])
    duration = float(project['media']['duration'])
    visibility = project.get('word_visibility', 'phrase')
    if visibility == 'spoken':
        from .word_captions import words
        return words(project)
    result = []
    for cue_index, cue in enumerate(cues_from_data(project['cues'])):
        saved_layouts = project.get('cue_layouts') or []
        placement = saved_layouts[cue_index] if cue_index < len(saved_layouts) else {
            'x': .5, 'y': project.get('position', .6234375), 'size': project.get('size', 1)}
        colors = (project.get('word_colors') or [])
        cue_colors = colors[cue_index] if cue_index < len(colors) else []
        word_offset = 0
        for page in paginate_cue(cue, project.get('font', 'template')):
            geometry = layout(width, height, [w.text.strip('.,!?:;') or w.text for w in page.words], project.get('font', 'template'))
            scale = float(placement['size'])
            for run in geometry['words']:
                i, font, text, row = run['index'], run['font'], run['text'], run['row']
                motion = motion_for(geometry['plan'], row, i)
                onset = page.words[i].start if visibility == 'styled_spoken' else page.words[motion['start_word']].start
                start = max(0., page.start, onset)
                end = min(duration, page.words[i].end if visibility == 'styled_spoken' else page.end)
                if end <= start:
                    continue
                _, left, right = text_metrics(font.path, font.size, text, run['tracking'])
                box = font.getbbox(text)
                native_x = run['x'] + (left + right) / 2
                baseline = run['baseline'] + round(height * .6234375 - geometry['height'] / 2)
                native_y = baseline - font.getmetrics()[0] + (box[1] + box[3]) / 2
                x = width * float(placement['x']) + (native_x - width / 2) * scale
                y = height * float(placement['y']) + (native_y - height * .6234375) * scale
                color_index = word_offset + i
                color = cue_colors[color_index] if color_index < len(cue_colors) else None
                gradient = profile()['gradient'] if row.get('blue') and not color else None
                fps = float(Fraction(str(project['media'].get('fps', 30))))
                animation_end = min(end - start, motion['duration'])
                offsets = sorted({0., animation_end, *[j / fps for j in range(1, math.ceil(animation_end * fps))]})
                animation = []
                for offset in offsets:
                    alpha, dx, dy = motion_state(start + offset - onset, motion)
                    animation.append({'time': offset, 'alpha': alpha,
                        'x': x + dx * geometry['scale'] * scale,
                        'y': y + dy * geometry['scale'] * scale})
                result.append({'text': text, 'start': start, 'end': end, 'cue': cue_index,
                    'slot': i, 'font_path': str(font.path), 'size_px': font.size * scale,
                    'tracking': run['tracking'], 'color': color or ('#25A8FC' if gradient else '#FFFFFF'),
                    'gradient': gradient, 'shadow': True, 'animation': animation,
                    'layout': {'x': x / width, 'y': y / height, 'size': scale},
                    'design': 'caption_1', 'spoken_start': page.words[i].start,
                    'spoken_end': page.words[i].end})
            word_offset += len(page.words)
    return sorted(result, key=lambda word: (word['start'], word['slot']))
