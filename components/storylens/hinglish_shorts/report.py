"""Review page for Long to Shorts: watch every short, change its title or cut points (±0.5 s), remove it,
add your own from times, switch the look, then Save & rebuild (only changed shorts are made again)."""
from pathlib import Path
import html
import json

from hinglish_app import BRIDGE_URL, embed_token
from hinglish_broll.report import STYLE


def _safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


def clock(seconds):
    m, s = divmod(max(0.0, float(seconds)), 60)
    return f'{int(m)}:{s:04.1f}'


EXTRA = '''
.short{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 16px;
display:grid;grid-template-columns:230px minmax(0,1fr);gap:20px}.short.removed{opacity:.45}
.short video{width:230px;aspect-ratio:9/16;background:#000;border-radius:10px;display:block}
.title{width:100%;font:600 18px "Segoe UI";background:#0f1216;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
.meta{color:var(--muted);font-size:13px;margin:8px 0}.meta b{color:var(--text)}.score{color:var(--accent);font-weight:700}
.why{font-size:14px;margin:6px 0 10px}.piece{border-top:1px solid var(--line);padding:10px 0}
.times{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:13px;color:var(--muted)}
.times input{width:78px;background:#0f1216;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:5px 7px;font:13px Consolas,monospace}
.times button{padding:4px 8px;font-size:12px}.said{font-size:14px;margin:6px 0 0;color:#d6d9de}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 18px}
.panel label{font-size:13px;color:var(--muted);display:inline-flex;gap:6px;align-items:center;margin-right:14px}
.panel select,.panel input[type=text]{background:#0f1216;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:6px 8px}
.tag{display:inline-block;font-size:11px;font-weight:700;border-radius:6px;padding:2px 7px;background:#2a2f38;margin-right:6px}
.tag.you{background:#0e7c66}
@media(max-width:700px){.short{grid-template-columns:1fr}.short video{width:100%;max-width:300px}}
'''

SCRIPT = r'''
const project=__PROJECT__;const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
const toSec=v=>{const p=String(v).trim().split(':').map(Number);if(p.some(isNaN))return NaN;return p.reduce((a,b)=>a*60+b,0)};
const toClock=s=>{s=Math.max(0,s);const m=Math.floor(s/60);return m+':'+(s-m*60).toFixed(1).padStart(4,'0')};
function dirty(){$('#save').disabled=false;$('#status').textContent='Changes not saved yet'}
$$('input,select').forEach(x=>x.addEventListener('input',dirty));
$$('.nudge').forEach(b=>b.onclick=()=>{const input=b.parentElement.querySelector(`input[data-edge="${b.dataset.edge}"]`);
  const v=toSec(input.value);if(!isNaN(v)){input.value=toClock(v+Number(b.dataset.step));dirty()}});
$$('.remove').forEach(b=>b.onclick=()=>{const card=b.closest('.short');card.classList.toggle('removed');
  b.textContent=card.classList.contains('removed')?'Keep this short':'Remove';dirty()});
$('#add').onclick=()=>{const s=toSec($('#newFrom').value),e=toSec($('#newTo').value);
  if(isNaN(s)||isNaN(e)||e-s<3){$('#status').textContent='Type From and To like 4:05 and 5:02';return}dirty();
  const li=document.createElement('li');li.textContent=`${toClock(s)} – ${toClock(e)} · ${$('#newTitle').value||'My short'}`;
  li.dataset.from=s;li.dataset.to=e;li.dataset.title=$('#newTitle').value;$('#added').append(li);
  $('#newFrom').value='';$('#newTo').value='';$('#newTitle').value=''};
$('#save').onclick=async()=>{const shorts=[];
  for(const card of $$('.short')){const pieces=[];for(const p of card.querySelectorAll('.piece')){
      const s=toSec(p.querySelector('[data-edge="from"]').value),e=toSec(p.querySelector('[data-edge="to"]').value);
      if(isNaN(s)||isNaN(e)||e<=s){$('#status').textContent='A From/To time is not valid';return}pieces.push([s,e])}
    shorts.push({index:Number(card.dataset.index),keep:!card.classList.contains('removed'),title:card.querySelector('.title').value,pieces})}
  for(const li of $$('#added li'))shorts.push({index:null,keep:true,title:li.dataset.title,pieces:[[Number(li.dataset.from),Number(li.dataset.to)]]});
  const body={project_path:project.project_path,shorts,look:$('#look').value,captions:$('#captions').checked,
    title:$('#sameTitle').value,handle:$('#handle').value};
  const button=$('#save');button.disabled=true;$('#status').textContent='Making the changed shorts again… (about 1 min per short)';
  try{const bridge=await(await fetch('__BRIDGE__/api/bridge')).json();
    const r=await fetch('__BRIDGE__/api/shorts/rebuild',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':bridge.token},body:JSON.stringify(body)});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'Rebuild failed');
    $('#status').textContent=`Saved ✓ ${d.shorts} shorts (${d.rendered} made again). Re-import the SHORT_*.xml files you changed.`;setTimeout(()=>location.reload(),1200)}
  catch(e){button.disabled=false;$('#status').textContent='Start Run Hinglish Editor.bat, then try again ('+e.message+')'}};
'''


def write_report(path, project):
    path = Path(path)
    project = dict(project)
    project['project_path'] = str((path.parent / 'shorts-project.json').resolve())
    words = project.pop('words', None)            # not needed on the page
    settings = project['settings']
    cards = []
    for s in project['shorts']:
        pieces = ''.join(
            f'<div class="piece"><div class="times">Piece {k + 1}: From <button class="nudge" data-edge="from" data-step="-0.5">−0.5</button>'
            f'<input data-edge="from" value="{clock(a)}"><button class="nudge" data-edge="from" data-step="0.5">+0.5</button>'
            f' To <button class="nudge" data-edge="to" data-step="-0.5">−0.5</button><input data-edge="to" value="{clock(b)}">'
            f'<button class="nudge" data-edge="to" data-step="0.5">+0.5</button> <span>{b - a:.1f}s</span></div>'
            + (f'<p class="said">“{html.escape(part)}”</p>' if part else '') + '</div>'
            for k, ((a, b), part) in enumerate(zip(s['pieces'], (s.get('text') or '').split(' … ') + [''] * 3)))
        tag = '<span class="tag you">ADDED BY YOU</span>' if s.get('added') else \
            f'<span class="tag">AI score <span class="score">{s.get("score", 0):.0f}/10</span></span>'
        cards.append(
            f'<section class="short" data-index="{s["index"]}"><div><video src="{html.escape(s["mp4"])}" controls '
            f'playsinline preload="metadata" poster="{html.escape(s.get("thumb", ""))}"></video></div><div>'
            f'<input class="title" value="{html.escape(s["title"])}" title="Title on the short">'
            f'<div class="meta">{tag}<b>{s.get("duration", sum(b - a for a, b in s["pieces"])):.0f}s</b> · '
            f'{len(s["pieces"])} piece(s) · starts {clock(s["pieces"][0][0])} · '
            f'<a style="color:#8ab4ff" href="{html.escape(s["mp4"])}">MP4</a> · <span>{html.escape(s.get("xml", ""))}</span></div>'
            + (f'<p class="why">{html.escape(s["why"])}</p>' if s.get('why') else '') +
            f'{pieces}<div class="row"><button class="remove">Remove</button></div></div></section>')
    summary = project.get('summary') or {}
    look = settings.get('look', 'template')
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Long to Shorts</title><style>{STYLE}{EXTRA}</style></head><body>
<header><div><h1>Long to Shorts · {html.escape(project.get("name", ""))}</h1><small>{len(project["shorts"])} shorts · AI: {html.escape(project.get("brain", ""))} · every short starts on a hook line and ends on a finished thought</small></div>
<div><span id="status">Watch, fix titles or cut points, then save.</span> <button id="save" class="primary" disabled>Save &amp; rebuild</button></div></header>
<main><p class="summary">Topic: <b>{html.escape(summary.get("topic", ""))}</b></p>
<div class="panel"><label>Look <select id="look"><option value="template"{" selected" if look == "template" else ""}>My template (framed video)</option><option value="face"{" selected" if look == "face" else ""}>Face crop 9:16</option></select></label>
<label><input type="checkbox" id="captions"{" checked" if settings.get("captions") else ""}> Captions</label>
<label>Same title on all <input type="text" id="sameTitle" value="{html.escape(settings.get("title", ""))}" placeholder="empty = AI title per short"></label>
<label>Channel <input type="text" id="handle" value="{html.escape(settings.get("handle", ""))}" placeholder="@yourchannel"></label></div>
{''.join(cards)}
<div class="panel"><b>+ Add a short</b> <small style="color:var(--muted)">(like FireCut's "from In/Out points": type the times in the long video)</small>
<div class="row"><label>From <input type="text" id="newFrom" placeholder="4:05"></label><label>To <input type="text" id="newTo" placeholder="5:02"></label>
<label>Title <input type="text" id="newTitle" placeholder="optional"></label><button id="add">Add</button></div><ul id="added"></ul></div>
<footer>Each short is a finished 1080×1920 MP4 in this folder, plus <b>SHORT_xx_….xml</b>: import it in Premiere Pro or DaVinci Resolve for an editable 9:16 sequence (background, your video pieces, title layer, sound). Your long video is never changed.</footer></main>
<script>{SCRIPT.replace('__PROJECT__', _safe_json(project)).replace('__BRIDGE__', BRIDGE_URL)}</script></body></html>'''
    path.write_text(embed_token(page), encoding='utf-8')
    if words is not None:
        project['words'] = words
