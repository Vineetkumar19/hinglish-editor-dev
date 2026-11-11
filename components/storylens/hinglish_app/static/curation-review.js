(()=>{
 const token=document.documentElement.dataset.token;
 const section=document.createElement('details');section.className='tool-history';
 const title=document.createElement('summary');title.textContent='History';
 const open=document.createElement('button');open.type='button';open.textContent='Review saved candidates';
 const status=document.createElement('p');status.setAttribute('role','status');
 const content=document.createElement('div');section.append(title,open,status,content);document.querySelector('main').append(section);
 const resume=document.createElement('button');resume.type='button';resume.textContent='Resume interrupted extraction';
 section.insertBefore(resume,status);
 resume.onclick=async()=>{try{const id=banks.value||localStorage.getItem('storylens.workbench.footage');const r=await window.storylensFetch('/api/workbench/resume',{method:'POST',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},body:JSON.stringify({id})});await window.storylensResponse(r);await window.storylensOpenFootage?.(id,section);}catch(e){status.textContent=e.message;}};
 const banks=document.createElement('select');banks.setAttribute('aria-label','Saved footage bank');section.insertBefore(banks,open);
 const last=document.createElement('button');last.type='button';last.textContent='Open last extraction';last.id='open-last-extraction';last.hidden=!localStorage.getItem('storylens.workbench.footage');last.onclick=()=>window.storylensOpenFootage?.(localStorage.getItem('storylens.workbench.footage'),section);section.insertBefore(last,status);
 window.storylensFetch('/api/workbench/curation-datasets',{headers:{'X-Hinglish-Token':token}}).then(window.storylensResponse).then(result=>{for(const row of result.datasets)banks.append(new Option(row.name,row.id));const prior=localStorage.getItem('storylens.workbench.footage');if([...banks.options].some(o=>o.value===prior))banks.value=prior;}).catch(error=>status.textContent=error.message);
 let data=null,jobId=null,search='',matches=null,reviewer='owner',visualTimer=null,searchFilters={};
 async function api(body){
  const url='/api/workbench/curation'+(body?'':'?id='+encodeURIComponent(jobId));
  const response=await window.storylensFetch(url,{method:body?'POST':'GET',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
  return window.storylensResponse(response);
 }
 async function change(operation,extra={}){
  const id=crypto.randomUUID();
  data=await api({id:jobId,operation,command_id:id,idempotency_key:id,expected_revision:data.revision,
   input_hashes:[...new Set(data.candidates.map(r=>r.source_sha256))].sort(),settings_version:1,reviewer,...extra});
  render();
 }
 function button(text,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=async()=>{b.disabled=true;try{await action();status.textContent='Saved.';}catch(e){status.textContent=e.message;}finally{b.disabled=false;}};return b;}
 function render(){
  content.replaceChildren();
  const info=document.createElement('p');info.textContent='Revision '+data.revision+' · Labels require source review. Empty phases remain gaps.';content.append(info);
  const identity=document.createElement('select');identity.setAttribute('aria-label','Review identity');identity.append(new Option('Owner review','owner'),new Option('Assistant review','assistant'));identity.value=reviewer;identity.onchange=()=>reviewer=identity.value;content.append(identity);
  const query=document.createElement('input');query.setAttribute('aria-label','Search scene, action or source');query.value=search;
  const filterPanel = document.createElement('details');
  const filterTitle = document.createElement('summary');
  filterTitle.textContent = 'Footage search filters';
  filterPanel.append(filterTitle);
  const fields = {};
  for (const [key, name, type] of [['phase','Story phase','text'],['review_state','Review state','text'],
   ['location','Location','text'],['camera_move','Camera move','text'],['date_from','From capture date','date'],
   ['date_to','Through capture date','date'],['min_duration','Minimum seconds','number'],
   ['min_quality','Minimum quality (0–1)','number'],['min_rating','Minimum rating (0–5)','number']]) {
   const label = document.createElement('label');
   const input = document.createElement('input');
   input.type = type;
   if (type === 'number') { input.min = '0'; input.step = 'any'; }
   input.value = searchFilters[key] || '';
   fields[key] = input;
   label.append(name, input);
   filterPanel.append(label);
  }
  function selectedFilters() {
   return Object.fromEntries(Object.entries(fields).map(([key,input]) => [key,input.value.trim()]).filter(([,value]) => value));
  }
  content.append(query, filterPanel, button('Search footage',async()=>{
   search = query.value;
   searchFilters = selectedFilters();
   const params = new URLSearchParams({id:jobId, q:search, ...searchFilters});
   const response = await window.storylensFetch('/api/workbench/curation-search?' + params, {headers:{'X-Hinglish-Token':token}});
   matches = (await window.storylensResponse(response)).results;
   render();
  }));
  const visual=document.createElement('label'),allowVisual=document.createElement('input');allowVisual.type='checkbox';visual.append(allowVisual,' Use installed visual retrieval when hosted embeddings are unavailable');content.append(visual,button('Find visual matches',async()=>{if(!allowVisual.checked)throw Error('Choose the installed retrieval provider first.');search=query.value;searchFilters=selectedFilters();const r=await window.storylensFetch('/api/workbench/visual-index',{method:'POST',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},body:JSON.stringify({dataset_id:jobId,provider:'installed_visual_retrieval',fallback_reason:'Hosted visual embeddings unavailable in this session; explicitly selected installed retrieval provider.',query:search,filters:searchFilters,idempotency_key:crypto.randomUUID()})});const job=await window.storylensResponse(r);localStorage.setItem('storylens.visual.preview',job.id);await watchVisual(job.id);}));
  content.append(button('Restore visual search',async()=>{const id=localStorage.getItem('storylens.visual.preview');if(!id)throw Error('Run a visual search first.');await watchVisual(id);}));
  const recipe=document.createElement('select');recipe.setAttribute('aria-label','Story recipe');
  for(const name of ['travel','waterfall','party']){const o=new Option(name,name);recipe.append(o);}const preselection = document.createElement('input');
  preselection.type = 'checkbox'; preselection.disabled = true;
  const option = document.createElement('label');
  option.append(preselection, 'Suggest source-reviewed clips for my approval');
  window.storylensFetch('/api/workbench/preselection-gate', {headers:{'X-Hinglish-Token':token}})
   .then(window.storylensResponse).then(gate => { preselection.disabled = !gate.passed; }).catch(() => {});
  content.append(recipe,option,button('Propose story',()=>change('propose_body',{recipe:recipe.value,preselection:preselection.checked})));
  if(matches && !matches.length){const empty=document.createElement('p');empty.textContent='No clips match the current search.';content.append(empty);}
  for(const row of matches||data.candidates){
   const article=document.createElement('article');article.className='shot-card';
   const text=document.createElement('p');text.textContent=row.source.split(/[\\/]/).pop()+' · '+row.start.toFixed(3)+'–'+(row.start+row.duration).toFixed(3)+'s · '+row.review_state;
   const measured = document.createElement('p');
   const signals = row.quality_signals || {};
   measured.textContent = ['Measured quality '+row.score?.toFixed(3),
    ...[['detail','Detail'],['exposure','Exposure'],['usable_luma','Usable luminance'],['stability','Stability estimate']]
     .filter(([key]) => Number.isFinite(signals[key])).map(([key,label]) => label+' '+signals[key].toFixed(3)),
    row.duplicate_group ? 'Duplicate group '+row.duplicate_group : '',
    (row.phase_tags || []).join(', ') || 'Unclassified',
   ].filter(Boolean).join(' · ');
   const video=document.createElement('video');video.controls=true;video.preload='none';video.width=240;video.src='/api/workbench/media?id='+jobId+'&asset='+row.id+'&token='+encodeURIComponent(token);video.poster=video.src+'&kind=poster';
   const phase=document.createElement('select');phase.setAttribute('aria-label','Phase for '+row.id);
   for(const name of ['', 'departure','preparation','travel','approach','reveal','experience','arrival','atmosphere','highlights','closing'])phase.append(new Option(name||'Unclassified',name));phase.value=row.phase_tags?.[0]||'';
   const reason=document.createElement('input');reason.placeholder='Review reason';reason.setAttribute('aria-label','Reason for '+row.id);
   const description=document.createElement('input');description.setAttribute('aria-label','Observed scene and action for '+row.id);description.placeholder='Observed scene and action';description.value=row.description||'';
   const rating = document.createElement('select');
   rating.setAttribute('aria-label', 'Rating for ' + row.id);
   for (let i = 0; i <= 5; i++) rating.append(new Option(i ? `${i} out of 5` : 'Unrated', i));
   rating.value = row.rating || 0;
   article.append(rating);
   const review=state=>change('review_candidate',{clip_id:row.id,phase_tags:phase.value?[phase.value]:[],review_state:state,reason:reason.value,rating:Number(rating.value)});
   article.append(video,text,measured,phase,reason,description,button('Save description',()=>change('annotate_candidate',{clip_id:row.id,annotation:{description:description.value,evidence:reason.value,reviewer}})),button('Save label',()=>review(row.review_state)),button('Approve candidate',()=>review('approved')),button('Reject candidate',()=>review('rejected')));
   article.append(button('Preview original source',async()=>{const r=await window.storylensFetch('/api/workbench/source-proxy',{method:'POST',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},body:JSON.stringify({dataset_id:jobId,candidate_id:row.id,idempotency_key:'source-preview:'+jobId+':'+row.id})});const job=await window.storylensResponse(r);if(['failed','interrupted'].includes(job.status)){const resumed=await window.storylensFetch('/api/workbench/resume',{method:'POST',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},body:JSON.stringify({id:job.id})});await window.storylensResponse(resumed);}await watchSource(job.id);}));
   if(row.match_reason){const match=document.createElement('p');const why=row.match_reason;match.textContent=[
     why.terms.length ? 'Matching words '+why.terms.join(', ') : '',
     Number.isFinite(why.vector_similarity) ? 'Visual similarity '+why.vector_similarity.toFixed(3) : '',
     why.uncertainty,
    ].filter(Boolean).join(' · ');article.append(match);}
   if(data.body){article.append(button((data.body.banned||[]).includes(row.id)?'Unban candidate':'Ban candidate',()=>change('ban_candidate',{clip_id:row.id,enabled:!(data.body.banned||[]).includes(row.id)})),button('Pin to chosen phase',()=>change('pin_candidate',{clip_id:row.id,phase:phase.value})));}
   content.append(article);
  }
  if(data.body){
   const h=document.createElement('h3');h.textContent='Phase storyboard';content.append(h);
   for(const slot of data.body.slot_assignments){
    const line=document.createElement('div');const label=document.createElement('span');label.textContent=slot.phase+(slot.gap?' — Missing footage':'')+(slot.locked?' — Locked':'');
    const choice=document.createElement('select');choice.setAttribute('aria-label','Clip for '+slot.phase);choice.append(new Option('Choose clip',''));
    for(const row of data.candidates.filter(r=>r.review_state!=='rejected'))choice.append(new Option(row.source.split(/[\\/]/).pop()+' @ '+row.start+'s',row.id));choice.value=slot.clip_id||'';
    line.append(label,choice,button('Use and lock',()=>change('edit_body',{phase:slot.phase,clip_id:choice.value,locked:true})),button('Unlock',()=>change('edit_body',{phase:slot.phase,clip_id:choice.value,locked:false})),button('Move phase earlier',()=>{const order=[...data.body.phase_order],index=order.indexOf(slot.phase);if(index>0)[order[index-1],order[index]]=[order[index],order[index-1]];return change('reorder_phases',{phase_order:order});}));content.append(line);
   }
   const gaps=document.createElement('label'),accept=document.createElement('input');accept.type='checkbox';gaps.append(accept,' Accept the displayed missing phases');
   content.append(gaps,button('Approve body plan',()=>change('approve_revision',{accept_missing_phases:accept.checked})));
   content.append(button('Render body-only preview',async()=>{const r=await window.storylensFetch('/api/workbench/body-render',{method:'POST',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},body:JSON.stringify({dataset_id:jobId,expected_revision:data.revision,idempotency_key:crypto.randomUUID()})});const job=await window.storylensResponse(r);localStorage.setItem('storylens.body.preview',job.id);await watchBody(job.id);}));
  }
 }
 async function watchSource(id){const r=await window.storylensFetch('/api/workbench/job?id='+id,{headers:{'X-Hinglish-Token':token}}),job=await window.storylensResponse(r);status.textContent=job.stage;if(['queued','running'].includes(job.status)){setTimeout(()=>watchSource(id).catch(e=>status.textContent=e.message),1000);return;}if(job.status!=='complete')throw Error(job.error?.message||'Source preview stopped.');const box=document.createElement('section'),h=document.createElement('h3'),video=document.createElement('video'),note=document.createElement('p');h.textContent='Original source context';video.controls=true;video.width=360;video.src='/api/workbench/source-preview?id='+id+'&token='+encodeURIComponent(token)+'#t='+job.result.span_start;note.textContent='Selected span '+job.result.span_start.toFixed(2)+'–'+job.result.span_end.toFixed(2)+'s · silent analysis proxy with verified original frame timestamps';const strip=document.createElement('a');strip.textContent='Open source thumbnail strip';strip.href='/api/workbench/source-preview?id='+id+'&kind=strip&token='+encodeURIComponent(token);strip.target='_blank';strip.rel='noopener';box.append(h,video,note,strip);content.prepend(box);status.textContent='Source preview ready.';}
 async function watchBody(id){const r=await window.storylensFetch('/api/workbench/job?id='+id,{headers:{'X-Hinglish-Token':token}}),job=await window.storylensResponse(r);status.textContent=job.stage;if(['queued','running'].includes(job.status)){setTimeout(()=>watchBody(id).catch(e=>status.textContent=e.message),1000);return;}if(job.status!=='complete')throw Error(job.error?.message||'Body render stopped.');const video=document.createElement('video');video.controls=true;video.width=300;video.src='/api/workbench/assembly-media?id='+id+'&part=body&token='+encodeURIComponent(token);content.append(video);status.textContent='Body-only preview ready. Native template verification is separate.';}
 async function watchVisual(id){clearTimeout(visualTimer);const r=await window.storylensFetch('/api/workbench/job?id='+id,{headers:{'X-Hinglish-Token':token}}),job=await window.storylensResponse(r);status.textContent=job.stage;if(['queued','running'].includes(job.status)){visualTimer=setTimeout(()=>watchVisual(id).catch(e=>status.textContent=e.message),1000);return;}if(job.status!=='complete')throw Error(job.error?.message||'Visual retrieval stopped.');if(job.result.dataset_id!==jobId)throw Error('Load the footage bank used by this saved visual search.');const current=Object.fromEntries(data.candidates.map(row=>[row.id,row]));matches=(job.result.matches||[]).filter(row=>current[row.id]&&current[row.id].source_sha256===row.source_sha256).map(row=>({...row,...current[row.id],match_reason:row.match_reason}));search=job.result.query||'';searchFilters=job.result.filters||{};render();status.textContent='Visual retrieval ready · '+job.result.candidate_count+' clips · Qwen3-VL-Embedding-2B fallback. Reviewed choices unchanged.';}
 open.onclick=async()=>{try{jobId=banks.value||localStorage.getItem('storylens.workbench.footage');search='';matches=null;clearTimeout(visualTimer);if(!jobId)throw Error('Collect footage first.');data=await api();render();}catch(e){status.textContent=e.message;}};
 window.addEventListener('beforeunload',()=>clearTimeout(visualTimer));
})();
