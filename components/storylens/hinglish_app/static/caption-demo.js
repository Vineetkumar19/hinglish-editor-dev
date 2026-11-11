// Caption source switch and editable pasted-caption previews.
(() => {
  const section = document.querySelector('#captionStyles')?.closest('section');
  const run = document.querySelector('#run');
  if (!section || !run) return;
  const head=document.querySelector('.panel-head');
  const sourceSwitch=document.createElement('div');
  sourceSwitch.className='caption-source-switch hidden';
  sourceSwitch.setAttribute('role','group');
  sourceSwitch.setAttribute('aria-label','Caption source');
  sourceSwitch.innerHTML='<button type="button" id="captionFromVideo" aria-pressed="true">From video</button><button type="button" id="captionFromText" aria-pressed="false">Paste captions</button>';
  head.append(sourceSwitch);
  const videoField=document.querySelector('#inputPath').closest('.field');
  const referenceField=document.querySelector('#captionReference').closest('.field');
  const settings=document.querySelector('details.settings');
  const entry=document.createElement('section');
  entry.className='caption-field caption-paste-entry hidden';
  entry.style.cssText='margin-bottom:22px';
  entry.innerHTML=`    <div id="captionPastePanel" class="hidden">
      <label for="captionPasteText">Your captions</label>
      <textarea id="captionPasteText" rows="7" maxlength="6000" placeholder="Paste English or Hinglish captions here. Put each caption on a new line, or paste a paragraph to group it automatically." style="width:100%"></textarea>
      <div class="caption-paste-options">
        <label for="captionPasteDuration">Preview duration (seconds)<input id="captionPasteDuration" type="number" min="3" max="180" value="30" step="1"></label>
        <label for="captionPasteFormat">Preview format<select id="captionPasteFormat"><option value="instagram_vertical">Vertical · 9:16</option><option value="square">Square · 1:1</option><option value="youtube_horizontal">Horizontal · 16:9</option></select></label></div>
      <p style="color:#aaa49b;font-size:13px">No video needed. Your exact words appear on a plain background with sample timing. Choose a template below, then edit words, template, timing, size and position in Caption Studio. No voice or music.</p>
      <p id="captionPasteStatus" role="status" aria-live="polite"></p>
    </div>`;
  videoField.before(entry);
  let pasted=false;
  const pasteText=entry.querySelector('#captionPasteText'),pasteStatus=entry.querySelector('#captionPasteStatus');
  const draftKey='storylens-caption-paste-v1';
  function keepDraft(){try{localStorage.setItem(draftKey,JSON.stringify({text:pasteText.value,duration:entry.querySelector('#captionPasteDuration').value,format:entry.querySelector('#captionPasteFormat').value,style:document.querySelector('.caption-card.active')?.dataset.style,pasted}))}catch{}}
  function updateEntry(){
    const active=mode==='captions'&&pasted;
    if(active)document.body.classList.add('tools-visible');
    entry.classList.toggle('hidden',!active);
    sourceSwitch.classList.toggle('hidden',mode!=='captions');
    head.classList.toggle('caption-head',mode==='captions');
    videoField.classList.toggle('hidden',active);
    settings?.classList.toggle('hidden',active);
    if(mode==='captions')referenceField.classList.toggle('hidden',active);
    entry.querySelector('#captionPastePanel').classList.toggle('hidden',!pasted);
    sourceSwitch.querySelector('#captionFromVideo').setAttribute('aria-pressed',String(!pasted));
    sourceSwitch.querySelector('#captionFromText').setAttribute('aria-pressed',String(pasted));
    if(mode==='captions')document.querySelector('#runText').textContent=active?'Create preview':'Generate captions';
  }
  sourceSwitch.querySelector('#captionFromVideo').onclick=()=>{pasted=false;keepDraft();updateEntry()};
  sourceSwitch.querySelector('#captionFromText').onclick=()=>{pasted=true;keepDraft();updateEntry();pasteText.focus()};
  entry.addEventListener('input',()=>{keepDraft();pasteStatus.textContent=''});entry.addEventListener('change',keepDraft);
  try{const draft=JSON.parse(localStorage.getItem(draftKey)||'null');if(draft){pasteText.value=draft.text||'';entry.querySelector('#captionPasteDuration').value=draft.duration||30;entry.querySelector('#captionPasteFormat').value=draft.format||'instagram_vertical';pasted=!!draft.pasted;if([...document.querySelectorAll('.caption-card')].some(c=>c.dataset.style===draft.style)){captionStyle=draft.style;document.querySelectorAll('.caption-card').forEach(c=>c.classList.toggle('active',c.dataset.style===draft.style))}}}catch{}
  document.querySelectorAll('.caption-card').forEach(card=>card.addEventListener('click',keepDraft));
  document.addEventListener('storylensmodechange',updateEntry);
  if(new URLSearchParams(location.search).get('caption_source')==='paste'){pasted=true;setMode('captions')}
  updateEntry();
  let opening = false;
  run.addEventListener('click', async event => {
    if (mode !== 'captions' || !pasted) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (opening) return;
    opening = true;
    run.disabled = true;
    window.storylensClearError?.();
    window.storylensPendingResult?.();
    pasteStatus.textContent='Creating your editable caption preview…';
    try {
      keepDraft();
      const response=await window.storylensFetch('/api/captions/script-preview',{method:'POST',headers,
        body:JSON.stringify({text:pasteText.value,style:document.querySelector('.caption-card.active')?.dataset.style,
          duration:entry.querySelector('#captionPasteDuration').value,format:entry.querySelector('#captionPasteFormat').value})});
      if(response.status===404)throw Object.assign(Error('Restart Storylens to load the pasted-caption feature, then press Create preview again. Your pasted text and settings are kept.'),{code:'caption_preview_service_outdated',details:'The running service does not recognise POST /api/captions/script-preview (HTTP 404).'});
      const result=await window.storylensResponse(response);
      if(!response.ok)throw Object.assign(Error(result.error||'Keep your script and try creating the preview again.'),{code:result.error_code,details:result.error_details});
      if(!/^\/caption-output\/script-previews\/[a-f0-9]+\/report\.html$/.test(result.url))throw Error('The caption preview could not be opened. Keep your script and retry.');
      location.assign(result.url);
    } catch (error) {
      pasteStatus.textContent=window.storylensError(error);
    } finally {
      opening = false;
      run.disabled = false;
    }
  }, true);
})();
