(function(root,factory){const api=factory(typeof module==='object'?require('./prepare-post-progress.js'):root.StorylensStageProgress);if(typeof module==='object'&&module.exports)module.exports=api;else root.StorylensAssistantProgress=api;})(typeof window==='object'?window:this,function(stages){
 'use strict';
 const labels={inspect:'Check video',speech:'Transcript',selection:'Choose Shorts','highlight-signals':'Gameplay scan','highlight-selection':'Choose highlights',highlights:'Create highlights'};
 function duration(seconds){seconds=Math.max(0,Math.round(seconds||0));return seconds<60?seconds+'s':Math.floor(seconds/60)+'m '+seconds%60+'s';}
 function name(key){if(labels[key])return labels[key];const [kind,platform,index]=key.split(':');return kind==='render'?'Create clip '+platform:kind==='context'?'Read section '+platform:kind==='copy'?(platform==='youtube'?'YouTube text ':'Instagram caption ')+index:key;}
 function build(session,now=Date.now()/1000){
  const data=session.task_progress,cards=[],busy=['planning','running','transcribing'].includes(session.status);
  if(data){
   const roles=data.workflow?['long','shorts']:['preparation'];
   for(const role of roles){
    const draft=data.drafts.find(d=>d.role===role),mode=draft?.mode||(role==='long'?'long':'shorts'),count=draft?.count||(role==='long'?1:data.count);
    for(const key of stages.plan(draft,mode,count)){
     const measure=stages.measure(key,draft,draft?.live),timing=draft?.stage_timings?.[key];
     const elapsed=timing?(timing.elapsed??Math.max(0,(measure.state==='active'?now:timing.finished||timing.started)-timing.started)):null;
     const eta=measure.state==='active'&&measure.percent>0&&measure.percent<100&&elapsed>0?elapsed*(100-measure.percent)/measure.percent:null;
     cards.push({id:role+':'+key,label:(data.workflow?(role==='long'?'Long · ':'Shorts · '):'')+name(key),...measure,elapsed,eta});
    }
    if(!data.workflow)continue;
    for(const platform of role==='long'?['long']:['youtube','instagram'])for(let index=1;index<=(role==='long'?1:data.count);index++){
     const job=data.jobs.find(j=>j.role===platform&&j.index===index),deleted=job?.deleted_by_owner,cancelled=job?.status==='cancelled'||deleted,buffered=platform==='instagram'&&job?.status==='ready'&&job.authorized;
     // Instagram's durable published state is set after its matching share receipt
     // is verified; it does not carry YouTube's verification timestamps.
     const instagramPublished=platform==='instagram'&&job?.status==='published';
     const done=buffered||instagramPublished||Boolean(job?.verified&&['scheduled','published'].includes(job.status)),failed=job&&['blocked','needs_review'].includes(job.status);
     cards.push({id:platform+':delivery:'+index,label:platform==='long'?'Long · YouTube schedule':platform==='instagram'?'Instagram buffer '+index:'YouTube schedule '+index,
      state:cancelled?'cancelled':done?'done':failed?'failed':job?'active':'pending',percent:cancelled||done?100:job?null:0,
      text:deleted?'Deleted by you · not reuploaded':cancelled?'Cancelled · kept private':buffered?'Queued locally · not posted':instagramPublished?'100% · Published on Instagram':done?'100% · Verified by YouTube':failed?'Needs attention':job?'Working · '+job.status.replaceAll('_',' '):'0% · Waiting',elapsed:null,eta:null});
    }
   }
  }else{
   const plan=session.steps||[],current=session.step_index||0;
   for(let index=0;index<Math.max(plan.length,busy?1:0);index++){
    const state=index<current||(!busy&&session.status==='complete')?'done':index===current?(busy?'active':'failed'):'pending';
    const actual=session.job?.progress,percent=state==='done'?100:state==='active'&&typeof actual==='number'&&Number.isFinite(actual)?Math.max(0,Math.min(99,actual)):state==='pending'?0:null;
    cards.push({id:'step:'+index,label:plan[index]?.tool?.replaceAll('_',' ')||(session.status==='transcribing'?'Listen to request':'Plan request'),state,percent,text:state==='done'?'100% · Done':state==='pending'?'0% · Waiting':session.stage||'Working',elapsed:null,eta:null});
   }
  }
  const finished=cards.filter(c=>['done','cancelled'].includes(c.state)).length;
  return {cards,finished,total:cards.length,remaining:cards.length-finished,percent:cards.length?Math.floor(finished/cards.length*100):null,
   elapsed:data?.elapsed??(session.active_request_created&&(busy||session.status_updated_at)?Math.max(0,(busy?now:session.status_updated_at)-session.active_request_created):null),busy};
 }
 function render(host,session){
  if(!host)return;const view=build(session);host.hidden=!view.total;if(!view.total){host.replaceChildren();return view;}
  const el=(tag,text,className)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(className)n.className=className;return n;};
  const changed=host.dataset.session!==session.id;host.dataset.session=session.id;
  if(changed)host.replaceChildren();
  let summary=host.querySelector('.assistant-progress-summary'),estimate=host.querySelector('.assistant-progress-estimate'),grid=host.querySelector('.assistant-progress-cards');
  if(!grid){summary=el('div','','assistant-progress-summary');estimate=el('p','','assistant-progress-estimate');grid=el('div','','assistant-progress-cards');host.append(summary,estimate,grid);}
  const scrollTop=grid.scrollTop,scrollLeft=grid.scrollLeft;
  summary.textContent=`${view.finished}/${view.total} steps finished · ${view.remaining} remaining`;
  if(view.elapsed!==null)summary.append(el('span','Elapsed '+duration(view.elapsed)));
  estimate.textContent=view.cards.some(c=>c.state==='active'&&c.eta!==null)?'Estimates update from measured progress.':view.busy?'Remaining time is not yet measurable.':'Saved progress';
  const cells=new Map(Array.from(grid.children,cell=>[cell.dataset.stage,cell]));
  let index=0;
  for(const card of view.cards){const cell=el('section','','assistant-step '+card.state);cell.append(el('b',card.label+(card.state==='done'?' ✓':'')));
   const bar=el('progress');bar.max=100;if(card.percent!==null)bar.value=card.percent;bar.setAttribute('aria-label',card.label);cell.append(bar,el('span',card.text));
   if(card.elapsed!==null)cell.append(el('small','Elapsed '+duration(card.elapsed)+(card.eta!==null?' · About '+duration(card.eta)+' left':'')));
   const existing=cells.get(card.id);
   if(existing){existing.className=cell.className;existing.replaceChildren(...Array.from(cell.childNodes));cells.delete(card.id);}
   const target=existing||cell;target.dataset.stage=card.id;
   if(grid.children[index]!==target)grid.insertBefore(target,grid.children[index]||null);
   index++;
  }
  for(const cell of cells.values())cell.remove();
  grid.scrollTop=changed?0:scrollTop;grid.scrollLeft=changed?0:scrollLeft;
  return view;
 }
 return {build,render,duration};
});
