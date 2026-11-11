"""Compact visual picker. Research evidence stays available without dominating the page."""
import html
import json
import re
from pathlib import Path


STYLE = '''
:root{color-scheme:dark;--bg:#101114;--panel:#181a1f;--border:#2b2e35;--muted:#999fae;--text:#eff1f5;--accent:#ff7b44}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
button,a{ -webkit-tap-highlight-color:transparent}button{font:inherit;color:inherit;background:#252831;border:1px solid var(--border);border-radius:8px;padding:7px 12px;cursor:pointer}
button:hover{background:#31353f}button:disabled{opacity:.45;cursor:default}button:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
a{color:#b8c5da;text-decoration:none}a:hover{text-decoration:underline}header{position:sticky;top:0;z-index:3;background:#101114f5;border-bottom:1px solid var(--border);backdrop-filter:blur(14px)}
.toolbar{max-width:1440px;margin:auto;display:flex;align-items:center;gap:16px;padding:16px 28px}.brand{display:flex;align-items:baseline;gap:12px;min-width:0;flex-shrink:0}h1{font-size:19px;line-height:1.2;letter-spacing:-.5px;margin:0;font-weight:650}
.filename{color:var(--muted);font-size:12px;max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.stats{display:flex;align-items:center;gap:13px;list-style:none;padding:0;margin:0;color:var(--muted);font-size:12px;flex:1;white-space:nowrap}.stats li+li:before{content:'·';margin-right:13px;color:#565b66}.stats b{color:#d9dde5;font-weight:550}
.actions{display:flex;gap:8px;white-space:nowrap}.primary{background:var(--accent);border-color:var(--accent);color:#1e100a;font-weight:650}.primary:hover{background:#ff925e}.status-row{max-width:1440px;margin:auto;padding:0 28px 10px;font-size:12px;color:var(--muted)}
main{max-width:1440px;margin:auto;padding:22px 28px 50px}.intro{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;gap:16px}.intro h2{font-size:14px;font-weight:500;margin:0;color:#c3c8d1}.editor-exports:empty{display:none}.editor-exports{font-size:12px;color:var(--muted)}
.visual-group{background:var(--panel);border:1px solid var(--border);border-radius:13px;padding:18px;margin-bottom:18px}.group-head{display:flex;align-items:center;gap:10px;min-width:0}.group-head h2{margin:0;font-size:16px;font-weight:600;letter-spacing:-.25px}.time,.count,.kind{font-size:11px;color:var(--muted)}.count{margin-left:auto;white-space:nowrap}.query{margin:5px 0 13px;color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.moment{min-width:0}.bank-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:10px 0;font-size:12px;color:var(--muted)}.none{font-size:11px;padding:4px 9px;background:transparent}.none.active{color:#c5cbd5;border-color:#535a68}
.visual-bank{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.visual-choice{min-width:0;overflow:hidden;background:#121419;border:1px solid var(--border);border-radius:9px}.asset{display:block;height:190px;background:repeating-conic-gradient(#202329 0% 25%,#262930 0% 50%) 50%/16px 16px}.asset img,.asset video{width:100%;height:100%;object-fit:contain;padding:10px}.choice-actions{padding:9px;display:flex;align-items:center;gap:10px}.option{flex:1;font-size:12px;padding:6px 10px}.option.active{background:#213d32;border-color:#66c99a;color:#a6f0cb}.source-link{font-size:13px;padding:3px;white-space:nowrap}.choice-details{font-size:11px;color:var(--muted);padding:0 10px 10px}.choice-details summary{cursor:pointer;list-style:none}.choice-details summary:after{content:' +';color:#737b8b}.choice-details[open] summary:after{content:' −'}.choice-details p{margin:7px 0;overflow-wrap:anywhere}.choice-details a{font-size:11px}
.research-details{font-size:12px;color:var(--muted);margin-top:12px}.research-details>summary{cursor:pointer}.research-details .said{font-size:12px;margin:10px 0}.research-details pre{white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.5 ui-monospace,monospace;max-height:250px;overflow:auto}.research-details ul{padding-left:18px}.unavailable{font-size:12px;color:var(--muted);margin-top:12px}.unavailable>summary{cursor:pointer}.empty{font-size:12px;color:var(--muted);padding:10px 0}.verdict{font-size:12px;color:var(--muted)}footer{font-size:11px;color:#727a89;margin-top:24px}.preview{max-width:100%;max-height:300px}.editor-exports button{font-size:12px}
@media(max-width:1150px){.toolbar{flex-wrap:wrap;gap:10px}.stats{order:3;flex-basis:100%;gap:12px}.actions{margin-left:auto}.visual-bank{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:800px){.visual-bank{grid-template-columns:repeat(3,minmax(0,1fr))}.filename{max-width:130px}.stats{flex-wrap:wrap}.asset{height:170px}.toolbar,main{padding-left:16px;padding-right:16px}.status-row{padding-left:16px}.visual-group{padding:14px}.time{font-size:10px}}
@media(max-width:520px){.visual-bank{grid-template-columns:repeat(2,minmax(0,1fr))}.brand{gap:8px}h1{font-size:17px}.filename{max-width:95px}.actions button{font-size:11px;padding:7px 9px}.group-head{flex-wrap:wrap}.group-head h2{font-size:14px}.asset{height:160px}}
'''


def render(path, project, script, bridge, *, source_result=None, source_issue=None):
    from hinglish_app import embed_token
    from .report import _clock, _safe_json
    from .recovery import profile_source
    from .source_bank import choice_target
    esc=lambda value:html.escape(str(value),quote=True)
    p=dict(project);p['project_path']=str((path.parent/'visuals-project.json').resolve())
    p['slots']=[{**s,'options':[o for o in s.get('options',[]) if not
        (((o.get('evaluation') or {}).get('checks',{}).get('profile_source')) and not profile_source(o['evaluation']['checks']['profile_source']))]}
        for s in p['slots']]
    target=choice_target(p)
    slots=p['slots'];groups={}
    for slot in slots:
        key=(slot['entity'],round(slot['start'],2),round(slot['end'],2))
        groups.setdefault(key,[]).append(slot)
    cards=[]
    for members in groups.values():
        members=sorted(members,key=lambda s:s.get('reference_type')=='evidence')
        first=members[0];banks=[]
        for s in members:
            evidence=s.get('reference_type')=='evidence'
            options=s.get('options',[]);chosen=(s.get('chosen') or {}).get('id','');items=[]
            for n,c in enumerate(options,1):
                asset=esc(c['asset']);title=esc(c.get('title',''))
                picture=(f'<video src="{asset}" controls muted preload="none"></video>' if c['kind']=='video' else
                    f'<img src="{esc(c.get("report_thumb") or c["asset"])}" alt="{esc(s["label"])} option {n}" loading="lazy">')
                visual=(f'<div class="asset">{picture}</div>' if c['kind']=='video' else
                    f'<a class="asset" href="{asset}" target="_blank" rel="noopener" aria-label="View full-size option {n} for {esc(s["label"])}">{picture}</a>')
                items.append(f'<article class="visual-choice">{visual}'
                    f'<div class="choice-actions"><button class="option{" active" if c["id"]==chosen else ""}" data-id="{esc(c["id"])}" aria-label="Use option {n} for {esc(s["label"])}" aria-pressed="{str(c["id"]==chosen).lower()}">Use {n}</button>'
                    f'<a class="source-link" href="{esc(c.get("page_url", ""))}" target="_blank" rel="noopener" aria-label="Source for option {n}">↗</a></div>'
                    f'<details class="choice-details"><summary>Details</summary><p>{title}</p><p>{esc((c.get("evaluation") or {}).get("seen",""))}</p>'
                    f'<a href="{asset}" download>Download</a> · <a href="{esc(c.get("page_url",""))}" target="_blank" rel="noopener">Source</a></details></article>')
            label='Evidence' if evidence else 'Visuals'
            meta={'spoken_words':s['text'],'search':s.get('queries',[]),'requested':s['visual'],
                'reference_type':s.get('reference_type','identity'),'rejected':s.get('rejected',[]),
                'errors':s.get('preparation_errors',[])}
            details='<details class="research-details"><summary>Research details</summary><pre>'+esc(json.dumps(meta,ensure_ascii=False,indent=2))+'</pre></details>'
            empty='<div class="empty">'+('Checking…' if p.get('collecting') else 'No approved options yet.')+'</div>' if not items else ''
            bank=(f'<section class="moment" data-slot="{s["index"]}"><div class="bank-head"><span>{label} · {len(options)}/{target}</span>'
                f'<button class="none{" active" if not chosen else ""}" data-id="">No visual</button></div>'
                f'<div class="visual-bank">{"".join(items)}</div>{empty}{details}</section>')
            if evidence and len(members)>1:
                bank='<details class="unavailable"><summary>Evidence · '+(str(len(options))+' options' if options else 'unavailable')+'</summary>'+bank+'</details>'
            banks.append(bank)
        count=sum(len(s.get('options',[])) for s in members)
        query=' · '.join(first.get('queries',[])[:1])
        cards.append('<section class="visual-group"><div class="group-head"><h2>'+esc(first['label'])+'</h2>'
            f'<span class="time">{_clock(first["start"])} – {_clock(first["end"])}</span><span class="count">{count} options</span>'
            f'<button class="find-subject none" data-entity="{esc(first["entity"])}" aria-label="Find more options for {esc(first["label"])}" title="Find more for this keyword">↻</button></div>'
            '<p class="query" title="'+esc(first['visual'])+'">'+esc(query or first['visual'])+'</p>'+''.join(banks)+'</section>')
    raw_name=p['timeline']['name'].replace(' · audio on black','')
    name=re.sub(r'^\d{3,4}-[a-f0-9]{8,}-','',raw_name)
    brain=p.get('brain','Local').replace('Ollama ','').replace('storylens-meaning:','').replace('b','B')
    count=sum(len(s.get('options',[])) for s in slots);selected=sum(bool(s.get('chosen')) for s in slots)
    status='Research paused' if p.get('research_state',{}).get('stage')=='paused' else ('Checking saved sources…' if p.get('collecting') else ('Some options unavailable' if any(len(s.get('options',[]))<target for s in slots) else 'Ready'))
    client={'project_path':p['project_path'],'collecting':bool(p.get('collecting')),'slots':[{'clip':s.get('clip')} for s in slots],
            'source_bank':source_result}
    source_link=(f'<a href="{esc(source_result["manifest_relative"])}" download>Source assets</a>' if source_result else '')
    source_error=('<details class="research-details"><summary>Source assets unavailable</summary><p>'+esc(source_issue['message'])+
        '</p><details><summary>Technical details</summary><pre>'+esc(source_issue['details'])+'</pre></details></details>' if source_issue else '')
    page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Smart Visuals · {esc(name)}</title><style>{STYLE}</style>
<link rel="stylesheet" href="{bridge}/editor-handoff.css"><script src="{bridge}/icons.js"></script><script src="{bridge}/feedback.js"></script><script src="{bridge}/editor-handoff.js"></script></head><body>
<header><div class="toolbar"><div class="brand"><h1>Smart Visuals</h1><span class="filename" title="{esc(name)}">{esc(name)}</span></div>
<ul class="stats"><li><b>{count}</b> checked choices</li><li><b>{len(slots)}</b> keywords</li><li><b>{selected}</b> selected</li><li>Ollama <b>{esc(brain)}</b></li></ul>
<div class="actions"><button id="recheck">Find more</button><button id="discard" hidden>Discard changes</button><button id="save" class="primary" disabled>Save &amp; rebuild</button></div></div><div class="status-row"><span id="status">{esc(status)}</span></div></header>
<main><div class="intro"><h2>Choose your visual</h2>{source_link}<div id="editors" class="editor-exports"></div></div>{source_error}{''.join(cards)}
<footer>Source links and check details are saved with each option.</footer></main><script>{script.replace('__PROJECT__',_safe_json(client)).replace('__BRIDGE__',bridge).replace('__FOLDER__',_safe_json(str(path.parent.resolve())))}</script></body></html>'''
    # Keep the shared job and export handlers. Their long default hints belong
    # to older reports; the compact picker already has a clear section label.
    page=page.replace("Collecting and checking more choices. Your current options are saved.","")
    page=page.replace("Choose the visuals you like, then Save & rebuild to send your selected layers to an editor.","")
    page=page.replace('change(s) — click Save & rebuild','unsaved selection(s)')
    if p.get('search_method')=='website' and p.get('review_policy')=='human':
        for asset_name in ('editor-handoff.css','icons.js','feedback.js','editor-handoff.js'):
            page=page.replace(bridge+'/'+asset_name,'/'+asset_name)
        page=page.replace('checked choices','choices to review').replace('No approved options yet.','No image options yet.')
        page=page.replace('Checking saved sources','Searching source images').replace('Checking…','Searching…')
        page=page.replace('Choose your visual','Human review · choose your visual')
        page=page.replace('Source links and check details are saved with each option.',
                          'Source links are saved. Identity and suitability need your review; Vision was not run.')
    path.write_text(embed_token(page),encoding='utf-8')
