"""Quality report page: every rule, pass/fail, the measured value, and what was re-done."""
from pathlib import Path
import html
import json

FEATURE_NAME = {'clean': 'Smart Clean', 'captions': 'Auto Captions', 'broll': 'B-roll', 'zoom': 'Smart Zoom',
                'sound': 'Sound Design', 'visuals': 'Smart Visuals', 'eyecontact': 'Eye Contact', 'script': 'Script Edit'}


def _row(c):
    mark = ('<b class="ok">PASS</b>' if c['passed'] else
            '<b class="bad">FAIL</b>' if c['hard'] else '<b class="warn">NOTE</b>')
    detail = f'<div class="detail">{html.escape(c["detail"])}</div>' if c.get('detail') else ''
    target = f' <span class="muted">(target {html.escape(c["target"])})</span>' if c.get('target') else ''
    return (f'<tr><td>{mark}</td><td>{html.escape(c["title"])}{detail}</td>'
            f'<td>{html.escape(str(c["value"]))}{target}</td><td class="muted">{"rule" if c["hard"] else "advice"}</td></tr>')


def write_report(path, attempts, chosen):
    """attempts: [{'attempt', 'results', 'evaluations': [Evaluation.to_dict()], 'fixes'}]; chosen: index."""
    blocks = []
    for n, a in enumerate(attempts):
        head = (f'Attempt {a["attempt"]}' + (' - USED' if n == chosen else '') +
                (f' · corrections: {html.escape(json.dumps(a.get("fixes") or {}, ensure_ascii=False))}'
                 if a.get('fixes') else ''))
        body = ''
        for e in a['evaluations']:
            name = FEATURE_NAME.get(e['feature'], e['feature'])
            state = 'passed' if e['passed'] else f'{sum(1 for c in e["checks"] if c["hard"] and not c["passed"])} rule(s) failed'
            body += (f'<h3>{html.escape(name)} · score {e["score"]}/100 · {state}</h3>'
                     f'<p class="muted">{html.escape(e["folder"])}</p>'
                     f'<table><tr><th></th><th>Rule</th><th>Measured</th><th></th></tr>'
                     f'{"".join(_row(c) for c in e["checks"])}</table>')
        if a.get('error'):
            body += f'<p class="bad">{html.escape(a["error"])}</p>'
        blocks.append(f'<section class="{"used" if n == chosen else ""}"><h2>{head}</h2>{body}</section>')
    best = attempts[chosen]['evaluations'] if attempts else []
    verdict = ('All rules passed' if best and all(e['passed'] for e in best) else
               'Best attempt still breaks some rules - see FAIL rows')
    Path(path).write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Quality Check</title><style>
:root{{--bg:#0d0f12;--card:#171a20;--line:#2a2f38;--text:#f3f4f6;--muted:#9aa3af;--accent:#ff6a2b}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 "Segoe UI",system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px}}h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:18px;margin:0 0 8px}}
h3{{font-size:15px;margin:18px 0 2px;color:var(--accent)}}.muted{{color:var(--muted);font-size:13px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:16px 0;opacity:.75}}
section.used{{opacity:1;border-color:var(--accent)}}table{{width:100%;border-collapse:collapse;font-size:14px}}
td,th{{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{color:var(--muted);font-size:12px}}
.ok{{color:#5ee08a}}.bad{{color:#ff5d5d}}.warn{{color:#ffb020}}.detail{{color:var(--muted);font-size:12px;margin-top:3px}}
</style></head><body><main><h1>Quality check · {html.escape(verdict)}</h1>
<p class="muted">Every result is measured against its feature's rules. A failed rule makes the tool redo the work with
corrections (and tells the AI exactly what went wrong); the best attempt is used. FAIL = rule broken,
NOTE = advice only.</p>{"".join(blocks)}</main></body></html>''', encoding='utf-8')
    return Path(path)
