/* One event-based audition box; changing selections never invokes a model. */
function mountSoundReview(review, project, mount) {
  const selected = new Map((review.selections || []).map(s => [s.event + '/' + s.candidate, {...s}]));
  const events = review.events || [];
  const folders=review.folders||[];
  let activeFolder=folders[0];
  let active = events[0], dirty = false;
  const priorHandoff=window.storylensBeforeHandoff;
  window.storylensBeforeHandoff=async options=>{if(dirty)throw Error('Save your sound choices before exporting. Your unsaved selections are still here.');return priorHandoff?priorHandoff(options):{};};
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; };
  const heading = el('h2', 'Sound Design');
  const note = el('p', 'Keyword folders + a separate draft timeline. Choose the recordings you want.', 'muted');
  const filter = el('input'); filter.type = 'search'; filter.placeholder = 'Find an event, keyword or sound'; filter.setAttribute('aria-label', 'Find sound event');
  const eventSelect = el('select'); eventSelect.setAttribute('aria-label', 'Sound event');
  const folderSelect=el('select');folderSelect.setAttribute('aria-label','Sound keyword folder');
  for(const folder of folders){const option=el('option',`${folder.name} (${folder.candidates.length} sounds)`);option.value=folder.id;folderSelect.append(option);}
  folderSelect.hidden=!folders.length;
  const controls = el('div', '', 'review-controls'); controls.append(folderSelect,filter,eventSelect);
  const intent = el('p'), choices = el('div', '', 'review-choices');
  const audio = el('audio'); audio.controls = true; audio.preload = 'none'; audio.hidden = true; audio.setAttribute('aria-label', 'Sound audition');
  const download = el('a', 'Download original sound'); download.hidden = true; download.download = '';
  const status = el('p', 'You choose. No second-model approval.', 'muted'); status.setAttribute('role', 'status');
  const timeline = el('div', '', 'review-timeline'); timeline.setAttribute('aria-label', 'Selected sound layers');
  const save = el('button', 'Save choices & remix'); save.disabled = true;
  const selectedDetails=el('details');selectedDetails.append(el('summary','Selected timeline layers'),timeline);
  const explanation=el('details');explanation.append(el('summary','Why these sounds'),intent);
  mount.append(heading, note, controls, explanation, audio, download, status, choices, selectedDetails, save);
  const api = async (route, data) => window.storylensResponse(await window.storylensFetch(route, {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Hinglish-Token': document.documentElement.dataset.token},
    body: JSON.stringify({plan_path: project.plan_path, ...data})
  }));
  const clock = n => Number(n).toFixed(2) + 's';
  function changed() { dirty = true; save.disabled = false; status.textContent = 'Unsaved choices. Save to update the preview and editable exports.'; drawTimeline(); }
  function drawTimeline() {
    timeline.replaceChildren();
    for (const s of [...selected.values()].sort((a,b) => a.start - b.start)) {
      const event = events.find(e => e.id === s.event), candidate = event?.candidates.find(c => c.id === s.candidate);
      if (!candidate) continue;
      const row = el('button', `${clock(s.start)} · ${candidate.asset.name} · ${clock(s.duration)} · ${s.level_db} dB`, 'review-layer');
      row.type = 'button';
      row.onclick = () => { filter.value = ''; activeFolder=folders.find(f=>f.events.includes(event.id));if(activeFolder)folderSelect.value=activeFolder.id;populate();eventSelect.value = event.id; active = event; render(); };
      timeline.append(row);
    }
    if (!selected.size) timeline.append(el('p', 'No effects selected. Your original audio will remain.', 'muted'));
  }
  function populate() {
    const query = filter.value.toLowerCase();
    const matches = events.filter(e => (!activeFolder||activeFolder.events.includes(e.id))&&[e.word,e.intent,...e.candidates.map(c=>c.asset.name)].join(' ').toLowerCase().includes(query));
    eventSelect.replaceChildren();
    for (const e of matches) { const option = el('option', `${clock(e.time)} · ${e.word ? e.word + ' · ' : ''}${e.intent}`); option.value = e.id; eventSelect.append(option); }
    if (!matches.includes(active)) active = matches[0];
    if (active) eventSelect.value = active.id;
  }
  function render() {
    choices.replaceChildren();
    intent.textContent = active ? active.reason || active.intent : 'No matching events. Try another keyword.';
    if (!active) return;
    const event = active;
    if (!event.candidates.length) choices.append(el('p', 'No library matches were found for this event. No substitute was inserted.', 'muted'));
    for (const candidate of event.candidates) {
      if(candidate.folder_approved===false)continue;
      const key = event.id + '/' + candidate.id, asset = candidate.asset;
      const card = el('article', '', 'review-option');
      const label = el('label'), check = el('input'); check.type = 'checkbox'; check.checked = selected.has(key);
      check.setAttribute('aria-label', 'Use ' + asset.name); label.append(check, document.createTextNode(asset.name));
      const meta = el('small', `${candidate.recommendation} · ${clock(asset.duration)} original`);
      const actions = el('div', '', 'review-actions'), listen = el('button', 'Listen'), replace = el('button', 'Use only this'), getSound = el('button', 'Get sound');
      listen.type = replace.type = getSound.type = 'button';
      getSound.onclick = async () => {
        getSound.disabled = true;
        try { const data = await api('/api/sound/audition', {event:event.id,candidate:candidate.id});
          const link=el('a'); link.href=(location.protocol==='file:'?project.bridge:'')+data.download;
          link.download=data.name; mount.append(link); link.click(); link.remove();
          status.textContent='Original sound is ready to import into your editor.';
        } catch(e) { status.textContent=window.storylensError(e); } finally {getSound.disabled=false;}
      };
      listen.onclick = async () => {
        listen.disabled = true; status.textContent = 'Preparing sound audition…';
        try {
          const data = await api('/api/sound/audition', {event:event.id, candidate:candidate.id});
          document.querySelector('video')?.pause(); audio.pause();
          const base = location.protocol === 'file:' ? project.bridge : location.origin;
          audio.hidden = false; audio.src = base + data.preview; download.href = base + data.download; download.hidden = false;
          download.download = data.name; status.textContent = data.notice; await audio.play();
        } catch (e) { status.textContent = window.storylensError(e); } finally { listen.disabled = false; }
      };
      const initial = selected.get(key) || {event:event.id, candidate:candidate.id, start:event.time,
        duration:Math.min(asset.duration, event.duration, project.seconds - event.time), level_db:event.level_db};
      const fields = el('div', '', 'review-fields');
      const inputs = {};
      for (const [name, title, min, max] of [['start','Start (s)',0,project.seconds],['duration','Duration (s)',0.01,asset.duration],['level_db','Level (dB)',-60,6]]) {
        const field = el('label', title), input = el('input'); input.type = 'number'; input.step = 'any'; input.required = true;
        input.min = min; input.max = max; input.value = initial[name]; input.setAttribute('aria-label', `${title} for ${asset.name}`);
        input.oninput = input.onchange = () => { if (selected.has(key)) { selected.set(key, read()); changed(); } };
        inputs[name] = input; field.append(input); fields.append(field);
      }
      const read = () => ({event:event.id, candidate:candidate.id, ...Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,Number(v.value)]))});
      check.onchange = () => { if (check.checked) selected.set(key, read()); else selected.delete(key); changed(); };
      replace.onclick = () => { for (const [k,s] of selected) if (s.event === event.id) selected.delete(k); selected.set(key,read()); changed(); render(); };
      const timing=el('details'); timing.append(el('summary','Timing & level'),fields);
      actions.append(listen, getSound, replace); card.append(label, meta, actions, timing); choices.append(card);
    }
  }
  filter.oninput = () => { populate(); render(); };
  folderSelect.onchange=()=>{activeFolder=folders.find(f=>f.id===folderSelect.value);filter.value='';populate();render();};
  eventSelect.onchange = () => { active = events.find(e=>e.id===eventSelect.value); render(); };
  save.onclick = async () => {
    if (!mount.querySelectorAll('input:invalid').length) {
      save.disabled = true; status.textContent = 'Saving your choices and rendering a new revision…';
      try {
        const result = await api('/api/sound/rebuild', {selections:[...selected.values()], music:!!document.querySelector('#music')?.checked});
        dirty = false; location.href = (location.protocol === 'file:' ? project.bridge : '') + result.report_url;
      } catch (e) { status.textContent = window.storylensError(e); save.disabled = false; }
    } else status.textContent = 'Check the highlighted timing and volume fields before saving.';
  };
  window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
  populate(); render(); drawTimeline();
}
