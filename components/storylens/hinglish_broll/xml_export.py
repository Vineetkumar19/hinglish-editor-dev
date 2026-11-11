"""Copy a sequence XML and add a B-roll video track directly above the talking-head track."""
from pathlib import Path
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET

from hinglish_cut.xml_export import add, premiere_pathurl, rate, video_format_dimensions


def _fps_text(fps):
    return f'{fps.numerator}/{fps.denominator}' if fps.denominator != 1 else str(fps.numerator)


def build_track(placements, fps, width, height, prefix='broll'):
    """One video track of pre-conformed clips: [{'path', 'start', 'end', 'name'}] in sequence seconds.

    Each file must already match the sequence size and frame rate (alpha .mov overlays included),
    so no motion/scale effects are needed and Premiere/Resolve place it pixel-exact."""
    fps_text = _fps_text(fps)
    track = ET.Element('track')
    last_end = 0
    for n, p in enumerate(sorted(placements, key=lambda p: p['start']), 1):
        start = max(last_end, round(p['start'] * fps))
        end = round(p['end'] * fps)
        if end <= start:
            continue
        frames = end - start
        source_in = round(p.get('source_in',0) * fps)
        source_frames = round(p.get('source_duration',p['end']-p['start']) * fps)
        if source_in < 0 or source_in + frames > source_frames:
            raise ValueError('B-roll trim exceeds its available footage. Shorten the cutaway or choose another clip.')
        item = add(track, 'clipitem', id=f'{prefix}-clip-{n}')
        add(item, 'name', p.get('name') or Path(p['path']).name)
        add(item, 'enabled', 'TRUE')
        add(item, 'duration', source_frames)
        rate(item, fps_text)
        for tag, value in (('start', start), ('end', end), ('in', source_in), ('out', source_in+frames)):
            add(item, tag, value)
        f = add(item, 'file', id=f'{prefix}-file-{n}')
        add(f, 'name', Path(p['path']).name)
        add(f, 'pathurl', premiere_pathurl(p['path']))
        rate(f, fps_text)
        add(f, 'duration', source_frames)
        tc = add(f, 'timecode'); rate(tc, fps_text)
        add(tc, 'string', '00:00:00:00'); add(tc, 'frame', 0); add(tc, 'displayformat', 'NDF')
        fv = add(add(f, 'media'), 'video')
        video_format_dimensions(add(fv, 'samplecharacteristics'), width, height, fps_text)
        if p.get('scale',100) != 100:
            effect=add(add(item,'filter'),'effect')
            for tag,value in (('name','Basic Motion'),('effectid','basic'),('effecttype','motion'),('mediatype','video')):
                add(effect,tag,value)
            parameter=add(effect,'parameter');add(parameter,'parameterid','scale')
            add(parameter,'name','Scale');add(parameter,'value',p['scale'])
        last_end = end
    add(track, 'enabled', 'TRUE')
    add(track, 'locked', 'FALSE')
    return track


def export_tracks_xml(timeline, tracks, target, suffix):
    """Copy the sequence and insert `tracks` (bottom to top) right above the talking-head track,
    below captions/graphics that were already on top."""
    tree = SafeET.parse(timeline.xml_path)
    root = tree.getroot()
    sequence = root if root.tag == 'sequence' else root.find('.//sequence')
    for uuid in sequence.findall('uuid'):
        sequence.remove(uuid)
    sequence.set('id', (sequence.get('id') or 'sequence') + suffix.lower().replace('_', '-'))
    name = sequence.find('name')
    if name is None: name = add(sequence, 'name')
    name.text = (timeline.name or name.text or 'Sequence') + suffix
    video = sequence.find('./media/video')
    existing = video.findall('track')
    position = list(video).index(existing[0]) + 1 if existing else len(video)
    for offset, track in enumerate(tracks):
        video.insert(position + offset, track)
    ET.indent(root, space='  ')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    Path(target).write_bytes(data.replace(b'?>', b'?>\n<!DOCTYPE xmeml>', 1))
    return Path(target)


def export_broll_xml(timeline, placements, target, suffix='_BROLL'):
    """placements: [{'path', 'start', 'end', 'name'}] with seconds on the sequence; B-roll becomes V2."""
    track = build_track(placements, timeline.fps, timeline.width, timeline.height, 'broll')
    return export_tracks_xml(timeline, [track], target, suffix)
