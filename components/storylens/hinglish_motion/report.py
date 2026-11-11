"""Review page for Motion Graphics: every key graphic as a still with its words; change the text, the template, full
screen / card, the style, or remove one. Save & rebuild renders only what changed and redoes the timeline and the
full video."""
from pathlib import Path
import html
import json

from hinglish_app import BRIDGE_URL, embed_token
from hinglish_broll.report import STYLE

FIELDS = {
    'asset_hero': ['title', 'label', 'motion'],
    'motion_title': ['title', 'label'],
    'motion_number': ['title', 'value', 'label'],
    'orbital_title': ['title', 'label'],
    'product_card': ['title', 'label'],
    'explainer_steps': ['title', 'label', 'items'],
    'archive_board': ['label', 'archive_style', 'archive_grade', 'archive_composition'],
    'cutout_hero': ['kicker', 'word', 'label'],
    'photo_card': ['title', 'title2', 'label'],
    'spotlight': ['title', 'title2', 'label'],
    'object_drop': ['title', 'title2', 'prefix', 'value', 'suffix', 'label'],
    'collage': ['title', 'title2', 'items'],
    'versus_assets': ['title', 'left_label', 'left_prefix', 'left_value', 'right_label', 'right_prefix', 'right_value'],
    'frame_clip': ['title', 'title2', 'label'],
    'silhouette': ['word', 'label'],
    'headline': ['kicker', 'title', 'title2', 'subtitle'],
    'big_number': ['kicker', 'label', 'prefix', 'value', 'suffix', 'caption'],
    'versus': ['kicker', 'left_label', 'left_prefix', 'left_value', 'right_label', 'right_prefix', 'right_value', 'caption'],
    'stamp': ['stamp', 'caption'],
    'phone': ['app', 'kicker', 'title', 'label', 'prefix', 'value', 'button', 'caption'],
    'call': ['kicker', 'title', 'title2', 'message'],
    'chat': ['kicker', 'messages'],
    'list': ['kicker', 'title', 'title2', 'items'],
    'timeline': ['kicker', 'title', 'items'],
    'route': ['kicker', 'from', 'to', 'caption'],
    'quote': ['quote', 'author'],
    'lower_third': ['name', 'role'],
    'end_card': ['kicker', 'title', 'title2', 'caption'],
}


def _safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


def _clock(seconds):
    m, s = divmod(max(0.0, float(seconds)), 60)
    return f'{int(m)}:{s:04.1f}'


EXTRA = '''
.scene{display:flex;gap:18px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 16px}
.scene.removed{opacity:.45}.pic{flex:none;width:250px}.pic.wide{width:400px}.pic img{width:100%;border-radius:8px;display:block;
background:repeating-conic-gradient(#333 0 25%,#222 0 50%) 0 0/24px 24px}.body{flex:1;min-width:0}
.said{font-size:15px;margin:4px 0 10px}.warn{font-size:12px;color:#e7a0a6;margin:6px 0}
.fields{display:grid;grid-template-columns:120px 1fr;gap:6px 10px;align-items:center;margin:10px 0}
.fields label{font-size:12px;color:var(--muted)}.fields input,.fields textarea,select{background:#0f1216;color:var(--text);
border:1px solid var(--line);border-radius:7px;padding:6px 8px;font:13px "Segoe UI";width:100%}.fields textarea{min-height:64px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.row select{width:auto}.muted{color:var(--muted);font-size:13px}
.full{max-width:100%;max-height:520px;border-radius:12px;border:1px solid var(--line);display:block;margin:0 0 10px}
.top{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 18px}
.pics{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}.pic-item{width:170px;font-size:11px;color:var(--muted)}
.pic-item img,.pic-item video{width:170px;height:130px;object-fit:contain;border-radius:8px;display:block;
background:repeating-conic-gradient(#333 0 25%,#222 0 50%) 0 0/16px 16px}.pic-item input{width:100%;margin-top:4px;
background:#0f1216;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:4px 6px;font:12px "Segoe UI"}
.pic-item .miss{height:130px;display:flex;align-items:center;justify-content:center;border:1px dashed #8a2630;border-radius:8px;color:#e7a0a6}
'''

SCRIPT = r'''
const project=__PROJECT__,FIELDS=__FIELDS__;const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
const changes={};let styleChoice=null;
const LIST_HELP={items:'one per line',messages:'one per line: who | message',years:'one per line: year | what happened'};
const MOTION_CHOICES=[['','Choose from the scene look'],['road-travel','Travelling timeline'],['horizontal-reel','Horizontal film reel'],['vertical-reel','Vertical film reel'],['cinema','Centred photo succession'],['orbit','Circular journey'],['print-sheet','Printed photo sheet'],['evidence-fan','Archive photo fan'],['hinged-triptych','Three hinged glass panels'],['turning-album','Turning album pages']];
function dirty(){$('#save').disabled=false;$('#status').textContent='Changes not saved yet'}
function listText(s,f){const v=s.data[f]||[];if(f==='messages')return v.map(m=>`${m.who||''} | ${m.text||''}`).join('\n');
  if(f==='items'&&s.template==='timeline')return v.map(y=>typeof y==='string'?y:`${y.year||''} | ${y.text||''}`).join('\n');
  return v.map(x=>typeof x==='string'?x:(x.text||'')).join('\n')}
function listValue(template,f,text){const rows=text.split('\n').map(x=>x.trim()).filter(Boolean);
  if(f==='messages')return rows.map(r=>{const [who,...t]=r.split('|');return{who:who.trim(),text:t.join('|').trim()}});
  if(f==='items'&&template==='timeline')return rows.map(r=>{const [year,...t]=r.split('|');return{year:year.trim(),text:t.join('|').trim()}});
  return rows}
function fields(card){const s=project.scenes.find(x=>x.index==card.dataset.index);const template=card.querySelector('.tpl').value;
  const box=card.querySelector('.fields');box.innerHTML='';
  (FIELDS[template]||[]).forEach(f=>{const l=document.createElement('label');l.textContent=f.replace('_',' ')+(LIST_HELP[f]?` (${LIST_HELP[f]})`:'');
    const list=f==='items'||f==='messages';const i=document.createElement(f==='archive_composition'?'select':list||f==='quote'||f==='message'?'textarea':'input');
    if(f==='archive_composition'){l.textContent='Photo movement';MOTION_CHOICES.forEach(([value,text])=>{const o=document.createElement('option');o.value=value;o.textContent=text;i.append(o)})}
    i.value=list?listText({...s,template},f):(s.data[f]||'');
    i.oninput=()=>{const c=changes[s.index]=changes[s.index]||{};c.data=c.data||{};c.data[f]=list?listValue(template,f,i.value):i.value;dirty()};
    box.append(l,i)})}
$$('.scene').forEach(card=>{fields(card);const index=card.dataset.index;
  card.querySelector('.tpl').onchange=e=>{(changes[index]=changes[index]||{}).template=e.target.value;fields(card);dirty()};
  const mode=card.querySelector('.mode');if(mode)mode.onchange=e=>{(changes[index]=changes[index]||{}).mode=e.target.value;dirty()};
  card.querySelector('.remove').onclick=e=>{const gone=!card.classList.contains('removed');card.classList.toggle('removed',gone);
    (changes[index]=changes[index]||{}).removed=gone;e.target.textContent=gone?'Put it back':'Remove';dirty()}});
$('#style').onchange=e=>{styleChoice=e.target.value;dirty()};
$$('.find').forEach(i=>i.addEventListener('input',()=>{const card=i.closest('.scene'),c=changes[card.dataset.index]=changes[card.dataset.index]||{};
  c.find=c.find||[];c.find[Number(i.dataset.slot)]=i.value;dirty()}));
$('#save').onclick=async()=>{const button=$('#save');button.disabled=true;$('#status').textContent='Finding pictures and rendering… (keep this page open)';
  try{const bridge=await(await fetch('__BRIDGE__/api/bridge')).json();
    const body={project_path:project.project_path,scenes:changes};if(styleChoice)body.style=styleChoice;
    const r=await fetch('__BRIDGE__/api/motion/rebuild',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':bridge.token},body:JSON.stringify(body)});
    const d=await r.json();if(!r.ok)throw new Error(d.error||'Rebuild failed');
    $('#status').textContent=`Saved ✓ ${d.shown} graphic(s), ${d.rendered} rendered again.`;setTimeout(()=>location.reload(),1200)}
  catch(e){button.disabled=false;$('#status').textContent='Start Run Hinglish Editor.bat, then try again ('+e.message+')'}};
'''


def _options(values, chosen):
    return ''.join(f'<option value="{html.escape(v)}"{" selected" if v == chosen else ""}>{html.escape(label)}</option>'
                   for v, label in values)


def write_report(path, project):
    from .engines import ENGINES
    engine_name=ENGINES[project.get('settings',{}).get('engine','hyperframes')]
    path = Path(path)
    project = dict(project)
    project['project_path'] = str((path.parent / 'motion-project.json').resolve())
    project.pop('words', None)
    has_video = project.get('timeline') is not None
    wide = project['width'] > project['height']
    fields = dict(FIELDS)
    if project.get('creator_profile') != 'cricket' and not any(s['template'] == 'archive_board' for s in project['scenes']):
        fields.pop('archive_board')
    templates = [(t, t.replace('_', ' ')) for t in fields]
    cards = []
    for s in project['scenes']:
        mode = ''
        if has_video:
            mode = (f'<select class="mode" title="Full screen, or a card over your video">'
                    f'{_options([("full", "Full screen (V2)"), ("overlay", "Card over my video (V3)")], s["mode"])}</select>')
        still = f'<img src="{html.escape(s["still"])}" alt="">' if s.get('still') else '<span class="muted">not rendered</span>'
        warn = ''.join(f'<div class="warn">⚠ layout: {html.escape(p)}</div>' for p in s.get('layout') or [])
        pics = ''
        for i, a in enumerate(s.get('assets_all') or []):
            what = html.escape(f'{a.get("kind", "")}: {a.get("name") or a.get("query", "")}'[:60])
            if a.get('file'):
                media = (f'<video src="{html.escape(a["file"])}" muted loop autoplay playsinline></video>' if a['file'].endswith('.mp4')
                         else f'<img src="{html.escape(a["file"])}" alt="">')
                src = html.escape(a.get('source', ''))
            else:
                media, src = '<div class="miss">not found</div>', 'none'
            historical = a.get('historical') or {}
            context = ' · '.join(str(historical[k]) for k in ('year', 'team', 'match_id') if historical.get(k))
            evidence = f'<div>Historical context: {html.escape(context or "needs review")}</div>' if historical else ''
            pics += (f'<div class="pic-item">{media}{what} · {src}{evidence}<input class="find" data-slot="{i}" '
                     f'placeholder="Find another: type search words"></div>')
        if pics:
            pics = f'<div class="pics">{pics}</div>'
        cards.append(
            f'<section class="scene{" removed" if s.get("removed") else ""}" data-index="{s["index"]}">'
            f'<div class="pic{" wide" if wide else ""}">{still}</div><div class="body">'
            f'<div class="muted">#{s["index"]} · {_clock(s["start"])} · {s["duration"]:.1f} s · {html.escape(s.get("why", ""))}</div>'
            f'<p class="said">“{html.escape(s["text"])}”</p>'
            f'<div class="row"><select class="tpl">{_options(templates, s["template"])}</select>{mode}'
            f'<button class="remove">{"Put it back" if s.get("removed") else "Remove"}</button></div>'
            f'{pics}{warn}<div class="fields"></div></div></section>')
    styles = project.get('style_choices') or [(project['style'], project.get('style_name', project['style']))]
    full = ''
    if project.get('standalone_file'):
        full = f'<video class="full" src="{html.escape(project["standalone_file"])}" controls playsinline></video>'
    toggle = ''
    shown = sum(1 for s in project['scenes'] if not s.get('removed'))
    where = (f'the timeline with the scenes above your video is <b>{html.escape(project["xml"])}</b> (import in Premiere Pro / '
             f'DaVinci Resolve): full-screen scenes on V2, scenes over your video (transparent) on V3; ' if project.get('xml') else '')
    if project.get('xml') and not has_video:
        where = f'<b>{html.escape(project["xml"])}</b> contains separate scene clips for Premiere Pro and CapCut; '
    engines = 'GSAP · Hyperframes' if project.get('creative_tools') else 'Edge / Chrome'
    if any(s['template'] == 'orbital_title' for s in project['scenes']):
        engines += ' · ThreeUI'
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Motion Graphics</title><style>{STYLE}{EXTRA}</style></head><body>
<header><div><h1>Motion Graphics</h1><small>{html.escape(engine_name)} · {shown} graphic(s) · {project["width"]}x{project["height"]} · style: {html.escape(project.get("style_name", ""))}</small></div>
<div><span id="status">Change words, template or style, then save.</span> <button id="save" class="primary" disabled>Save &amp; rebuild</button></div></header>
<main><div class="top">{full}<div class="row"><span class="muted">Style</span><select id="style">{_options(styles, project["style"])}</select>{toggle}</div></div>
{''.join(cards)}
<footer>Every graphic is in the <b>scenes</b> folder; {where}{('the whole script animated is <b>' + html.escape(project["standalone_file"]) + '</b>. ') if project.get("standalone_file") else ''}{engines}. Text stays editable here; editor exports contain rendered scene clips.</footer></main>
<script>{SCRIPT.replace('__PROJECT__', _safe_json(project)).replace('__FIELDS__', _safe_json(fields)).replace('__BRIDGE__', BRIDGE_URL)}</script></body></html>'''
    path.write_text(embed_token(page), encoding='utf-8')
