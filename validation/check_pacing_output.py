"""Compare the user's rushed edit with the regenerated natural-paced export."""
import json
from pathlib import Path
import sys

old, new = map(Path, sys.argv[1:3])
before = json.loads((old / 'report.json').read_text(encoding='utf-8'))
after = json.loads((new / 'report.json').read_text(encoding='utf-8'))
decisions = json.loads((new / 'edit-decisions.json').read_text(encoding='utf-8'))
assert after['pacing'] == 'natural'
assert not after['errors']
assert after['duration_seconds'] > before['duration_seconds']
assert [r['selected_id'] for r in after['rows']] == [r['selected_id'] for r in before['rows']]
joins = []
for previous, current in zip(after['rows'], after['rows'][1:]):
    if not previous['selected'] or not current['selected']: continue
    left = [c for c in decisions['cuts'] if c['line_index'] == previous['index']][-1]
    right = [c for c in decisions['cuts'] if c['line_index'] == current['index']][0]
    # Report padding around the original recognized spans; restored endings can
    # contain speech and are excluded from the silence measurement below.
    if previous.get('restored_ending'): continue
    a, b = previous['selected']['span'], current['selected']['span']
    gap = left['end_frame'] / 30 - a['end'] + b['start'] - right['start_frame'] / 30
    joins.append({'after_sentence': previous['index'] + 1, 'retained_source_pause_seconds': round(gap, 3),
                  'paragraph_break': previous['paragraph_index'] != current['paragraph_index']})
for row in after['rows']:
    if not row['selected']: continue
    s = row['selected']['span']
    cuts = [c for c in decisions['cuts'] if c['line_index'] == row['index']]
    assert cuts[0]['start_frame'] / 30 <= s['start'] + 1 / 30
    assert cuts[-1]['end_frame'] / 30 >= s['end'] - 1 / 30
result = {'previous_seconds': before['duration_seconds'], 'new_seconds': after['duration_seconds'],
          'selected_takes_unchanged': True, 'pacing': after['pacing'], 'joins': joins,
          'restored_endings': [r['restored_ending'] for r in after['rows'] if r.get('restored_ending')]}
(new / 'pacing-validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
