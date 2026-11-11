(()=>{
const $=id=>document.getElementById(id),token=document.documentElement.dataset.token;
let catalog=null,inspection=null,inspectionId=null,populationId=null,comparisonId=null,bank=null,timer=null,busy=false;
async function api(path,body){const response=await window.storylensFetch('/api/workbench/'+path,{method:body?'POST':'GET',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});return window.storylensResponse(response);}
function setBusy(value){busy=value;for(const node of document.querySelectorAll('button,select,input')){if(value){node.dataset.wasDisabled=String(node.disabled);node.disabled=true;}else{node.disabled=node.dataset.wasDisabled==='true';delete node.dataset.wasDisabled;}}}
function fail(error){if(busy)setBusy(false);$('status').textContent=error.message;}
function remember(id){$('savedJob').value=id;try{localStorage.setItem('storylens-native-job-v1',id);}catch(e){/* Job ID stays visible if storage is unavailable. */}}
async function restore(){if(busy)return;const id=$('savedJob').value.trim();if(!/^[a-f0-9]{32}$/.test(id))throw Error('Enter the saved native job ID.');setBusy(true);clearTimeout(timer);await watch(id);}

async function start(action,extra={}){if(busy)return;setBusy(true);$('status').textContent='Checking native request…';const job=await api('native-curation',{action,...extra,idempotency_key:crypto.randomUUID()});remember(job.id);await watch(job.id);}
async function watch(id){const job=await api('job?id='+id);if(job.kind!=='native-curation')throw Error('Choose a native curation job.');remember(id);$('status').textContent=job.stage;if(['queued','running'].includes(job.status)){timer=setTimeout(()=>watch(id).catch(fail),1000);return;}if(busy)setBusy(false);if(job.status!=='complete')throw Error(job.error?.message||'Native action stopped; review its receipt before retrying.');const result=job.result;if(['render','intro_variants'].includes(job.request.action))populationId=job.request.population_id;
if(job.request.action==='catalog'){catalog=result;$('project').textContent=result.project_path||'Save the current After Effects project before continuing.';$('composition').replaceChildren(...result.compositions.map(c=>new Option(c.name+' · '+c.duration.toFixed(2)+'s',c.id)));$('inspect').disabled=!result.project_path;$('status').textContent='Connected project read. Choose the intended template composition.';}
if(job.request.action==='inspect'){inspection=result;inspectionId=id;$('review').textContent=result.supported?result.slot_count+' native media slots · '+result.composition_count+' dependent compositions verified':result.unsupported.join('; ');drawSlots();$('status').textContent='Template inspected. Review every slot assignment.';}
if(job.request.action==='populate'){populationId=id;$('render').disabled=false;$('nativeIntros').disabled=false;$('result').textContent='Separate editable project saved: '+result.project_path+' · '+result.filled.length+' native slots filled. Original template dependencies unchanged.';}
if(job.request.action==='intro_variants'){comparisonId=id;$('renderComparison').disabled=false;$('result').textContent='Editable Intro A/B/C and Trial A/B/C saved: '+result.project_path+' · same original body composition '+result.body_comp_id+'. '+(result.assembly_mode==='dedicated_slot'?'Dedicated five-second slot replaced. ':'Intro prepended. ')+
result.variants.map(v=>'Trial '+v.variant+' '+(v.trial_frames/30).toFixed(2)+'s').join(' · ')+'. Native preview rendering is still required.';$('nativeIntros').disabled=false;}
if(job.request.action==='render'){if(job.request.comparison_id){comparisonId=job.request.comparison_id;$('renderComparison').disabled=false;$('comparisonPart').value=job.request.comparison_part;}$('result').textContent='Native preview verified: '+result.decoded_frames+' decoded frames';const video=document.createElement('video');video.controls=true;video.width=360;video.src='/api/workbench/native-preview?id='+id+'&token='+encodeURIComponent(token);$('result').append(video);$('render').disabled=false;$('nativeIntros').disabled=false;}
}
function drawSlots(){$('slots').replaceChildren();$('populate').disabled=!(inspection?.supported&&bank);$('suggest').disabled=!(inspection?.supported&&bank?.body);$('downloadSlotMap').disabled=!(inspection&&bank);if(!inspection||!bank)return;for(const slot of inspection.slots){const label=document.createElement('label'),select=document.createElement('select');label.textContent='Slot '+slot.slot_id+' · '+(slot.duration_frames/slot.fps).toFixed(2)+'s';select.dataset.slot=slot.slot_id;select.setAttribute('aria-label','Candidate for slot '+slot.slot_id);select.append(new Option('Choose reviewed candidate',''));for(const row of bank.candidates.filter(r=>r.review_state==='approved'&&!(bank.body?.banned||[]).includes(r.id)&&r.duration*slot.fps+.01>=slot.duration_frames))select.append(new Option((row.description||row.source.split(/[\\/]/).pop())+' @ '+row.start.toFixed(2)+'s',row.id));const evidence=document.createElement('small');
select.addEventListener('change',()=>{const row=bank.candidates.find(item=>item.id===select.value);evidence.textContent=row?
 [(row.phase_tags||[]).join(', ')||'Unclassified','Source '+row.start.toFixed(3)+'–'+(row.start+row.duration).toFixed(3)+'s',
 'Quality '+row.score?.toFixed(3),'Fit '+slot.fit_policy,'Audio '+slot.audio_policy].join(' · '):'';});
label.append(select,evidence);$('slots').append(label);}}
$('connect').onclick=()=>start('catalog').catch(fail);
$('inspect').onclick=()=>start('inspect',{composition_id:$('composition').value,project_path:catalog.project_path}).catch(fail);
$('load').onclick=async()=>{if(busy)return;setBusy(true);try{bank=await api('curation?id='+$('dataset').value);setBusy(false);drawSlots();$('status').textContent='Reviewed footage loaded. Missing or short choices remain empty.';}catch(e){fail(e);}};
$('suggest').onclick=async()=>{if(busy)return;setBusy(true);try{const proposal=await api('native-slot-proposal',{inspection_id:inspectionId,dataset_id:bank.id,expected_revision:bank.revision});setBusy(false);for(const assignment of proposal.assignments){const select=[...$('slots').querySelectorAll('select')].find(s=>s.dataset.slot===assignment.slot_id);if(select){select.value=assignment.candidate_id||'';select.dispatchEvent(new Event('change'));}}$('status').textContent=(proposal.ready_for_review?'Story-order suggestion ready. Review each slot.':'Some slots or locked choices need review.')+' Missing story phases: '+(proposal.missing_phases.join(', ')||'none');}catch(e){fail(e);}};
$('downloadSlotMap').onclick=async()=>{
 try{
  const assignments=[...$('slots').querySelectorAll('select')].map(s=>({slot_id:s.dataset.slot,candidate_id:s.value}));
  const map=await api('native-slot-map',{inspection_id:inspectionId,dataset_id:bank.id,expected_revision:bank.revision,assignments});
  const url=URL.createObjectURL(new Blob([JSON.stringify(map,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='slot-map-'+inspectionId.slice(0,8)+'.json';link.click();
  setTimeout(()=>URL.revokeObjectURL(url),5000);
  $('status').textContent='Slot map downloaded for manual review.';
 }catch(error){fail(error);}
};
$('populate').onclick=()=>start('populate',{inspection_id:inspectionId,dataset_id:bank.id,expected_revision:bank.revision,assignments:[...$('slots').querySelectorAll('select')].map(s=>({slot_id:s.dataset.slot,candidate_id:s.value}))}).catch(fail);
$('nativeIntros').onclick=()=>start('intro_variants',{population_id:populationId,intro_job_id:$('introJob').value.trim()}).catch(fail);
$('renderComparison').onclick=()=>start('render',{comparison_id:comparisonId,comparison_part:$('comparisonPart').value}).catch(fail);
$('render').onclick=()=>start('render',{population_id:populationId}).catch(fail);
try{$('introJob').value=localStorage.getItem('storylens.intro.preview')||'';}catch(e){}
$('restore').onclick=()=>restore().catch(fail);try{$('savedJob').value=localStorage.getItem('storylens-native-job-v1')||'';}catch(e){}
api('curation-datasets').then(d=>{for(const row of d.datasets)$('dataset').append(new Option(row.name,row.id));}).catch(fail);
window.addEventListener('beforeunload',()=>clearTimeout(timer));
})();
