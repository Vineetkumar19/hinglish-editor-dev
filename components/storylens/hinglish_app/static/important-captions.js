(() => {
  const $ = id => document.getElementById(id);
  const status = $('status');
  let busy = false, transcriptJob = null, words = [], highlights = [];
  const stamp = seconds => new Date(seconds * 1000).toISOString().slice(11, 19);
  async function api(path, body) {
    const response = await fetch(path, {
      method: body ? 'POST' : 'GET',
      headers: {'Content-Type': 'application/json', 'X-Hinglish-Token': window.storylensImportantToken},
      ...(body ? {body: JSON.stringify(body)} : {}),
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Caption request failed.');
    return data;
  }
  async function job(payload) {
    let result = await api('/api/captions/important/start', payload);
    const id = result.id;
    while (result.status === 'running') {
      await new Promise(resolve => setTimeout(resolve, 1500));
      result = await api('/api/captions/important/status?id=' + encodeURIComponent(id));
    }
    if (result.status !== 'complete') throw Error(result.error || 'Caption job interrupted.');
    return result;
  }
  function options() {
    const search = $('word-search').value.trim().toLowerCase();
    const matching = words.filter(word => !search || word.text.toLowerCase().includes(search));
    $('word-list').replaceChildren(...matching.slice(0, 100).map(word =>
      new Option(stamp(word.start) + ' · ' + word.text, word.id)));
    $('add').disabled = busy || !matching.length;
  }
  function draw() {
    highlights.sort((a, b) => a.first - b.first);
    const nodes = highlights.map((cue, index) => {
      const row = document.createElement('div');
      row.className = 'cue-row';
      const time = document.createElement('time');
      time.textContent = stamp(words[cue.first].start);
      const text = document.createElement('input');
      text.value = cue.text;
      text.maxLength = 80;
      text.setAttribute('aria-label', 'Highlight ' + (index + 1));
      text.oninput = () => { cue.text = text.value; $('output').hidden = true; };
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = 'Remove';
      remove.onclick = () => { highlights.splice(index, 1); $('output').hidden = true; draw(); };
      row.append(time, text, remove);
      return row;
    });
    $('highlights').replaceChildren(...nodes);
    $('build').disabled = busy || !highlights.length;
  }
  function setBusy(value) {
    busy = value;
    $('source').disabled = $('script').disabled = $('transcribe').disabled = value;
    $('review').inert = value;
    $('build').disabled = value || !highlights.length;
  }
  $('source').oninput = () => {
    transcriptJob = null;
    $('review').hidden = true;
    status.textContent = '';
  };
  $('input-form').onsubmit = async event => {
    event.preventDefault();
    if (busy) return;
    transcriptJob = null;
    $('review').hidden = true;
    $('output').hidden = true;
    status.textContent = 'Transcribing and finding highlights…';
    setBusy(true);
    try {
      const source = $('source').value.trim().replace(/^"(.*)"$/, '$1');
      const completed = await job({action:'transcribe', source, script:$('script').value, suggest:true});
      transcriptJob = completed.id;
      words = completed.result.words;
      highlights = completed.result.highlights;
      $('review').hidden = false;
      status.textContent = completed.result.suggestion_error ?
        'Transcript ready. ChatGPT suggestions unavailable. Add words below.' :
        highlights.length ? '' : 'No highlights suggested. Add words below.';
      options();
      draw();
    } catch (error) { status.textContent = error.message; }
    finally { setBusy(false); options(); }
  };
  $('word-search').oninput = options;
  $('add').onclick = () => {
    if (busy || !$('word-list').value) return;
    const first = Number($('word-list').value);
    const last = Math.min(words.length - 1, first + Number($('word-count').value) - 1);
    if (highlights.some(cue => first <= cue.last && last >= cue.first)) {
      status.textContent = 'That phrase overlaps an existing highlight.';
      return;
    }
    highlights.push({first, last, text: words.slice(first, last + 1).map(word => word.text).join(' ')});
    $('output').hidden = true;
    status.textContent = '';
    draw();
  };
  $('build').onclick = async () => {
    if (busy || !transcriptJob || !highlights.length) return;
    if (highlights.some(cue => !cue.text.trim() || cue.text.trim().split(/\s+/).length > 8)) {
      status.textContent = 'Enter 1–8 words in each highlight.';
      return;
    }
    $('output').hidden = true;
    status.textContent = 'Building captions…';
    setBusy(true);
    try {
      const {result} = await job({action:'build-reviewed', transcript_job:transcriptJob, highlights});
      status.textContent = 'Captions ready';
      $('output').textContent = 'Timeline: ' + result.xml + ' · Captions: ' + result.srt;
      $('output').hidden = false;
    } catch (error) { status.textContent = error.message; }
    finally { setBusy(false); }
  };
})();
