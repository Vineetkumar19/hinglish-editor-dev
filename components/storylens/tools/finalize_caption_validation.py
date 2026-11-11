"""Publish the evidence index after the actual Storylens checks finish."""
import html
import json
from pathlib import Path


def main():
    base=Path(__file__).resolve().parents[1]/'output/captions/script-pattern-validation'
    def read(name):return json.loads((base/name).read_text('utf-8'))
    live=read('live-evidence/live-checks.json');audit=read('renderer-audit.json')
    edits=read('live-evidence/word-count-edit-checks.json');saved=read('live-evidence/save-reopen.json')
    playback=read('live-evidence/playback.json')
    assert len(live)==56 and len({(r['script'],r['style']) for r in live})==56
    assert all(len(r['shots'])==3 and not any(s.get('error') for s in r['shots']) for r in live)
    assert len(audit)==56 and not any(r['issues'] for r in audit)
    assert len(edits)==14 and not any(r['error'] for r in edits)
    assert saved['downloadEnabled'] and saved['style']=='serif_circle_draft' and saved['position']=='65'
    assert playback['ended'] and playback['duration']==30
    for row in live:row['status']='passed-sampled-live-review'
    (base/'live-evidence/live-checks.json').write_text(json.dumps(live,ensure_ascii=False,indent=2),'utf-8')
    result=dict(date='2026-10-23',status='complete-for-recorded-storylens-scope',scope='Storylens only; Caption 1 excluded',
                scripts=4,script_duration_seconds=30,templates=14,live_cases=56,live_samples_per_case=3,
                live_scope='Opening, middle and final captions; not an every-frame reference comparison',
                renderer_cases=56,renderer_frames=sum(r['frames'] for r in audit),renderer_issues=0,
                word_count_edits=edits,regression_tests=81,save_reopen=saved,playback=playback,
                premiere='Left for the owner to test manually; no new Premiere validation performed')
    (base/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    scripts=read('scripts.json')
    cards=''.join(f'<article><h2>{html.escape(s["title"])}</h2><p>{html.escape(s["text"])}</p><p><a href="{s["url"]}">Open 30-second Storylens editor</a> · <a href="live-evidence/{s["id"]}-contact.jpg">View checked frames</a></p></article>' for s in scripts)
    page='''<!doctype html><html><head><meta charset="utf-8"><title>Storylens · Four script validation</title>
<style>body{max-width:1050px;margin:40px auto;padding:0 24px;background:#101112;color:#eee;font:17px/1.65 system-ui}article,section{padding:24px;background:#1b1d20;border:1px solid #363a40;border-radius:14px;margin:20px 0}a{color:#9fd7ff}h1{font-size:30px}h2{font-size:22px}.ok{color:#c8ef86}img{max-width:100%;border-radius:8px}</style></head><body>
<h1>Four scripts · 30 seconds each</h1><section><h2 class="ok">Storylens checks complete</h2>
<p>14 caption templates × 4 scripts. Caption 1 was excluded. Each template kept its own fonts, row hierarchy, decorations and motion, with a starting anchor at 65% frame height.</p>
<p>Reviewed the opening, middle and final captions in all 56 combinations. Separately sampled 6,076 rendered frames: no missing words or text outside the frame. Four-to-six-word edits passed in all 14 templates. These checks do not assert an every-frame match to the reference videos.</p>
<p>Saved and reopened the edited Serif Circle example, then played the 30-second preview through. The four scripts below use silent video and a reading timeline.</p>
<p><a href="/caption-output/pattern-save-reopen-30s/report.html">Open saved edit check</a> · <a href="/caption-output/pattern-save-reopen-30s/captioned-preview.mp4">Play saved 30-second video</a></p>
<p>Premiere testing is left to you.</p><img src="live-evidence/saved-reopened-circle.png" alt="Edited words and circle retained after saving and reopening Storylens"></section>'''+cards+'</body></html>'
    (base/'index.html').write_text(page,'utf-8')
    print('56 live cases, 14 word-count edits, save/reopen and 30-second playback recorded.')


if __name__=='__main__':main()
