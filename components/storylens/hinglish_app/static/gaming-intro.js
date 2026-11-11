(() => {
  const $ = id => document.getElementById(id);
  const token = document.documentElement.dataset.token;
  const source = $('gaming-intro-source');
  const create = $('gaming-intro-create');
  const browse = $('gaming-intro-browse');
  const resume = $('gaming-intro-resume');
  const status = $('gaming-intro-status');
  const result = $('gaming-intro-result');
  const history = $('gaming-intro-history');
  const storage = 'storylens.gaming-intro.history';
  let selected, timer, submission;
  let entries = [];
  try { entries = JSON.parse(localStorage.getItem(storage) || '[]'); } catch (_) {}
  const api = async (path, body) => window.storylensResponse(await window.storylensFetch(path, {
    method: body ? 'POST' : 'GET',
    headers: {'X-Hinglish-Token': token, 'Content-Type': 'application/json'},
    ...(body ? {body: JSON.stringify(body)} : {})
  }));
  const jobPath = '/api/workbench/job?id=';
  const showError = error => {
    status.textContent = window.storylensError(error);
    create.disabled = false;
  };

  function showHistory() {
    const buttons = entries.map(entry => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = entry.name;
      button.onclick = () => open(entry.id);
      return button;
    });
    history.querySelector('div').replaceChildren(...buttons);
    history.hidden = buttons.length === 0;
  }
  function remember(id, name) {
    entries = [{id, name}, ...entries.filter(entry => entry.id !== id)].slice(0, 12);
    try { localStorage.setItem(storage, JSON.stringify(entries)); } catch (_) {}
    showHistory();
  }
  function media(id, params = {}) {
    return '/api/workbench/gaming-intro-media?' + new URLSearchParams({id, token, ...params});
  }
  function showResult(job) {
    const {source_name, seconds, cuts} = job.result;
    const title = document.createElement('h2');
    title.textContent = 'Gaming intro · ' + Number(seconds.toFixed(2)) + ' s · ' + cuts.length + ' clips';
    const player = document.createElement('video');
    player.controls = true;
    player.playsInline = true;
    player.preload = 'metadata';
    player.style.width = 'min(100%, 720px)';
    player.src = media(job.id);
    const links = document.createElement('div');
    links.className = 'hook-options';
    for (const [label, options] of [['Download intro', {download:'1'}], ['Download editable intro + replay timeline', {asset:'timeline'}]]) {
      const link = document.createElement('a');
      link.className = 'button';
      link.href = media(job.id, options);
      link.textContent = label;
      links.append(link);
    }
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Selected commentary';
    const list = document.createElement('ol');
    for (const cut of cuts) {
      const item = document.createElement('li');
      item.textContent = cut.text + ' (' + cut.reason + ')';
      list.append(item);
    }
    details.append(summary, list);
    result.replaceChildren(title, player, links, details);
    status.textContent = 'Ready to review. The timeline starts ' + source_name + ' after the 30-second opener.';
  }
  async function watch(id) {
    const job = await api(jobPath + encodeURIComponent(id));
    if (selected !== id) return;
    if (job.kind !== 'gaming-intro') throw Error('Choose a saved gaming intro.');
    const active = ['queued','running'].includes(job.status);
    create.disabled = active;
    resume.hidden = !['failed','interrupted'].includes(job.status) || (job.resume_attempts || 0) >= 3;
    status.textContent = job.error?.message || job.stage;
    if (active) {
      timer = setTimeout(() => watch(id).catch(showError), 1000);
    } else if (job.status === 'complete') {
      showResult(job);
    }
  }
  function open(id) {
    clearTimeout(timer);
    selected = id;
    result.replaceChildren();
    resume.hidden = true;
    watch(id).catch(showError);
  }
  browse.onclick = async () => {
    try {
      const {path} = await api('/api/pick?kind=handoff-video');
      if (path) source.value = path;
    } catch (error) { showError(error); }
  };
  resume.onclick = async () => {
    const id = selected;
    resume.disabled = true;
    try {
      await api('/api/workbench/resume', {id});
      open(id);
    } catch (error) { showError(error); }
    finally { resume.disabled = false; }
  };
  window.storylensGamingIntro = {async create() {
    const path = source.value.trim();
    if (create.disabled) return;
    if (!path) {
      status.textContent = 'Choose a downloaded gaming replay with commentary.';
      source.focus();
      return;
    }
    if (submission?.source !== path) submission = {source:path, idempotency_key:crypto.randomUUID()};
    create.disabled = true;
    try {
      const job = await api('/api/workbench/gaming-intro', submission);
      submission = null;
      remember(job.id, path.split(/[\\/]/).pop());
      history.open = false;
      open(job.id);
    } catch (error) { showError(error); }
  }};
  showHistory();
  window.addEventListener('beforeunload', () => clearTimeout(timer));
})();
