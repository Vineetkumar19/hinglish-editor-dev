(()=>{
 const $=id=>document.getElementById(id),token=document.documentElement.dataset.token;
 let input=null,bank=null,nodes=[],timer=null;
 async function api(path,body){const r=await window.storylensFetch('/api/workbench/'+path,{method:body?'POST':'GET',headers:{'X-Hinglish-Token':token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});return window.storylensResponse(r);}
 function fail(e){$('status').textContent=e.message;}
 function command(){const id=crypto.randomUUID();return {command_id:id,idempotency_key:id,expected_revision:bank?.revision||0,input_hashes:input.input_hashes,settings_version:1};}
 $('import').onclick=async()=>{try{
  const value={body_path:$('body-path').value,transcript_path:$('transcript-path').value,script_path:$('script-path').value};
  input=await api('documentary-inspect',value);bank=await api('documentary-import',{...value,...command(),id:crypto.randomUUID().replaceAll('-',''),category:'cricket'});
  localStorage.setItem('storylens.documentary',bank.id);$('review').hidden=false;$('script').textContent=input.script;$('words').textContent=input.words.map(w=>w.start.toFixed(3)+'–'+w.end.toFixed(3)+' '+w.text).join('\n');
  $('source-note').textContent='The transcript is bound to this exact video. Review names, numbers, incomplete words and historical context before using it.';
  $('source-video').src='/api/workbench/documentary-media?id='+bank.id+'&token='+encodeURIComponent(token);$('status').textContent='Body imported. Add and review source spans.';
 }catch(e){fail(e);}};
 function textFor(a,b){return input.words.filter(w=>w.start>=a-.001&&w.end<=b+.001).map(w=>w.text).join(' ').trim();}
 function duration(){
  let frames=0;
  const clock=$('actual-doc-clock');
  clock.replaceChildren();
  for(const node of nodes.filter(n=>n.selected.checked)){
   const end=frames+Math.round((+node.end.value-+node.start.value)*30);
   const row=document.createElement('li');
   row.textContent=(frames/30).toFixed(2)+'–'+(end/30).toFixed(2)+'s · '+node.kind.value+' · source '+node.start.value+'–'+node.end.value+'s';
   clock.append(row);
   frames=end;
  }
  $('duration').textContent=frames+' / 1,200 frames';return frames;
 }
 $('add').onclick=()=>{
  const id='n'+(nodes.length+1),field=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent='Span '+id;field.append(legend);
  function element(tag,type,label,value){const wrap=document.createElement('label');wrap.textContent=label;const e=document.createElement(tag);if(type)e.type=type;if(value!==undefined)e.value=value;e.setAttribute('aria-label',id+' '+label);wrap.append(e);field.append(wrap);return e;}
  const kind=element('select',null,'Role');for(const role of ['setup','question','evidence','payoff','bridge','title'])kind.append(new Option(role,role));
  const start=element('input','number','Start',0),end=element('input','number','End',5);start.step=end.step='0.001';const wording=document.createElement('p');field.append(wording);
  const payoff=element('input','text','Answer span ID'),evidence=element('input','text','Evidence span IDs (comma separated)'),selected=element('input','checkbox','Include in intro'),protectedBox=element('input','checkbox','Reveals an answer'),reviewed=element('input','checkbox','Complete speech boundaries reviewed');
  const n={id,kind,start,end,payoff,evidence,selected,protectedBox,reviewed};nodes.push(n);const update=()=>{wording.textContent=textFor(+start.value,+end.value);duration();$('render').disabled=true;};for(const e of [kind,start,end,payoff,evidence,selected,protectedBox,reviewed])e.onchange=update;update();$('nodes').append(field);
 };
 function graph(){const rows=nodes.map(n=>({id:n.id,kind:n.kind.value,source_id:bank.source.id,source_start:+n.start.value,source_end:+n.end.value,body_start:+n.start.value,body_end:+n.end.value,text:textFor(+n.start.value,+n.end.value),word_boundary_review:n.reviewed.checked,reveals_payoff:n.protectedBox.checked}));return {category:'cricket',script_hash:bank.script_hash,transcript_hash:bank.transcript_hash,body_hash:bank.body.timeline_hash,nodes:rows,
  protected_visuals:JSON.parse($('protected-visuals').value).map(row=>({start:row.start,end:row.end,reason:row.reason,source_id:bank.source.id})),
  question_payoffs:nodes.filter(n=>n.kind.value==='question').map(n=>({question_id:n.id,payoff_id:n.payoff.value,evidence_ids:n.evidence.value.split(',').map(s=>s.trim()).filter(Boolean)})),spoiler_review:$('spoilers').checked?'approved':'pending',reviewer:$('reviewer').value};}
 $('protected-visuals').oninput=()=>{$('render').disabled=true;};
 $('save').onclick=async()=>{try{if(!$('reviewer').value.trim())throw Error('Record who reviewed these spans.');bank=await api('documentary-graph',{...command(),id:bank.id,graph:graph()});$('render').disabled=false;$('status').textContent='Story review saved. Select the introduction spans in their displayed order.';}catch(e){fail(e);}};
 $('render').onclick=async()=>{try{
  if(duration()!==1200)throw Error('The introduction must total exactly 1,200 frames.');const selected=nodes.filter(n=>n.selected.checked),g=bank.story_graph;
  const plans=[{variant:'Documentary',premise:'Source-backed cricket questions',fps:30,frame_count:1200,body_revision:bank.revision,canvas:bank.canvas,spoiler_review:g.spoiler_review,
   source_spans:selected.map(n=>({candidate_id:bank.candidates[0].id,source_id:bank.source.id,node_id:n.id,start:+n.start.value,end:+n.end.value,frames:Math.round((+n.end.value-+n.start.value)*30)})),
   promises:g.question_payoffs.filter(l=>selected.some(n=>n.id===l.question_id)).map(l=>({question_id:l.question_id,payoff_id:l.payoff_id,evidence_id:l.evidence_ids[0],payoff_timestamp:g.nodes.find(n=>n.id===l.payoff_id).body_start}))}];
  const plan_id=crypto.randomUUID().replaceAll('-',''),cmd=command();cmd.expected_revision=0;cmd.input_hashes=[bank.source.hash];await api('intro-plan',{...cmd,dataset_id:bank.id,plan_id,mode:'documentary',category:'cricket',body_revision:bank.revision,reference_card_id:$('doc-style-card').value,plans});
  const job=await api('intro-render',{plan_id,idempotency_key:cmd.idempotency_key+':render'});localStorage.setItem('storylens.documentary.preview',job.id);await watch(job.id);
 }catch(e){fail(e);}};
 async function watch(id){$('saved-job').value=id;const job=await api('job?id='+id);$('resume').hidden = !['failed','interrupted'].includes(job.status) || (job.resume_attempts || 0) >= 3; $('status').textContent=job.stage;if(['queued','running'].includes(job.status)){timer=setTimeout(()=>watch(id).catch(fail),1000);return;}if(job.status!=='complete')throw Error(job.error?.message||'The render stopped.');$('results').replaceChildren();const v=document.createElement('video');v.controls=true;v.width=640;v.src='/api/workbench/intro-media?id='+id+'&variant=0&token='+encodeURIComponent(token);$('results').append(v);
  const source = document.createElement('p');
  source.textContent = 'Original audio for the sound recipe: ' + job.result.intros[0].path;
  const label = document.createElement('label');
  const input = document.createElement('input');
  label.append('Completed sound mix job ID', input);
  const attach = document.createElement('button');
  attach.textContent = 'Apply sound recipe to documentary intro';
  attach.onclick = async () => {
   attach.disabled = true;
   try {
    const queued = await api('intro-sound', {intro_job_id: id, mix_job_id: input.value.trim(), variant: 0, idempotency_key: crypto.randomUUID()});
    localStorage.setItem('storylens.documentary.preview', queued.id);
    await watch(queued.id);
   } catch (e) { fail(e); }
   finally { attach.disabled = false; }
  };
  $('results').append(source, label, attach);
  $('status').textContent='40-second preview ready. Review the complete speech, pictures, sound and handoff. Main body preserved.';
 }
 // Restore documentary previews without reimporting or rerendering the source.
 async function restore(){clearTimeout(timer);const id=$('saved-job').value.trim(),job=await api('job?id='+id);if(!['intro','intro-sound'].includes(job.kind))throw Error('Choose a documentary intro render.');const plan=await api('intro-plan?id='+encodeURIComponent(job.request.plan_id));if(plan.mode!=='documentary')throw Error('Choose a cricket documentary preview.');localStorage.setItem('storylens.documentary.preview',id);await watch(id);}
 $('restore').onclick=()=>restore().catch(fail);
 $('resume').onclick = async () => {
  $('resume').disabled = true;
  try { await api('resume', {id: $('saved-job').value.trim()}); await restore(); }
  catch (e) { fail(e); }
  finally { $('resume').disabled = false; }
 };
 const previous=localStorage.getItem('storylens.documentary.preview');if(previous){$('saved-job').value=previous;restore().catch(fail);}
 window.addEventListener('beforeunload',()=>clearTimeout(timer));
})();
