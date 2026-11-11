"""B-roll review page: see every moment, swap to an alternative or remove, then Save & rebuild."""
from pathlib import Path
import html
import json

from hinglish_app import BRIDGE_URL, embed_token, app_token


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
display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px 18px}
.moment.removed{opacity:.55}
.time{color:var(--accent);font-weight:700;font-size:13px}.said{font-size:16px;margin:4px 0 8px}
.idea{color:var(--muted);font-size:13px}.idea b{color:var(--text)}
.moment-meta{display:flex;flex-wrap:wrap;gap:4px 18px;align-items:baseline;margin:6px 0 8px}
.moment-meta .idea{min-width:0;overflow-wrap:anywhere}
.preview{display:block;margin:0 auto;height:min(420px,60vh);width:auto;max-width:100%;aspect-ratio:var(--ratio);background:#000;border-radius:10px;object-fit:cover}
.options{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.option{position:relative;padding:0;width:104px;height:74px;overflow:hidden;border-width:2px}
.option img{width:100%;height:100%;object-fit:cover;display:block}
.option span{position:absolute;left:4px;bottom:3px;font-size:10px;background:rgba(0,0,0,.7);padding:1px 5px;border-radius:4px}
.option.active{border-color:var(--good)}.none{width:auto;height:30px;padding:4px 11px;font-size:12px;line-height:20px}
.none.active{border-color:var(--good)}
.empty{color:var(--muted);font-size:13px;padding:10px 0}
footer{color:var(--muted);font-size:12px;margin-top:26px}
#status{color:var(--muted);font-size:13px}#status:empty{display:none}
.save-controls{display:flex;align-items:center;gap:12px}.editor-exports{margin:0 0 12px}
.timing{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}.timing label{font-size:12px;color:var(--muted)}
.timing input{display:block;width:100px;padding:6px;background:#0d0f12;color:white;border:1px solid #46515b;border-radius:6px}
.source{font-size:12px;color:#b3d7ef;overflow-wrap:anywhere}.watch{width:100%;max-height:48vh;background:black;margin:12px 0}
.moment p.source{margin:8px 0 0}.footage{font-size:12px;color:var(--muted)}
.choice-bank{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-top:14px}
.choice-card{border:1px solid var(--line);border-radius:10px;padding:8px}.choice-card video{width:100%;height:130px;object-fit:contain;background:black}
.choice-actions{display:flex;align-items:center;gap:8px;justify-content:space-between;margin-top:7px}
.choice-card .option{width:auto;height:28px;padding:3px 9px;font-size:12px;line-height:20px;border-width:1px}
.moment.review-bank .preview{height:148px;max-width:230px;object-fit:contain}
@media (max-width:760px){.moment{grid-template-columns:1fr}header{flex-wrap:wrap}}
'''

SCRIPT = '''
const project=__PROJECT__;const choices={};const edits={};const $=s=>document.querySelector(s);
let choiceEditor=null;
let previewBlack=Boolean(project.audio_only_test);
document.documentElement.dataset.token=__TOKEN__;
function dirty(){ $('#save').disabled=false;$('#status').textContent='Unsaved changes'; }
function pick(slot,id){choices[slot]=id;const card=document.querySelector(`[data-slot="${slot}"]`);
  card.querySelectorAll('.option,.none').forEach(b=>b.classList.toggle('active',(b.dataset.id||'')===id));
  card.classList.toggle('removed',!id);$('#save').disabled=false;
  $('#status').textContent='Unsaved changes';}
async function sendChoice(slot,id,defer_project=false){
 if(!choiceEditor?.active||!id)return;
 if(Object.keys(edits).length||previewBlack!==Boolean(project.audio_only_test))throw Error('Save your timing or background changes first with Save & rebuild. Your selected videos are kept.');
 $('#status').textContent='Waiting for editor confirmation…';
 const result=await choiceEditor.select({folder:__FOLDER__,project:project.project_path,slot_index:Number(slot),source_id:id,
  content_format:project.content_format||'short',defer_project});
 if(result.manifest?.type==='capcut'){
  const r=await window.storylensFetch('__BRIDGE__/api/editors/action',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':document.documentElement.dataset.token},body:JSON.stringify({id:result.manifest.task_id,action:'open-editor'})});
  await window.storylensResponse(r);
 }
 $('#status').textContent=result.message||'Editor confirmed this choice.';
}
document.querySelectorAll('.option,.none').forEach(b=>b.onclick=async()=>{
 const slot=b.closest('.moment').dataset.slot,id=b.dataset.id||'';pick(slot,id);
 if(!id){try{const r=await window.storylensFetch('__BRIDGE__/api/panel/broll-native',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':document.documentElement.dataset.token},body:JSON.stringify({action:'clear',folder:__FOLDER__,project:project.project_path,slot_index:Number(slot),content_format:project.content_format||'short'})});await window.storylensResponse(r);$('#status').textContent='No B-roll chosen. Existing editor clips are kept; remove them in your editor if needed.';}catch(error){$('#status').textContent=window.storylensError(error);}return;}
 b.disabled=true;try{await sendChoice(slot,id);}catch(error){$('#status').textContent=window.storylensError(error);}finally{b.disabled=false;}
});
document.querySelectorAll('.timing input').forEach(input=>input.oninput=()=>{
  const key=input.closest('.moment').dataset.slot;edits[key]||={};edits[key][input.dataset.field]=Number(input.value);dirty();
});
document.querySelectorAll('video.preview').forEach(video=>{
 const slot=project.slots.find(s=>String(s.index)===video.closest('.moment').dataset.slot);
 const begin=()=>{video.currentTime=slot.source_in||0};video.addEventListener('loadedmetadata',begin);
 video.addEventListener('timeupdate',()=>{if(video.currentTime>(slot.source_in||0)+slot.end-slot.start)begin()});
});
$('#save').onclick=async()=>{const button=$('#save');button.disabled=true;$('#status').textContent='Rebuilding…';
  try{const bridge=await(await fetch('__BRIDGE__/api/bridge')).json();
    const r=await fetch('__BRIDGE__/api/broll/rebuild',{method:'POST',headers:{'Content-Type':'application/json',
      'X-Hinglish-Token':bridge.token},body:JSON.stringify({project_path:project.project_path,choices,edits,black_background:previewBlack})});
    const d=await window.storylensResponse(r);
    $('#status').textContent='Saved';setTimeout(()=>location.reload(),900);}
  catch(e){button.disabled=false;$('#status').textContent=window.storylensError(e);}};
window.storylensBeforeHandoff=async()=>{if(Object.keys(choices).length||Object.keys(edits).length||previewBlack!==Boolean(project.audio_only_test))
 throw Error('Save your chosen clips and timing first with Save & rebuild, then choose an editor. Your unsaved choices are kept on this page.');
 return {broll_include_options:false,open_editor:true};};
if(project.collecting){$('#editors').textContent='More choices are being collected. Preview these now; editor handoff is available when the search finishes.';
 setInterval(()=>{if(!Object.keys(choices).length&&!Object.keys(edits).length&&![...document.querySelectorAll('video')].some(v=>!v.paused))location.reload()},15000);}
else if(project.slots.some(s=>s.chosen&&s.clip||s.options?.length)){
 if(project.review_options&&window.storylensBrollEditors)choiceEditor=window.storylensBrollEditors.render($('#editors'),{
  initialEditor:new URLSearchParams(location.search).get('editor'),
  api:async value=>{const r=await window.storylensFetch('__BRIDGE__/api/panel/broll-native',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':document.documentElement.dataset.token},body:JSON.stringify(value)});return window.storylensResponse(r);},
  onStatus:message=>{$('#status').textContent=message;},
  onConnect:async()=>{const selected=Object.entries(choices).filter(([,id])=>id);for(let n=0;n<selected.length;n++){const [slot,id]=selected[n];await sendChoice(slot,id,choiceEditor.active==='capcut'&&n<selected.length-1);}}
 });else window.storylensEditors.render($('#editors'),{folder:__FOLDER__});
}
else $('#editors').textContent='No approved cutaways to send yet. Your source and audio are kept.';
'''


def empty_bank_status(slot):
    """Empty review != proof that the internet has no relevant footage."""
    checked={c.get('id') for c in slot.get('checks',[]) if c.get('id')}
    attempted={c.get('id') for c in slot.get('attempted',[]) if c.get('id')}
    if checked:return f'No clip passed the current checks · {len(checked)} videos checked.'
    if attempted:return f'No usable clip collected · {len(attempted)} sources tried.'
    return 'No video options collected for this keyword yet.'


def write_report(path, project):
    path = Path(path)
    project = dict(project)
    project['project_path'] = str((path.parent / 'broll-project.json').resolve())
    t = project['timeline']
    ratio = f"{t['width']}/{t['height']}"
    cards = []
    for s in project['slots']:
        rejected={c.get('id') for c in s.get('checks',[]) if c.get('passed') is False}
        chosen_id = (s.get('chosen') or {}).get('id', '')
        preview = (f'<video class="preview" src="{html.escape(s["clip"])}" muted loop playsinline controls preload="metadata"></video>'
                   if s.get('clip') else '<div class="empty">No B-roll at this moment.</div>')
        options = ''.join(
            f'<button class="option{" active" if c["id"] == chosen_id else ""}" data-id="{html.escape(c["id"])}" '
            f'title="{html.escape(c["source"])}: {html.escape(c["title"][:80])}">'
            + (f'<img src="{html.escape(c["report_thumb"])}" alt="">' if c.get('report_thumb') else '')
            + f'<span>{html.escape(c["source"])} {c["score"]:.2f}</span></button>'
            for c in s['alternatives'] if c.get('kind','video')=='video' and c['id'] not in rejected)
        options += f'<button class="none{"" if chosen_id else " active"}" data-id="">No B-roll</button>'
        if not chosen_id:
            options = '<div class="empty">No relevant video passed for this moment. Your audio is kept.</div>' + options
        controls=''.join(f'<label>{label}<input aria-label="{label} for cutaway {s["index"]+1}" type="number" step="0.01" min="0" data-field="{field}" value="{s.get(field,0):.3f}"></label>'
                         for field,label in [('start','Start (seconds)'),('end','End (seconds)'),('source_in','Source trim (seconds)')])
        chosen=s.get('chosen') or {}
        source=(f'<p class="source">{html.escape(chosen.get("kind","video").title())} · '
                f'<a style="color:#b3d7ef" href="{html.escape(chosen.get("page_url", ""),quote=True)}" target="_blank" rel="noopener noreferrer">Source page</a> · '
                f'{html.escape(chosen.get("license") or "Check the source page for usage terms")}</p>') if chosen else ''
        bank=''
        if project.get('review_options'):
            options=f'<button class="none{"" if chosen_id else " active"}" data-id="">No B-roll</button>'
            for number,c in enumerate(s.get('options',[]),1):
                poster=f' poster="{html.escape(c["report_thumb"],quote=True)}"' if c.get('report_thumb') else ''
                bank+=f'''<div class="choice-card"><video src="{html.escape(c['clip'])}"{poster} controls muted playsinline preload="none"></video>
<div class="choice-actions"><button class="option{' active' if c['id']==chosen_id else ''}" data-id="{html.escape(c['id'],quote=True)}" aria-label="Use option {number}">Option {number}</button>
<a class="source" href="{html.escape(c.get('page_url',''),quote=True)}" target="_blank" rel="noopener noreferrer">Source</a></div></div>'''
            bank='<div class="choice-bank">'+bank+'</div>' if bank else '<p class="empty">'+html.escape(empty_bank_status(s))+'</p>'
        cards.append(
            f'<section class="moment{" review-bank" if project.get("review_options") else ""}{"" if chosen_id else " removed"}" data-slot="{s["index"]}">'
            f'<div><div class="time">{_clock(s["start"])} – {_clock(s["end"])}</div>'
            f'<p class="said">“{html.escape(s["text"])}”</p>'
            + '<div class="moment-meta">' + (f'<span class="idea">Means: <b>{html.escape(s["meaning"])}</b></span>' if s.get('meaning') else '') +
            f'<span class="idea">Shows: <b>{html.escape(s["visual"])}</b></span><span class="idea">Search: {html.escape(", ".join(s["queries"]))}</span></div>'
            f'<div class="timing">{controls}</div><span class="footage">Footage: {s.get("source_duration",s["end"]-s["start"]):.2f}s · Trim or extend in your editor</span>'
            f'<div class="options">{options}</div>{source}</div><div>{preview}</div>{bank}</section>')
    summary = project.get('summary') or {}
    credits = sorted({f'{c["author"]} ({c["source"].title()})' for s in project['slots'] for c in [s.get('chosen') or {}]
                      if c.get('source') in ('pexels', 'pixabay') and c.get('author')})
    filled = sum(1 for s in project['slots'] if s.get('clip'))
    requested=project.get('requested_count',0)
    coverage=(f'{filled} approved video cutaways · {requested} requested' if requested else
              f'{filled} of {len(project["slots"])} moments have B-roll')
    option_count=sum(len(s.get('options',[])) for s in project['slots'])
    if project.get('review_options'):
        coverage=f'{option_count} playable videos · {len(project["slots"])} keyword moments'
    watch=''
    deferred=project.get('preview_state')=='deferred'
    if deferred:
        source=(path.parent.parent/'audio-only-source.mp4').resolve()
        if (project.get('preview_source')=='../audio-only-source.mp4'
                and source.parent==path.parent.parent.resolve() and source.is_file()):
            watch='<video class="watch" src="../audio-only-source.mp4" data-preview-kind="source-audio" aria-label="Original audio over black" controls playsinline preload="metadata"></video>'
    elif project.get('preview_state') in (None,'ready') and (path.parent/'preview.mp4').is_file():
        watch='<video class="watch" src="preview.mp4" data-preview-kind="combined" controls playsinline preload="metadata"></video>'
    save_disabled='' if deferred else ' disabled'
    page = f'''<!doctype html><html lang="en" data-token="{html.escape(app_token(),quote=True)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>B-roll Review</title><style>{STYLE}:root{{--ratio:{ratio}}}</style>
<link rel="stylesheet" href="{BRIDGE_URL}/editor-handoff.css"><script src="{BRIDGE_URL}/icons.js"></script>
<script src="{BRIDGE_URL}/feedback.js"></script><script src="{BRIDGE_URL}/editor-handoff.js"></script><script src="{BRIDGE_URL}/broll-editor-choices.js?v=20261028-1"></script></head><body>
<header><div><h1>B-roll review · {html.escape(t["name"].removesuffix(" — B-roll audio-only test"))}</h1><small>{coverage}</small></div>
<div class="save-controls"><span id="status" role="status"></span><button id="save" class="primary"{save_disabled}>Save &amp; rebuild</button></div></header>
<main>
{('<button id="websiteSearch" type="button">Search websites · I choose</button>') if project.get('review_options') and (path.parent.parent/'recovery.json').is_file() else ''}
<div id="editors" class="editor-exports"></div>
{('<p class="empty">No suitable B-roll was found yet. This is an incomplete search result, not an approved edit.</p>') if not filled else ''}
{watch}
{('<p class="empty">'+html.escape(project['preview_notice'])+'</p>') if project.get('preview_notice') else ''}
{''.join(cards) or '<p class="empty">No B-roll moments were chosen for this timeline.</p>'}
<footer>Open <b>BROLL_SEQUENCE.xml</b> in Premiere Pro or DaVinci Resolve. Your original timeline is unchanged.
<br>Source pages and usage terms are saved in CREDITS.txt. Internet search results do not automatically grant reuse permission.
{('<br>Footage by '+html.escape(', '.join(credits))) if credits else ''}
{('<details><summary>Technical details</summary>'+''.join('<p>'+html.escape(str(note))+'</p>' for note in project.get('source_notices',[]))+'</details>') if project.get('source_notices') else ''}</footer></main>
<script>{SCRIPT.replace('__PROJECT__', _safe_json(project)).replace('__BRIDGE__', BRIDGE_URL).replace('__TOKEN__',_safe_json(__import__('hinglish_app',fromlist=['app_token']).app_token())).replace('__FOLDER__',_safe_json(str(path.parent.resolve())))}</script>
<script>const websiteButton=document.querySelector('#websiteSearch');if(websiteButton)websiteButton.onclick=async()=>{{websiteButton.disabled=true;try{{
const r=await window.storylensFetch('{BRIDGE_URL}/api/panel/broll-website',{{method:'POST',headers:{{'Content-Type':'application/json','X-Hinglish-Token':document.documentElement.dataset.token}},body:JSON.stringify({{action:'start',folder:{_safe_json(str(path.parent.resolve()))}}})}});
const result=await window.storylensResponse(r);location.href=result.page;
}}catch(error){{document.querySelector('#status').textContent=window.storylensError(error);websiteButton.disabled=false;}}}};</script></body></html>'''
    path.write_text(embed_token(page), encoding='utf-8')


def write_index(path, results, notes):
    rows = ''.join(f'<a href="{html.escape(r["folder"])}/report.html"><b>{html.escape(r["name"])}</b>'
                   f'<span>{r["filled"]} of {r["moments"]} moments with B-roll</span></a>' for r in results)
    issues = ''.join(f'<li>{html.escape(n)}</li>' for n in notes)
    Path(path).write_text(f'''<!doctype html><html><head><meta charset="utf-8"><title>B-roll results</title><style>
body{{background:#0d0f12;color:#fff;font:16px "Segoe UI";margin:40px auto;max-width:820px;padding:0 20px}}
a{{display:flex;justify-content:space-between;padding:16px;margin:10px 0;background:#171a20;border:1px solid #2a2f38;border-radius:12px;color:#fff;text-decoration:none}}
span,li{{color:#9aa3af}}</style></head><body><h1>B-roll results</h1>{rows}{f"<h3>Notes</h3><ul>{issues}</ul>" if issues else ""}</body></html>''',
                          encoding='utf-8')
