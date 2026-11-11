"""Apply the owner's compact panel layout without changing Sound/Beat/Cinematic."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def edit(name,changes):
 p=root/name;s=p.read_text('utf-8')
 for old,new in changes:
  if old not in s:raise ValueError(f'Missing revision anchor in {name}: {old[:70]}')
  s=s.replace(old,new,1)
 p.write_text(s,encoding='utf-8')
edit('hinglish_app/static/editor-panel.html',[
 ('editor-panel.css?v=3','editor-panel.css?v=4'),
 ('<div id="captionSettings" hidden><label for="captionStyle">Caption pattern<select id="captionStyle"></select></label><p class="hint">Uses the same saved Caption Studio design and word geometry.</p></div>','<div id="captionSettings" hidden><select id="captionStyle" aria-label="Caption style"></select></div>'),
 ('<div id="savedBrollControls" hidden>','<details id="savedBrollControls" hidden><summary>History</summary>'),
 ('<button id="openBroll">Review options</button></div></div>','<button id="openBroll">Open</button></div></details>'),
 ('<div id="savedVisualControls" hidden>','<details id="savedVisualControls" hidden><summary>History</summary>'),
 ('<button id="openVisuals">Review source images</button></div></div>','<button id="openVisuals">Open</button></div></details>'),
 ('<button id="run" class="primary">Run Smart Clean</button>','<div id="runControls"><button id="run" class="primary">Run Smart Clean</button></div>'),
 ('Connect the current timeline to begin.</p><progress','</p><progress'),
 ('copy-paste.js?v=2','copy-paste.js?v=3'),('editor-panel.js?v=5','editor-panel.js?v=6')])
edit('hinglish_app/static/editor-panel.js',[
 ("keyboard:enabled=>native('clipboardWatch',{enabled})","shortcuts:false,enabled:false"),
 ("async function run(){if(busy)return;clearError();", "async function run(){if(busy)return;busy=true;$('run').disabled=true;clearError();"),
 ("function select(next){mode=next;", "function select(next){mode=next;document.body.dataset.mode=mode;clearError();$('status').textContent='';$('captionSettings').append(...(mode==='captions'?[$('run')]:[]));if(mode!=='captions')$('runControls').append($('run'));$('run').hidden=['zoom','broll','visuals'].includes(mode);$('toolTitle').hidden=mode!=='sound';"),
 ("$('choiceHint').hidden=!['broll','visuals'].includes(mode);", "$('choiceHint').hidden=true;"),
 ("b.onclick=()=>select(tool);", "b.onclick=()=>{if(busy)return;select(tool);if(['zoom','broll','visuals'].includes(tool))return run();};"),
 ("copy.onclick=()=>select('copyPaste');", "copy.onclick=async()=>{if(busy)return;select('copyPaste');const enabled=await copyPasteView.setEnabled(!copyPasteView.isEnabled());copy.textContent=enabled?'Copy Paste · On':'Copy Paste';copy.setAttribute('aria-pressed',String(enabled));};"),
 ("for(const style of config.caption_styles)$('captionStyle').add(new Option(style.name,style.id));$('captionStyle').value='caption_2';", "await refreshCaptionStyles();window.setInterval?.(()=>refreshCaptionStyles().catch(error),5000);window.addEventListener('focus',()=>refreshCaptionStyles().catch(error));"),
 ("(async()=>{try{const config=await api('/api/panel/config');", "async function refreshCaptionStyles(){const previous=$('captionStyle').value||'caption_2',catalogue=await api('/api/captions/auto2/catalog');$('captionStyle').replaceChildren();for(const style of catalogue.styles||[])$('captionStyle').add(new Option(style.name,style.id));if([...(catalogue.styles||[])].some(s=>s.id===previous))$('captionStyle').value=previous;}\n(async()=>{try{const config=await api('/api/panel/config');")])
edit('editor_plugins/copy-paste/ui.js',[
 ("make('p','Ctrl+1 Copy · Ctrl+2 Paste next, while Storylens has focus. AE reserves these keys for Tools/Info elsewhere; Explorer-focused keys are not changed.',settings);", "if(options.shortcuts!==false)make('p','Ctrl+1 Copy · Ctrl+2 Paste next, while Storylens has focus.',settings);"),
 ("if(!enabled||!root.contains(e.target)","if(options.shortcuts===false||!enabled||!root.contains(e.target)")])
css=root/'hinglish_app/static/editor-panel.css'
with css.open('a',encoding='utf-8')as f:f.write('''
/* Compact action surfaces; Sound Design and embedded Beat/Cinematic retain their design. */
body:not([data-mode="sound"]) #toolTitle,body:not([data-mode="sound"]) #toolDescription{display:none}
#captionSettings{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,3fr);gap:6px;align-items:stretch}
#captionSettings select,#captionSettings #run{margin:0;min-width:0;height:34px;padding:6px}
#runControls:empty{display:none}#status{font-size:12px;margin:6px 0}#templateAlinerSection:has(#templateAlinerChoices[hidden]){min-height:0}
#copyPasteSection>select{margin:0 0 6px}#copyPasteSection>p{font-size:12px;margin:6px 0}.copy-paste-actions{gap:6px!important;flex-wrap:nowrap}
body[data-mode="broll"] #choices,body[data-mode="visuals"] #choices{display:block}.candidate-group{margin:8px 0}.candidate-group>h3{font-size:12px;margin:5px 0}.candidate-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.candidate-grid .asset{padding:0;position:relative;overflow:hidden}.candidate-grid .asset img,.candidate-grid .asset video{display:block;height:125px}.candidate-grid .asset button{position:absolute;right:5px;top:5px;width:auto;min-height:28px;background:#171a1fe8}.candidate-grid .asset p{padding:0 6px}
''')
