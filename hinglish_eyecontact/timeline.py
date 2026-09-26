"""Which camera files a timeline uses (and which parts of them), and the same timeline relinked to the
eye-contact copies. Only the media links change: every cut, effect and keyframe stays exactly as it was."""
from pathlib import Path
import xml.etree.ElementTree as ET

from hinglish_broll.timeline import _int, path_from_pathurl, path_key, read_rate
from hinglish_cut.xml_export import premiere_pathurl

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mxf', '.mkv', '.avi', '.mts', '.m2ts', '.webm', '.m4v'}


def _sequence(root):
    sequence = root if root.tag == 'sequence' else root.find('.//sequence')
    if sequence is None:
        raise ValueError('This XML has no sequence. Export a Final Cut Pro 7 XML timeline.')
    return sequence


def _merge(ranges):
    merged = []
    for a, b in sorted(ranges):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def used_sources(xml_path, skip=()):
    """[{'path', 'ranges': [(start_s, end_s) in the source]}] for camera clips on the video tracks.

    `skip`: folders whose media are never talking heads (our B-roll downloads and library)."""
    root = ET.parse(xml_path).getroot()
    sequence = _sequence(root)
    fps = read_rate(sequence)
    files = {f.get('id'): path_from_pathurl(f.findtext('pathurl')) for f in root.iter('file')
             if f.get('id') and f.findtext('pathurl')}
    skip = [path_key(s) for s in skip]
    found = {}
    for track in sequence.findall('./media/video/track'):
        if (track.findtext('enabled') or 'TRUE').upper() == 'FALSE':
            continue
        for item in track.findall('clipitem'):
            if (item.findtext('enabled') or 'TRUE').upper() == 'FALSE':
                continue
            file = item.find('file')
            path = files.get(file.get('id')) if file is not None else None
            if not path or Path(path).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            key = path_key(path)
            if any(key.startswith(s) for s in skip):
                continue
            rate = read_rate(item, fps)
            start, end = _int(item, 'in'), _int(item, 'out')
            if end <= start:
                continue
            entry = found.setdefault(key, {'path': path, 'ranges': []})
            entry['ranges'].append((float(start / rate), float(end / rate)))
    return [{'path': e['path'], 'ranges': _merge(e['ranges'])} for e in found.values()]


def relink(xml_path, target, fixed):
    """Write `target`: the same sequence with every file in `fixed` ({original path: new path}) swapped."""
    tree = ET.parse(xml_path)
    wanted = {path_key(k): Path(v) for k, v in fixed.items()}
    swapped = 0
    for f in tree.getroot().iter('file'):
        url = f.find('pathurl')
        if url is None or not url.text:
            continue
        new = wanted.get(path_key(path_from_pathurl(url.text)))
        if new is None:
            continue
        url.text = premiere_pathurl(new)
        name = f.find('name')
        if name is not None:
            name.text = new.name
        swapped += 1
    sequence = _sequence(tree.getroot())
    title = sequence.find('name')
    if title is not None and title.text:
        title.text = f'{title.text} - Eye Contact'
    data = ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True)
    Path(target).write_bytes(data.replace(b'?>', b'?>\n<!DOCTYPE xmeml>', 1))
    return swapped
