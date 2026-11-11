"""Review page for AI Images and AI Video: see every moment, pick the option you like (AI Video: the first frame the
clip is animated from), change a prompt and make it again, or remove it; Save & rebuild redoes the chosen folder and
the timeline."""
from pathlib import Path
import html
import json

from hinglish_app import BRIDGE_URL, embed_token
from hinglish_broll.report import STYLE


def _safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


def _clock(seconds):
    m, s = divmod(max(0.0, float(seconds)), 60)
    return f'{int(m)}:{s:04.1f}'


EXTRA = '''
.moment{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 16px}
.moment.removed{opacity:.5}.said{font-size:16px;margin:4px 0 8px}.tag{display:inline-block;font-size:11px;font-weight:700;
border-radius:6px;padding:2px 7px;margin-right:6px;background:#2a2f38}.tag.video{background:#6b4dff}
.grid{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0}.opt{position:relative;padding:0;border:3px solid transparent;
border-radius:10px;overflow:hidden;background:#000;cursor:pointer;width:260px}.opt img,.opt video{display:block;width:100%}
.opt.active{border-color:var(--good)}.opt .v{position:absolute;left:6px;top:6px;font-size:11px;border-radius:5px;padding:1px 6px}
.v.pass{background:#1f6f4a}.v.fail{background:#8a2630}.v.none{background:#444}.reasons{font-size:12px;color:#e7a0a6;margin:4px 0}
textarea{width:100%;min-height:70px;background:#0f1216;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:8px;font:13px "Segoe UI"}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.muted{color:var(--muted);font-size:13px}
.clip{width:320px;border-radius:10px;border:3px solid #6b4dff}
.image-option{margin:0}.image-option a{display:block;padding:8px 0}.direct-images .opt{width:min(640px,100%)}.direct-images .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr))}.direct-images .opt{max-width:100%}
'''

SCRIPT = r'''
const project=__PROJECT__;const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
const choices={},regenerate={};
function dirty(){$('#save').disabled=false;$('#status').textContent='Changes not saved yet'}
$$('.opt').forEach(b=>b.onclick=()=>{const card=b.closest('.moment');card.querySelectorAll('.opt').forEach(x=>x.classList.toggle('active',x===b));
  choices[card.dataset.index]=b.dataset.id;card.classList.remove('removed');dirty()});
$$('.none').forEach(b=>b.onclick=()=>{const card=b.closest('.moment');card.querySelectorAll('.opt').forEach(x=>x.classList.remove('active'));
  choices[card.dataset.index]='';card.classList.add('removed');dirty()});
$$('.again').forEach(b=>b.onclick=()=>{const card=b.closest('.moment');regenerate[card.dataset.index]=card.querySelector('textarea').value;
  b.textContent='Will be made again ✓';dirty()});
$$('textarea').forEach(t=>t.addEventListener('input',()=>{const card=t.closest('.moment');regenerate[card.dataset.index]=t.value;
  card.querySelector('.again').textContent='Will be made again ✓';dirty()}));
$('#save').onclick=async()=>{const button=$('#save');button.disabled=true;
  $('#status').textContent=Object.keys(regenerate).length?'Making them again on your GPU… (keep this page open; clips take minutes)':'Saving…';
  try{const bridge=await(await fetch('__BRIDGE__/api/bridge')).json();
    const r=await fetch('__BRIDGE__/api/aigen/rebuild',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':bridge.token},
      body:JSON.stringify({project_path:project.project_path,choices,regenerate})});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'Rebuild failed');
    $('#status').textContent=`Saved ✓ ${d.with_visual} of ${d.moments} moments have a visual (${d.remade} made again).`;setTimeout(()=>location.reload(),1200)}
  catch(e){button.disabled=false;$('#status').textContent=window.storylensError?window.storylensError(e):'The images could not be rebuilt. Your saved choices are kept; reopen Storylens and try again.'}};
'''


def _verdict(v):
    if not v:
        return '<span class="v none">not checked</span>', ''
    if v.get('passed'):
        return f'<span class="v pass">PASS {v.get("score", 0):.0f}/10</span>', ''
    return '<span class="v fail">FAIL</span>', f'<div class="reasons">✗ {html.escape("; ".join(v.get("reasons", [])))}</div>'


def write_report(path, project):
    path = Path(path)
    project = dict(project)
    kind = project.get('kind', 'image')
    project['project_path'] = str((path.parent / f'{"aiimage" if kind == "image" else "aivideo"}-project.json').resolve())
    word = 'picture' if kind == 'image' else 'first frame'
    cards = []
    for m in project['moments']:
        options, notes = '', ''
        for o in m.get('options', []):
            if o.get('error'):
                notes += f'<div class="reasons">✗ option not made: {html.escape(o["error"][:160])}</div>'
                continue
            badge, why = _verdict(o.get('verdict'))
            options += (f'<figure class="image-option"><button class="opt{" active" if o["id"] == m.get("chosen") else ""}" data-id="{html.escape(o["id"])}">'
                        f'<img src="{html.escape(o["file"])}" alt="{html.escape(m["prompt"],quote=True)}">{badge}</button>'
                        f'<a href="{html.escape(o["file"])}" download>Download image</a></figure>')
            notes += why
        video = m.get('video') or {}
        clip = ''
        if video.get('file') and not video.get('error'):
            badge, why = _verdict(video.get('verdict'))
            label='2-second quick preview' if project['settings'].get('quality')=='preview' else '5-second clip'
            origin='animated from the chosen first frame' if video.get('from') else 'generated from text'
            clip = (f'<div class="muted">{label} {badge} ({origin})</div>'
                    f'<video class="clip" src="{html.escape(video["file"])}" controls loop muted playsinline></video>{why}')
        elif video.get('error'):
            clip = f'<div class="reasons">✗ clip not made: {html.escape(video["error"][:200])} (its first frame is used)</div>'
        tag = '<span class="tag video">CLIP</span>' if m['kind'] == 'video' else '<span class="tag">PICTURE</span>'
        removed = m.get('removed') or (kind == 'image' and not m.get('chosen'))
        motion = (f'<div class="muted">Motion: {html.escape(m.get("motion", ""))}</div>' if m.get('motion') else '')
        again = 'Make new pictures with this prompt' if kind == 'image' else 'Make new first frames + a new clip'
        cards.append(
            f'<section class="moment{" removed" if removed else ""}" data-index="{m["index"]}">'
            f'<div class="muted">{tag}#{m["index"]} · {_clock(m["start"])} · importance {m.get("importance", 5)}/10 · {html.escape(m.get("why", ""))}</div>'
            f'<p class="said">“{html.escape(m["text"])}”</p>'
            f'{clip}<div class="muted">{word.capitalize()}s: click one to use it</div>'
            f'<div class="grid">{options or f"<span class=muted>No {word} (made from the text)</span>"}</div>{notes}'
            f'<textarea title="What is shown (the style is added)">{html.escape(m["prompt"])}</textarea>{motion}'
            f'<div class="row"><button class="again">{again}</button><button class="none">Not here</button></div>'
            f'</section>')
    ents = project.get('entities') or {}
    never = ', '.join((ents.get('people') or []) + (ents.get('brands') or []))
    tool = html.escape(project.get('tool', 'AI Images'))
    if kind == 'image':
        made = sum(1 for m in project['moments'] if m.get('chosen') and not m.get('removed'))
        counts = f'{made} of {len(project["moments"])} moments have a picture'
    else:
        made = sum(1 for m in project['moments'] if (m.get('video') or {}).get('file') and not (m.get('video') or {}).get('error')
                   and not m.get('removed'))
        counts = f'{made} of {len(project["moments"])} clips made'
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{tool}</title><style>{STYLE}{EXTRA}</style><script src="/feedback.js"></script></head><body class="{'direct-images' if project['settings'].get('request_mode')=='idea' else ''}">
<header><div><h1>{tool}</h1><small>{counts} · style: {html.escape(project["style"][:90])} · evaluator: {html.escape(project.get("evaluator", ""))}</small></div>
<div><span id="status">Click the option you like, change a prompt, then save.</span> <button id="save" class="primary" disabled>Save &amp; rebuild</button></div></header>
<main>{f'<p class="summary">Never AI-generated (real people / brands, use Smart Visuals for them): <b>{html.escape(never)}</b></p>' if never else ''}
{('<p>Method: '+html.escape(project['production']['method'])+' · '+html.escape(' · '.join(project['production']['tools']))+'</p><details><summary>Generation and reference details</summary><pre style="white-space:pre-wrap">'+html.escape(json.dumps(project['production'],ensure_ascii=False,indent=2))+'</pre></details>') if project.get('production') else ''}
{('<p>Channel: '+html.escape(project['image_direction']['knowledge']['channel'])+' · '+html.escape(project['image_direction']['planner'])+' · Z-Image Turbo</p><details><summary>Saved image direction</summary><pre style="white-space:pre-wrap">'+html.escape(json.dumps(project['image_direction'],ensure_ascii=False,indent=2))+'</pre></details>') if project.get('image_direction') else ''}
{''.join(cards)}
<footer>The chosen pictures and clips are in the <b>chosen</b> folder, in story order{'; the timeline with them on V2 is <b>' + html.escape(project["xml"]) + '</b> (import in Premiere Pro / DaVinci Resolve)' if project.get("xml") else ''}. Made on your GPU with Z-Image Turbo (pictures / first frames) and Wan 2.2 (clips), both Apache 2.0.</footer></main>
<script>{SCRIPT.replace('__PROJECT__', _safe_json(project)).replace('__BRIDGE__', BRIDGE_URL)}</script></body></html>'''
    path.write_text(embed_token(page), encoding='utf-8')
