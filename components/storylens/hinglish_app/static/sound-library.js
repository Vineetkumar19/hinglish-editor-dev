(()=>{
 const $=id=>document.getElementById(id),token=document.documentElement.dataset.token;let catalog=[],recipes={},timer=null,loopTimer=null;
 async function api(path,body){const r=await window.storylensFetch('/api/workbench/'+path,{method:body?'POST':'GET',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});return window.storylensResponse(r);}
 function envelope(row){const key=crypto.randomUUID();return {id:row.id,command_id:key,idempotency_key:key,expected_revision:row.revision||0,input_hashes:[row.hash],settings_version:1};}
 async function refresh(){const data=await api('sounds');catalog=data.sounds;recipes=data.recipes;if(!$('category').options.length)for(const category of data.categories)$('category').append(new Option(category.replaceAll('_',' '),category));if($('sound-category-filter').options.length===1)for(const category of data.categories)$('sound-category-filter').append(new Option(category.replaceAll('_',' '),category));if(!$('recipe').options.length)for(const id of Object.keys(recipes))$('recipe').append(new Option(id,id));render();roles();renderLoopSources();}
 function roles(){
  const recipeId = $('recipe').value;
  const recipe = recipes[recipeId];
  $('impact-duration-label').hidden = !['SND_IMPACT_v1', 'SND_REVEAL_v1', 'SND_AMBIENCE_v1'].includes(recipeId);
  $('cue-anchor-label').hidden = recipe.anchor === undefined;
  $('cue-anchor').placeholder = recipe.anchor ?? '';
  $('cue-tail-label').hidden = recipeId !== 'SND_IMPACT_v1';
  $('roles').replaceChildren();
  const roleDefaults = new Map(recipe.events.map(([role, start, end, gain]) => [role, gain]));
  const approved = catalog.filter(row => row.rights_state === 'approved' && row.audition_approved);
  for (const [role, defaultGain] of roleDefaults) {
   const controls = document.createElement('fieldset');
   controls.dataset.role = role;
   const heading = document.createElement('legend');
   heading.textContent = role;
   const select = document.createElement('select');
   select.setAttribute('aria-label', 'Recording for ' + role);
   select.append(new Option('Choose an approved recording', ''));
   for (const row of approved) select.append(new Option(row.alias, row.id));
   const startLabel = document.createElement('label');
   startLabel.textContent = 'Recording in point (s)';
   const sourceIn = document.createElement('input');
   Object.assign(sourceIn, {type:'number', name:'source_in', min:0, step:0.001, value:0});
   sourceIn.setAttribute('aria-label', 'Recording in point for ' + role);
   startLabel.append(sourceIn);
   const gainLabel = document.createElement('label');
   gainLabel.textContent = 'Gain (dB)';
   const gain = document.createElement('input');
   Object.assign(gain, {type:'number', name:'gain_db', min:-60, max:6, step:0.1, value:defaultGain});
   gain.setAttribute('aria-label', 'Gain for ' + role);
   gainLabel.append(gain);
   controls.append(heading, select, startLabel, gainLabel);
   $('roles').append(controls);
  }
 }
 $('recipe').onchange = () => {
  for (const id of ['impact-duration', 'cue-anchor', 'cue-tail']) $(id).value = '';
  roles();
 };
 $('mix').onclick=async()=>{try{
  const choices = {};
  for (const role of $('roles').querySelectorAll('fieldset[data-role]')) {
   const row = catalog.find(row => row.id === role.querySelector('select').value);
   if (!row) throw Error('Choose every required recording.');
   const sourceIn = role.querySelector('[name=source_in]').valueAsNumber;
   const gain = role.querySelector('[name=gain_db]').valueAsNumber;
   if (!Number.isFinite(sourceIn) || sourceIn < 0 || sourceIn >= row.duration) {
    throw Error('Choose an in point within the recording for ' + role.dataset.role + '.');
   }
   if (!Number.isFinite(gain) || gain < -60 || gain > 6) {
    throw Error('Choose gain between -60 and +6 dB for ' + role.dataset.role + '.');
   }
   choices[role.dataset.role] = {asset_id:row.id, hash:row.hash, source_in:sourceIn, gain_db:gain};
  }
  const key=crypto.randomUUID(),id=crypto.randomUUID().replaceAll('-','');$('mix').disabled=true;
  const optionalNumber = (id, label) => !$(label).hidden && $(id).value ? $(id).valueAsNumber : undefined;
  const duration = optionalNumber('impact-duration', 'impact-duration-label');
  const anchor = optionalNumber('cue-anchor', 'cue-anchor-label');
  const tail = optionalNumber('cue-tail', 'cue-tail-label');
  const plan=await api('sound-plan',{id,recipe_id:$('recipe').value,duration,anchor,tail,target_lufs:$('mix-lufs').valueAsNumber,true_peak_dbtp:$('mix-peak').valueAsNumber,choices,original_audio:$('original').value,dialogue_activity:JSON.parse($('dialogue').value),command_id:key,idempotency_key:key,expected_revision:0,input_hashes:[...new Set(Object.values(choices).map(c=>c.hash))].sort(),settings_version:1});
  const job=await api('sound-render',{id,expected_revision:plan.revision,idempotency_key:key+':render'});localStorage.setItem('storylens.sound.mix',job.id);await watch(job.id);
 }catch(e){$('status').textContent=e.message;$('mix').disabled=false;}};
 async function watch(id){const job=await api('job?id='+id);$('status').textContent=job.stage;if(['queued','running'].includes(job.status)){timer=setTimeout(()=>watch(id).catch(e=>{$('status').textContent=e.message;}),1000);return;}$('mix').disabled=false;if(job.status!=='complete')throw Error(job.error?.message||'Mix stopped.');$('mixed').src='/api/workbench/mix-media?id='+id+'&token='+encodeURIComponent(token);$('status').textContent='Recipe mix job '+job.id+' ready. Loudness '+job.result.metrics.integrated_lufs+' LUFS; true peak '+job.result.metrics.true_peak_dbtp+' dBTP. Audition pending.';}
 function render(){
  $('sounds').replaceChildren();
  const query = $('search').value.trim().toLowerCase();
  const category = $('sound-category-filter').value;
  const matches = catalog.filter(row => (!category || row.categories.includes(category)) &&
   (!query || row.id === query || row.alias.toLowerCase().includes(query) || row.original_filename.toLowerCase().includes(query)));
  matches.sort((a, b) => Number(b.alias.toLowerCase() === query || b.id === query) - Number(a.alias.toLowerCase() === query || a.id === query));
  for (const row of matches) {
   const section=document.createElement('section'),h=document.createElement('h2'),p=document.createElement('p'),audio=document.createElement('audio'),evidence=document.createElement('textarea'),approve=document.createElement('button');
   h.textContent=row.alias;p.textContent=row.original_filename+' · '+row.duration.toFixed(2)+'s · '+row.rights_state+' · '+(row.audition_approved?'Audition approved':'Awaiting audition');
   audio.controls=true;audio.preload='none';audio.src='/api/workbench/sound-media?asset='+row.id+'&token='+encodeURIComponent(token);
   evidence.value=row.license_evidence;evidence.setAttribute('aria-label','Permission evidence for '+row.alias);approve.textContent='Approve recording and permission';approve.disabled=true;
   audio.onended=()=>{approve.disabled=false;};approve.onclick=async()=>{try{await api('sound-review',{...envelope(row),license_evidence:evidence.value,rights_state:'approved',audition_approved:true});await refresh();$('status').textContent='Saved approval for this exact recording.';}catch(e){$('status').textContent=e.message;}};
   const details = document.createElement('p');
   details.textContent = [row.categories.map(name => name.replaceAll('_', ' ')).join(', '), row.source_url,
    row.attribution, row.commercial_scope, row.expiry ? 'Expires ' + row.expiry : ''].filter(Boolean).join(' · ');
   section.append(h,p,details,audio,evidence,approve);$('sounds').append(section);
  }
 }
 function renderLoopSources() {
  const select = $('loop-source'), previous = select.value;
  select.replaceChildren(new Option('Choose an approved original ambience', ''));
  for (const asset of catalog.filter(row => row.categories.includes('03_Ambience') &&
       row.rights_state === 'approved' && row.audition_approved && !row.derivation)) {
   select.append(new Option(asset.alias, asset.id));
  }
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
 }
 async function watchLoop(id) {
  try {
   const job = await api('job?id=' + id);
   $('loop-status').textContent = job.stage;
   if (['queued','running'].includes(job.status)) {
    loopTimer = setTimeout(() => watchLoop(id), 1000);
    return;
   }
   if (job.status !== 'complete') throw Error(job.error?.message || 'Ambience loop stopped.');
   $('search').value = job.result.alias;
   $('sound-category-filter').value = '03_Ambience';
   await refresh();
   $('loop-status').textContent = 'Loop ready. Play the complete recording below and review it before selecting it for a recipe.';
  } catch (error) {
   $('loop-status').textContent = error.message;
  }
  $('loop-render').disabled = false;
 }
 $('loop-form').onsubmit = async event => {
  event.preventDefault();
  $('loop-render').disabled = true;
  try {
   const asset = catalog.find(row => row.id === $('loop-source').value);
   if (!asset) throw Error('Choose an approved original ambience recording.');
   const job = await api('sound-loop', {asset_id:asset.id, source_hash:asset.hash,
    source_in:$('loop-in').valueAsNumber, segment_seconds:$('loop-segment').valueAsNumber,
    crossfade_seconds:$('loop-crossfade').valueAsNumber, duration:$('loop-duration').valueAsNumber,
    idempotency_key:crypto.randomUUID()});
   localStorage.setItem('storylens.sound.loop', job.id);
   await watchLoop(job.id);
  } catch (error) {
   $('loop-status').textContent = error.message;
   $('loop-render').disabled = false;
  }
 };
 $('search').oninput=render;
 $('sound-category-filter').onchange=render;
 $('import').onsubmit=async event=>{event.preventDefault();try{const measured=await api('sound-inspect',{path:$('path').value});await api('sound-import',{...envelope(measured),path:measured.path,alias:$('alias').value,categories:[$('category').value],license_evidence:$('evidence').value,source_url:$('sound-source-url').value,attribution:$('sound-attribution').value,commercial_scope:$('sound-scope').value||'unknown',expiry:$('sound-expiry').value||null});await refresh();$('status').textContent='Imported into quarantine. Listen and review permission before using it in a recipe.';}catch(e){$('status').textContent=e.message;}};
 refresh().catch(e=>{$('status').textContent=e.message;});
 const previous=localStorage.getItem('storylens.sound.mix');if(previous)watch(previous).catch(e=>{$('status').textContent=e.message;});
 const savedLoop=localStorage.getItem('storylens.sound.loop');
 if(savedLoop)watchLoop(savedLoop);
 window.addEventListener('beforeunload',()=>{clearTimeout(timer);clearTimeout(loopTimer);});
})();
