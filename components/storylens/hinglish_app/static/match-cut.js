(() => {
  const byId = id => document.getElementById(id);
  const token = document.documentElement.dataset.token;
  const storageKey = 'storylens.workbench.match-cut.scene-handoff';
  const form = byId('scan'), player = byId('video');
  let current, result, request, pollTimer;
  let groups = [], uploaded = [], active = false;

  if (new URLSearchParams(location.search).get('embedded') === '1') {
    document.body.dataset.embedded = '';
    document.querySelector('header').hidden = true;
  }

  async function send(path, body) {
    return window.storylensFetch(path, {
      method: body ? 'POST' : 'GET',
      headers: {'Content-Type': 'application/json', 'X-Hinglish-Token': token},
      ...(body ? {body: JSON.stringify(body)} : {}),
    });
  }

  async function api(path, body) {
    return window.storylensResponse(await send(path, body));
  }

  function report(error) {
    const box = byId('toolError');
    box.textContent = window.storylensProblem(error).message;
    box.hidden = false;
  }

  function busy(on, canCancel = false) {
    active = on;
    for (const field of form.querySelectorAll('textarea, input, button')) field.disabled = on;
    byId('cancel').hidden = !canCancel;
    byId('cancel').disabled = false;
    byId('progress').hidden = !on;
    byId('resume').hidden = on || !['failed', 'interrupted'].includes(current?.status);
  }

  function media(asset, download = false) {
    return '/api/workbench/match-cut-media?' + new URLSearchParams({
      id: current.id, asset, token, ...(download ? {download: '1'} : {}),
    });
  }

  function resetPreview() {
    player.pause();
    player.removeAttribute('src');
    player.load();
    byId('results').hidden = true;
  }

  function select() {
    const group = groups[Number(byId('choices').value)];
    if (!group) return;
    player.src = media(group.preview);
    byId('clipCount').textContent = group.count + ' clips';
    byId('download').href = media(group.preview, true);
    byId('download').download = result.artifacts[group.preview].path.split('/').at(-1);
  }

  function render(data) {
    result = data;
    groups = result.groups.filter(group => group.status === 'verified' &&
      group.calibration === 'scene-handoff-v1' && group.rank !== null && result.artifacts[group.preview]);
    byId('choices').replaceChildren(...groups.map((group, i) =>
      new Option('Preview ' + (i + 1) + ' · ' + group.count + ' clips', i)));
    byId('choices').hidden = groups.length <= 1;
    byId('results').hidden = !groups.length;
    byId('status').textContent = groups.length ? '' :
      result.failures.length ? 'No preview exported. Check that the source videos are readable.' :
        'No cut with convincing movement between distinct scenes was found.';
    if (groups.length) select();
  }

  function watchError(error) {
    busy(false);
    report(error);
  }

  async function watch(id) {
    current = await api('/api/workbench/job?' + new URLSearchParams({id}));
    if (current.kind !== 'match-cut') throw Error('Choose a Match Cut Finder scan.');
    byId('progress').value = current.progress || 0;
    if (['queued', 'running'].includes(current.status)) {
      byId('status').textContent = current.stage;
      busy(true, true);
      pollTimer = setTimeout(() => watch(id).catch(watchError), 800);
      return;
    }
    busy(false);
    if (current.status === 'complete') {
      render(await api('/api/workbench/match-cut-result?' + new URLSearchParams({id})));
    } else if (current.status === 'cancelled') {
      byId('status').textContent = 'Scan stopped.';
    } else {
      byId('status').textContent = '';
      report(current.error || Error(current.stage));
    }
  }

  form.addEventListener('input', () => { request = null; });
  form.onsubmit = async event => {
    event.preventDefault();
    if (active) return;
    byId('toolError').hidden = true;
    resetPreview();
    busy(true);
    byId('progress').value = 0;
    try {
      const files = [...byId('files').files];
      const folders = byId('folders').value.split(/\r?\n/).map(path => path.trim().replace(/^"(.*)"$/, '$1')).filter(Boolean);
      if (!folders.length && !files.length) throw Error('Choose a footage folder or videos.');
      for (let i = uploaded.length; i < files.length; i++) {
        byId('status').textContent = 'Adding video ' + (i + 1) + ' of ' + files.length;
        const response = await window.storylensFetch('/api/cinematic/upload?' + new URLSearchParams({name: files[i].name}), {
          method: 'POST', headers: {'X-Hinglish-Token': token, 'Content-Type': 'application/octet-stream'}, body: files[i],
        });
        uploaded.push((await window.storylensResponse(response)).path);
      }
      request ??= {paths: uploaded, folders, max_clips: Number(byId('maximum').value),
        groups_per_count: Number(byId('limit').value), transition_previews_only: true, idempotency_key: crypto.randomUUID()};
      current = await api('/api/workbench/match-cut', request);
      request = null;
      localStorage.setItem(storageKey, current.id);
      await watch(current.id);
    } catch (error) { watchError(error); }
  };
  byId('pick').onclick = async () => {
    try {
      const {path} = await api('/api/pick?kind=folder');
      if (path) {
        byId('folders').value = [byId('folders').value.trim(), path].filter(Boolean).join('\n');
        request = null;
      }
    } catch (error) { report(error); }
  };
  byId('pickFiles').onclick = () => byId('files').click();
  byId('files').onchange = () => {
    uploaded = [];
    request = null;
    const count = byId('files').files.length;
    byId('fileSummary').textContent = count ? count + ' videos selected' : '';
  };
  byId('cancel').onclick = async () => {
    byId('cancel').disabled = true;
    try { await api('/api/workbench/cancel', {id: current.id}); }
    catch (error) { byId('cancel').disabled = false; report(error); }
  };
  byId('resume').onclick = async () => {
    busy(true);
    byId('toolError').hidden = true;
    try {
      current = await api('/api/workbench/resume', {id: current.id});
      await watch(current.id);
    } catch (error) { watchError(error); }
  };

  const exportDialog = byId('exportDialog');
  byId('choices').onchange = select;
  byId('export').onclick = () => exportDialog.showModal();
  byId('closeExport').onclick = () => exportDialog.close();
  byId('download').onclick = () => exportDialog.close();
  byId('exportXml').onclick = async () => {
    const group = groups[Number(byId('choices').value)];
    byId('exportXml').disabled = true;
    byId('exportError').textContent = '';
    try {
      const response = await send('/api/workbench/match-cut-review', {
        project: result.project, group: group.id, revision: group.revision, action: 'insert_group', download: true,
      });
      if (!response.ok) await window.storylensResponse(response);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = 'Match Cut.xml';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      exportDialog.close();
    } catch (error) {
      byId('exportError').textContent = window.storylensProblem(error).message;
    } finally { byId('exportXml').disabled = false; }
  };

  const saved = localStorage.getItem(storageKey);
  if (saved && /^[a-f0-9]{32}$/.test(saved)) {
    busy(true);
    watch(saved).catch(watchError);
  }
  window.addEventListener('pagehide', () => clearTimeout(pollTimer));
})();
