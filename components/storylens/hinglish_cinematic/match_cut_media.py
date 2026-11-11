"""Verified source-sized extracts, joined previews and editable sequence handoff."""

import math
from pathlib import Path
from threading import Event
import tempfile
from uuid import uuid4
import xml.etree.ElementTree as ET

import av

from hinglish_cut.compute_policy import ffmpeg_h264
from hinglish_cut.model import Cut, Media
from hinglish_cut.xml_export import export_xml
from .match_cut_analysis import check_stop
from .render import run_ffmpeg


FPS = 30


def _verify(path, expected, stop):
    with av.open(str(path)) as media:
        stream = media.streams.video[0]
        stream.codec_context.thread_count = 2
        frames = 0
        for _ in media.decode(stream):
            check_stop(stop)
            frames += 1
        if frames != expected:
            raise ValueError(f'Check the source range and retry. Export produced {frames} frames, expected {expected}.')
        return {'frames': frames, 'seconds': frames / FPS, 'width': stream.width, 'height': stream.height,
                'audio': bool(media.streams.audio),
                'channels': media.streams.audio[0].codec_context.channels if media.streams.audio else 0,
                'sample_rate': media.streams.audio[0].codec_context.sample_rate if media.streams.audio else 0}


def _extract(row, dest, device, stop):
    frames = math.floor(row['duration'] * FPS + 1e-6)
    filters = "fps=30:start_time=0:eof_action=pass,scale='max(2,trunc(iw*sar/2)*2)':'max(2,trunc(ih/2)*2)',setsar=1"
    run_ffmpeg(['-ss', row['seek'], '-i', row['source'], '-map', '0:v:0', '-map', '0:a:0?',
                '-vf', filters, '-t', frames / FPS, '-frames:v', frames, *ffmpeg_h264(device, 19),
                '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', dest],
               dest.parent, stop)
    return _verify(dest, frames, stop)


def extract_marked(source, first, after, dest, device, stop):
    frames = after - first
    run_ffmpeg(['-i', source, '-map', '0:v:0', '-map', '0:a:0?',
                '-vf', f'trim=start_frame={first}:end_frame={after},setpts=PTS-STARTPTS',
                '-af', f'atrim=start={first / FPS}:end={after / FPS},asetpts=PTS-STARTPTS',
                '-frames:v', frames, *ffmpeg_h264(device, 19), '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', dest],
               dest.parent, stop)
    return _verify(dest, frames, stop)


def _join(parts, dest, work, device, stop):
    # Use the first cut's display aspect and fit mixed footage inside it.
    width, height = parts[0][1]['width'], parts[0][1]['height']
    scale = min(1, 1920 / max(width, height))
    width, height = max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)
    inputs, filters, pads = [], [], []
    for i, (path, info) in enumerate(parts):
        inputs.extend(('-i', path))
        filters.append(f'[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,'
                       f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[v{i}]')
        audio = f'[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,apad' if info['audio'] else 'anullsrc=r=48000:cl=stereo'
        filters.append(f'{audio},atrim=end_sample={info["frames"] * 1600},asetpts=PTS-STARTPTS[a{i}]')
        pads.append(f'[v{i}][a{i}]')
    filters.append(''.join(pads) + f'concat=n={len(parts)}:v=1:a=1[v][a]')
    frames = sum(info['frames'] for _, info in parts)
    run_ffmpeg([*inputs, '-filter_complex_threads', '1', '-filter_complex', ';'.join(filters),
                '-map', '[v]', '-map', '[a]', '-r', FPS, '-frames:v', frames,
                *ffmpeg_h264(device, 21), '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                '-movflags', '+faststart', dest], work, stop)
    return _verify(dest, frames, stop)


def supporting_frames(parts, folder, stop):
    result = []
    for i, ((left, _), (right, _)) in enumerate(zip(parts, parts[1:]), 1):
        check_stop(stop)
        paths = []
        for side, video in (('exit', left), ('entry', right)):
            with av.open(str(video)) as media:
                stream = media.streams.video[0]
                stream.codec_context.thread_count = 2
                if side == 'exit':
                    media.seek(max(0, stream.duration - round(1 / stream.time_base)), stream=stream)
                for frame in media.decode(stream):
                    check_stop(stop)
                    if side == 'entry':
                        break
                image = frame.to_image()
                image.thumbnail((480, 360))
                path = folder / f'join-{i:02d}-{side}.jpg'
                image.save(path, quality=87)
                paths.append(path)
        result.append(paths)
    return result


def insert_group(folder, clips, artifacts, preview):
    """Write an editable timeline referencing the verified per-shot media."""
    from hinglish_app.timeline_cut import validate

    parent = (folder / artifacts[preview]['path']).resolve().parent
    if not parent.is_relative_to(folder.resolve()):
        raise ValueError('The selected match preview is outside the export folder.')
    channels = {artifacts[row['asset']]['channels'] for row in clips}
    normalize_audio = len(channels) > 1
    if normalize_audio:
        timeline_media = parent / 'Timeline Media'
        timeline_media.mkdir(exist_ok=True)
    media, cuts = {}, []
    for order, row in enumerate(clips, 1):
        key = row['asset']
        part = artifacts[key]
        path = (folder / part['path']).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():
            raise ValueError('One of the verified match clips is missing. Scan again before inserting.')
        if normalize_audio:
            path = _linked_audio(path, part, timeline_media, Event())
        sample_rate = part.get('sample_rate')
        if sample_rate is None and part['channels']:
            with av.open(str(path)) as container:
                sample_rate = container.streams.audio[0].codec_context.sample_rate
        media[key] = Media(key, str(path), part['frames'] / FPS, str(FPS), part['width'], part['height'],
                           2 if normalize_audio else part['channels'], 48000 if normalize_audio else sample_rate or 48000)
        cuts.append(Cut(key, 0, part['frames'], order - 1))
    dest = parent / 'Match Cut.xml'
    temp = dest.with_name('.match-cut-' + uuid4().hex + '.xml')
    try:
        export_xml(temp, cuts, media)
        document = ET.parse(temp)
        document.find('./sequence/name').text = 'Match Cut ' + parent.name
        video = document.findall('./sequence/media/video/track/clipitem')
        if [int(row.findtext('end')) - int(row.findtext('start')) for row in video] != [cut.duration for cut in cuts]:
            raise RuntimeError('The exported timeline did not preserve the selected cut lengths.')
        document.write(temp, encoding='utf-8', xml_declaration=True)
        validate(temp)
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)
    return dest


def _linked_audio(source, part, folder, stop):
    dest = folder / (part['sha256'][:16] + '.mp4')
    if dest.is_file():
        info = _verify(dest, part['frames'], stop)
        if info['channels'] == 2 and info['sample_rate'] == 48000:
            return dest
    with tempfile.TemporaryDirectory(prefix='.match-cut-', dir=folder) as temp:
        work = Path(temp)
        staged = work / dest.name
        audio = ['-map', '0:a:0'] if part['audio'] else [
            '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-map', '1:a:0']
        run_ffmpeg(['-i', source, *audio, '-map', '0:v:0', '-c:v', 'copy',
                    '-af', 'apad', '-ac', '2', '-ar', '48000', '-c:a', 'aac', '-b:a', '192k',
                    '-t', part['frames'] / FPS, '-movflags', '+faststart', staged], work, stop)
        _verify(staged, part['frames'], stop)
        staged.replace(dest)
    return dest


