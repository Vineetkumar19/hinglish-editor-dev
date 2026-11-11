(()=>{
 const $=id=>document.getElementById(id),token=document.documentElement.dataset.token;
 let bank=null,timer=null,editRecipes={};const recipeIds=['EDIT_CIN_A_v1','EDIT_CIN_B_v1','EDIT_CIN_C_v1'];
 async function api(path,body){const r=await window.storylensFetch('/api/workbench/'+path,{method:body?'POST':'GET',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});return window.storylensResponse(r);}
 function error(e){$('status').textContent=e.message;}
 function showResume(job) {
  $('resume').hidden = !['failed', 'interrupted'].includes(job.status) || (job.resume_attempts || 0) >= 3;
 }
 $('resume').onclick = async () => {
  const id = $('saved-job').value.trim();
  $('resume').disabled = true;
  try { await api('resume', {id}); await restore(id); }
  catch (e) { error(e); }
  finally { $('resume').disabled = false; }
 };
 $('load').onclick=async()=>{try{
  clearTimeout(timer);$('results').replaceChildren();$('create').disabled=true;editRecipes=(await api('sounds')).edit_recipes;
  bank=await api('curation?id='+encodeURIComponent($('datasets').value));$('choices').replaceChildren();
  if(!bank.body)throw Error('Open Cinematic Footage and save a story proposal first.');
  for(const [index,premise] of ['Destination tease','Journey momentum','Human reaction'].entries()){
   const field=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=String.fromCharCode(65+index)+' — '+premise;field.append(legend);
   editRecipes[recipeIds[index]].frames.forEach((frames,slot)=>{const label=document.createElement('label');label.textContent='Shot '+(slot+1)+' · '+(frames/30).toFixed(1)+'s';const select=document.createElement('select');select.id='shot-'+index+'-'+slot;select.setAttribute('aria-label',legend.textContent+' shot '+(slot+1));select.append(new Option('Choose source moment',''));for(const row of bank.candidates.filter(r=>r.review_state==='approved'&&!bank.body.banned?.includes(r.id)&&r.duration>=frames/30))select.append(new Option(row.source.split(/[\\/]/).pop()+' @ '+row.start.toFixed(2)+'s',row.id));label.append(select);field.append(label);});$('choices').append(field);
  }$('create').disabled=false;$('status').textContent='Choose source-backed moments for each premise. Use a different opening and at least half different moments.';
 }catch(e){error(e);}};
 $('create').onclick=async()=>{try{
  const rows=Object.fromEntries(bank.candidates.map(r=>[r.id,r]));
  const plans=['Destination tease','Journey momentum','Human reaction'].map((premise,i)=>({variant:'ABC'[i],premise,edit_recipe_id:recipeIds[i],edit_recipe_version:editRecipes[recipeIds[i]].version,fps:30,frame_count:150,body_revision:bank.revision,canvas:[720,1280],source_spans:editRecipes[recipeIds[i]].frames.map((frames,slot)=>{
   const row=rows[$('shot-'+i+'-'+slot).value];if(!row)throw Error('Choose every intro shot.');return {candidate_id:row.id,source_id:row.source_id,start:row.start,end:row.start+frames/30,frames};})}));
  const key=crypto.randomUUID(),plan_id=crypto.randomUUID().replaceAll('-','');
  $('create').disabled=true;
  await api('intro-plan',{dataset_id:bank.id,plan_id,mode:'cinematic',category:'travel',body_revision:bank.revision,plans,command_id:key,idempotency_key:key,expected_revision:0,input_hashes:[...new Set(plans.flatMap(p=>p.source_spans.map(s=>s.source_id)))].sort(),settings_version:1});
  const job=await api('intro-render',{plan_id,idempotency_key:key+':render'});localStorage.setItem('storylens.intro.preview',job.id);await watch(job.id);
 }catch(e){$('create').disabled=false;error(e);}};
 async function watch(id){$('saved-job').value=id;const job=await api('job?id='+id);showResume(job);$('status').textContent=job.stage;
  if(['queued','running'].includes(job.status)){timer=setTimeout(()=>watch(id).catch(error),1000);return;}
  $('create').disabled=!$('choices').children.length;if(job.status!=='complete')throw Error(job.error?.message||'Intro render stopped.');
  $('results').replaceChildren();job.result.intros.forEach((intro,i)=>{const section=document.createElement('section'),h=document.createElement('h2'),video=document.createElement('video');h.textContent='Intro '+'ABC'[i]+' · '+intro.frame_count+' frames';video.controls=true;video.preload='metadata';video.width=300;video.src='/api/workbench/intro-media?id='+id+'&variant='+i+'&token='+encodeURIComponent(token);section.append(h,video);const mix=document.createElement('input'),attach=document.createElement('button'),source=document.createElement('p');mix.setAttribute('aria-label','Recipe mix job for Intro '+'ABC'[i]);mix.placeholder='Completed recipe mix job ID';attach.textContent='Apply recipe mix to Intro '+'ABC'[i];source.textContent='Original audio for this recipe: '+intro.path;attach.onclick=async()=>{attach.disabled=true;try{const queued=await api('intro-sound',{intro_job_id:id,mix_job_id:mix.value.trim(),variant:i,idempotency_key:crypto.randomUUID()});localStorage.setItem('storylens.intro.preview',queued.id);await watch(queued.id);}catch(e){error(e);}finally{attach.disabled=false;}};section.append(source,mix,attach);
   if (job.kind === 'intro') section.append(replacementControls(job, i));
   $('results').append(section);
  });
  $('status').textContent='Three previews ready. Review story and audio; apply an approved recipe mix or create editable native comparisons separately.';
  const previousLabel = document.createElement('label');
  const previousComparison = document.createElement('input');
  previousComparison.placeholder = 'Optional comparison job ID from this body revision';
  previousLabel.append('Reuse unchanged trials from a previous comparison', previousComparison);
  $('results').append(previousLabel);
  const trials=document.createElement('button');trials.textContent='Compare all intros with the same body';trials.onclick=async()=>{try{if(!bank)throw Error('Load the matching footage bank first.');const queued=await api('trials-render',{dataset_id:bank.id,expected_revision:bank.revision,intro_job_id:id,mode:'prepend',previous_trial_job_id:previousComparison.value.trim() || undefined,idempotency_key:crypto.randomUUID()});localStorage.setItem('storylens.intro.trials',queued.id);await watchTrials(queued.id);}catch(e){error(e);}};$('results').append(trials);
 }
 function replacementControls(job, variant) {
  const panel = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Replace Intro ' + 'ABC'[variant];
  panel.append(summary);
  panel.addEventListener('toggle', async () => {
   if (!panel.open || panel.dataset.loaded) return;
   panel.dataset.loaded = 'true';
   try {
    const saved = await api('intro-plan?id=' + encodeURIComponent(job.request.plan_id));
    const dataset = await api('curation?id=' + encodeURIComponent(saved.dataset_id));
    if (dataset.revision !== saved.body_revision) throw Error('The body changed. Load the current footage bank.');
    const plan = saved.plans[variant];
    const rows = dataset.candidates.filter(row => row.review_state === 'approved' && !dataset.body.banned?.includes(row.id));
    const form = document.createElement('form');
    const selects = plan.source_spans.map((span, index) => {
     const label = document.createElement('label');
     label.textContent = 'Shot ' + (index + 1) + ' · ' + (span.frames / plan.fps).toFixed(2) + ' s';
     const select = document.createElement('select');
     for (const row of rows.filter(row => row.duration >= span.frames / plan.fps)) {
      select.append(new Option(row.source.split(/[\\/]/).pop() + ' @ ' + row.start.toFixed(2) + 's', row.id));
     }
     select.value = span.candidate_id;
     label.append(select);
     form.append(label);
     return select;
    });
    const submit = document.createElement('button');
    submit.textContent = 'Render replacement';
    form.append(submit);
    form.onsubmit = async event => {
     event.preventDefault();
     submit.disabled = true;
     try {
      const source_spans = plan.source_spans.map((span, index) => {
       if (span.candidate_id === selects[index].value) return span;
       const row = rows.find(row => row.id === selects[index].value);
       if (!row) throw Error('Choose a reviewed source moment for every shot.');
       return {candidate_id: row.id, source_id: row.source_id, start: row.start,
               end: row.start + span.frames / plan.fps, frames: span.frames};
      });
      const sourceIds = saved.plans.flatMap((item, index) => (index === variant ? source_spans : item.source_spans).map(span => span.source_id));
      const key = crypto.randomUUID();
      const queued = await api('replace-intro', {intro_job_id: job.id, variant, source_spans,
       plan_id: key.replaceAll('-', ''), command_id: key, idempotency_key: key,
       expected_revision: 0, input_hashes: [...new Set(sourceIds)].sort(), settings_version: 1});
      localStorage.setItem('storylens.intro.preview', queued.id);
      await watch(queued.id);
     } catch (e) { error(e); }
     finally { submit.disabled = false; }
    };
    panel.append(form);
   } catch (e) { error(e); delete panel.dataset.loaded; }
  });
  return panel;
 }
 async function watchTrials(id){$('saved-job').value=id;const job=await api('job?id='+id);showResume(job);$('status').textContent=job.stage;if(['queued','running'].includes(job.status)){timer=setTimeout(()=>watchTrials(id).catch(error),1000);return;}if(job.status!=='complete')throw Error(job.error?.message||'Trial assembly stopped.');
  bank=await api('curation?id='+encodeURIComponent(job.request.dataset_id));$('datasets').value=bank.id;$('create').disabled=true;$('choices').replaceChildren();$('results').replaceChildren();
  for(const [i,part] of ['body','0','1','2'].entries()){const section=document.createElement('section'),h=document.createElement('h2'),video=document.createElement('video');h.textContent=i?'Trial '+'ABC'[i-1]:'Body only';video.controls=true;video.width=300;video.src='/api/workbench/assembly-media?id='+id+'&part='+part+'&token='+encodeURIComponent(token);section.append(h,video);
   const download = document.createElement('a');
   download.href = video.src + '&download=1';
   download.textContent = i ? 'Download Trial ' + 'ABC'[i-1] : 'Download Body only';
   section.append(download);
   if (i) section.append(trialNotes(id, i-1));
   $('results').append(section);
  }
  $('status').textContent='Saved comparison '+id+'. All trials preserve the same decoded body frames. '+(bank.revision!==job.request.expected_revision?'This saved comparison is obsolete after a body edit. ':'')+'Review pacing, sound and the intro-to-body transition.';
 }
 function trialNotes(jobId, variant) {
  const panel = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Upload notes and observations';
  panel.append(summary);
  panel.addEventListener('toggle', async () => {
   if (!panel.open || panel.dataset.loaded) return;
   panel.dataset.loaded = 'true';
   const status = document.createElement('p');
   status.setAttribute('role', 'status');
   panel.append(status);
   try {
    let record = await api('trial-review?id=' + encodeURIComponent(jobId) + '&variant=' + variant);
    const form = document.createElement('form');
    function field(label, type, value = '') {
     const wrapper = document.createElement('label');
     const input = document.createElement('input');
     input.type = type;
     input.value = value;
     if (type === 'number') { input.min = '0'; input.step = '1'; }
     wrapper.append(label, input);
     form.append(wrapper);
     return input;
    }
    const title = field('Upload title', 'text', record.title);
    const cover = field('Cover note', 'text', record.cover_note);
    const post = field('Actual trial ID or URL', 'text', record.observations[0]?.post_id || '');
    const posted = field('Posted at (local time)', 'datetime-local');
    const observed = field('Observed at (local time)', 'datetime-local');
    if (record.observations[0]) {
     const time = new Date(record.observations[0].posted_at);
     time.setMinutes(time.getMinutes() - time.getTimezoneOffset());
     posted.value = time.toISOString().slice(0, 16);
     posted.readOnly = post.readOnly = true;
    }
    const metrics = Object.fromEntries(['views','reach','likes','comments','shares'].map(name => [name, field(name, 'number')]));
    const save = document.createElement('button');
    save.textContent = 'Save locally';
    const history = document.createElement('ul');
    const guidance = document.createElement('p');
    guidance.textContent = 'Compare observations at similar time since posting and similar reach. Views alone cannot identify the cause.';
    function renderHistory() {
     history.replaceChildren(...record.observations.map(row => {
      const item = document.createElement('li');
      item.textContent = new Date(row.observed_at).toLocaleString() + ' · ' + (row.elapsed_seconds / 3600).toFixed(1) + ' h since posting · ' + Object.entries(row.metrics).map(([name, count]) => name + ' ' + count).join(', ');
      return item;
     }));
    }
    form.append(save);
    panel.append(form, guidance, history);
    renderHistory();
    form.onsubmit = async event => {
     event.preventDefault();
     save.disabled = true;
     try {
      const key = crypto.randomUUID();
      const body = {job_id: jobId, variant, title: title.value, cover_note: cover.value,
                    command_id: key, idempotency_key: key, expected_revision: record.revision,
                    input_hashes: record.input_hashes, settings_version: 1};
      const entered = Object.fromEntries(Object.entries(metrics).filter(([, input]) => input.value).map(([name, input]) => [name, input.valueAsNumber]));
      if (observed.value || Object.keys(entered).length) {
       if (!post.value.trim() || !posted.value || !observed.value) throw Error('Enter the trial ID and both times for this observation.');
       body.observation = {post_id: post.value, posted_at: record.observations[0]?.posted_at || new Date(posted.value).toISOString(),
                           observed_at: new Date(observed.value).toISOString(), ...entered};
      }
      record = await api('trial-review', body);
      if (record.observations.length) { posted.readOnly = post.readOnly = true; }
      observed.value = '';
      for (const input of Object.values(metrics)) input.value = '';
      renderHistory();
      status.textContent = 'Saved locally.';
     } catch (e) { status.textContent = e.message; }
     finally { save.disabled = false; }
    };
   } catch (e) { status.textContent = e.message; delete panel.dataset.loaded; }
  });
  return panel;
 }
 async function restore(id){clearTimeout(timer);const job=await api('job?id='+id);if(job.kind==='trials')return watchTrials(id);if(!['intro','intro-sound'].includes(job.kind))throw Error('Choose a saved cinematic intro or comparison job.');const plan=await api('intro-plan?id='+encodeURIComponent(job.request.plan_id));if(plan.mode!=='cinematic')throw Error('Open documentary previews in Cricket Documentary Intro.');bank=await api('curation?id='+encodeURIComponent(plan.dataset_id));$('datasets').value=bank.id;$('choices').replaceChildren();$('create').disabled=true;await watch(id);}
 $('restore').onclick=()=>restore($('saved-job').value.trim()).catch(error);
 $('datasets').onchange=()=>{clearTimeout(timer);$('resume').hidden=true;bank=null;$('choices').replaceChildren();$('results').replaceChildren();$('create').disabled=true;$('status').textContent='Load the selected bank to choose its intro moments.';};
 api('curation-datasets').then(async data=>{for(const row of data.datasets)$('datasets').append(new Option(row.name,row.id));const previous=localStorage.getItem('storylens.intro.preview');if(previous)await restore(previous);}).catch(error);
 window.addEventListener('beforeunload',()=>clearTimeout(timer));

})();
