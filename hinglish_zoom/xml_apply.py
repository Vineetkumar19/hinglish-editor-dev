"""Apply a per-frame zoom curve to the talking-head track of an FCP 7 XML sequence.

Zooms are written as clip pieces with *static* Basic Motion values (scale + centre). Eased ramps
are baked frame by frame, so Premiere and Resolve reproduce them exactly: no keyframe import
quirks, no interpolation differences, no jitter. Audio is never cut.
"""
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from hinglish_broll.timeline import path_from_pathurl, read_rate
from hinglish_cut.xml_export import add

# FCP 7 XML Basic Motion centre: offset from the frame centre as a fraction of the sequence
# width/height (x right, y down). One place to change if an editor reads it differently.
CENTER_X_UNIT, CENTER_Y_UNIT = 1.0, 1.0


@dataclass
class TrackClip:
    item: ET.Element
    id: str
    start: int            # sequence frames
    end: int
    source_in: int        # clip-rate frames
    rate: Fraction
    path: str
    base_scale: float     # 1.0 = 100 %
    base_center: tuple    # sequence pixels from the frame centre
    zoomable: bool
    reason: str = ''

    def source_seconds(self, fps):
        return float(Fraction(self.source_in) / self.rate), float(Fraction(self.source_in) / self.rate
                                                                   + Fraction(self.end - self.start) / fps)


def _int(node, tag, default=-1):
    try: return int(float(node.findtext(tag)))
    except (TypeError, ValueError): return default


def basic_motion(item):
    for effect in item.iter('effect'):
        if (effect.findtext('effectid') or '').lower() == 'basic' or (effect.findtext('name') or '') == 'Basic Motion':
            return effect
    return None


def _param(effect, pid):
    for p in effect.findall('parameter'):
        if (p.findtext('parameterid') or '').lower() == pid.lower():
            return p
    return None


class Sequence:
    def __init__(self, path):
        self.path = Path(path)
        self.tree = ET.parse(self.path)
        self.root = self.tree.getroot()
        self.sequence = self.root if self.root.tag == 'sequence' else self.root.find('.//sequence')
        if self.sequence is None:
            raise ValueError('This XML has no sequence')
        self.fps = read_rate(self.sequence)
        fmt = self.sequence.find('./media/video/format/samplecharacteristics')
        self.width = _int(fmt, 'width', 1920) if fmt is not None else 1920
        self.height = _int(fmt, 'height', 1080) if fmt is not None else 1080
        self.files = {f.get('id'): path_from_pathurl(f.findtext('pathurl')) for f in self.root.iter('file')
                      if f.get('id') and f.findtext('pathurl')}
        tracks = self.sequence.findall('./media/video/track')
        if not tracks:
            raise ValueError('The sequence has no video track')
        self.track = tracks[0]
        self.upper = tracks[1:]
        self.clips = [self._clip(item) for item in self.track.findall('clipitem')]
        self.clips = [c for c in self.clips if c]
        frames = _int(self.sequence, 'duration', 0)
        self.frames = max([frames] + [c.end for c in self.clips])

    def _clip(self, item):
        start, end = _int(item, 'start'), _int(item, 'end')
        file = item.find('file')
        path = self.files.get(file.get('id')) if file is not None else None
        clip = TrackClip(item, item.get('id') or '', start, end, max(0, _int(item, 'in', 0)),
                         read_rate(item, self.fps), path or '', 1.0, (0.0, 0.0), True)
        if (item.findtext('enabled') or 'TRUE').upper() == 'FALSE':
            clip.zoomable, clip.reason = False, 'disabled'
        if start < 0 or end <= start:
            clip.zoomable, clip.reason = False, 'next to a transition'
        if item.find('sequence') is not None or not path:
            clip.zoomable, clip.reason = False, 'nested sequence'
        motion = basic_motion(item)
        if motion is not None:
            if motion.find('.//keyframe') is not None:
                clip.zoomable, clip.reason = False, 'already has motion keyframes'
            scale = _param(motion, 'scale')
            if scale is not None and scale.findtext('value'):
                clip.base_scale = float(scale.findtext('value')) / 100
            center = _param(motion, 'center')
            if center is not None and center.find('value/horiz') is not None:
                clip.base_center = (float(center.findtext('value/horiz')) * self.width / CENTER_X_UNIT,
                                    float(center.findtext('value/vert')) * self.height / CENTER_Y_UNIT)
        return clip if start >= 0 or end >= 0 else None

    def blocked_seconds(self, include_popups=True):
        """Time ranges covered by B-roll/cutaways above the talking head (zooms there would be hidden).

        Long clips on upper tracks (caption layers, logos, full-length graphics) are ignored. Smart Visuals
        pop-up cards leave the face visible; with include_popups=False they do not block anything.
        """
        ranges = []
        for track in self.upper:
            if (track.findtext('enabled') or 'TRUE').upper() == 'FALSE':
                continue
            for item in track.findall('clipitem'):
                start, end = _int(item, 'start'), _int(item, 'end')
                name = (item.findtext('name') or '') + (item.get('id') or '')
                if start < 0 or end <= start or 'caption' in name.lower() or end - start > .5 * self.frames:
                    continue
                if not include_popups and 'popup' in name.lower():
                    continue
                ranges.append((float(start / self.fps), float(end / self.fps)))
        return ranges


FACE_TARGET = (0.0, -.12)   # ideal face spot: centred, 38 % from the top (fraction of the frame from its centre)


def motion_values(clip, z, face, width, height):
    """Scale (percent) and centre for zoom z that moves the face toward the ideal spot.

    face: (dx, dy, source_w, source_h): face position relative to the source-frame centre in
    source pixels, plus the upright source size. The face is pulled toward FACE_TARGET only as far
    as the zoomed image still covers the whole frame, so no edge is ever revealed; at z = 1 the
    framing is exactly the original. Clips the editor already repositioned keep the face fixed instead.
    """
    b = clip.base_scale
    dx, dy = face[0], face[1]
    s = b * z
    if clip.base_center != (0.0, 0.0) or len(face) < 4:
        cx = clip.base_center[0] - (z - 1) * b * dx
        cy = clip.base_center[1] - (z - 1) * b * dy
    else:
        sw, sh = face[2], face[3]
        cx, cy = (_reframe(FACE_TARGET[0] * width - s * dx, s * sw, width),
                  _reframe(FACE_TARGET[1] * height - s * dy, s * sh, height))
    return s * 100, (cx / width * CENTER_X_UNIT, cy / height * CENTER_Y_UNIT)


def _reframe(wanted, scaled_size, canvas):
    room = max(0.0, (scaled_size - canvas) / 2)     # how far the image can move before an edge shows
    return min(room, max(-room, wanted))


def _set_motion(item, scale, center):
    effect = basic_motion(item)
    if effect is None:
        node = ET.Element('filter')
        effect = add(node, 'effect')
        add(effect, 'name', 'Basic Motion'); add(effect, 'effectid', 'basic')
        add(effect, 'effectcategory', 'motion'); add(effect, 'effecttype', 'motion'); add(effect, 'mediatype', 'video')
        children = list(item)
        anchor = next((i for i, c in enumerate(children) if c.tag in ('link', 'labels', 'comments')), len(children))
        item.insert(anchor, node)
    p = _param(effect, 'scale')
    if p is None:
        p = add(effect, 'parameter'); add(p, 'parameterid', 'scale'); add(p, 'name', 'Scale')
        add(p, 'valuemin', 0); add(p, 'valuemax', 1000)
    (p.find('value') if p.find('value') is not None else add(p, 'value')).text = f'{scale:.4f}'.rstrip('0').rstrip('.')
    p = _param(effect, 'center')
    if p is None:
        p = add(effect, 'parameter'); add(p, 'parameterid', 'center'); add(p, 'name', 'Center')
    value = p.find('value')
    if value is None: value = add(p, 'value')
    for tag, v in (('horiz', center[0]), ('vert', center[1])):
        node = value.find(tag)
        if node is None: node = add(value, tag)
        node.text = f'{v:.6f}'


def _runs(values):
    """[(offset, length, value)] for consecutive equal values."""
    runs, start = [], 0
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i] != values[start]:
            runs.append((start, i - start, values[start])); start = i
    return runs


def apply_curve(seq, curve, anchors, target, suffix='_ZOOM'):
    """anchors: per sequence frame, the face (dx, dy, source_w, source_h) the zoom goes into, or None
    (frame centre). Returns the number of zoomed clip pieces."""
    removed, zoomed = set(), 0
    children = list(seq.track)
    for clip in seq.clips:
        if not clip.zoomable:
            continue
        values = np.asarray(curve[clip.start:clip.end])
        if len(values) != clip.end - clip.start or np.all(values == 1.0):
            continue
        keys = [(float(z), tuple(anchors[f]) if anchors[f] is not None else None)
                for z, f in zip(values, range(clip.start, clip.end))]
        pieces = []
        for k, (offset, length, (z, anchor)) in enumerate(_runs(keys)):
            piece = deepcopy(clip.item)
            piece.set('id', f'{clip.id}-z{k + 1}')
            src_in = clip.source_in + round(Fraction(offset) * clip.rate / seq.fps)
            src_out = src_in + round(Fraction(length) * clip.rate / seq.fps)
            for tag, v in (('start', clip.start + offset), ('end', clip.start + offset + length),
                           ('in', src_in), ('out', src_out)):
                node = piece.find(tag)
                if node is None: node = add(piece, tag)
                node.text = str(v)
            for tag in ('pproTicksIn', 'pproTicksOut'):
                for node in piece.findall(tag): piece.remove(node)
            for link in piece.findall('link'):
                piece.remove(link)
            if z != 1.0:
                scale, center = motion_values(clip, z, anchor or (0.0, 0.0), seq.width, seq.height)
                _set_motion(piece, scale, center)
                zoomed += 1
            pieces.append(piece)
        position = children.index(clip.item)
        children[position:position + 1] = pieces
        removed.add(clip.id)
    for node in list(seq.track):
        seq.track.remove(node)
    seq.track.extend(children)
    # Audio stays whole; drop its links to video clips that were split.
    for item in seq.sequence.iter('clipitem'):
        for link in item.findall('link'):
            if link.findtext('linkclipref') in removed:
                item.remove(link)
    _single_file_definitions(seq.sequence)
    for uuid in seq.sequence.findall('uuid'):
        seq.sequence.remove(uuid)
    seq.sequence.set('id', (seq.sequence.get('id') or 'sequence') + '-zoom')
    name = seq.sequence.find('name')
    if name is None: name = add(seq.sequence, 'name')
    name.text = (name.text or 'Sequence') + suffix
    ET.indent(seq.root, space='  ')
    data = ET.tostring(seq.root, encoding='utf-8', xml_declaration=True)
    Path(target).write_bytes(data.replace(b'?>', b'?>\n<!DOCTYPE xmeml>', 1))
    return zoomed


def _single_file_definitions(sequence):
    """Only the first reference to a file carries its full definition (FCP 7 XML convention)."""
    seen = set()
    for file in sequence.iter('file'):
        fid = file.get('id')
        if not fid:
            continue
        if fid in seen and len(file):
            for child in list(file): file.remove(child)
        elif len(file):
            seen.add(fid)
