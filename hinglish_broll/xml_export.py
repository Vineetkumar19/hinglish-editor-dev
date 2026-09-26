"""Copy a sequence XML and add a B-roll video track directly above the talking-head track."""
from pathlib import Path
import math
import xml.etree.ElementTree as ET

from hinglish_cut.xml_export import add, premiere_pathurl, rate, video_format_dimensions


def _fps_text(fps):
    return f'{fps.numerator}/{fps.denominator}' if fps.denominator != 1 else str(fps.numerator)


def export_broll_xml(timeline, placements, target, suffix='_BROLL'):
    """placements: [{'path', 'start', 'end', 'name'}] with seconds on the sequence.

    Each B-roll file must already be conformed to the sequence size and frame rate,
    so no motion/scale effects are needed and Premiere/Resolve place it pixel-exact.
    """
    tree = ET.parse(timeline.xml_path)
    root = tree.getroot()
    sequence = root if root.tag == 'sequence' else root.find('.//sequence')
    for uuid in sequence.findall('uuid'):
        sequence.remove(uuid)
    sequence.set('id', (sequence.get('id') or 'sequence') + '-broll')
    name = sequence.find('name')
    if name is None: name = add(sequence, 'name')
    name.text = (name.text or 'Sequence') + suffix
    video = sequence.find('./media/video')
    tracks = video.findall('track')
    fps, fps_text = timeline.fps, _fps_text(timeline.fps)
    track = ET.Element('track')
    last_end = 0
    for n, p in enumerate(sorted(placements, key=lambda p: p['start']), 1):
        start = max(last_end, round(p['start'] * fps))
        end = round(p['end'] * fps)
        if end <= start:
            continue
        frames = end - start
        item = add(track, 'clipitem', id=f'broll-clip-{n}')
        add(item, 'name', p.get('name') or Path(p['path']).name)
        add(item, 'enabled', 'TRUE')
        add(item, 'duration', frames)
        rate(item, fps_text)
        for tag, value in (('start', start), ('end', end), ('in', 0), ('out', frames)):
            add(item, tag, value)
        f = add(item, 'file', id=f'broll-file-{n}')
        add(f, 'name', Path(p['path']).name)
        add(f, 'pathurl', premiere_pathurl(p['path']))
        rate(f, fps_text)
        add(f, 'duration', frames)
        tc = add(f, 'timecode'); rate(tc, fps_text)
        add(tc, 'string', '00:00:00:00'); add(tc, 'frame', 0); add(tc, 'displayformat', 'NDF')
        fv = add(add(f, 'media'), 'video')
        video_format_dimensions(add(fv, 'samplecharacteristics'), timeline.width, timeline.height, fps_text)
        last_end = end
    add(track, 'enabled', 'TRUE')
    add(track, 'locked', 'FALSE')
    # Insert as V2: above the talking head, below captions/graphics that were already on top.
    position = list(video).index(tracks[0]) + 1 if tracks else len(video)
    video.insert(position, track)
    ET.indent(root, space='  ')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    Path(target).write_bytes(data.replace(b'?>', b'?>\n<!DOCTYPE xmeml>', 1))
    return Path(target)
