from pathlib import Path

from .styles import FONT_CHOICES, font_file, template


def _srt_time(seconds):
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f'{hours:02}:{minutes:02}:{secs:02},{millis:03}'


def write_srt(path, cues):
    lines = []
    for index, cue in enumerate(cues, 1):
        lines += [str(index), f'{_srt_time(cue.start)} --> {_srt_time(cue.end)}', cue.text, '']
    Path(path).write_text('\n'.join(lines), encoding='utf-8-sig')


def _ass_time(seconds):
    centis = max(0, round(seconds * 100))
    hours, centis = divmod(centis, 360_000)
    minutes, centis = divmod(centis, 6_000)
    secs, centis = divmod(centis, 100)
    return f'{hours}:{minutes:02}:{secs:02}.{centis:02}'


def _ass_color(value, alpha='00'):
    value = value.lstrip('#')
    return f'&H{alpha}{value[4:6]}{value[2:4]}{value[0:2]}'


def _font_name(font_id, style_name):
    filename = font_file(font_id, style_name)
    return {
        'impact.ttf': 'Impact', 'arialbd.ttf': 'Arial', 'bahnschrift.ttf': 'Bahnschrift',
        'segoeuib.ttf': 'Segoe UI', 'georgiab.ttf': 'Georgia', 'segoesc.ttf': 'Segoe Script',
        'trebucbd.ttf': 'Trebuchet MS',
    }.get(filename, Path(filename).stem)


def write_ass(path, cues, style, width, height, font_id='template', position=.70, size_scale=1.0):
    selected = template(style)
    font_name = _font_name(font_id, style)
    font_size = max(18, round(max(42, width // 22) * min(1.8, max(.55, float(size_scale)))))
    primary = _ass_color(selected['base'])
    secondary = _ass_color(selected['accent'])
    surface = selected.get('surface')
    border_style = 3 if surface else 1
    background = _ass_color(surface or '#000000', '10' if surface else 'A0')
    outline = 0 if surface else max(2, width // 640)
    shadow = 0 if surface else max(1, width // 960)
    y = round(height * min(.92, max(.10, float(position))))
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Premium,{font_name},{font_size},{primary},{secondary},&HCC000000,{background},-1,0,0,0,100,100,0,0,{border_style},{outline},{shadow},5,60,60,0,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    events = []
    for cue in cues:
        parts = []
        for word in cue.words:
            delay = max(1, round((word.end - word.start) * 100))
            parts.append(f'{{\\k{delay}}}{word.text}')
        events.append(f'Dialogue: 0,{_ass_time(cue.start)},{_ass_time(cue.end)},Premium,,0,0,0,,{{\\pos({width // 2},{y})}}{" ".join(parts)}')
    Path(path).write_text(header + '\n'.join(events) + '\n', encoding='utf-8-sig')
