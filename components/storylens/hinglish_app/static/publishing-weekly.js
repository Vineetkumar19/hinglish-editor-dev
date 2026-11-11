/* Optional1-4week refresh of an existing YouTube video through Chrome. */
(function(root){
 'use strict';
 function render(container,options){
  if(!options.generateWeekly||options.mode==='shorts')return null;
  const {copy,preparation,weeklyPlans=[],generateWeekly,enableWeekly,pauseWeekly}=options;
  let currentLock=options.weeklyLocked;
  const proposal=copy?.weekly_seo,ready=proposal?.status==='ready',buttons=[],editable=[];
  const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  const button=(text,work)=>{const b=el('button',text);b.type='button';b.onclick=work;buttons.push(b);return b;};
  const details=el('details'),body=el('div');details.open=ready||weeklyPlans.length>0;details.className='weekly-review';body.className='discovery-body';details.append(el('summary','Weekly YouTube refresh · optional'),body);container.append(details);
  body.append(el('p','Choose 1–4 weekly packages for this same video. Week 1 starts after its verified public release. Later sets run seven days after the previous update succeeds, through YouTube Studio in Chrome.'));
  const selection=el('label','Weeks'),weeks=el('select');
  for(let i=1;i<=4;i++){const o=el('option',i+' week'+(i>1?'s':''));o.value=String(i);weeks.append(o);}weeks.value=String(proposal?.weeks||1);selection.append(weeks);editable.push(weeks);
  const actions=el('div');actions.className='inline';actions.append(selection,button('Generate weekly packages · V8',()=>generateWeekly(Number(weeks.value))));body.append(actions);
  if(proposal?.status==='needs_review'){
   body.append(el('p',proposal.message||'The weekly plan needs review. Generate it again; your publishing text is kept.'));
   if(proposal.technical_details){const technical=el('details');technical.append(el('summary','Technical details'),el('pre',proposal.technical_details));body.append(technical);}
  }
  const enabled=weeklyPlans.some(p=>p.enabled&&!['complete','cancelled'].includes(p.status));
  if(ready){
   const toggle=el('label'),images=el('input');images.type='checkbox';toggle.className='weekly-thumbnail-toggle';toggle.append(images,el('span','Also change the thumbnail each week'));body.append(toggle);editable.push(images);
   const fields=[];
   for(const row of proposal.variants){
    const week=el('details');week.open=row.week===1;week.append(el('summary','Week '+row.week+' · '+row.title));
    const form=el('div');form.className='discovery-body';form.append(el('p',row.reason));
    if(row.evidence){const evidence=el('details');evidence.append(el('summary','Spoken evidence'),el('p',row.evidence));form.append(evidence);}
    const titleLabel=el('label','Week '+row.week+' title'),title=el('input');title.maxLength=100;title.value=row.title;titleLabel.append(title);
    const descriptionLabel=el('label','Week '+row.week+' description & hashtags'),description=el('textarea');description.rows=4;description.maxLength=5000;description.value=row.description;descriptionLabel.append(description);
    const imageLabel=el('label','Week '+row.week+' finished thumbnail path'),image=el('input');image.placeholder='Choose an existing PNG, JPEG or WebP file';image.value=row.week===1?preparation?.thumbnail?.path||'':'';imageLabel.append(image);imageLabel.hidden=true;
    const brief=el('p','Thumbnail brief: '+row.thumbnail.text+' · '+row.thumbnail.subject+' · '+row.thumbnail.composition+' · '+row.thumbnail.style);brief.className='muted';
    const link=el('a','Open week '+row.week+' brief in Thumbnail Studio');link.href='/?tool=thumbnail';link.target='_blank';link.rel='noopener';
    link.onclick=event=>{try{const key='storylens-thumbnail-studio-v1',previous=localStorage.getItem(key);let saved={};try{saved=JSON.parse(previous||'{}')||{};}catch(_){}if(previous)localStorage.setItem(key+'-before-weekly-'+Date.now(),previous);localStorage.setItem(key,JSON.stringify(root.StorylensDiscovery.thumbnailDraft({thumbnail:row.thumbnail,primary_query:title.value},saved)));}catch(_){event.preventDefault();form.append(el('p','The thumbnail brief could not be saved. Copy the brief above into Thumbnail Studio.'));}};
    form.append(titleLabel,descriptionLabel,brief,link,imageLabel);week.append(form);body.append(week);fields.push({row,title,description,image,imageLabel});editable.push(title,description,image);
   }
   images.onchange=()=>fields.forEach(f=>f.imageLabel.hidden=!images.checked);
   const enable=button('Enable this '+proposal.weeks+'-week browser plan',()=>{
    const variants=fields.map(({row,title,description})=>({...row,title:title.value,description:description.value}));
    return enableWeekly({revision:proposal.revision,variants,change_thumbnails:images.checked,thumbnails:fields.map(f=>f.image.value.trim())});
   });enable.dataset.enabledPlan=enabled?'true':'false';enable.dataset.planWeeks=String(proposal.weeks);body.append(enable);
   body.append(el('small','You approve every set here. Changing the week selector requires generating a new plan. Hashtags are part of each description. Weekly changes apply to this existing YouTube video only.'));
  }
  for(const plan of weeklyPlans.slice(-4)){
   const status=el('div');status.className='weekly-status';status.append(el('p',plan.weeks+'-week plan · '+plan.status.replaceAll('_',' ')),el('p',plan.message));
   if(plan.start_at)status.append(el('small','Started '+new Date(plan.start_at*1000).toLocaleString()+(plan.estimated_end_at?' · Earliest finish '+new Date(plan.estimated_end_at*1000).toLocaleString():'')));
   for(const step of plan.steps||[])status.append(el('small','Week '+(step.week||'?')+' · '+(step.status==='complete'?'Text verified in Studio':step.status==='queued'&&step.not_before*1000<=Date.now()?'Due · waiting for the connection':step.status.replaceAll('_',' '))+(step.not_before?' · '+new Date(step.not_before*1000).toLocaleDateString():'')));
   if(plan.enabled&&!['complete','cancelled'].includes(plan.status))status.append(button('Pause future weekly changes',()=>pauseWeekly(plan.id)));
   if(plan.technical_details){const d=el('details');d.append(el('summary','Technical details'),el('pre',plan.technical_details));status.append(d);}body.append(status);
  }
  body.append(el('small','If your laptop or internet is off, the due set waits and runs when Storylens, Chrome and Studio reconnect. Later sets move to seven days after each successful update. Your manual saved edits do not stop the plan; the next set replaces them. Unsaved Studio edits wait until saved or discarded. Use Pause to stop future changes. This is a sequential refresh plan, not a controlled A/B test or a guaranteed boost.'));
  const lock=value=>{currentLock=value;for(const b of buttons)b.disabled=!!value||b.dataset.enabledPlan==='true'||!!b.dataset.planWeeks&&b.dataset.planWeeks!==weeks.value;for(const f of editable)f.disabled=!!value||enabled;};weeks.onchange=()=>lock(currentLock);lock(options.weeklyLocked);
  return {lock};
 }
 const api={render};root.StorylensWeekly=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
