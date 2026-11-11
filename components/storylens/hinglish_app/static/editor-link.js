(() => {
  const query = new URLSearchParams(location.search);
  if (document.documentElement.dataset.token === '__APP_TOKEN__') {
    location.replace('http://127.0.0.1:8883/editor-link.html?' + query);
    return;
  }
  const editors = {premiere:'Premiere Pro', aftereffects:'After Effects', resolve:'DaVinci Resolve', capcut:'CapCut'};
  const $ = id => document.getElementById(id);
  const source = $('source'), kind = $('kind'), draft = $('draft'), composition = $('composition');
  const form = $('handoff-form'), result = $('result'), error = $('toolError'), status = $('status');
  const headers = {'Content-Type':'application/json','X-Hinglish-Token':document.documentElement.dataset.token};
  let job, fingerprint, path = '', busy = false;
  const options = (select, pairs) => select.replaceChildren(...pairs.map(([key,label]) => new Option(label,key)));

  async function call(action,payload) {
    const reply = await window.storylensFetch('/api/editor-link/'+action,{method:'POST',headers,body:JSON.stringify(payload)});
    return window.storylensResponse(reply);
  }

  function showError(problem) {
    error.replaceChildren(document.createTextNode(window.storylensProblem(problem).message));
    const details = window.storylensDetails(problem);
    if (details) error.append(details);
    error.hidden = false;
    status.textContent = '';
  }

  function refreshControls() {
    $('draft-row').hidden = kind.value !== 'capcut-draft';
    $('composition-row').hidden = kind.value !== 'ae-render';
    $('pick-row').hidden = ['active','capcut-draft'].includes(kind.value);
    $('pick-source').textContent = kind.value === 'ae-render' ? 'Choose project' : 'Choose file';
    $('source-name').textContent = path.split(/[/\\]/).pop();
    if (kind.value !== 'capcut-draft') return;
    const selected = source.value;
    call('capcut-drafts',{}).then(value => {
      if (source.value !== selected || kind.value !== 'capcut-draft') return;
      options(draft,[['','Choose a saved project'],...value.drafts.map(row=>[row.path,row.name])]);
    }).catch(showError);
  }

  function changeSource() {
    path = ''; composition.value = ''; job = null; result.hidden = true; error.hidden = true;
    status.textContent = '';
    const formats = [];
    if (['premiere','resolve'].includes(source.value)) formats.push(['active','Active timeline']);
    if (source.value === 'capcut') formats.push(['capcut-draft','Saved project']);
    if (source.value === 'aftereffects') formats.push(['ae-render','Saved composition']);
    formats.push(['media','Finished video'],['xml','Editable timeline file']);
    options(kind,formats);
    refreshControls();
    window.storylensEditors.exportRow($('export-targets'), transfer);
    const same = Array.from($('export-targets').querySelectorAll('button')).find(button=>button.title === 'Export to '+editors[source.value]);
    if (same) { same.disabled = true; same.title = 'Choose a different editor'; }
  }

  async function pick() {
    const format = kind.value;
    const type = {media:'handoff-video', xml:'xml', 'ae-render':'handoff-aep'}[format];
    if (!type) return '';
    const reply = await window.storylensFetch('/api/pick?kind='+type,{headers});
    const selection = await window.storylensResponse(reply);
    if (kind.value === format && selection.path) {
      path = selection.path;
      $('source-name').textContent = path.split(/[/\\]/).pop();
    }
    return path;
  }

  async function apply() {
    if (!job) return;
    const current=job;
    await window.storylensEditors.confirmTransfer(()=>call('apply',{id:current.id}),
      message=>status.textContent=message,()=>job===current);
  }

  async function transfer(target) {
    if (busy || target === source.value) return;
    busy = true;
    form.setAttribute('aria-busy','true');
    error.hidden = true;
    try {
      const selected = kind.value === 'capcut-draft' ? draft.value
        : kind.value === 'active' ? '' : path || await pick();
      if (!selected && kind.value !== 'active') {
        if (kind.value === 'capcut-draft') draft.focus();
        return;
      }
      if (kind.value === 'ae-render' && !composition.value.trim()) {
        composition.focus();
        status.textContent = 'Enter the composition name, then choose an editor.';
        return;
      }
      const payload = {source:source.value,target,kind:kind.value,path:selected,composition:composition.value.trim()};
      const key = JSON.stringify(payload);
      status.textContent = 'Sending to '+editors[target]+'…';
      if (!job || fingerprint !== key) {
        result.hidden = true;
        job = await call('prepare',payload);
        fingerprint = key;
      }
      $('instruction').textContent = job.instruction;
      $('apply').textContent = 'Retry in '+editors[target];
      result.hidden = false;
      await apply();
    } catch (problem) { showError(problem); }
    finally { busy = false; form.removeAttribute('aria-busy'); }
  }

  options(source,Object.entries(editors));
  changeSource();
  source.addEventListener('change',changeSource);
  kind.addEventListener('change',()=>{path=''; job=null; result.hidden=true; error.hidden=true; refreshControls();});
  $('pick-source').onclick = () => pick().catch(showError);
  form.onsubmit = event => event.preventDefault();
  $('apply').onclick = async () => {
    if (busy) return;
    busy = true;
    try { error.hidden = true; await apply(); }
    catch (problem) { showError(problem); }
    finally { busy = false; }
  };
  $('copy').onclick = async () => {
    try { await navigator.clipboard.writeText(job.artifact); status.textContent = 'Transfer location copied.'; }
    catch (problem) { showError(problem); }
  };
})();
