"""Add the music bed and every sound effect to the sequence as their own editable audio tracks."""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
from defusedxml import ElementTree as SafeET

from hinglish_cut.xml_export import add, premiere_pathurl, rate

SAMPLE_RATE = 48000


def _fps_text(fps):
    return f'{fps.numerator}/{fps.denominator}' if fps.denominator != 1 else str(fps.numerator)


def _audio_clip(track, clip_id, file_id, path, start, frames, channel, fps_text, full_definition, name):
    item = add(track, 'clipitem', id=clip_id)
    add(item, 'name', name)
    add(item, 'enabled', 'TRUE')
    add(item, 'duration', frames)
    rate(item, fps_text)
    for tag, value in (('start', start), ('end', start + frames), ('in', 0), ('out', frames)):
        add(item, tag, value)
    f = add(item, 'file', id=file_id)
    if full_definition:
        add(f, 'name', Path(path).name)
        add(f, 'pathurl', premiere_pathurl(path))
        rate(f, fps_text)
        add(f, 'duration', frames)
        audio = add(add(f, 'media'), 'audio')
        characteristics = add(audio, 'samplecharacteristics')
        add(characteristics, 'depth', 16); add(characteristics, 'samplerate', SAMPLE_RATE)
        add(audio, 'channelcount', 2)
    source = add(item, 'sourcetrack'); add(source, 'mediatype', 'audio'); add(source, 'trackindex', channel)
    return item


def lanes(effects):
    """Put overlapping effects on separate tracks (fewest tracks)."""
    ends, assigned = [], []
    for e in sorted(effects, key=lambda e: e['start']):
        lane = next((i for i, end in enumerate(ends) if end <= e['start']), None)
        if lane is None:
            ends.append(0.0); lane = len(ends) - 1
        ends[lane] = e['start'] + e['length']
        assigned.append((lane, e))
    return assigned, len(ends)


def export_sound_xml(xml_path, fps, stems, target, suffix='_SOUND'):
    tree = SafeET.parse(xml_path)
    root = tree.getroot()
    sequence = root if root.tag == 'sequence' else root.find('.//sequence')
    if sequence is None:
        raise ValueError('Sound timeline has no sequence')
    media = sequence.find('media')
    if media is None:
        media = add(sequence, 'media')
    audio = media.find('audio')
    if audio is None:
        audio = add(media, 'audio')
    fps_text = _fps_text(fps)
    to_frames = lambda seconds: int(math.floor(seconds * float(fps) + 1e-6))
    clip_no = 0

    def stereo(path, start_s, length_s, name, left, right, file_id):
        nonlocal clip_no
        start, frames = to_frames(start_s), max(1, math.ceil(length_s * float(fps) - 1e-6))
        clip_no += 1
        _audio_clip(left, f'sound-{clip_no}-L', file_id, path, start, frames, 1, fps_text, True, name)
        _audio_clip(right, f'sound-{clip_no}-R', file_id, path, start, frames, 2, fps_text, False, name)

    if stems.get('voice'):
        # Do not also play the source mix and its original background music.
        for track in list(audio.findall('track')):
            audio.remove(track)
        for clip in media.findall('./video/track/clipitem'):
            for link in list(clip.findall('link')):
                if link.findtext('mediatype')=='audio':clip.remove(link)
        left,right=add(audio,'track'),add(audio,'track')
        stereo(stems['voice'],0.,_seconds(stems['voice']),stems.get('voice_label','Dialogue'),left,right,'sound-voice')
    if stems.get('music'):
        left, right = add(audio, 'track'), add(audio, 'track')
        stereo(stems['music'], 0.0, _seconds(stems['music']), 'Background music', left, right, 'sound-music')
    # XML clip starts are frame-quantized. Carry the fractional start in the WAV
    # itself so a transient stays aligned with the preview to within one sample.
    aligned = []
    for effect in stems.get('effects', []):
        aligned.append(_frame_aligned(effect, fps))
    assigned, count = lanes(aligned)
    tracks = [(add(audio, 'track'), add(audio, 'track')) for _ in range(count)]
    for n, (lane, e) in enumerate(assigned, 1):
        label=f"SFX {e['category']}" + (f" · {e['role']} · {e.get('group_id','')}" if e.get('role') else '')
        stereo(e['path'], e['start'], e['length'], label, *tracks[lane], f'sound-sfx-{n}')
    for uuid in sequence.findall('uuid'):
        sequence.remove(uuid)
    sequence.set('id', (sequence.get('id') or 'sequence') + '-sound')
    name = sequence.find('name')
    if name is None: name = add(sequence, 'name')
    name.text = (name.text or 'Sequence') + suffix
    ET.indent(root, space='  ')
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    Path(target).write_bytes(data.replace(b'?>', b'?>\n<!DOCTYPE xmeml>', 1))
    return Path(target)


def _frame_aligned(effect, fps):
    import wave
    row = dict(effect)
    start_frame = math.floor(float(row['start']) * float(fps) + 1e-6)
    start_s = start_frame / float(fps)
    with wave.open(str(row['path']), 'rb') as source:
        params = source.getparams()
        pcm = source.readframes(params.nframes)
    pad = max(0, round((float(row['start']) - start_s) * params.framerate))
    length_frames = max(1, math.ceil((params.nframes + pad) / params.framerate * float(fps) - 1e-6))
    total_samples = max(params.nframes + pad, round(length_frames / float(fps) * params.framerate))
    tail = total_samples - params.nframes - pad
    if pad or tail:
        path = Path(row['path'])
        path = path.with_name(path.stem + '-frame-aligned.wav')
        stride = params.sampwidth * params.nchannels
        silence = b'\x80' if params.sampwidth == 1 else b'\x00'
        with wave.open(str(path), 'wb') as out:
            out.setparams(params)
            out.writeframes(silence * (pad * stride) + pcm + silence * (tail * stride))
        row['path'] = str(path)
    row.update(start=start_s, length=length_frames / float(fps))
    return row


def _seconds(path):
    import wave
    with wave.open(str(path), 'rb') as w:
        return w.getnframes() / w.getframerate()
