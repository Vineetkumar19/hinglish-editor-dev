(() => {
 const $ = id => document.getElementById(id);
 const token = document.documentElement.dataset.token;
 const cards = $('style-cards');
 const choice = $('doc-style-card');
 const feedback = $('style-feedback');
 let inspected;

 async function api(path, body) {
  const response = await window.storylensFetch('/api/workbench/' + path, {
   method: body ? 'POST' : 'GET',
   headers: {'X-Hinglish-Token':token,'Content-Type':'application/json'},
   ...(body ? {body:JSON.stringify(body)} : {}),
  });
  return window.storylensResponse(response);
 }

 function envelope(id, revision, hash) {
  const command = crypto.randomUUID();
  return {id,command_id:command,idempotency_key:command,expected_revision:revision,input_hashes:[hash],settings_version:1};
 }

 async function refresh() {
  const data = await api('reference-styles');
  const previous = choice.value;
  choice.replaceChildren(new Option('Use the documentary recipe', ''));
  $('approved-style-patterns').replaceChildren();
  cards.replaceChildren();
  for (const card of data.cards) {
   if (card.patterns.some(pattern => pattern.state === 'accepted')) choice.append(new Option(card.title, card.id));
   const details = document.createElement('details');
   const title = document.createElement('summary');
   title.textContent = card.title + ' · revision ' + card.revision;
   const source = document.createElement('p');
   source.textContent = card.reference.url + ' · SHA-256 ' + card.reference.hash;
   const table = document.createElement('table');
   const heading = table.createTHead().insertRow();
   for (const label of ['Range (s)','Role','Evidence','Shot','Narration','Text','Sound','Transition']) {
    const cell = document.createElement('th');
    cell.textContent = label;
    heading.append(cell);
   }
   const body = table.createTBody();
   for (const row of card.events) {
    const line = body.insertRow();
    for (const text of [row.start+'–'+row.end,row.role,row.certainty,row.shot,row.narration,row.text,row.sound,row.transition]) {
     line.insertCell().textContent = text;
    }
   }
   const rhythm = document.createElement('p');
   rhythm.textContent = 'Shot lengths ' + card.rhythm.shot_lengths.join(', ') + ' s. ' +
    [card.rhythm.silence,card.rhythm.speech_density,card.rhythm.music_intensity].filter(Boolean).join(' · ');
   details.append(title,source,table,rhythm);
   for (const pattern of card.patterns) {
    const row = document.createElement('p');
    row.textContent = pattern.constraint + ' · ' + pattern.state + ' · Events ' + pattern.evidence.join(', ') + ' ';
    for (const [label,decision] of [['Accept pattern','accepted'],['Reject pattern','rejected']]) {
     const button = document.createElement('button');
     button.type = 'button';
     button.textContent = label;
     button.onclick = async () => {
      button.disabled = true;
      try {
       await api('reference-pattern-review',{...envelope(card.id,card.revision,card.reference.hash),
        pattern_id:pattern.id,decision,reviewer:$('style-reviewer').value});
       await refresh();
       feedback.textContent = 'Pattern review saved.';
      } catch (error) { feedback.textContent = error.message; }
      finally { button.disabled = false; }
     };
     row.append(button);
    }
    details.append(row);
   }
   cards.append(details);
  }
  choice.value = [...choice.options].some(option => option.value === previous) ? previous : '';
  choice.onchange = () => {
   const card = data.cards.find(row => row.id === choice.value);
   const patterns = card?.patterns.filter(pattern => pattern.state === 'accepted') || [];
   $('approved-style-patterns').textContent = patterns.map(pattern => pattern.constraint).join(' · ');
  };
  choice.onchange();
 }

 function reference() { return {path:$('style-path').value,url:$('style-url').value}; }
 $('style-inspect').onclick = async () => {
  try {
   inspected = await api('reference-inspect',reference());
   feedback.textContent = 'Reference verified. ' + inspected.duration.toFixed(2) + ' s · ' + inspected.hash;
  } catch (error) { feedback.textContent = error.message; }
 };
 $('style-form').onsubmit = async event => {
  event.preventDefault();
  try {
   if (!inspected) throw Error('Inspect the exact reference first.');
   const id = crypto.randomUUID().replaceAll('-','');
   await api('reference-style',{...envelope(id,0,inspected.hash),reference:reference(),
    title:$('style-title').value,events:JSON.parse($('style-events').value),patterns:JSON.parse($('style-patterns').value),
    rhythm:{silence:$('style-silence').value,speech_density:$('style-speech').value,music_intensity:$('style-music').value}});
   await refresh();
   feedback.textContent = 'Reference saved for review. Accept individual patterns to make them available to planning.';
  } catch (error) { feedback.textContent = error.message; }
 };
 refresh().catch(error => { feedback.textContent = error.message; });
})();
