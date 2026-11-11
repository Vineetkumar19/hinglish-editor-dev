(() => {
  const $ = id => document.getElementById(id);
  const token = document.documentElement.dataset.token;
  const preset = [0.7, 0.6, 0.5];
  const storage = 'storylens.selectiveSlowMotion';
  let scan, moment, plans, active, lastRender, pending = false, uploaded = [];

  if (new URLSearchParams(location.search).get('embedded') === '1') document.body.dataset.embedded = '';

  function url(name, params) {
    return '/api/workbench/' + name + '?' + new URLSearchParams(params);
  }

  async function api(path, body) {
    const response = await window.storylensFetch(path, {
      method: body ? 'POST' : 'GET',
      headers: {'Content-Type': 'application/json', 'X-Hinglish-Token': token},
      ...(body ? {body: JSON.stringify(body)} : {}),
    });
    return window.storylensResponse(response);
  }

  function error(reason) {
    $('toolError').hidden = false;
    $('toolError').textContent = window.storylensProblem(reason).message;
  }

  function busy(value) {
    pending = value;
    for (const control of document.querySelectorAll('#scan button, #scan input, #scan textarea, #scan select, #render button, #render input, #render select, #moments, #batch')) {
      control.disabled = value;
    }
    if (!value) {
      $('batch').disabled = !scan?.result?.moments?.length;
      $('addPoint').disabled = !moment || currentPoints().length >= 8;
    }
    $('cancel').hidden = !value || !active;
    $('progress').hidden = !value;
  }

  function remember() {
    const options = {backend: $('backend').value, audio: $('audio').value,
      folder: $('folder').value,
      lock: $('lock').checked, slot: $('slot').value, variant: $('variant').selectedIndex,
      enabled: [...$('alternates').querySelectorAll('input')].map(input => input.checked)};
    localStorage.setItem(storage, JSON.stringify({scan: scan?.id, moment: moment?.id, plans, lastRender, active, options}));
    $('slowHistory').hidden = !scan?.id && !lastRender;
  }

  function length() {
    return Number((moment.end - moment.start).toFixed(8));
  }

  function constant(speed) {
    return [{offset: 0, speed}, {offset: length(), speed}];
  }

  function currentPoints() {
    return plans[$('variant').selectedIndex];
  }

  function field(row, label, value, min, max, locked, update) {
    const wrapper = document.createElement('label');
    wrapper.textContent = label;
    const input = document.createElement('input');
    input.type = 'number';
    input.step = 'any';
    input.required = true;
    input.min = min;
    input.max = max;
    input.value = value;
    input.readOnly = locked;
    input.addEventListener('input', () => { update(input.valueAsNumber); curve(); remember(); });
    wrapper.append(input);
    row.append(wrapper);
  }

  function editPoints() {
    $('pointRows').replaceChildren();
    const points = currentPoints();
    points.forEach((point, index) => {
      const row = document.createElement('div');
      row.className = 'speed-row';
      const endpoint = index === 0 || index === points.length - 1;
      field(row, 'Offset (s)', point.offset, 0, length(), endpoint, value => { point.offset = value; });
      field(row, 'Speed (×)', point.speed, .5, 1, false, value => { point.speed = value; });
      if (!endpoint) {
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = 'Remove';
        remove.setAttribute('aria-label', 'Remove speed point ' + (index + 1));
        remove.onclick = () => { points.splice(index, 1); editPoints(); remember(); };
        row.append(remove);
      }
      $('pointRows').append(row);
    });
    $('addPoint').disabled = points.length >= 8;
    curve();
  }

  function curve() {
    const points = currentPoints();
    const chart = $('curve');
    chart.replaceChildren();
    if (points.some(point => !Number.isFinite(point.offset) || !Number.isFinite(point.speed))) return;
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    line.setAttribute('points', points.map(point => (4 + 272 * point.offset / length()) + ',' + (54 - 48 * (point.speed - .5) / .5)).join(' '));
    chart.append(line);
    let seconds = 0;
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i];
      const span = b.offset - a.offset, difference = b.speed - a.speed;
      seconds += Math.abs(difference) < 1e-7 ? span / a.speed : span * Math.log(b.speed / a.speed) / difference;
    }
    $('curveInfo').textContent = length().toFixed(2) + ' s source · ' + seconds.toFixed(2) + ' s planned · ' + Math.round(seconds * 30) + ' frames';
  }

  function selectMoment(id, savedPlans) {
    moment = scan.result.moments.find(row => row.id === id);
    $('momentEditor').hidden = !moment;
    if (!moment) return;
    $('moments').value = id;
    plans = savedPlans || preset.map(constant);
    $('variant').selectedIndex = 0;
    editPoints();
    $('sourceNote').textContent = 'Original speed · ' + moment.start.toFixed(2) + '–' + moment.end.toFixed(2) +
      ' s · action near ' + moment.event.toFixed(2) + ' s · try ' + moment.recommended.toFixed(1) + '×. ' + moment.review_risk + '.';
    $('sourcePreview').src = url('slow-motion-media', {id: scan.id, moment: moment.id, token});
    remember();
  }

  function name(path) {
    return path.replaceAll('\\', '/').split('/').pop();
  }

  function showScan(job, selected, savedPlans) {
    scan = job;
    const result = job.result;
    $('review').hidden = false;
    $('moments').replaceChildren();
    $('scanDetails').replaceChildren();
    for (const item of result.sources) {
      const entry = document.createElement('li');
      entry.textContent = name(item.source) + ' · ' + item.reason;
      $('scanDetails').append(entry);
    }
    $('skipped').hidden = !result.sources.length;
    $('moments').disabled = !result.moments.length;
    $('batch').disabled = !result.moments.length;
    for (const row of result.moments) {
      const option = document.createElement('option');
      option.value = row.id;
      option.textContent = name(row.source) + ' · ' + row.start.toFixed(2) + '–' + row.end.toFixed(2) + ' s';
      $('moments').append(option);
    }
    if (!result.moments.length) $('moments').append(new Option('No qualifying moving shots'));
    $('toolStatus').textContent = result.moments.length + ' suggested moments · ' + result.scanned + ' files checked.';
    selectMoment(selected || result.moments[0]?.id, savedPlans);
    remember();
  }

  async function showRender(job) {
    $('results').hidden = false;
    $('outputRange').textContent = job.result.variants.length + ' previews · 30 fps · Approve only after checking the action, edges and cadence.';
    $('outputs').replaceChildren();
    $('recipe').href = url('slow-motion-media', {id: job.id, part: 'recipe', token, download: 1});
    const review = await api(url('slow-motion-media', {id: job.id, part: 'review'}));
    exportLinks(job.id, review);
    for (const [index, item] of job.result.variants.entries()) {
      const card = document.createElement('article');
      card.className = 'shot-card';
      const label = item.preset.toFixed(1) + '× variant';
      const title = document.createElement('h3');
      title.textContent = item.moment.label + ' · ' + label;
      card.append(title);
      if (item.state === 'render-rejected') {
        const failure = document.createElement('p');
        failure.textContent = 'Render rejected · ' + item.reason;
        card.append(failure);
        $('outputs').append(card);
        continue;
      }
      const video = document.createElement('video');
      video.setAttribute('aria-label', label);
      video.controls = true;
      video.preload = 'metadata';
      video.playsInline = true;
      video.src = url('slow-motion-media', {id: job.id, part: index, token});
      const caption = document.createElement('p');
      caption.className = 'shot-caption';
      caption.textContent = name(item.moment.source) + ' · ' + item.duration.toFixed(2) + ' s · ' + item.method +
        ' · action frame ' + item.impact_frame + ' · ' + item.near_repeat_pairs + ' near-repeat pairs';
      const notes = document.createElement('textarea');
      notes.className = 'review-note';
      notes.rows = 2;
      notes.maxLength = 1200;
      notes.setAttribute('aria-label', 'Visual review note for ' + title.textContent);
      notes.placeholder = 'Describe motion quality or visible artifacts';
      const state = document.createElement('p');
      state.className = 'muted';
      const actions = document.createElement('div');
      actions.className = 'input-row';
      const exports = document.createElement('div');
      exports.className = 'editor-exports';
      function displayDecision(value) {
        window.storylensEditors.renderMedia(exports,value.exports?.[index]);
        const decision = value.decisions[index];
        state.textContent = decision ? decision.decision + ' · ' + decision.notes : 'Waiting for visual review';
        if (decision) notes.value = decision.notes;
      }
      displayDecision(review);
      for (const decision of ['approve', 'reject']) {
        const button = document.createElement('button');
        button.textContent = decision === 'approve' ? 'Approve export' : 'Reject preview';
        button.onclick = async () => {
          button.disabled = true;
          $('toolError').hidden = true;
          try {
            const saved = await api('/api/workbench/slow-motion-review', {id: job.id, variant: index, decision, notes: notes.value});
            displayDecision(saved);
            exportLinks(job.id, saved);
          } catch (reason) { error(reason); }
          finally { button.disabled = false; }
        };
        actions.append(button);
      }
      card.append(video, caption, notes, actions, state, exports, nativeControls(job, item, index));
      $('outputs').append(card);
    }
    lastRender = job.id;
    remember();
  }

  function exportLinks(id, state) {
    const available = Object.keys(state.decisions).length > 0;
    $('open').hidden = !available;
    $('manifest').hidden = !available;
    $('manifest').href = url('slow-motion-media', {id, part: 'manifest', token, download: 1});
  }

  function nativeControls(job, item, index) {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Adobe comparison';
    const select = document.createElement('select');
    select.setAttribute('aria-label', 'Adobe editor');
    select.append(new Option('Premiere Optical Flow', 'premiere'), new Option('After Effects Pixel Motion', 'aftereffects'));
    const generate = document.createElement('button');
    generate.textContent = 'Prepare native request';
    const file = document.createElement('input');
    file.className = 'native-path';
    file.setAttribute('aria-label', 'Native rendered MP4 path');
    file.placeholder = 'Path to the rendered native MP4';
    const attach = document.createElement('button');
    attach.textContent = 'Check and attach native render';
    const status = document.createElement('p');
    status.className = 'muted';
    const playback = document.createElement('video');
    playback.controls = true;
    playback.hidden = true;
    playback.preload = 'metadata';
    playback.setAttribute('aria-label', 'Adobe comparison preview');
    const note = document.createElement('textarea');
    note.className = 'review-note';
    note.rows = 2;
    note.maxLength = 1200;
    note.placeholder = 'Describe the native render quality and comparison';
    note.setAttribute('aria-label', 'Native visual review note');
    const approve = document.createElement('button');
    approve.textContent = 'Approve native export';
    const reject = document.createElement('button');
    reject.textContent = 'Reject native render';
    const reviewControls = document.createElement('div');
    reviewControls.hidden = true;
    reviewControls.append(note, approve, reject);
    let selectedEditor = select.value;
    let refreshEpoch = 0;
    async function refresh() {
      const epoch = ++refreshEpoch;
      const editor = select.value;
      approve.disabled = reject.disabled = true;
      reviewControls.hidden = playback.hidden = true;
      const result = await api('/api/workbench/slow-motion-native-status', {id: job.id, variant: index, editor});
      if (select.value !== editor || epoch !== refreshEpoch) return;
      selectedEditor = editor;
      playback.hidden = !result.imported;
      reviewControls.hidden = !result.imported;
      if (result.imported) playback.src = url('slow-motion-media', {id: job.id, part: index, native: editor, token});
      else { playback.removeAttribute('src'); playback.load(); }
      note.value = result.decision?.notes || '';
      status.textContent = result.decision ? result.decision.decision + ' · ' + result.decision.notes :
        (result.imported ? result.imported.frames + ' matching frames · Inspect motion and edges before approval.' : 'Prepare a request, then attach the matching native render.');
      approve.disabled = reject.disabled = false;
    }
    for (const [button, decision] of [[approve, 'approve'], [reject, 'reject']]) {
      button.onclick = async () => {
        button.disabled = true;
        try {
          const result = await api('/api/workbench/slow-motion-review', {
            id: job.id, variant: index, editor: selectedEditor, decision, notes: note.value,
          });
          exportLinks(job.id, result);
          await refresh();
        } catch (reason) { error(reason); }
        finally { button.disabled = false; }
      };
    }
    select.onchange = () => { playback.pause(); refresh().catch(error); };
    async function run(button, action, payload, done) {
      button.disabled = true;
      status.textContent = 'Working…';
      try {
        const result = await api('/api/workbench/slow-motion-native-' + action, {
          id: job.id, variant: index, editor: select.value, ...payload,
        });
        done(result);
      } catch (reason) { status.textContent = window.storylensProblem(reason).message; }
      finally { button.disabled = false; }
    }
    generate.onclick = () => run(generate, 'request', {}, result => { status.textContent = result.folder; });
    attach.onclick = () => run(attach, 'import', {path: file.value.trim()}, result => {
      refresh().catch(error);
    });
    details.append(summary, select, generate, file, attach, status, playback, reviewControls);
    details.ontoggle = () => { if (details.open) refresh().catch(error); };
    return details;
  }

  async function watch(id) {
    active = id;
    remember();
    busy(true);
    $('retry').hidden = true;
    let job;
    do {
      job = await api(url('job', {id}));
      $('toolStatus').textContent = job.stage;
      $('progress').value = job.progress || 0;
      if (['queued', 'running'].includes(job.status)) await new Promise(resolve => setTimeout(resolve, 750));
    } while (['queued', 'running'].includes(job.status));
    active = null;
    busy(false);
    if (job.status === 'complete') {
      if (job.kind === 'slow-motion-scan') showScan(job);
      else {
        await showRender(job);
        $('toolStatus').textContent = job.result.variants.filter(row => row.state === 'awaiting-review').length + ' previews ready for visual review.';
      }
    } else if (job.status !== 'cancelled') {
      $('retry').hidden = !['failed', 'interrupted'].includes(job.status);
      $('retry').dataset.job = job.id;
      error(job.error || Error(job.stage));
    }
    remember();
  }

  function failed(reason) {
    busy(false);
    if (active) {
      $('retry').hidden = false;
      $('retry').dataset.job = active;
      $('cancel').hidden = false;
    }
    error(reason);
  }

  $('browse').onclick = async () => {
    try {
      const choice = await api('/api/pick?kind=folder');
      if (choice.path) $('folder').value = [$('folder').value.trim(), choice.path].filter(Boolean).join('\n');
    } catch (reason) { error(reason); }
  };
  $('addVideos').onclick = () => $('files').click();
  $('files').onchange = () => {
    uploaded = [];
    $('filesSummary').textContent = $('files').files.length + ' videos selected';
  };
  $('scan').onsubmit = async event => {
    event.preventDefault();
    if (pending || active) return;
    const history = $('slowHistory');
    history.open = false;
    for (const id of ['review','results']) { const panel = $(id); history.before(panel); panel.hidden = true; }
    const files = [...$('files').files];
    $('toolError').hidden = true;
    busy(true);
    try {
      if (files.length > 100) throw Error('Choose at most 100 videos.');
      for (let i = uploaded.length; i < files.length; i++) {
        $('toolStatus').textContent = 'Adding video ' + (i + 1) + ' of ' + files.length;
        const file = files[i];
        const response = await window.storylensFetch('/api/cinematic/upload?' + new URLSearchParams({name: file.name}), {
          method: 'POST', headers: {'Content-Type': 'application/octet-stream', 'X-Hinglish-Token': token}, body: file,
        });
        uploaded.push((await window.storylensResponse(response)).path);
      }
      const job = await api('/api/workbench/slow-motion-scan', {
        folders: $('folder').value.split(/\r?\n/).map(path => path.trim()).filter(Boolean), paths: uploaded,
        idempotency_key: crypto.randomUUID(),
      });
      await watch(job.id);
    } catch (reason) { failed(reason); }
  };
  $('moments').onchange = () => selectMoment($('moments').value);
  $('variant').onchange = () => { editPoints(); remember(); };
  for (const control of document.querySelectorAll('#backend, #audio, #lock, #slot, #alternates input'))
    control.addEventListener('change', remember);
  $('resetPoints').onclick = () => {
    const index = $('variant').selectedIndex;
    plans[index] = constant(preset[index]);
    editPoints();
    remember();
  };
  $('addRamps').onclick = () => {
    const index = $('variant').selectedIndex;
    const edge = Math.min(.35, length() / 4);
    plans[index] = [{offset: 0, speed: 1}, {offset: edge, speed: preset[index]},
      {offset: length() - edge, speed: preset[index]}, {offset: length(), speed: 1}];
    editPoints();
    remember();
  };
  $('addPoint').onclick = () => {
    const points = currentPoints();
    let largest = 1;
    for (let i = 2; i < points.length; i++) {
      if (points[i].offset - points[i - 1].offset > points[largest].offset - points[largest - 1].offset) largest = i;
    }
    const left = points[largest - 1], right = points[largest];
    points.splice(largest, 0, {offset: (left.offset + right.offset) / 2, speed: (left.speed + right.speed) / 2});
    editPoints();
    remember();
  };
  const preview = $('sourcePreview');
  preview.onloadedmetadata = () => { if (moment) preview.currentTime = moment.start; };
  preview.onplay = () => {
    if (moment && (preview.currentTime < moment.start || preview.currentTime >= moment.end)) preview.currentTime = moment.start;
  };
  preview.ontimeupdate = () => { if (moment && preview.currentTime >= moment.end) preview.pause(); };
  preview.onerror = () => { $('sourceNote').textContent = 'Original format cannot play here. The MP4 exports can still be previewed.'; };
  $('render').onsubmit = async event => {
    event.preventDefault();
    if (pending || active || !moment) return;
    $('toolError').hidden = true;
    busy(true);
    try {
      const enabled = [...$('alternates').querySelectorAll('input')];
      const job = await api('/api/workbench/slow-motion-render', {
        scan_id: scan.id, moment_id: moment.id, variants: plans.map((plan, i) => enabled[i].checked ? plan : null),
        backend: $('backend').value, audio: $('audio').value,
        lock_from: $('lock').checked ? lastRender : null, slot_frames: $('slot').valueAsNumber || null,
      });
      await watch(job.id);
    } catch (reason) { failed(reason); }
  };
  $('batch').onclick = async () => {
    if (pending || active || !scan) return;
    $('toolError').hidden = true;
    busy(true);
    try {
      const job = await api('/api/workbench/slow-motion-render', {
        scan_id: scan.id, batch: true, backend: $('backend').value, audio: $('audio').value,
      });
      await watch(job.id);
    } catch (reason) { failed(reason); }
  };
  $('cancel').onclick = () => active && api('/api/workbench/cancel', {id: active}).catch(error);
  $('retry').onclick = async () => {
    if (pending) return;
    $('toolError').hidden = true;
    busy(true);
    try {
      const id = $('retry').dataset.job;
      if (!active) await api('/api/workbench/resume', {id});
      await watch(id);
    } catch (reason) { failed(reason); }
  };
  $('open').onclick = () => api('/api/workbench/slow-motion-open', {id: lastRender}).catch(error);

  async function restore(saved) {
    $('slowHistory').append($('review'),$('results'));
    if (typeof saved.options?.folder === 'string') $('folder').value = saved.options.folder;
    if (saved.scan) showScan(await api(url('job', {id: saved.scan})), saved.moment, saved.plans);
    if (saved.lastRender) await showRender(await api(url('job', {id: saved.lastRender})));
    if (saved.options) {
      const settings = saved.options;
      if (['interpolate','repeat','blend'].includes(settings.backend)) $('backend').value = settings.backend;
      if (['mute','pitch','separate'].includes(settings.audio)) $('audio').value = settings.audio;
      $('lock').checked = settings.lock === true;
      $('slot').value = settings.slot || '';
      if (Array.isArray(settings.enabled) && settings.enabled.length === 3)
        [...$('alternates').querySelectorAll('input')].forEach((input,i) => { input.checked = settings.enabled[i] === true; });
      if (moment && [0,1,2].includes(settings.variant)) { $('variant').selectedIndex = settings.variant; editPoints(); }
      remember();
    }
    if (saved.active) await watch(saved.active);
  }
  const saved = JSON.parse(localStorage.getItem(storage) || '{}');
  $('slowHistory').hidden = !saved.scan && !saved.lastRender;
  $('restoreSlow').onclick = () => {
    if (pending || active) return;
    restore(JSON.parse(localStorage.getItem(storage) || '{}')).catch(failed);
  };
  if (saved.active) {
    $('slowHistory').open = true;
    restore(saved).catch(failed);
  }
})();
