(() => {
  const $ = id => document.getElementById(id);
  const status = $('status'), error = $('error'), form = $('analyze');
  let token, referenceUrl, draftUrl;
  let referenceFile, referenceId;

  async function request(path, options = {}) {
    token ??= (await (await fetch('/api/bridge')).json()).token;
    const response = await fetch(path, {
      ...options,
      headers: {...options.headers, 'X-Hinglish-Token': token},
    });
    if (!response.ok) {
      const issue = await response.json();
      throw Error(issue.error_details || issue.error || 'Reference Reel request failed.');
    }
    return response;
  }
  const api = (route, data) => request('/api/reference-reel/' + route, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data),
  }).then(response => response.json());

  function setPreview(name, url) {
    const player = $(name + '-player');
    player.src = url;
    player.hidden = false;
    $(name + '-empty').hidden = true;
  }

  function resetResult() {
    const player = $('draft-player');
    player.pause();
    player.removeAttribute('src');
    player.load();
    player.hidden = true;
    $('draft-empty').hidden = false;
    $('exports').hidden = true;
    $('exports').replaceChildren();
    if (draftUrl) URL.revokeObjectURL(draftUrl);
    draftUrl = undefined;
  }

  $('reference').onchange = () => {
    if (referenceUrl) URL.revokeObjectURL(referenceUrl);
    referenceFile = $('reference').files[0];
    referenceId = undefined;
    resetResult();
    if (referenceFile) {
      referenceUrl = URL.createObjectURL(referenceFile);
      setPreview('reference', referenceUrl);
    } else {
      $('reference-player').removeAttribute('src');
      $('reference-player').hidden = true;
      $('reference-empty').hidden = false;
    }
  };
  $('footage-folder').oninput = resetResult;
  $('pick-folder').onclick = async () => {
    $('pick-folder').disabled = true;
    try {
      const {path} = await (await request('/api/pick?kind=folder')).json();
      if (path) {
        $('footage-folder').value = path;
        resetResult();
      }
    } catch (issue) { error.textContent = issue.message; }
    finally { $('pick-folder').disabled = false; }
  };

  function download(label, result, name) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.onclick = async () => {
      button.disabled = true;
      try {
        const response = await request('/api/reference-reel/jobs/' + result.id + '/' + name);
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement('a');
        link.href = url;
        link.download = name;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
      } catch (issue) { error.textContent = issue.message; }
      finally { button.disabled = false; }
    };
    return button;
  }

  form.onsubmit = async event => {
    event.preventDefault();
    const inputs = [...form.querySelectorAll('input,button')];
    const folder = $('footage-folder').value.trim().replace(/^"(.*)"$/, '$1');
    if (!referenceFile || !folder) return;
    resetResult();
    error.textContent = '';
    inputs.forEach(input => input.disabled = true);
    try {
      if (!referenceId) {
        status.textContent = 'Loading reference…';
        const response = await request('/api/reference-reel/upload?name=' + encodeURIComponent(referenceFile.name),
          {method: 'POST', body: referenceFile});
        referenceId = (await response.json()).id;
      }
      status.textContent = 'Finding cuts and matching footage…';
      const analysis = await api('analyze', {reference: referenceId, folder});
      const missing = analysis.mappings.filter(mapping => !mapping.asset).length;
      if (missing) throw Error('No suitable footage for ' + missing + (missing === 1 ? ' shot.' : ' shots.'));
      status.textContent = 'Building preview…';
      const result = await api('export', {
        analysis: analysis.id,
        cuts: analysis.shots.map(shot => shot.start),
        mappings: analysis.mappings.map(mapping => ({...mapping, transition:'cut', transition_frames:0,
          speed_in:1, speed_out:1, speed_mid:null, zoom_in:100, zoom_out:100, exposure:0, contrast:0, flash_frame:null})),
        use_audio:false, allow_missing:false,
      });
      const preview = await request('/api/reference-reel/jobs/' + result.id + '/preview.mp4');
      draftUrl = URL.createObjectURL(await preview.blob());
      setPreview('draft', draftUrl);
      const labels = {'preview.mp4':'Download video', 'REFERENCE_REEL.xml':'Premiere / Resolve XML', 'reference-reel.jsx':'After Effects script'};
      for (const [name, label] of Object.entries(labels)) {
        if (result.files.includes(name)) $('exports').append(download(label, result, name));
      }
      $('exports').hidden = false;
      status.textContent = analysis.skipped_footage?.length ? 'Ready · ' + analysis.skipped_footage.length + ' files skipped' : 'Ready';
    } catch (issue) {
      status.textContent = '';
      error.textContent = issue.message;
    } finally { inputs.forEach(input => input.disabled = false); }
  };
})();
