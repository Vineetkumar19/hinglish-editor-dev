"""Native editable Caption 1 graphics using a Premiere-created project template.

The template is read-only. This adapter writes a separate project, preserving
the clean picture, exact font faces and independent word graphics/keyframes.
"""
import base64
import copy
import gzip
import hashlib
import math
import json
import os
import struct
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from functools import lru_cache
from fractions import Fraction

TICKS = 254016000000
SOURCE_START = 914457600000000


def editor_font_path(path):
    font=Path(path)
    bundled=Path(__file__).resolve().parents[1]/'hinglish_captions/fonts'
    if font.resolve().parent==bundled.resolve() and font.name=='Inter-SemiBold.ttf':
        return bundled/'StorylensCircleSans-SemiBold.ttf'
    if font.resolve().parent==bundled.resolve() and font.name in ('Inter-Bold.otf','Inter-Medium.otf'):
        return bundled/('StorylensCaptionOne-'+font.name.removeprefix('Inter-'))
    return font


@lru_cache(maxsize=128)
def font_name(path):
    """Use the font's real PostScript face; family aliases can select a substitute."""
    from fontTools.ttLib import TTFont
    with TTFont(editor_font_path(path), lazy=True) as font:
        name = font['name'].getDebugName(6)
    if not name:
        raise ValueError('This caption font has no usable editor face name. Reinstall the caption fonts, then retry.')
    return name


def check_fonts(rows):
    """Fail before opening Premiere if an exact bundled face is unavailable."""
    paths=sorted({str(editor_font_path(row['font_path']).resolve()) for row in rows})
    root=Path(__file__).resolve().parents[1]
    bundled=(root/'hinglish_captions/fonts').resolve()
    receipt_path=root/'output/editor-handoffs/caption-font-installation.json'
    try:receipt=json.loads(receipt_path.read_text('utf-8'))
    except (OSError,ValueError):receipt={}
    installed={str(Path(row['source']).resolve()).casefold():row for row in receipt.get('fonts',[])}
    for path in paths:
        font=Path(path)
        if not font.is_file():
            raise ValueError(f'The exact caption font {font.name} is missing. Restore the caption fonts before importing; your saved captions are kept.')
        if os.name=='nt' and font.is_relative_to(bundled):
            row=installed.get(path.casefold())
            target=Path(row['path']) if row else None
            digest=hashlib.sha256(font.read_bytes()).hexdigest()
            if not target or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                raise ValueError(f'The exact caption font {font.name} is not installed for Premiere. Run tools/install_caption_fonts.py --install, then restart Premiere and retry. Your saved captions are kept.')
        font_name(path)
    return len(paths)


def _set(node, path, value):
    child = node.find(path)
    if child is None:
        child = ET.SubElement(node, path)
    child.text = str(value)


def _text_data(template, row):
    """Patch fields through their FlatBuffer vtables; never shift existing data."""
    b = bytearray(template)
    u32 = lambda p: struct.unpack_from('<I', b, p)[0]
    def field(table, index):
        vt = table - struct.unpack_from('<i', b, table)[0]
        size = struct.unpack_from('<H', b, vt)[0]
        if 4 + index * 2 >= size:
            raise ValueError('This Premiere text template has an unsupported structure.')
        offset = struct.unpack_from('<H', b, vt + 4 + index * 2)[0]
        if not offset:
            raise ValueError('The Premiere text template is missing a required style field.')
        return table + offset
    def target(p):
        return p + u32(p)
    def string(pointer, value):
        data = value.encode('utf-8')
        while len(b) % 4:
            b.append(0)
        start = len(b)
        b.extend(struct.pack('<I', len(data)) + data + b'\0')
        struct.pack_into('<I', b, pointer, start - pointer)
    def rgb(pointer, color):
        values = bytes.fromhex(color.lstrip('#'))
        while len(b) % 4:
            b.append(0)
        start = len(b)
        # Explicit RGB fields (including 0 and 255) avoid omitted defaults.
        b.extend(struct.pack('<HHHHH', 10, 8, 4, 5, 6) + b'\0\0')
        table = len(b)
        b.extend(struct.pack('<i', table - start) + values + b'\0')
        struct.pack_into('<I', b, pointer, table - pointer)
    root = target(12)
    document = target(field(root, 0))
    # Premiere's document-level shadow flag is independent of fill/stroke.
    # Do not inherit Caption 1's 100% shadow into clean typography styles.
    b[field(document, 11)] = 1 if row.get('shadow', False) else 0
    fonts = target(field(document, 1))
    runs = target(field(document, 0))
    run = target(runs + 4)
    style = target(field(run, 1))
    face = font_name(row['font_path']) if Path(row['font_path']).is_file() else ('Inter-Bold' if 'Bold' in row['font_path'] else 'Inter-Medium')
    string(fonts + 4, face)
    string(field(run, 0), row['text'])
    struct.pack_into('<f', b, field(style, 1), float(row['size_px']))
    struct.pack_into('<f', b, field(style, 8), float(row['tracking']) * 1000)
    # Native Appearance flags are byte fields, not 32-bit enums. The bundled
    # sample was saved by Premiere with both fields present so solid and hollow
    # words can share the same safe serialization contract.
    if row.get('color') or row.get('outline') or row.get('stroke_width'):
        b[field(style,3)]=0 if row.get('outline') else 1
        b[field(style,5)]=1 if row.get('outline') or row.get('stroke_width') else 0
        struct.pack_into('<f',b,field(style,6),float(row.get('stroke_width') or 1))
        rgb(field(style,4),row.get('stroke_color') or row.get('color','#FFFFFF'))
    if row.get('color') or row.get('gradient'):
        rgb(field(style, 2), row.get('color', '#FFFFFF'))
        gradient = row.get('gradient')
        struct.pack_into('<I', b, field(style, 20), 1 if gradient else 0)
        if gradient:
            stops = target(field(target(field(style, 21)), 1))
            if u32(stops) != 3:
                raise ValueError('The native gradient template needs three color stops. Restore the bundled editor template, then retry.')
            if len(gradient) == 2:
                a, z = gradient
                aa, zz = bytes.fromhex(a[1][1:]), bytes.fromhex(z[1][1:])
                middle = '#' + bytes(round((x+y)/2) for x,y in zip(aa,zz)).hex()
                gradient = [a, [.5, middle], z]
            for i, (location, color) in enumerate(gradient):
                stop = target(stops + 4 + i * 4)
                rgb(field(stop, 0), color)
                if i:
                    struct.pack_into('<f', b, field(stop, 1), float(location))
    # Native center alignment in a fixed text box. The box is positioned below.
    struct.pack_into('<f', b, field(document, 2), float(row.get('box_width', 540)))
    struct.pack_into('<f', b, field(document, 3), float(row.get('box_height',384)))
    while len(b) % 4:
        b.append(0)
    struct.pack_into('<I', b, 0, len(b) - 12)
    return bytes(b)


def export(template_path, project, destination, *, scene_rows=None):
    from PIL import ImageFont
    from .caption_scene import build
    destination = Path(destination)
    if destination.exists():
        raise ValueError('This Premiere caption project already exists. Choose a new output file.')
    template_path = Path(template_path)
    raw = template_path.read_bytes()
    tree = ET.fromstring(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)
    ids = {n.get('ObjectID'): n for n in tree if n.get('ObjectID')}
    # This explicit template contract is validated before any output is written.
    required = ['164', '166', '251', '377', '378', '678', '679', *map(str, range(820, 842))]
    if not all(key in ids for key in required) or ids['820'].findtext('Name') != 'Source Text':
        raise ValueError('A supported native Premiere text template is required. Your saved videos are unchanged.')
    rows = build(project) if scene_rows is None else scene_rows
    check_fonts(rows)
    blob = Path(__file__).with_name('templates').joinpath('premiere-source-text.bin').read_bytes()
    blur_template=ET.parse(Path(__file__).with_name('templates')/'premiere-blur.xml').getroot()
    seq = next(n for n in tree if n.tag == 'Sequence' and any(x.get('ObjectRef') == '164' for x in n.iter()))
    from hinglish_captions.styles import template
    _set(seq, 'Name', template(project.get('style','caption_1'))['name']+' - Editable Words')
    props = seq.find('Node/Properties')
    duration = float(project['media']['duration'])
    _set(props, 'MZ.EditLine', round(min(duration - .1, 1.65) * TICKS))
    _set(props, 'MZ.Sequence.PlaybackFractionalResolution', 4)
    _set(props, 'MZ.Sequence.ScrubbingFractionalResolution', 4)
    _set(props, 'Monitor.ProgramZoomOut', round(duration * TICKS))
    source = str(Path(project['media']['path']).resolve())
    for element in tree.iter():
        if element.tag in ('FilePath', 'ActualMediaFilePath', 'RelativePath') and element.text and ('taj-mahal-background.mp4' in element.text or element.text == '__STORYLENS_SOURCE__'):
            element.text = source
    for item_id in ('238', '239', '240'):
        _set(ids[item_id], 'ClipTrackItem/TrackItem/End', round(duration * TICKS))
    for clip_id in ('372', '374', '376'):
        _set(ids[clip_id], 'Clip/OutPoint', round(duration * TICKS))
    # Omit the old subtitle track from this new sequence to prevent double text.
    ids['166'].find('TrackGroup/Tracks').clear()
    tracks = ids['164'].find('TrackGroup/Tracks')
    base_track = next(n for n in tree if n.get('ObjectUID') == tracks[1].get('ObjectURef'))
    tracks.remove(tracks[1])
    group_ids = ['251', '377', '378', '678', '679', *map(str, range(820, 842))]
    next_id = max(map(int, ids)) + 1
    lanes = {}
    for slot in sorted({row['slot'] for row in rows}):
        track = copy.deepcopy(base_track)
        uid = str(uuid.uuid4())
        track.set('ObjectUID', uid)
        index = slot + 1
        _set(track, 'ClipTrack/Track/ID', index + 1)
        _set(track, 'ClipTrack/Track/Index', index)
        _set(track, 'ClipTrack/ClipItems/Index', index)
        _set(track, 'ClipTrack/TransitionItems/Index', index)
        items = track.find('ClipTrack/ClipItems/TrackItems')
        items.clear()
        items.set('Version', '1')
        lanes[slot] = items
        tree.append(track)
        ET.SubElement(tracks, 'Track', Index=str(index), ObjectURef=uid)
    _set(ids['164'], 'TrackGroup/NextTrackID', len(lanes) + 2)
    width, height = project['width'], project['height']
    _set(ids['164'], 'FrameRect', f'0,0,{width},{height}')
    # Native graphics have their own source canvas. Leaving the template's
    # 720px stream inside a 1080px sequence compresses text positions and clips
    # long support rows, even though the sequence settings look correct.
    graphic_media=ids['842'].find('MediaSource/Media').get('ObjectURef')
    graphic=next(n for n in tree if n.tag=='Media' and n.get('ObjectUID')==graphic_media)
    graphic_stream=ids[graphic.find('VideoStream').get('ObjectRef')]
    _set(graphic_stream,'FrameRect',f'0,0,{width},{height}')
    _set(props, 'MZ.Sequence.PreviewFrameSizeWidth', width)
    _set(props, 'MZ.Sequence.PreviewFrameSizeHeight', height)
    rate = Fraction(str(project['media'].get('fps', 30)))
    fps = float(rate)
    frame_ticks=round(Fraction(TICKS)/rate)
    # Premiere reads the sequence timebase inside TrackGroup. A direct sibling
    # is ignored, leaving the template's 60fps rate even for a 30fps source.
    for group_id in ('164','166'):
        _set(ids[group_id],'TrackGroup/FrameRate',frame_ticks)
    # Adobe PProPanel time-display enums; fractional rates use non-drop display.
    displays={Fraction(24):100,Fraction(25):101,Fraction(30000,1001):103,
        Fraction(30):104,Fraction(50):105,Fraction(60000,1001):107,
        Fraction(60):108,Fraction(24000,1001):110,Fraction(48):113}
    _set(props,'MZ.Sequence.VideoTimeDisplayFormat',displays.get(rate,109))
    _set(graphic_stream,'FrameRate',frame_ticks)
    source_width=project['media'].get('width',width);source_height=project['media'].get('height',height)
    _set(ids['162'],'FrameRect',f'0,0,{source_width},{source_height}')
    _set(ids['162'],'FrameRate',frame_ticks)
    for clip_id in ('43','48','372'):
        if clip_id in ids:_set(ids[clip_id],'Clip/FrameRate',frame_ticks)
    for row in rows:
        # A template-sized box wraps larger hero words after scaling to 1080p
        # (CHANGES became CHANGE + S). Give every word a full canvas-width box.
        row['box_width'] = width
        mapping = {old: str(next_id + i) for i, old in enumerate(group_ids)}
        next_id += len(group_ids)
        clones = {}
        for old in group_ids:
            node = copy.deepcopy(ids[old])
            node.set('ObjectID', mapping[old])
            for element in node.iter():
                if element.get('ObjectRef') in mapping:
                    element.set('ObjectRef', mapping[element.get('ObjectRef')])
                if element.tag == 'ClipID':
                    element.text = str(uuid.uuid4())
            tree.append(node)
            clones[old] = node
        start = round(row['start'] * fps) / fps
        end = max(start + 1 / fps, round(row['end'] * fps) / fps)
        item = clones['251'].find('ClipTrackItem/TrackItem')
        _set(item, 'Start', round(start * TICKS))
        _set(item, 'End', round(end * TICKS))
        # TrackItem.TrackIndex selects a SOURCE stream, not the timeline lane.
        # Synthetic text has only stream zero; lanes are set on VideoClipTrack.
        source_index = item.find('TrackIndex')
        if source_index is not None:
            item.remove(source_index)
        _set(clones['679'], 'Clip/InPoint', SOURCE_START)
        _set(clones['679'], 'Clip/OutPoint', SOURCE_START + round((end - start) * TICKS))
        _set(clones['378'], 'Name', row['text'])
        _set(clones['678'], 'Component/InstanceName', row['text'])
        value = clones['820'].find('StartKeyframeValue')
        font = ImageFont.truetype(row['font_path'], round(row['size_px']))
        row['box_height']=max(384,math.ceil(sum(font.getmetrics())*1.5))
        data = _text_data(blob, row)
        # Premiere's binary resource key includes the blob length + its 12-byte
        # resource header. Omitting this metadata can stall its text renderer.
        digest = hashlib.md5(data).hexdigest()[:24] + f'{len(data) + 12:08x}'
        value.set('BinaryHash', str(uuid.UUID(hex=digest)))
        value.text = base64.b64encode(data).decode()
        # Premiere bottom-aligns the native glyph line in its text box.
        box = font.getbbox(row['text'])
        # Position the paragraph box by the shared text BASELINE, not by each
        # word's ink height. Otherwise descenders (j/g/p/y) shift a word down
        # within a row. All same-font words on that row must share this value.
        baseline_adjust = font.getmetrics()[0] - (box[1] + box[3]) / 2
        positions, alphas, scales, horizontal = [], [], [], []
        sampled = {round(frame['time'] * fps): frame for frame in row['animation']}
        for frame_number, frame in sorted(sampled.items()):
            time = SOURCE_START + frame_number * round(TICKS / fps)
            sx,sy=frame.get('sx',1.),frame.get('sy',1.)
            x = (frame['x'] - row['box_width'] / 2*sx) / width
            y = (frame['y'] - (row['box_height'] - baseline_adjust)*sy) / height
            positions.append(f'{time},{x:.12g}:{y:.12g},0,0,0,0.16666666666666666,0,0.16666666666666666,5,4,0,0,0,0;')
            alphas.append(f'{time},{frame["alpha"] * 100:.12g},0,0,0,0.16666666666666666,0,0.16666666666666666;')
            scales.append(f'{time},{sy*100:.12g},0,0,0,0.16666666666666666,0,0.16666666666666666;')
            horizontal.append(f'{time},{sx*100:.12g},0,0,0,0.16666666666666666,0,0.16666666666666666;')
        _set(clones['825'],'StartKeyframe','-91445760000000000,false,0,0,0,0,0,0')
        for key, frames in [('822', positions), ('827', alphas),('823',scales),('824',horizontal)]:
            _set(clones[key], 'IsTimeVarying', 'true')
            _set(clones[key], 'Keyframes', ''.join(frames))
        if any(frame.get('blur',0)>.05 for frame in sampled.values()):
            blur_nodes={n.get('ObjectID'):copy.deepcopy(n) for n in blur_template}
            remap={old:str(next_id+i) for i,old in enumerate(blur_nodes)}
            next_id+=len(blur_nodes)
            for old,node in blur_nodes.items():
                node.set('ObjectID',remap[old])
                for element in node.iter():
                    if element.get('ObjectRef') in remap:element.set('ObjectRef',remap[element.get('ObjectRef')])
                tree.append(node)
            blur=next(n for n in blur_nodes.values() if n.findtext('Name')=='Blurriness')
            _set(blur,'IsTimeVarying','true')
            # Adobe's legacy Gaussian amount is approximately three standard
            # deviations; Pillow's radius is its standard deviation.
            _set(blur,'Keyframes',''.join(f'{SOURCE_START+n*round(TICKS/fps)},{frame.get("blur",0)*3:.12g},0,0,0,0.16666666666666666,0,0.16666666666666666;' for n,frame in sorted(sampled.items())))
            _set(blur,'StartKeyframe','-91445760000000000,0.,0,0,0,0,0,0')
            components=clones['377'].find('ComponentChain/Components')
            components[0].set('Index','1')
            component=next(n for n in blur_nodes.values() if n.tag=='VideoFilterComponent')
            components.insert(0,ET.Element('Component',Index='0',ObjectRef=component.get('ObjectID')))
        lane = lanes[row['slot']]
        ET.SubElement(lane, 'TrackItem', Index=str(len(lane)), ObjectRef=mapping['251'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if project.get('style') in ('caption_2','caption_3','kinetic_gold_draft','serif_circle_draft') and project.get('word_visibility','phrase')!='spoken':
        from .premiere_decorations import render, attach
        decoration_path=render(project,destination)
        attach(tree,project,decoration_path,TICKS)
    if project.get('omit_source_video'):
        # Caption-only review: keep the source audio, omit its video timeline item.
        source_track=next(n for n in tree if n.get('ObjectUID')==tracks[0].get('ObjectURef'))
        source_items=source_track.find('ClipTrack/ClipItems/TrackItems')
        if source_items is not None:source_items.clear()
    destination.write_bytes(gzip.compress(ET.tostring(tree, encoding='utf-8', xml_declaration=True)))
    return {'path': str(destination.resolve()), 'words': len(rows), 'tracks': len(lanes),
            'notice': 'Native editable word graphics with saved fonts, colors and animation keyframes.'}
