(() => {
  const $ = id => document.getElementById(id);
  const headers = {'X-Hinglish-Token':document.documentElement.dataset.token};
  const picker = $('resolveLut'), download = $('resolveLutDownload'), note = $('resolveLutNote');
  const builtin = $('resolveBuiltinLut'), restore = $('restoreResolveGrade');
  const builtinStatus = $('resolveBuiltinStatus');
  let rows = [], neutral = [];
  let previewTarget = null;
  const swatches = (id, colors) => $(id).replaceChildren(...colors.map(color => {
    const chip = document.createElement('span');
    chip.style.background = color;
    return chip;
  }));
  async function load() {
    const response = await window.storylensFetch('/api/workbench/grade-luts',{headers});
    const data = await window.storylensResponse(response);
    rows = data.luts;
    neutral = data.neutral;
    for (const name of new Set(rows.map(row=>row.group))) {
      const group = document.createElement('optgroup');
      group.label = name;
      group.append(...rows.filter(row=>row.group===name).map(row=>new Option(row.name,row.id)));
      picker.append(group);
    }
    const factory = data.built_in || [];
    for (const name of new Set(factory.map(row=>row.group))) {
      const group = document.createElement('optgroup');
      group.label = name;
      group.append(...factory.filter(row=>row.group===name).map(row=>new Option(row.name,row.id)));
      builtin.append(group);
    }
    if (!factory.length) builtinStatus.textContent = 'No built-in 3D LUTs found in the installed Resolve library.';
    note.textContent = rows.length ? 'Preview the Sony looks here. Download one to use in Resolve with the matching picture profile.' : 'No validated Sony LUTs found.';
  }
  picker.onchange = () => {
    const row = rows.find(row=>row.id===picker.value);
    download.disabled = !row;
    $('resolveLutPreview').hidden = !row;
    if (row) {
      swatches('resolveLutNeutral',neutral);
      swatches('resolveLutApplied',row.preview);
      note.textContent = row.group+' · '+row.grid+'³ LUT · Preview on test swatches only.';
    } else note.textContent = 'Preview the Sony looks here. Download one to use in Resolve with the matching picture profile.';
  };
  download.onclick = async () => {
    const row = rows.find(row=>row.id===picker.value);
    if (!row) return;
    download.disabled = true;
    try {
      const response = await window.storylensFetch('/api/workbench/grade-lut-file?'+new URLSearchParams({id:row.id}),{headers});
      if (!response.ok) await window.storylensResponse(response);
      const blob = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = blob;
      link.download = row.name+'.cube';
      link.click();
      setTimeout(()=>URL.revokeObjectURL(blob),5000);
    } catch (error) { note.textContent = window.storylensError(error); }
    finally { download.disabled = !picker.value; }
  };
  async function updateResolve(action) {
    builtin.disabled = restore.disabled = true;
    builtinStatus.textContent = action === 'restore' ? 'Restoring the previous grade…' : 'Updating the Resolve preview…';
    try {
      const response = await window.storylensFetch('/api/workbench/grade-lut-preview', {
        method:'POST', headers:{...headers,'Content-Type':'application/json'},
        body:JSON.stringify({action,id:builtin.value,target:previewTarget})
      });
      const result = await window.storylensResponse(response);
      previewTarget = action === 'restore' ? null : result.target;
      if (action === 'restore') builtin.value = '';
      builtinStatus.textContent = result.message;
    } catch (error) {
      previewTarget = null;
      builtin.value = '';
      builtinStatus.textContent = window.storylensError(error);
    } finally {
      builtin.disabled = restore.disabled = false;
    }
  }
  builtin.onchange = () => builtin.value ? updateResolve('apply') : updateResolve('restore');
  restore.onclick = () => updateResolve('restore');
  load().catch(error=>{note.textContent=window.storylensError(error);});
})();
