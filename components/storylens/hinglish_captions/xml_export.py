from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET

from hinglish_cut.model import Cut
from hinglish_cut.xml_export import add, export_xml, premiere_pathurl, rate, video_format_dimensions


def export_caption_xml(path, media, overlay, output_format=None, overlay_width=None, overlay_height=None):
    total = math.floor(media.duration * float(media.rate) + 1e-6)
    export_xml(path, [Cut(media.id, 0, total, 0)], {media.id: media}, output_format)
    tree = SafeET.parse(path)
    root = tree.getroot()
    sequence = root.find('sequence')
    sequence.find('name').text = 'CAPTIONED_' + Path(media.path).stem
    video = sequence.find('./media/video')
    track = add(video, 'track')
    item = add(track, 'clipitem', id='caption-overlay-1')
    add(item, 'name', Path(overlay).name)
    add(item, 'enabled', 'TRUE')
    add(item, 'duration', total)
    rate(item, media.fps)
    for tag, value in [('start', 0), ('end', total), ('in', 0), ('out', total)]:
        add(item, tag, value)
    file = add(item, 'file', id='caption-overlay-file')
    add(file, 'name', Path(overlay).name)
    add(file, 'pathurl', premiere_pathurl(overlay))
    rate(file, media.fps)
    add(file, 'duration', total)
    timecode = add(file, 'timecode'); rate(timecode, media.fps)
    add(timecode, 'string', '00:00:00:00'); add(timecode, 'frame', 0); add(timecode, 'displayformat', 'NDF')
    file_media = add(file, 'media'); file_video = add(file_media, 'video')
    video_format_dimensions(add(file_video, 'samplecharacteristics'), overlay_width or media.width,
                            overlay_height or media.height, media.fps)
    ET.indent(root, space='  ')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    Path(path).write_bytes(data.replace(b'?>', b'?>\n<!DOCTYPE xmeml>', 1))
