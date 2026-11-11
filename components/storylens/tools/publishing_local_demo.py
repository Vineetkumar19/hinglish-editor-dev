"""Create a local draft-only demonstration using an existing reviewed Shorts export."""
import html
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hinglish_publish.service import Publisher
from hinglish_publish.store import IST


def main():
    root = Path(__file__).resolve().parents[1]
    result = root / 'output' / 'validation' / 'publisher-demo'
    result.mkdir(parents=True, exist_ok=True)
    project_file = root / 'output/shorts/20260929-073445-2d4313/001-as/shorts-project.json'
    project = json.loads(project_file.read_text(encoding='utf-8'))
    publisher = Publisher(result)
    publisher.init_folders()
    long = publisher.folders()['long-youtube'] / 'DEMO - 7000 RPM Monologue.mp4'
    short = publisher.folders()['shorts-both'] / 'DEMO - Ek Khaas Ehsaas.mp4'
    shutil.copy2(project['video']['path'], long)
    shutil.copy2(project_file.parent / project['shorts'][0]['mp4'], short)
    words = ' '.join(word[0] for word in project['words'])
    long.with_suffix('.txt').write_text(words, encoding='utf-8')
    # Review the model's draft for source accuracy before demonstrating the queue.
    reviewed = {
        'title': '7000 RPM: When Everything Blurs | A Motorsport Monologue',
        'description': 'A motorsport monologue about reaching 7,000 RPM, when everything blurs and '
                       'the machine seems to lose its weight. It ends with a question about who you are.',
        'instagram_caption': 'At 7,000 RPM, everything blurs and one question remains: who are you? '
                             '#7000RPM #Motorsport #Monologue',
        'tags': ['7000 RPM', 'motorsport', 'monologue'],
    }
    clipped = {
        'title': 'One Extraordinary Feeling, Then One Question | Motorsport Monologue',
        'description': 'An extraordinary feeling gives way to the question that matters. '
                       'This Short comes from the closing section of the original motorsport monologue.',
        'instagram_caption': 'One extraordinary feeling. Then the question that matters. '
                             '#Motorsport #Monologue #Shorts',
        'tags': ['motorsport', 'monologue', 'Shorts'],
    }
    for video, meta in ((long, reviewed), (short, clipped)):
        video.with_suffix('.publish.json').write_text(json.dumps({'metadata_language': 'en', 'metadata': meta}, ensure_ascii=False, indent=2),
                                                      encoding='utf-8')
        os.utime(video, (time.time() - 20, time.time() - 20))
    a = publisher.prepare({'name': 'Upload DEMO - 7000 RPM Monologue on YouTube', 'make_shorts': False})
    b = publisher.prepare({'name': 'DEMO - Ek Khaas Ehsaas'})
    again = publisher.prepare({'name': 'DEMO - Ek Khaas Ehsaas'})
    assert b['job_ids'] == again['job_ids']
    for job in publisher.store.list():
        publisher.edit({'id': job['id'], 'metadata': reviewed if job['kind'] == 'long' else clipped})
    jobs = publisher.store.list()
    assert len(jobs) == 3 and all(job['status'] == 'draft' for job in jobs)
    shorts = [job for job in jobs if job['kind'] == 'short']
    assert shorts[0]['due'] == shorts[1]['due']
    assert datetime.fromtimestamp(shorts[0]['due'], IST).strftime('%H:%M') == '19:00'
    receipt = {'source': project['video']['path'], 'clip_origin': str(project_file),
               'note': 'Existing Short reused. Metadata reviewed. Draft-only; no real account or publishing API called.',
               'jobs': jobs, 'checks': ['MP4 inspected', 'local model draft generated separately',
                   'reviewed metadata accepted', 'same clip/date for both platforms', '19:00 IST',
                   're-preparation produced no duplicate', 'all items unapproved drafts']}
    (result / 'draft-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = ''.join('<tr><td>' + html.escape(job['metadata']['title']) + '</td><td>' + job['platform'] +
                   '</td><td>' + datetime.fromtimestamp(job['due'], IST).strftime('%d %b %Y · %I:%M %p IST') +
                   '</td><td>Draft — not authorized</td></tr>' for job in jobs)
    report = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Publishing Studio — local demo</title><style>body{background:#101317;color:#f4f1ea;font:16px/1.5 system-ui;margin:0}
main{max-width:1050px;margin:auto;padding:40px 24px}h1{font-size:38px;line-height:1.1}h2{margin-top:34px;color:#ffad65}
.note{padding:18px;background:#252b34;border:1px solid #454d58;border-radius:12px}video{max-width:100%;max-height:450px;background:#000}
table{width:100%;border-collapse:collapse}td,th{padding:13px;text-align:left;border-bottom:1px solid #30353d}
.players{display:grid;grid-template-columns:1.5fr 1fr;gap:24px}.metadata{background:#171a1f;padding:20px;border-radius:12px}
@media(max-width:700px){.players{grid-template-columns:1fr}.table{overflow:auto}}</style><main>
<p style="color:#ffad65">HINGLISH EDITOR · PUBLISHING STUDIO</p><h1>A real video, a local draft, a daily queue.</h1>
<p class="note">This is a local preparation test. No YouTube or Instagram account was connected and nothing was uploaded.
The Short below was reused from the existing Long to Shorts output; it was not generated again during this demo.</p>
<div class="players"><section><h2>Source video</h2><video controls src="publishing/long-youtube/DEMO%20-%207000%20RPM%20Monologue.mp4"></video></section>
<section><h2>Existing generated Short</h2><video controls src="publishing/shorts-both/DEMO%20-%20Ek%20Khaas%20Ehsaas.mp4"></video></section></div>
<h2>Proposed queue</h2><div class="table"><table><tr><th>Title</th><th>Platform</th><th>Target</th><th>Status</th></tr>''' + rows + '''</table></div>
<h2>Reviewed metadata</h2><div class="metadata"><b>''' + html.escape(reviewed['title']) + '''</b><p>''' + html.escape(reviewed['description']) + '''</p>
<p>''' + html.escape(clipped['instagram_caption']) + '''</p></div><h2>Checks that passed</h2><ul>''' + ''.join(
        '<li>' + html.escape(check) + '</li>' for check in receipt['checks']) + '''</ul>
<p>The first model draft is saved separately as generated-metadata.json. Titles and descriptions need factual/editorial review before publishing.
Eight clips is a target for suitable long sources; this short demonstration has one existing clip.</p></main></html>'''
    (result / 'report.html').write_text(report, encoding='utf-8')
    print('Local demo passed: 3 drafts, paired 19:00 IST Short dates, no duplicate or real upload.')
    print(result / 'report.html')


if __name__ == '__main__':
    main()
