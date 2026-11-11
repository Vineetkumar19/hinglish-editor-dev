"""Smart Visuals review page (swap any visual for an alternative or remove it, then Save & rebuild)
and CREDITS.txt (authors + licences, ready to paste into the video description)."""
from pathlib import Path
import html
import json

from hinglish_app import BRIDGE_URL, embed_token
from hinglish_broll.report import STYLE, _clock, write_index as _broll_index
from .presentation import LABELS

EXTRA_STYLE = '''
.tag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;border-radius:6px;padding:2px 7px;
margin-right:6px;background:#2a2f38;color:#fff}.tag.popup{background:#6b4dff}.tag.full{background:#0e7c66}
.who{margin:6px 0 2px;font-size:14px}.who a{color:#8ab4ff}
.card-preview{display:block;margin:0 auto;max-width:100%;max-height:260px;background:
repeating-conic-gradient(#2a2f38 0% 25%,#1d2128 0% 50%) 50%/22px 22px;border-radius:10px;padding:10px}
.credit{font-size:12px;color:var(--muted);margin-top:6px}
.verdict{margin-top:8px;font-size:13px;border-radius:8px;padding:7px 10px;background:#11261b;border:1px solid #28543c}
.verdict.fail{background:#2a1416;border-color:#6b2a30}.verdict.none{background:#1d2128;border-color:var(--line)}
.verdict b{margin-right:6px}.rejected{font-size:12px;color:#e7a0a6;margin:4px 0 0 0;padding-left:18px}
.visual-bank{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.visual-choice{min-width:0;padding:10px;background:#11151a;border:1px solid var(--line);border-radius:10px}
.visual-choice img,.visual-choice video{width:100%;height:175px;object-fit:contain;background:repeating-conic-gradient(#222 0% 25%,#30343a 0% 50%) 50%/18px 18px}
.visual-choice .option{width:auto;height:auto;padding:6px 10px;margin:7px 5px 5px 0}
.visual-choice a{color:#a5d2f8;font-size:12px}.visual-choice p{font-size:12px;color:var(--muted)}
'''

SCRIPT = '''
const project=__PROJECT__;const choices={};const $=s=>document.querySelector(s);
window.storylensVisualsSourceBank={request:()=>{
  const bank=project.source_bank;
  if(!bank||bank.state!=='available')throw Error('The raw source bank is not available yet. Saved choices are kept.');
  return {type:'smart_visuals.source_bank.select',version:1,project_path:project.project_path,
    base_manifest:bank.manifest_path,base_manifest_sha256:bank.manifest_sha256,choices:{...choices}};
}};
const draftKey='storylens-visuals-choices:'+project.project_path;
const API=location.protocol.startsWith('http')?location.origin:'__BRIDGE__';
function pick(slot,id){choices[slot]=id;const card=document.querySelector(`[data-slot="${slot}"]`);
  if(!card)return;sessionStorage.setItem(draftKey,JSON.stringify(choices));
  if($('#discard'))$('#discard').hidden=false;
  card.querySelectorAll('.option,.none').forEach(b=>b.classList.toggle('active',(b.dataset.id||'')===id));
  card.querySelectorAll('.option').forEach(b=>b.setAttribute('aria-pressed',String((b.dataset.id||'')===id)));
  card.classList.toggle('removed',!id);$('#save').disabled=false;
  $('#status').textContent=`${Object.keys(choices).length} change(s) — click Save & rebuild`;}
document.querySelectorAll('.option,.none').forEach(b=>b.onclick=()=>pick(b.closest('.moment').dataset.slot,b.dataset.id||''));
if($('#discard'))$('#discard').onclick=()=>{sessionStorage.removeItem(draftKey);location.reload()};
try{const draft=JSON.parse(sessionStorage.getItem(draftKey)||'{}');for(const [slot,id] of Object.entries(draft))if(typeof id==='string')pick(slot,id);}catch(e){}
$('#save').onclick=async()=>{const button=$('#save');button.disabled=true;$('#status').textContent='Rebuilding…';
  try{const bridge=await(await fetch(API+'/api/bridge')).json();
    const r=await fetch(API+'/api/visuals/rebuild',{method:'POST',headers:{'Content-Type':'application/json',
      'X-Hinglish-Token':bridge.token},body:JSON.stringify({project_path:project.project_path,choices})});
    const d=await window.storylensResponse(r);
    sessionStorage.removeItem(draftKey);
    $('#status').textContent=`Saved ${d.filled} visual selections`;setTimeout(()=>location.reload(),900);}
  catch(e){button.disabled=false;$('#status').textContent=window.storylensError(e);}};
window.storylensBeforeHandoff=async()=>{if(Object.keys(choices).length)throw Error('Save your visual choices first with Save & rebuild, then choose an editor. Your selections are kept.');return {open_editor:true};};
if(project.collecting){$('#editors').textContent='Collecting and checking more choices. Your current options are saved.';
 setInterval(()=>{if(!document.querySelector('#recheck')?.disabled&&!Object.keys(choices).length&&![...document.querySelectorAll('video')].some(v=>!v.paused))location.reload()},20000);}
else if(project.slots.some(s=>s.clip))window.storylensEditors.render($('#editors'),{folder:__FOLDER__});
else $('#editors').textContent='Choose the visuals you like, then Save & rebuild to send your selected layers to an editor.';
const resumeKey='storylens-visuals-job:'+project.project_path;
let requestedEntity=null;
const recheck=$('#recheck');if(recheck)recheck.onclick=async()=>{recheck.disabled=true;
 const entity=requestedEntity;requestedEntity=null;
 try{if(Object.keys(choices).length&&!sessionStorage.getItem(resumeKey))throw Error('Save your visual choices first with Save & rebuild, then choose an editor. Your selections are kept.');
 const bridge=await(await fetch(API+'/api/bridge')).json();const headers={'Content-Type':'application/json','X-Hinglish-Token':bridge.token};
 let start;const saved=sessionStorage.getItem(resumeKey);
 if(saved){const response=await fetch(API+'/api/jobs/'+saved,{headers});
   if(response.status===404){sessionStorage.removeItem(resumeKey);throw Error('The saved research job is unavailable. Your choices are kept. Press Find more to continue.');}
   await window.storylensResponse(response);start={job_id:saved};}
 else start=await window.storylensResponse(await fetch(API+'/api/visuals/recheck',{method:'POST',headers,body:JSON.stringify({project_path:project.project_path,entity})}));
 sessionStorage.setItem(resumeKey,start.job_id);
 let job;do{await new Promise(r=>setTimeout(r,1200));job=await window.storylensResponse(await fetch(API+'/api/jobs/'+start.job_id,{headers}));$('#status').textContent=job.stage;}while(['queued','running'].includes(job.status));
 sessionStorage.removeItem(resumeKey);
 if(job.status==='failed'){const error=Error(job.error);error.details=job.error_details;throw error}
 if(Object.keys(choices).length){recheck.disabled=false;$('#status').textContent='Research finished. Your unsaved selections are kept.';}else location.reload();
 }catch(e){recheck.disabled=false;$('#status').textContent=window.storylensError(e)}};
if(recheck&&sessionStorage.getItem(resumeKey))recheck.click();
document.querySelectorAll('.find-subject').forEach(b=>b.onclick=()=>{if(recheck&&!recheck.disabled){requestedEntity=b.dataset.entity;recheck.click()}});
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


def evaluation_html(slot):
    """PASS / FAIL box: what the evaluator saw, which rules failed, and the files it threw out."""
    out = ''
    errors = slot.get('preparation_errors') or []
    if errors and not slot.get('clip') and not slot.get('options'):
        from hinglish_app.user_messages import problem
        issue = problem('Smart Visuals source unavailable: '+errors[-1])
        out += '<div class="verdict fail">' + html.escape(issue['message']) + '</div>'
        out += '<details><summary>Technical details</summary><pre>' + html.escape(issue['details']) + '</pre></details>'
    verdict = slot.get('evaluation')
    if verdict:
        state = 'none' if verdict.get('passed') is None else '' if verdict.get('passed') else 'fail'
        label = 'NOT CHECKED' if state == 'none' else 'PASS' if not state else 'FAIL'
        detail = verdict.get('seen') or '; '.join(verdict.get('warnings', []))
        extra = ''.join(f'<br>⚠ {html.escape(w)}' for w in verdict.get('warnings', []) if verdict.get('seen'))
        out += (f'<div class="verdict {state}"><b>{"✓" if label == "PASS" else "•"} Evaluator {label}</b>'
                f'{html.escape(detail[:260])}{extra}<br><small>{html.escape(verdict.get("judge", ""))}</small></div>')
    rejected = slot.get('rejected') or []
    if rejected:
        out += (f'<details><summary>Technical details: rejected sources ({len(rejected)})</summary><ul class="rejected">' + ''.join(
            f'<li>✗ Rejected {html.escape(r.get("source", ""))} “{html.escape(r.get("title", "")[:60])}”: '
            f'{html.escape("; ".join(r.get("reasons", []))[:200])}</li>' for r in rejected) + '</ul></details>')
    return out


def write_report(path, project, has_preview=False):
    path = Path(path)
    if project.get('review_options'):
        from .review_ui import render
        source_result = source_issue = None
        file = path.parent / 'visuals-project.json'
        paused_manual=(project.get('search_method')=='website' and project.get('research_state',{}).get('stage')=='paused')
        if not project.get('collecting') and not paused_manual and file.is_file():
            try:
                # Never advertise an artifact from a different in-memory/disk
                # revision. Collection saves the project before this report.
                if json.loads(file.read_text('utf-8')) != project:
                    raise ValueError('This review has unsaved changes. Save the project before preparing its raw source bank.')
                from .source_result import ensure_source_result
                source_result = ensure_source_result(file)
            except (ValueError, OSError, KeyError, TypeError) as error:
                from hinglish_app.user_messages import problem
                source_issue = problem(error, feature='Smart Visuals')
        return render(path,project,SCRIPT,BRIDGE_URL,source_result=source_result,source_issue=source_issue)
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
            preview = '<div class="empty">No visual selected for this moment. Original audio is kept.</div>'
        bank = ''
        options = ''.join(
            f'<button class="option{" active" if c["id"] == chosen_id else ""}" data-id="{html.escape(c["id"])}" '
            f'title="{html.escape(c["source"])}: {html.escape(c["title"][:90])}">'
            + (f'<img src="{html.escape(c["report_thumb"])}" alt="">' if c.get('report_thumb') else '')
            + f'<span>{"▶ " if c["kind"] == "video" else ""}{html.escape(c["source"])}</span></button>'
            for c in s['alternatives'])
        options += f'<button class="none{"" if chosen_id else " active"}" data-id="">No visual</button>'
        if not s['alternatives']:
            options = '<div class="empty">No file clearly showing this was found.</div>' + options
        if project.get('review_options'):
            options = f'<button class="none{"" if chosen_id else " active"}" data-id="">No visual</button>'
            for number, c in enumerate(s.get('options', []), 1):
                asset = html.escape(c['asset'], quote=True)
                picture = (f'<video src="{asset}" controls muted playsinline preload="none"></video>' if c['kind']=='video'
                    else f'<img src="{html.escape(c.get("report_thumb") or c["asset"], quote=True)}" alt="{html.escape(c["title"], quote=True)}" loading="lazy">')
                if c['kind']=='image':picture=(f'<a href="{asset}" target="_blank" rel="noopener noreferrer" '
                    f'aria-label="View full-size option {number} for {html.escape(s["label"],quote=True)}">{picture}</a>')
                bank += (f'<article class="visual-choice">{picture}<button class="option{" active" if c["id"]==chosen_id else ""}" '
                    f'data-id="{html.escape(c["id"],quote=True)}" aria-label="Use option {number} for {html.escape(s["label"],quote=True)}">Use option {number}</button> '
                    f'<a href="{asset}" download>Download asset</a><br><a href="{html.escape(c.get("page_url", ""),quote=True)}" '
                    f'target="_blank" rel="noopener noreferrer">Source page</a><p>{html.escape(c["title"][:100])}</p>'
                    f'<p>Local vision: {html.escape((c.get("evaluation") or {}).get("seen", "")[:210])}</p></article>')
            bank = f'<div class="visual-bank">{bank}</div>'
            count = len(s.get('options', []))
            options += f'<p class="empty">{count}/5 choices passed source and local vision checks.' + (
                ' More checks are pending.' if project.get('collecting') and count<5 else ' Missing choices were not replaced with unrelated pictures.' if count<5 else '') + '</p>'
            options += '<p class="empty">'+('Document evidence: must visibly support the requested fact.' if s.get('reference_type')=='evidence' else
                'Identity reference only: this photo or logo does not prove a score, result or event.')+'</p>'
        link = (f' · <a href="https://www.wikidata.org/wiki/{html.escape(entity["qid"])}" target="_blank">Wikidata</a>'
                if entity.get('qid') else '')
        tag = '<span class="tag">' + html.escape(LABELS.get(s['display'], s['display']).upper()) + '</span>'
        chosen = s.get('chosen') or {}
        cards.append(
            f'<section class="moment{"" if chosen_id else " removed"}" data-slot="{s["index"]}">'
            f'<div><div class="time">{tag}{_clock(s["start"])} – {_clock(s["end"])}</div>'
            f'<p class="said">“{html.escape(s["text"])}”</p>'
            f'<div class="who"><b>{html.escape(s["label"])}</b> — {html.escape(entity.get("description") or entity.get("kind", ""))}{link}</div>'
            + (f'<div class="idea">Means: <b>{html.escape(s["meaning"])}</b></div>' if s.get('meaning') and not project.get('review_options') else '') +
            f'<div class="idea">Shows: <b>{html.escape(s["visual"])}</b><br>Searched: {html.escape(", ".join(s["queries"]))}</div>'
            f'<div class="options">{options}</div>'
            + (f'<div class="credit">{html.escape(credit_line(chosen))}</div>' if chosen else '')
            + evaluation_html(s) +
            f'</div><div>{preview}</div>{bank}</section>')
    summary = project.get('summary') or {}
    filled = sum(1 for s in project['slots'] if s.get('clip'))
    passed = sum(1 for s in project['slots'] if s.get('clip') and (s.get('evaluation') or {}).get('passed'))
    thrown = sum(len(s.get('rejected') or []) for s in project['slots'])
    review_summary = (f'{sum(len(s.get("options",[])) for s in project["slots"])} locally checked choices for '
        f'{len(project["slots"])} spoken keywords / facts · {filled} selected · up to five per keyword' if project.get('review_options')
        else f'{filled} of {len(project["slots"])} moments have a real photo, logo or video · evaluator passed {passed}, threw out {thrown} wrong files')
    video = ('<video class="preview" style="height:min(560px,70vh);margin:0 0 20px" src="preview.mp4" controls playsinline></video>'
             if has_preview else '')
    if not video and project.get('black_background') and (path.parent/'audio-on-black.mp4').is_file():
        video='<p>Original speech · existing pictures hidden</p><audio controls preload="metadata" src="audio-on-black.mp4" aria-label="Original speech audio"></audio>'
    unmatched = ''.join('<p class="empty">' + html.escape(row['label']) + ': ' + html.escape(row['reason']) + '</p>'
                        for row in project.get('unmatched', []))
    progress_note=('Searching or checking saved sources; completed choices are kept.' if project.get('collecting') else
        'Research finished with missing choices. Review the unmatched subjects below.' if any(len(s.get('options',[]))<5 for s in project['slots']) else
        'Research finished. Choose your preferred files below.') if project.get('review_options') else ''
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Visuals Review</title><style>{STYLE}{EXTRA_STYLE}:root{{--ratio:{t["width"]}/{t["height"]}}}</style>
<link rel="stylesheet" href="{BRIDGE_URL}/editor-handoff.css"><script src="{BRIDGE_URL}/icons.js"></script>
<script src="{BRIDGE_URL}/feedback.js"></script><script src="{BRIDGE_URL}/editor-handoff.js"></script></head><body>
<header><div><h1>Smart Visuals · {html.escape(t["name"])}</h1><small>{review_summary} · brain: {html.escape(project.get("brain", ""))}</small></div>
<div><span id="status">{html.escape(progress_note or 'Pick a different file or “No visual”, then save.')}</span> <button id="save" class="primary" disabled>Save &amp; rebuild</button>
{('<button id="recheck">'+('Resume saved research' if project.get('collecting') else 'Recheck context &amp; find more')+'</button>') if project.get('review_options') else ''}</div></header>
<main><div id="editors" class="editor-exports"></div><p class="summary">Topic interpreted by the local model: <b>{html.escape(summary.get("topic", ""))}</b></p>
{('<details><summary>Local model interpretation (not fact verification)</summary>'+html.escape(' '.join(project.get('stories',[])))+'</details>') if project.get('stories') else ''}
{video}
{unmatched}
{''.join(cards) or '<p class="empty">No famous people, brands, places or events were found in this speech.</p>'}
<footer>Select your preferred files and Save &amp; rebuild to prepare animated editor layers.
<br>Source pages are saved with each option. Credits for selected assets are in <b>CREDITS.txt</b>.</footer></main>
<script>{SCRIPT.replace('__PROJECT__', _safe_json(project)).replace('__BRIDGE__', BRIDGE_URL).replace('__FOLDER__',_safe_json(str(path.parent.resolve())))}</script></body></html>'''
    path.write_text(embed_token(page), encoding='utf-8')


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
