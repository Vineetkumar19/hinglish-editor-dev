"""Select actual applied local-model headings for one-frame-at-a-time AE review."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
repair=root/'output/template-text-repair'
read=lambda p:json.loads(p.read_text('utf-8-sig'))
native=read(repair/'scene-heading-native-progress.json')
if native.get('phase') not in ('complete','needs_review'):
    raise SystemExit('Native application is not finished; do not render stale headings.')
seed=read(repair/'scene-heading-native-seed.json')
if native.get('result',{}).get('job_id')!=seed['plan']['job_id']:
    raise SystemExit('The native result belongs to a different saved plan.')
checks=[]
for i,h in enumerate(native['audit']['headings']):
    if not h['enabled'] or not h['runs']:continue
    run=max(h['runs'],key=lambda r:r['end']-r['start'])
    checks.append({'template':h['template_layer_id'],'time':(run['start']+run['end'])/2,
                   'text':h['expected'],'path':h['text_id'],'file':f'checked-heading-{i:03d}.png'})
(repair/'scene-heading-review-frames.json').write_text(json.dumps(checks,indent=2),'utf-8')
print(len(checks),'applied headings prepared for actual frame review.')
