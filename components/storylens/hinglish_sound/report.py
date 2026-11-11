"""Sound design results page: story and emotion map, music and every sound with WHY it is there (trigger +
evidence), what the evaluator heard, the mix check, and Keep / Remove + Save & remix (your choices teach
the AI your taste)."""
from pathlib import Path
import html
import json

from hinglish_app import BRIDGE_URL, app_token


def _clock(seconds):
    m, s = divmod(max(0.0, float(seconds)), 60)
    return f'{int(m)}:{s:04.1f}'


def _verdict(v):
    if not v:
        return ''
    e = html.escape
    state = 'none' if v.get('passed') is None else 'ok' if v.get('passed') else 'bad'
    label = {'none': 'NOT CHECKED', 'ok': '✓ PASS', 'bad': '✗ FAIL'}[state]
    out = f'<div class="v {state}"><b>{label}</b> {e(v.get("heard", ""))}'
    out += ''.join(f'<br>⚠ {e(w)}' for w in v.get('warnings', []))
    out += ''.join(f'<br><span class="rej">✗ threw out {e(r.get("file", ""))}: {e("; ".join(r.get("reasons", [])))}</span>'
                   for r in v.get('rejected', []))
    return out + '</div>'


SCRIPT = '''
const plan=__PLAN__;const $=s=>document.querySelector(s);
const base=location.protocol==='file:'?'__BRIDGE__':location.origin;
const originalFetch=window.storylensFetch;
window.storylensFetch=(url,options)=>originalFetch(typeof url==='string'&&url.startsWith('/')?base+url:url,options);
window.storylensEditors.render($('#editorExports'),{folder:plan.folder});
document.querySelectorAll('.keep').forEach(b=>b.onchange=()=>{b.closest('tr').classList.toggle('off',!b.checked);$('#save').disabled=false});
$('#music').onchange=()=>{$('#save').disabled=false};
$('#save').onclick=async()=>{const button=$('#save');button.disabled=true;$('#status').textContent='Remixing…';
  const keep=[...document.querySelectorAll('.keep')].filter(b=>b.checked).map(b=>+b.dataset.i);
  try{const r=await window.storylensFetch('/api/sound/rebuild',{method:'POST',headers:{'Content-Type':'application/json',
      'X-Hinglish-Token':document.documentElement.dataset.token},body:JSON.stringify({plan_path:plan.plan_path,keep,music:$('#music').checked})});
    const d=await window.storylensResponse(r);
    $('#status').textContent=`Saved ✓ ${d.sounds} sounds. Your choices are remembered. Re-import SOUND_SEQUENCE.xml`;
    setTimeout(()=>location.reload(),900);}
  catch(e){button.disabled=false;$('#status').textContent=window.storylensError(e);}};
'''


def write_report(path, name, plan, preview=None):
    e = html.escape
    path = Path(path)
    feel = ''.join(
        f'<tr><td>{_clock(l["start"])}</td><td>{e(l["text"])}</td><td><b>{e(str(l.get("emotion", "")))}</b> '
        f'{"●" * int(l.get("intensity") or 0)}</td><td class="muted">{e(str(l.get("role", "")))}</td>'
        f'<td class="muted">{e(l.get("voice", ""))}</td></tr>' for l in plan['lines'])
    music = ''.join(
        f'<tr><td>{_clock(s["start"])}–{_clock(s["end"])}</td><td><b>{e(s["mood"])}</b></td>'
        f'<td>{e(Path(s["path"]).name)}{_verdict(s.get("evaluation"))}</td>'
        f'<td class="muted">{e(s.get("why", ""))}<br>{e(s.get("pick_why", ""))}</td></tr>'
        for s in plan['music'])
    listed = plan.get('all_cues') or plan['cues']            # after a remix: every proposed sound, ticked or not
    kept = set(plan.get('kept', range(len(listed))))
    sounds = ''.join(
        f'<tr class="{"" if i in kept else "off"}"><td><label><input type="checkbox" class="keep" data-i="{i}"'
        f'{" checked" if i in kept else ""}> {_clock(c["target"])}</label></td>'
        f'<td><b>{e(c["category"])}</b><br><small>{e(c.get("role") or c["source"])}'
        f'{" · group " + e(c["group_id"]) if c.get("group_id") else ""}'
        f'{" · approximate action timing" if c.get("timing_precision")=="visual_interval" else ""}</small></td>'
        f'<td>{e(c.get("word") or "")}<br><small>{e(c.get("emotion") or "")}</small></td>'
        f'<td><small>{e(c.get("sound") or "")}</small><br>{e(Path(c["path"]).name)}{_verdict(c.get("evaluation"))}</td>'
        f'<td class="muted">{e(c["reason"])}</td></tr>' for i, c in enumerate(listed))
    dropped = ''.join(f'<li>“{e(d["word"])}” ({e(d["type"])}): {e(d["why"])}</li>' for d in plan.get('dropped', []))
    qa = ''.join(f'<tr class="{"" if r["passed"] else "bad"}"><td>{"✓" if r["passed"] else "✗"}</td>'
                 f'<td>{e(r["check"])}</td><td>{e(r["value"])}</td></tr>' for r in plan.get('mix_qa', []))
    passed = sum(1 for r in plan.get('mix_qa', []) if r['passed'])
    video = f'<video src="{e(preview)}?v={len(plan["cues"])}" controls playsinline></video>' if preview else ''
    data = dict(plan, plan_path=str((path.parent / 'sound-plan.json').resolve()))
    data = {'plan_path':data['plan_path'],'folder':str(path.parent.resolve()),'seconds':plan['seconds'],'bridge':BRIDGE_URL}
    listener = plan.get('listener') or 'not available (choices made by names/tags)'
    tools = ['Qwen'] + (['Vision'] if plan.get('settings', {}).get('vision', False) else [])
    tools += (['CLAP'] if plan.get('listener') else []) + ['PyAV']
    if plan.get('source_audio'):tools.insert(-1,'Demucs')
    notices = ''.join('<p>' + e(n) + '</p>' for n in plan.get('notices', []))
    from hinglish_app.user_messages import catalog
    helpers = ('window.storylensErrorCatalog=' + json.dumps(catalog(), ensure_ascii=False).replace('<', '\\u003c') + ';\n' +
               (Path(__file__).resolve().parents[1] / 'hinglish_app/static/feedback.js').read_text(encoding='utf-8'))
    static=Path(__file__).resolve().parents[1]/'hinglish_app/static'
    editor_scripts='\n'.join((static/name).read_text('utf-8') for name in ('icons.js','editor-handoff.js'))
    editor_css=(static/'editor-handoff.css').read_text('utf-8')
    script = SCRIPT.replace('__PLAN__', json.dumps(data).replace('<', '\\u003c')).replace('__BRIDGE__', BRIDGE_URL)
    review = plan.get('human_review')
    if review:
        from .keyword_folders import organize
        organize(review)
    review_html = '<section class="sound-review" id="soundReview" aria-label="Sound choices"></section>' if review else ''
    if review:
        from .human_review import register
        register(path.parent/'sound-plan.json')
        editor_css += (static/'sound-human-review.css').read_text('utf-8')
        script += '\n' + (static/'sound-human-review.js').read_text('utf-8')
        script += '\nmountSoundReview(' + json.dumps(review).replace('<','\\u003c') + ',plan,document.querySelector("#soundReview"));'
        script += '\ndocument.querySelectorAll(".keep").forEach(el=>el.disabled=true);'
    path.write_text(f'''<!doctype html><html lang="en" data-token="{e(app_token())}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sound Design</title><style>
body{{margin:0;background:#0d0f12;color:#f3f4f6;font:14px/1.45 "Segoe UI",system-ui,sans-serif}}
a{{color:#ffb07a}}
main{{max-width:1250px;margin:0 auto;padding:24px;display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr);gap:24px}}
.review-main{{display:block;max-width:900px}}.review-main>section:first-child{{margin-bottom:10px}}
video{{width:100%;max-height:80vh;background:#000;border-radius:12px;position:sticky;top:16px}}
h1{{font-size:22px;margin:0 0 6px}}h2{{font-size:15px;margin:22px 0 6px;color:#ffb07a}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:6px;border-bottom:1px solid #2a2f38;text-align:left;vertical-align:top}}
th{{color:#9aa3af;font-size:12px}}td:first-child{{color:#ff6a2b;font-weight:700;white-space:nowrap}}.muted,small{{color:#9aa3af}}
tr.off{{opacity:.4}}tr.bad td{{color:#f19aa1}}.v{{margin-top:4px;font-size:12px;border-radius:6px;padding:4px 7px;background:#11261b}}
.v.bad{{background:#2a1416}}.v.none{{background:#1d2128}}.rej{{color:#e7a0a6}}
.bar{{position:sticky;top:0;background:#0d0f12;padding:10px 0;display:flex;gap:12px;align-items:center;z-index:2}}
button{{font:inherit;border:0;border-radius:8px;background:#ff6a2b;color:#fff;font-weight:700;padding:8px 14px;cursor:pointer}}
button:disabled{{opacity:.5}}details{{color:#9aa3af;white-space:pre-wrap;font-size:12px}}
@media(max-width:860px){{main{{grid-template-columns:1fr}}}}
</style><style>{editor_css}</style></head><body><main class="{'review-main' if review else ''}"><section>{('<details><summary>Video preview</summary>'+video+'</details>') if review else video}</section><section>
<h1>{'Sound recommendations' if review else 'Sound design · '+e(name)}</h1>
{('<details><summary>Source and analysis notes</summary><p>'+e(name)+'</p>'+notices+'</details>') if review else notices}<p class="muted">{e(' · '.join(tools))} · <a href="CREDITS.txt">Audio credits</a></p>
<div id="editorExports" aria-label="Export sound design"></div>
<p><a href="SOUND_SEQUENCE.xml" download>Download editable timeline</a> · <a href="sound/full-mix.wav" download>Download full mix</a></p>
{('<p><a href="SOUND_KEYWORD_PROJECT.xml" download>Premiere: keyword folders + draft timeline</a> · <a href="sound-keyword-folders.zip" download>Download sound folders</a></p>') if review and (path.parent/'SOUND_KEYWORD_PROJECT.xml').exists() else ''}
{'<details><summary>Video context</summary>' if review else ''}
<p><b>Story:</b> {e(plan.get("story", ""))}<br><span class="muted">Palette: {e(plan.get("palette", ""))} · voice {plan["voice_db"]} dB · listening model: {e(listener)} · budget {plan.get("budget", "")} sounds</span></p>
{'</details>' if review else ''}
{review_html}
<div class="bar" {"hidden style='display:none'" if review else ""}><label><input type="checkbox" id="music" {"checked" if plan["music"] else ""}> Music</label>
<button id="save" disabled>Save &amp; remix</button><span id="status" class="muted">Untick sounds you don't like, then Save &amp; remix. The AI learns your taste.</span></div>
{'<details><summary>Saved plan and technical details</summary>' if review else ''}
<h2>Sounds (why each one is there)</h2><table><tr><th>Keep</th><th>Type · trigger</th><th>Word · tone</th><th>Sound / file · evaluator</th><th>Why</th></tr>{sounds}</table>
{f"<h2>Skipped by the rules</h2><ul class='muted'>{dropped}</ul>" if dropped else ""}
<h2>Music</h2><table><tr><th>Time</th><th>Mood</th><th>Track · evaluator</th><th>Why</th></tr>{music}</table>
<h2>Mix check ({passed}/{len(plan.get("mix_qa", []))} passed)</h2><table>{qa}</table>
<h2>Story and emotion</h2><table><tr><th>Time</th><th>Line</th><th>Emotion</th><th>Role</th><th>Voice</th></tr>{feel}</table>
<details><summary>The model's own thinking</summary>{e(plan.get("thinking", ""))}</details>
<p class="muted">Import <b>SOUND_SEQUENCE.xml</b>: music and each effect are on their own audio tracks, levels already set.</p>
{'</details>' if review else ''}
</section></main><script>{helpers}</script><script>{editor_scripts}</script><script>{script}</script></body></html>''',
                    encoding='utf-8')
