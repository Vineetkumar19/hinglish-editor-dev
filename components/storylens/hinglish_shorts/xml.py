"""One editable 1080x1920 sequence per short (FCP 7 XML for Premiere Pro and DaVinci Resolve).

Template look:  V1 dark blurred background (small file, scaled 200%)
                V2 your long video, only the chosen pieces, scaled into the frame (cuts are real edits)
                V3 title + glow frame + "watch full video" (transparent layer)
                V4 captions (transparent layer, when chosen)
                A1/A2 the long video's sound for the same pieces
Face look:      V1 the long video cropped to 9:16 around the face, V2 captions, A1/A2 sound."""
from fractions import Fraction
from pathlib import Path
import math
import xml.etree.ElementTree as ET

from hinglish_cut.xml_export import add, premiere_pathurl, rate, video_format_dimensions

from .render import FG_CY, H, W, fg_box


def _file(parent, file_id, path, fps, frames, width, height, channels=0, sample_rate=48000, seen=None):
    f = add(parent, 'file', id=file_id)
    if seen is not None and file_id in seen:
        return f
    if seen is not None:
        seen.add(file_id)
    add(f, 'name', Path(path).name)
    add(f, 'pathurl', premiere_pathurl(path))
    if Path(path).suffix.lower() in ('.png','.jpg','.jpeg'):
        add(f,'stillframe','TRUE')
    rate(f, fps)
    add(f, 'duration', frames)
    tc = add(f, 'timecode'); rate(tc, fps)
    add(tc, 'string', '00:00:00:00'); add(tc, 'frame', 0); add(tc, 'displayformat', 'NDF')
    media = add(f, 'media')
    video_format_dimensions(add(add(media, 'video'), 'samplecharacteristics'), width, height, fps)
    if channels:
        audio = add(media, 'audio')
        chars = add(audio, 'samplecharacteristics')
        add(chars, 'depth', 16); add(chars, 'samplerate', sample_rate)
        add(audio, 'channelcount', channels)
    return f


def _motion(item, scale, horiz=0.0, vert=0.0):
    node = add(item, 'filter')
    effect = add(node, 'effect')
    add(effect, 'name', 'Basic Motion'); add(effect, 'effectid', 'basic')
    add(effect, 'effectcategory', 'motion'); add(effect, 'effecttype', 'motion'); add(effect, 'mediatype', 'video')
    p = add(effect, 'parameter'); add(p, 'parameterid', 'scale'); add(p, 'name', 'Scale')
    add(p, 'valuemin', 0); add(p, 'valuemax', 1000); add(p, 'value', f'{scale:.4f}'.rstrip('0').rstrip('.'))
    p = add(effect, 'parameter'); add(p, 'parameterid', 'center'); add(p, 'name', 'Center')
    value = add(p, 'value')
    add(value, 'horiz', f'{horiz:.6f}'); add(value, 'vert', f'{vert:.6f}')


def _layer_track(video, path, frames, fps, prefix, scale=None, width=W, height=H):
    track = add(video, 'track')
    item = add(track, 'clipitem', id=f'{prefix}-1')
    add(item, 'name', Path(path).name)
    add(item, 'enabled', 'TRUE')
    add(item, 'duration', frames)
    rate(item, fps)
    for tag, value in (('start', 0), ('end', frames), ('in', 0), ('out', frames)):
        add(item, tag, value)
    if scale is not None:
        _motion(item, scale)
    _file(item, f'{prefix}-file', path, fps, frames, width, height)
    add(track, 'enabled', 'TRUE'); add(track, 'locked', 'FALSE')


def export_short_xml(target, name, video, plan, look, layers, face_x=.5):
    """plan: [(first frame, frame count)] at the short's frame rate (video.short_fps). The sequence runs at the
    source's own rate (layer files too), so every clip has one clear timebase in Premiere and Resolve."""
    fps = video.fps
    ratio = int(video.fps / video.short_fps)
    plan = [(first * ratio, count * ratio) for first, count in plan]
    total = sum(c for _, c in plan)
    source_frames = math.floor(video.duration * float(video.fps) + 1e-6)
    root = ET.Element('xmeml', version='5')
    seq = add(root, 'sequence', id='sequence-1')
    add(seq, 'name', name)
    add(seq, 'duration', total)
    rate(seq, fps)
    tc = add(seq, 'timecode'); rate(tc, fps)
    add(tc, 'string', '00:00:00:00'); add(tc, 'frame', 0); add(tc, 'displayformat', 'NDF')
    media = add(seq, 'media')
    video_node = add(media, 'video')
    video_format_dimensions(add(add(video_node, 'format'), 'samplecharacteristics'), W, H, fps)
    if look == 'template' and layers.get('background'):
        _layer_track(video_node, layers['background'], total, fps, 'background', scale=200, width=W // 2, height=H // 2)
    # the long video's pieces
    if look == 'template':
        x, y, w, h = fg_box(video.width, video.height)
        scale, horiz, vert = w / video.width * 100, 0.0, (y + h / 2 - H / 2) / H
    else:
        scale = H / video.height * 100
        scaled_w = video.width * H / video.height
        room = max(0.0, (scaled_w - W) / 2)
        horiz = min(room, max(-room, -(face_x - .5) * scaled_w)) / W
        vert = 0.0
    vtrack = add(video_node, 'track')
    audio_node = add(media, 'audio')
    add(audio_node, 'numOutputChannels', 2)
    chars = add(add(audio_node, 'format'), 'samplecharacteristics')
    add(chars, 'depth', 16); add(chars, 'samplerate', 48000)
    channels = max(1, min(2, video.channels))
    atracks = [add(audio_node, 'track') for _ in range(channels)]
    seen, position = set(), 0
    for n, (first, count) in enumerate(plan, 1):
        ids = [f'v-{n}'] + [f'a-{n}-{ch + 1}' for ch in range(channels)]
        for kind, channel, parent, clip_id in [('video', 0, vtrack, ids[0])] + \
                [('audio', ch + 1, atracks[ch], ids[ch + 1]) for ch in range(channels)]:
            item = add(parent, 'clipitem', id=clip_id)
            add(item, 'name', f'{Path(video.path).name} | short piece {n}')
            add(item, 'enabled', 'TRUE')
            add(item, 'duration', math.floor(video.duration * float(fps) + 1e-6))
            rate(item, fps)
            for tag, value in (('start', position), ('end', position + count), ('in', first), ('out', first + count)):
                add(item, tag, value)
            if kind == 'video':
                _motion(item, scale, horiz, vert)
            _file(item, 'source-file', video.path, video.fps, source_frames, video.width, video.height,
                  channels, video.sample_rate, seen)
            if kind == 'audio':
                src = add(item, 'sourcetrack'); add(src, 'mediatype', 'audio'); add(src, 'trackindex', channel)
            for li, lid in enumerate(ids):
                link = add(item, 'link'); add(link, 'linkclipref', lid)
                add(link, 'mediatype', 'video' if li == 0 else 'audio')
                add(link, 'trackindex', 1 if li == 0 else li)
                add(link, 'clipindex', n)
                if li:
                    add(link, 'groupindex', 1)
        position += count
    add(vtrack, 'enabled', 'TRUE'); add(vtrack, 'locked', 'FALSE')
    for key in ('overlay', 'captions'):
        if layers.get(key):
            _layer_track(video_node, layers[key], total, fps, key)
    ET.indent(root, space='  ')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    Path(target).write_bytes(data.replace(b'?>', b'?>\n<!DOCTYPE xmeml>', 1))
    return Path(target)
