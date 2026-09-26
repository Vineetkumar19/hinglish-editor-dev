"""Observed source ranges for the user's Rapido failure, not an accuracy score.

These expectations were established from saved source transcripts/timestamps.
They verify keeping the complete phrases and their order, not subjective audio quality.
"""
import sys
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import av

output = Path(sys.argv[1]).resolve()
report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
expected = [
    ('e55e64b52d78c66f', 0, 9), None,
    ('ade78872999ea659', 0, 7), ('ade78872999ea659', 7, 13), ('ade78872999ea659', 13, 17),
    ('fade5c6678246a2c', 0, 13), ('79d833fea1300f95', 3, 20),
    ('a22ab7d833fa8b7b', 0, 4), ('a671e7333904d558', 0, 5),
    ('c339ed672a361be9', 0, 4), ('c339ed672a361be9', 4, 6), ('c339ed672a361be9', 6, 8),
    ('8bb88a51e9705667', 0, 11), ('a170ad1aa5112d4a', 0, 7), ('a170ad1aa5112d4a', 7, 14),
    ('d5c8f19613eb6ba1', 0, 6), ('0bcc940bd925fcbb', 0, 4), ('0bcc940bd925fcbb', 4, 8),
    ('71fabd0b9f5c63b7', 0, 12), ('71fabd0b9f5c63b7', 12, 17)]
failures = []
for row, target in zip(report['rows'], expected):
    s = row['selected']['span'] if row['selected'] else None
    actual = (s['media_id'], s['first'], s['last']) if s else None
    if actual != target: failures.append({'idea': row['idea'], 'expected': target, 'actual': actual})
assert len(report['rows']) == len(expected)
assert not failures, json.dumps(failures, indent=2)
assert 'quantity_unclear_in_transcript_listen_before_export' in report['rows'][2]['issues']
edit = json.loads((output / 'edit-decisions.json').read_text(encoding='utf-8'))
cuts = edit['cuts']
for i, a in enumerate(cuts):
    assert a['start_frame'] < a['end_frame']
    for b in cuts[i + 1:]:
        if a['media_id'] == b['media_id']:
            assert max(a['start_frame'], b['start_frame']) >= min(a['end_frame'], b['end_frame'])
for m in edit['media'].values(): assert Path(m['path']).is_file()
tree = ET.parse(output / 'EDITED_SEQUENCE.xml')
xml_clips = tree.findall('.//sequence/media/video/track/clipitem')
assert len(xml_clips) == len(cuts)
for xml, cut in zip(xml_clips, cuts):
    assert int(xml.findtext('in')) == cut['start_frame']
    assert int(xml.findtext('out')) == cut['end_frame']
frames = sum(c['end_frame'] - c['start_frame'] for c in cuts)
with av.open(str(output / 'preview.mp4')) as video:
    actual_frames = sum(1 for _ in video.decode(video=0))
assert frames == actual_frames
assert not report['errors'], report['errors']
print(json.dumps({'output': str(output), 'source_ranges': 'match inspected complete phrases',
                  'missing_unspoken_cue': 'Sun', 'price_transcription': 'flagged for listening',
                  'duration_seconds': frames/30, 'preview_frames': frames,
                  'xml_media_links': 'present', 'premiere_import': 'not tested in UI'}, indent=2))
