import html
import json
from pathlib import Path


def write_report(folder,report):
    folder=Path(folder)
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    esc=lambda s:html.escape(str(s),quote=True)
    cards=[]
    for line in report['lines']:
        issues=line['issues']
        badge='Review needed' if issues else 'Checks passed'
        audio=f'<audio controls preload="none" src="{esc(line["audio"])}"></audio>' if line.get('audio') else ''
        alternatives=''
        if line.get('alternatives'):
            alternatives='<details><summary>Other candidate takes</summary><pre>'+esc(json.dumps(line['alternatives'],indent=2))+'</pre></details>'
        judgment=line.get('judgment')
        judge=f'<p><strong>Semantic evaluator:</strong> {esc(judgment["reason"])}</p>' if judgment else ''
        cards.append(f'''<article class="line {'review' if issues else 'pass'}">
<div class="meta">Script line {line['line_index']+1}<span>{badge}</span></div>
<h2>{esc(line['script'])}</h2>
<p class="source">Source: {esc(line.get('source','No matching take'))} · Match {line.get('score',0):.0%}</p>
<p><strong>Heard after cutting:</strong> {esc(line.get('actual','Not available'))}</p>
{audio}{judge}<ul>{''.join('<li>'+esc(x.replace('_',' '))+'</li>' for x in issues)}</ul>{alternatives}</article>''')
    demo='<p class="notice">Synthetic demonstration: the media contains tones and the transcript is a test fixture. This does not demonstrate Hinglish speech accuracy.</p>' if report.get('demo') else ''
    errors=''.join('<li>'+esc(x)+'</li>' for x in report.get('errors',[]))
    xml='<a class="button" href="draft.xml">Open Premiere XML file</a>' if report.get('cut_count',0) else ''
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hinglish Auto Cutter — edit review</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f2f0ea;color:#202b30;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1050px;margin:auto;padding:48px 24px}}.eyebrow{{letter-spacing:.15em;text-transform:uppercase;font-size:12px;color:#536d66}}h1{{font-size:clamp(32px,5vw,56px);line-height:1.12;margin:12px 0}}.intro{{max-width:740px;color:#536168}}.stats{{display:flex;gap:24px;flex-wrap:wrap;margin:32px 0}}.stat{{background:#e3e8e1;border-radius:12px;padding:18px 26px;min-width:170px}}.stat strong{{display:block;font-size:28px}}.stat small{{color:#52625b}}.line{{background:#fffdf8;margin:20px 0;padding:26px;border-radius:12px;border-left:5px solid #b48743}}.line.pass{{border-color:#447665}}h2{{font-size:21px;font-weight:600;margin:14px 0}}.meta{{display:flex;justify-content:space-between;font-size:12px;text-transform:uppercase;letter-spacing:.07em}}.meta span{{color:#946328}}.source{{font-size:13px;color:#697378;overflow-wrap:anywhere}}audio{{width:100%;max-width:650px;margin:8px 0}}li{{font-size:14px}}.button{{display:inline-block;padding:12px 22px;background:#244f46;color:white;text-decoration:none;border-radius:8px}}.notice{{padding:16px;background:#f7e6c3;border-radius:8px}}pre{{white-space:pre-wrap;font-size:12px}}footer{{color:#637169;font-size:13px;margin-top:40px}}</style>
<main><div class="eyebrow">Hinglish Auto Cutter / Premiere workflow</div><h1>Your script.<br>Your edit, ready to review.</h1>
<p class="intro">{esc(report['status'].replace('_',' '))}. Listen to each edited line and check highlighted concerns before your final export. Import the XML into Premiere Pro to continue editing.</p>{demo}
<div class="stats"><div class="stat"><strong>{len(report['lines'])}</strong><small>script lines</small></div><div class="stat"><strong>{report.get('cut_count',0)}</strong><small>timeline clips</small></div><div class="stat"><strong>{report.get('duration_seconds',0):.1f}s</strong><small>edited duration</small></div><div class="stat"><strong>{sum(bool(x['issues']) for x in report['lines'])}</strong><small>lines to review</small></div></div>
{xml}<ul>{errors}</ul>{''.join(cards)}<footer>Local processing · FCP 7 XML · Original media remains editable.<br>ASR and alignment are estimates. Structural checks and a model judgment do not certify a perfect edit. Stereo remains in the XML; review audio is mono.</footer></main></html>'''
    (folder/'report.html').write_text(page,encoding='utf-8')
