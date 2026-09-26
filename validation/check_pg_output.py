"""Check the real batch that previously crashed on shared source frames."""
from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse
import wave
import av

out = Path(sys.argv[1]).resolve()
report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
decisions = json.loads((out / 'edit-decisions.json').read_text(encoding='utf-8'))
project = json.loads((out / 'project.json').read_text(encoding='utf-8'))
xml = ET.parse(out / 'EDITED_SEQUENCE.xml')
clips = xml.findall('.//sequence/media/video/track/clipitem')
cuts = decisions['cuts']
assert len(clips) == len(cuts)
used, cursor = {}, 0
for clip, cut in zip(clips, cuts):
    mid, a, b = cut['media_id'], cut['start_frame'], cut['end_frame']
    assert 0 <= a < b <= int(decisions['media'][mid]['duration'] * 30 + 1e-6)
    assert not any(max(a, x) < min(b, y) for x, y in used.get(mid, []))
    used.setdefault(mid, []).append((a, b))
    assert int(clip.findtext('in')) == a and int(clip.findtext('out')) == b
    assert int(clip.findtext('start')) == cursor
    cursor += b - a
    assert int(clip.findtext('end')) == cursor
assert cursor == int(xml.findtext('.//sequence/duration'))
for node in xml.findall('.//pathurl'):
    assert Path(unquote(urlparse(node.text).path).lstrip('/')).is_file()
with av.open(str(out / 'preview.mp4')) as preview:
    assert sum(1 for _ in preview.decode(video=0)) == cursor
with wave.open(str(out / 'full-timeline.wav')) as wav:
    assert abs(wav.getnframes() / wav.getframerate() - cursor / 30) < .001
assert not report['errors']
assert len(project['transcripts']) == 11
rows = report['rows']
for label in ('Washing machine? Nahi', 'Fridge? Nahi'):
    row = next(r for r in rows if r['idea'] == label)
    assert row['selected'] and 'nahin' in row['selected']['span']['text']
assert 'nahi rehna chahta' in next(r['idea'] for r in rows if r['idea'].startswith('“Main'))
missing = [r['idea'] for r in rows if not r['selected']]
uncertain = [r['idea'] for r in rows if r.get('selection_status') == 'unverified_context_passage']
assert not missing
assert len(uncertain) == 3
assert '3 included passages need listening review' in (out / 'report.html').read_text(encoding='utf-8')
result = {'frames': cursor, 'duration_seconds': cursor / 30, 'selected_sections': len(rows) - len(missing),
          'missing_sections': missing, 'uncertain_passages': uncertain, 'source_overlap': False, 'all_media_exist': True,
          'decoded_preview_matches_xml': True, 'premiere_import_checked': False}
(out / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
