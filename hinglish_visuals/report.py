"""Smart Visuals review page (swap any visual for an alternative or remove it, then Save & rebuild)
and CREDITS.txt (authors + licences, ready to paste into the video description)."""
from pathlib import Path
import html
import json

from hinglish_app import BRIDGE_URL
from hinglish_broll.report import STYLE, _clock, write_index as _broll_index

EXTRA_STYLE = '''
.tag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;border-radius:6px;padding:2px 7px;
margin-right:6px;background:#2a2f38;color:#fff}.tag.popup{background:#6b4dff}.tag.full{background:#0e7c66}
.who{margin:6px 0 2px;font-size:14px}.who a{color:#8ab4ff}
.card-preview{display:block;margin:0 auto;max-width:100%;max-height:260px;background:
repeating-conic-gradient(#2a2f38 0% 25%,#1d2128 0% 50%) 50%/22px 22px;border-radius:10px;padding:10px}
.credit{font-size:12px;color:var(--muted);margin-top:6px}
'''

SCRIPT = '''
const project=__PROJECT__;const choices={};const $=s=>document.querySelector(s);
function pick(slot,id){choices[slot]=id;const card=document.querySelector(`[data-slot="${slot}"]`);
  card.querySelectorAll('.option,.none').forEach(b=>b.classList.toggle('active',(b.dataset.id||'')===id));
  card.classList.toggle('removed',!id);$('#save').disabled=false;
  $('#status').textContent=`${Object.keys(choices).length} change(s) — click Save & rebuild`;}
document.querySelectorAll('.option,.none').forEach(b=>b.onclick=()=>pick(b.closest('.moment').dataset.slot,b.dataset.id||''));
$('#save').onclick=async()=>{const button=$('#save');button.disabled=true;$('#status').textContent='Rebuilding…';
  try{const bridge=await(await fetch('__BRIDGE__/api/bridge')).json();
    const r=await fetch('__BRIDGE__/api/visuals/rebuild',{method:'POST',headers:{'Content-Type':'application/json',
      'X-Hinglish-Token':bridge.token},body:JSON.stringify({project_path:project.project_path,choices})});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'Rebuild failed');
    $('#status').textContent=`Saved ✓ ${d.filled} visuals. Re-import VISUALS_SEQUENCE.xml`;setTimeout(()=>location.reload(),900);}
  catch(e){button.disabled=false;$('#status').textContent='Start Run Hinglish Editor.bat, then try again ('+e.message+')';}};
'''


def _safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


def credit_line(media):
    parts = [media.get('title', '')[:80]]
    if media.get('author'): parts.append('by ' + media['author'])
    if media.get('license'): parts.append(media['license'])
    if media.get('nonfree'): parts.append('trademark/non-free, shown for identification')
    if media.get('page_url'): parts.append(media['page_url'])
    return ' · '.join(p for p in parts if p)


def write_report(path, project, has_preview=False):
    path = Path(path)
    project = dict(project)
    project['project_path'] = str((path.parent / 'visuals-project.json').resolve())
    t = project['timeline']
    entities = project.get('entities') or {}
    cards = []
    for s in project['slots']:
        chosen_id = (s.get('chosen') or {}).get('id', '')
        entity = entities.get(s['entity'], {})
        if s.get('clip') and s['display'] == 'popup':
            preview = f'<img class="card-preview" src="thumbs/popup-{s["index"] + 1:02d}.png" alt="">'
        elif s.get('clip'):
            preview = f'<video class="preview" src="{html.escape(s["clip"])}" muted loop playsinline controls></video>'
        else:
            preview = '<div class="empty">No visual at this moment (you stay on screen).</div>'
        options = ''.join(
            f'<button class="option{" active" if c["id"] == chosen_id else ""}" data-id="{html.escape(c["id"])}" '
            f'title="{html.escape(c["source"])}: {html.escape(c["title"][:90])}">'
            + (f'<img src="{html.escape(c["report_thumb"])}" alt="">' if c.get('report_thumb') else '')
            + f'<span>{"▶ " if c["kind"] == "video" else ""}{html.escape(c["source"])}</span></button>'
            for c in s['alternatives'])
        options += f'<button class="none{"" if chosen_id else " active"}" data-id="">No visual</button>'
        if not s['alternatives']:
            options = '<div class="empty">No file clearly showing this was found.</div>' + options
        link = (f' · <a href="https://www.wikidata.org/wiki/{html.escape(entity["qid"])}" target="_blank">Wikidata</a>'
                if entity.get('qid') else '')
        tag = '<span class="tag popup">POP-UP</span>' if s['display'] == 'popup' else '<span class="tag full">FULL SCREEN</span>'
        chosen = s.get('chosen') or {}
        cards.append(
            f'<section class="moment{"" if chosen_id else " removed"}" data-slot="{s["index"]}">'
            f'<div><div class="time">{tag}{_clock(s["start"])} – {_clock(s["end"])}</div>'
            f'<p class="said">“{html.escape(s["text"])}”</p>'
            f'<div class="who"><b>{html.escape(s["label"])}</b> — {html.escape(entity.get("description") or entity.get("kind", ""))}{link}</div>'
            + (f'<div class="idea">Means: <b>{html.escape(s["meaning"])}</b></div>' if s.get('meaning') else '') +
            f'<div class="idea">Shows: <b>{html.escape(s["visual"])}</b><br>Searched: {html.escape(", ".join(s["queries"]))}</div>'
            f'<div class="options">{options}</div>'
            + (f'<div class="credit">{html.escape(credit_line(chosen))}</div>' if chosen else '') +
            f'</div><div>{preview}</div></section>')
    summary = project.get('summary') or {}
    filled = sum(1 for s in project['slots'] if s.get('clip'))
    video = ('<video class="preview" style="height:min(560px,70vh);margin:0 0 20px" src="preview.mp4" controls playsinline></video>'
             if has_preview else '')
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Visuals Review</title><style>{STYLE}{EXTRA_STYLE}:root{{--ratio:{t["width"]}/{t["height"]}}}</style></head><body>
<header><div><h1>Smart Visuals · {html.escape(t["name"])}</h1><small>{filled} of {len(project["slots"])} moments have a real photo, logo or video · brain: {html.escape(project.get("brain", ""))}</small></div>
<div><span id="status">Pick a different file or “No visual”, then save.</span> <button id="save" class="primary" disabled>Save &amp; rebuild</button></div></header>
<main><p class="summary">Topic: <b>{html.escape(summary.get("topic", ""))}</b>{(" · Story: " + html.escape(" ".join(project.get("stories", [])))[:600]) if project.get("stories") else ""}</p>
{video}
{''.join(cards) or '<p class="empty">No famous people, brands, places or events were found in this speech.</p>'}
<footer>Import <b>VISUALS_SEQUENCE.xml</b> in Premiere Pro or DaVinci Resolve (full-screen visuals on V2, pop-ups on V3). Your original timeline is unchanged.
<br>Media come from Wikimedia Commons, Wikipedia and stock sites; authors and licences are in <b>CREDITS.txt</b> — paste it into your video description.</footer></main>
<script>{SCRIPT.replace('__PROJECT__', _safe_json(project)).replace('__BRIDGE__', BRIDGE_URL)}</script></body></html>'''
    path.write_text(page, encoding='utf-8')


def write_credits(path, project):
    lines = ['Visuals used in this video', '']
    for s in project['slots']:
        if s.get('chosen') and s.get('clip'):
            lines.append(f'{_clock(s["start"])}  {s["label"]}: {credit_line(s["chosen"])}')
    if len(lines) == 2:
        lines.append('(none)')
    lines += ['', 'Wikimedia Commons files are free to use with credit to the author and licence above (CC BY / '
              'CC BY-SA need this credit). Logos are trademarks of their owners, shown only to identify them.']
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_index(path, results, notes):
    _broll_index(path, results, notes)
    page = Path(path).read_text(encoding='utf-8')
    page = page.replace('B-roll results', 'Smart Visuals results').replace('moments with B-roll', 'moments with visuals')
    Path(path).write_text(page, encoding='utf-8')
