"""B-roll review page: see every moment, swap to an alternative or remove, then Save & rebuild."""
from pathlib import Path
import html
import json


def _safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


def _clock(seconds):
    m, s = divmod(max(0.0, seconds), 60)
    return f'{int(m)}:{s:04.1f}'


STYLE = '''
:root{--bg:#0d0f12;--card:#171a20;--line:#2a2f38;--text:#f3f4f6;--muted:#9aa3af;--accent:#ff6a2b;--good:#3ecf8e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 "Segoe UI",system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;display:flex;gap:16px;align-items:center;justify-content:space-between;
padding:14px 24px;background:rgba(13,15,18,.94);border-bottom:1px solid var(--line);backdrop-filter:blur(6px)}
header h1{font-size:18px;margin:0}header small{color:var(--muted);display:block}
button{font:inherit;cursor:pointer;border-radius:8px;border:1px solid var(--line);background:#20242c;color:var(--text);padding:8px 14px}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button:disabled{opacity:.5;cursor:wait}
main{max-width:1100px;margin:0 auto;padding:20px 24px 80px}
.summary{color:var(--muted);margin:0 0 18px}.summary b{color:var(--text)}
.moment{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 14px;
display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr);gap:18px}
.moment.removed{opacity:.55}
.time{color:var(--accent);font-weight:700;font-size:13px}.said{font-size:16px;margin:4px 0 8px}
.idea{color:var(--muted);font-size:13px}.idea b{color:var(--text)}
.preview{width:100%;aspect-ratio:var(--ratio);background:#000;border-radius:10px;object-fit:cover;max-height:320px}
.options{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.option{position:relative;padding:0;width:104px;height:74px;overflow:hidden;border-width:2px}
.option img{width:100%;height:100%;object-fit:cover;display:block}
.option span{position:absolute;left:4px;bottom:3px;font-size:10px;background:rgba(0,0,0,.7);padding:1px 5px;border-radius:4px}
.option.active{border-color:var(--good)}.none{width:104px;height:74px;font-size:12px}
.none.active{border-color:var(--good)}
.empty{color:var(--muted);font-size:13px;padding:10px 0}
footer{color:var(--muted);font-size:12px;margin-top:26px}
#status{color:var(--muted);font-size:13px}
@media (max-width:760px){.moment{grid-template-columns:1fr}header{flex-wrap:wrap}}
'''

SCRIPT = '''
const project=__PROJECT__;const choices={};const $=s=>document.querySelector(s);
function pick(slot,id){choices[slot]=id;const card=document.querySelector(`[data-slot="${slot}"]`);
  card.querySelectorAll('.option,.none').forEach(b=>b.classList.toggle('active',(b.dataset.id||'')===id));
  card.classList.toggle('removed',!id);$('#save').disabled=false;
  $('#status').textContent=`${Object.keys(choices).length} change(s) — click Save & rebuild`;}
document.querySelectorAll('.option,.none').forEach(b=>b.onclick=()=>pick(b.closest('.moment').dataset.slot,b.dataset.id||''));
$('#save').onclick=async()=>{const button=$('#save');button.disabled=true;$('#status').textContent='Rebuilding…';
  try{const bridge=await(await fetch('http://127.0.0.1:8765/api/bridge')).json();
    const r=await fetch('http://127.0.0.1:8765/api/broll/rebuild',{method:'POST',headers:{'Content-Type':'application/json',
      'X-Hinglish-Token':bridge.token},body:JSON.stringify({project_path:project.project_path,choices})});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'Rebuild failed');
    $('#status').textContent=`Saved ✓ ${d.filled} B-roll clips. Re-import BROLL_SEQUENCE.xml`;setTimeout(()=>location.reload(),900);}
  catch(e){button.disabled=false;$('#status').textContent='Start Run Hinglish Editor.bat, then try again ('+e.message+')';}};
'''


def write_report(path, project):
    path = Path(path)
    project = dict(project)
    project['project_path'] = str((path.parent / 'broll-project.json').resolve())
    t = project['timeline']
    ratio = f"{t['width']}/{t['height']}"
    cards = []
    for s in project['slots']:
        chosen_id = (s.get('chosen') or {}).get('id', '')
        preview = (f'<video class="preview" src="{html.escape(s["clip"])}" muted loop playsinline controls></video>'
                   if s.get('clip') else '<div class="empty">No B-roll at this moment.</div>')
        options = ''.join(
            f'<button class="option{" active" if c["id"] == chosen_id else ""}" data-id="{html.escape(c["id"])}" '
            f'title="{html.escape(c["source"])}: {html.escape(c["title"][:80])}">'
            + (f'<img src="{html.escape(c["report_thumb"])}" alt="">' if c.get('report_thumb') else '')
            + f'<span>{html.escape(c["source"])} {c["score"]:.2f}</span></button>'
            for c in s['alternatives'])
        options += f'<button class="none{"" if chosen_id else " active"}" data-id="">No B-roll</button>'
        if not s['alternatives']:
            options = '<div class="empty">No footage matched well enough. Add footage folders or keys in Settings.</div>' + options
        cards.append(
            f'<section class="moment{"" if chosen_id else " removed"}" data-slot="{s["index"]}">'
            f'<div><div class="time">{_clock(s["start"])} – {_clock(s["end"])}</div>'
            f'<p class="said">“{html.escape(s["text"])}”</p>'
            f'<div class="idea">Shows: <b>{html.escape(s["visual"])}</b><br>Searched: {html.escape(", ".join(s["queries"]))}</div>'
            f'<div class="options">{options}</div></div><div>{preview}</div></section>')
    summary = project.get('summary') or {}
    credits = sorted({f'{c["author"]} ({c["source"].title()})' for s in project['slots'] for c in [s.get('chosen') or {}]
                      if c.get('source') in ('pexels', 'pixabay') and c.get('author')})
    filled = sum(1 for s in project['slots'] if s.get('clip'))
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>B-roll Review</title><style>{STYLE}:root{{--ratio:{ratio}}}</style></head><body>
<header><div><h1>B-roll review · {html.escape(t["name"])}</h1><small>{filled} of {len(project["slots"])} moments have B-roll · {html.escape(project.get("profile", ""))}-form rules · density {html.escape(project.get("density", ""))}</small></div>
<div><span id="status">Pick a different clip or “No B-roll”, then save.</span> <button id="save" class="primary" disabled>Save &amp; rebuild</button></div></header>
<main><p class="summary">Topic: <b>{html.escape(summary.get("topic", ""))}</b> · Setting: {html.escape(summary.get("visual_world", ""))}</p>
{''.join(cards) or '<p class="empty">No B-roll moments were chosen for this timeline.</p>'}
<footer>Open <b>BROLL_SEQUENCE.xml</b> in Premiere Pro or DaVinci Resolve. Your original timeline is unchanged.
{('<br>Stock footage by ' + html.escape(', '.join(credits)) + '. Pexels and Pixabay content is free to use.') if credits else ''}</footer></main>
<script>{SCRIPT.replace('__PROJECT__', _safe_json(project))}</script></body></html>'''
    path.write_text(page, encoding='utf-8')


def write_index(path, results, notes):
    rows = ''.join(f'<a href="{html.escape(r["folder"])}/report.html"><b>{html.escape(r["name"])}</b>'
                   f'<span>{r["filled"]} of {r["moments"]} moments with B-roll</span></a>' for r in results)
    issues = ''.join(f'<li>{html.escape(n)}</li>' for n in notes)
    Path(path).write_text(f'''<!doctype html><html><head><meta charset="utf-8"><title>B-roll results</title><style>
body{{background:#0d0f12;color:#fff;font:16px "Segoe UI";margin:40px auto;max-width:820px;padding:0 20px}}
a{{display:flex;justify-content:space-between;padding:16px;margin:10px 0;background:#171a20;border:1px solid #2a2f38;border-radius:12px;color:#fff;text-decoration:none}}
span,li{{color:#9aa3af}}</style></head><body><h1>B-roll results</h1>{rows}{f"<h3>Notes</h3><ul>{issues}</ul>" if issues else ""}</body></html>''',
                          encoding='utf-8')
