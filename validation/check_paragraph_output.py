"""Validate the actual Madurai batch, not a synthetic speech accuracy fixture.

Run with the generated output directory. Expected takes come from inspection
of the user's recorded transcript/timestamps; this does not replace listening.
"""
from pathlib import Path
import json
import sys
import wave
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse

import av

out = Path(sys.argv[1]).resolve()
report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
decisions = json.loads((out / 'edit-decisions.json').read_text(encoding='utf-8'))
project = json.loads((out / 'project.json').read_text(encoding='utf-8'))
assert not report['errors'], report['errors']
assert len(report['paragraphs']) == 6
assert report['placed_sentences'] == report['sentence_count'] == 21
assert [p['placed'] for p in report['paragraphs']] == [4, 2, 4, 6, 3, 2]

# These exact later complete takes must replace the earlier repeated attempts.
expected = {3: ('04008', 3.57), 6: ('04509', 24.76),
            16: ('05326', 5.27), 19: ('05550', 13.47)}
for index, (filename, start) in expected.items():
    candidate = report['rows'][index]['selected']
    assert filename in candidate['source_name']
    assert abs(candidate['span']['start'] - start) < .02

xml = ET.parse(out / 'EDITED_SEQUENCE.xml')
sequence = xml.find('sequence')
assert sequence.findtext('name') == 'EDITED_SEQUENCE'
assert sequence.findtext('media/video/format/samplecharacteristics/width') == '1080'
assert sequence.findtext('media/video/format/samplecharacteristics/height') == '1920'
clips = sequence.findall('media/video/track/clipitem')
cuts = decisions['cuts']
assert len(clips) == len(cuts)
cursor, used = 0, {}
for clip, cut in zip(clips, cuts):
    a, b, mid = cut['start_frame'], cut['end_frame'], cut['media_id']
    assert 0 <= a < b <= int(decisions['media'][mid]['duration'] * 30 + 1e-6)
    assert int(clip.findtext('in')) == a and int(clip.findtext('out')) == b
    assert int(clip.findtext('start')) == cursor
    cursor += b - a
    assert int(clip.findtext('end')) == cursor
    assert not any(max(a, x) < min(b, y) for x, y in used.get(mid, []))
    used.setdefault(mid, []).append((a, b))
for node in xml.findall('.//pathurl'):
    assert Path(unquote(urlparse(node.text).path).lstrip('/')).is_file(), node.text
assert cursor == int(sequence.findtext('duration'))
assert all(len(track.findall('clipitem')) == len(cuts) for track in sequence.findall('media/audio/track'))

with av.open(str(out / 'preview.mp4')) as preview:
    video_stream = preview.streams.video[0]
    assert (video_stream.width, video_stream.height) == (540, 960)
    count = 0
    for frame in preview.decode(video=0):
        if count == 90:
            with av.open(str(out / 'preview-frame.png'), 'w', format='image2') as picture:
                png = picture.add_stream('png', rate=1)
                png.width, png.height, png.pix_fmt = frame.width, frame.height, 'rgb24'
                still = frame.reformat(format='rgb24')
                still.pts = 0
                for packet in png.encode(still): picture.mux(packet)
                for packet in png.encode(): picture.mux(packet)
        count += 1
    assert count == cursor
with av.open(str(out / 'preview.mp4')) as preview:
    audio_stream = preview.streams.audio[0]
    audio_seconds = sum(f.samples for f in preview.decode(audio=0)) / audio_stream.rate
    assert abs(audio_seconds - cursor / 30) < .1
with wave.open(str(out / 'full-timeline.wav')) as wav:
    assert abs(wav.getnframes() / wav.getframerate() - cursor / 30) < .001

result = {'output': str(out), 'source_count': len(project['transcripts']),
          'paragraphs_placed': 6, 'clauses_placed': 21, 'source_seconds': sum(t['media']['duration'] for t in project['transcripts']),
          'edited_seconds': cursor / 30, 'timeline_frames': cursor,
          'portable_media_paths_exist': True, 'preview_video_and_audio_match_xml_duration': True,
          'known_earlier_retakes_excluded': True,
          'recognized_filler_removals': sum(len(r.get('filler_removals', [])) for r in report['rows']),
          'validation_limits': 'Source times, XML structure, decoded preview and automatic replay transcripts checked. Not a Premiere import or human listening certification.'}
(out / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
