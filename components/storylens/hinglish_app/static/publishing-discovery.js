/* SEO and packaging review. Applying suggestions edits local fields only. */
(function (host) {
 'use strict';
 const words=s=>new Set(String(s).toLowerCase().match(/[a-z0-9]+/g)?.filter(w=>!['the','a','an','in','on','of','for','to','and','my','your','is'].includes(w))||[]);
 function checks(title,thumb=''){
  const notes=[];
  if(!title.trim()||title.length>100)notes.push('Keep the title between 1 and 100 characters.');
  if(title.length>60)notes.push('The title may truncate on some surfaces. Put the subject first.');
  if(thumb.trim().split(/\s+/).filter(Boolean).length>5)notes.push('Check that the thumbnail wording stays readable at feed size.');
  const left=words(title),right=words(thumb);
  if(right.size>=2&&[...right].filter(w=>left.has(w)).length/right.size>=.75)notes.push('The thumbnail repeats much of the title. Consider complementary wording.');
  return notes;
 }
 function thumbnailDraft(plan,previous={}){
  const t=plan.thumbnail;
  return {...previous,idea:`${t.subject}\nComposition: ${t.composition}\nStyle: ${t.style}\nVideo topic: ${plan.primary_query}`,
   category:'youtube',aspect:'16:9',count:'1',text_mode:'exact',title:t.text,subtitle:'',custom_style:t.style};
 }
 const panels=new WeakMap();
 function render(container,options){
  if(!container)return;
  const {copy,id,mode,title,description,tags,apply,save,review,locked=false}=options,plan=copy?.discovery;
  const signature=JSON.stringify([id,plan||null,copy?.weekly_seo,options.weeklyPlans]);
  const previous=panels.get(container);
  if(previous?.signature===signature){previous.lock?.(locked);previous.weeklyLock?.(options.weeklyLocked);previous.update();return;}
  previous?.detach?.();
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const buttons=[];
  const button=(text,work)=>{const b=el('button',text);b.type='button';b.disabled=locked;b.onclick=work;buttons.push(b);return b;};
  const expanded=container.firstElementChild?.open===true;
  container.replaceChildren();container.hidden=!copy;
  if(!copy){panels.delete(container);return;}
  const details=el('details'),summary=el('summary','SEO & thumbnail review');details.open=expanded;details.append(summary);
  const body=el('div',undefined,'discovery-body');details.append(body);container.append(details);
  const weekly=mode!=='shorts'?host.StorylensWeekly?.render(body,options):null;
  if(!plan||plan.status!=='ready'){
   body.append(el('p',plan?.message||'This saved preparation has no SEO review. Refresh it to add suggestions without regenerating the video.','muted'));
   if(review)body.append(button('Refresh review',review));
   if(plan?.technical_details){const tech=el('details');tech.append(el('summary','Technical details'),el('pre',plan.technical_details));body.append(tech);}
   panels.set(container,{signature,update(){},lock:value=>buttons.forEach(b=>b.disabled=value),weeklyLock:weekly?.lock});return;
  }
  body.append(el('p',`Search intent: ${plan.intent} · Main phrase: ${plan.primary_query}`));
  if(plan.secondary_queries?.length)body.append(el('p','Related phrases: '+plan.secondary_queries.join(' · '),'muted'));
  const research=plan.research||{},observed=research.status==='observed';
  const source=el('details'),sourceLabel=observed?'Observed YouTube search suggestions':research.status==='disabled'?'Live search suggestions turned off':research.status==='no_suggestions'?'No live search suggestions returned':'Live search suggestions unavailable';
  source.append(el('summary',sourceLabel));
  if(research.query)source.append(el('p','Query: '+research.query));
  if(observed){const list=el('ul');for(const text of research.suggestions||[])list.append(el('li',text));source.append(list);}
  if(research.observed_at)source.append(el('p','Checked: '+new Date(research.observed_at*1000).toLocaleString()));
  source.append(el('p','Autocomplete suggestions are observations, not search volumes or ranking predictions.','muted'));body.append(source);
  const list=el('div',undefined,'discovery-titles');
  for(const row of plan.titles){
   const item=el('div',undefined,'discovery-title'),content=el('div');
   content.append(el('span',({search:'Search-focused',browse:'Browse-focused',hybrid:'Search + browse'})[row.angle]||row.angle,'muted'),el('p',row.title),el('small',row.reason));
   item.append(content,button('Use title',()=>{apply({title:row.title});update();}));list.append(item);
  }
  body.append(list);
  const seo=el('details');seo.append(el('summary','Suggested description & search tags'),el('p',plan.description,'discovery-description'),el('p','Search tags: '+plan.tags.join(', '),'muted'),button('Use description & tags',()=>apply({description:plan.description,tags:plan.tags})));
  body.append(seo);
  const t=plan.thumbnail,brief=el('div',undefined,'discovery-brief');brief.append(el('h3','Thumbnail brief'),el('p',`Suggested wording: ${t.text}`),el('p',t.subject),el('p',t.composition),el('p',t.style,'muted'));
  if(mode!=='shorts'){
   const link=el('a','Open brief in Thumbnail Studio');link.href='/?tool=thumbnail';link.target='_blank';link.rel='noopener';
   link.onclick=event=>{
    try{
     const key='storylens-thumbnail-studio-v1',old=localStorage.getItem(key);
     let prior={};try{prior=JSON.parse(old||'{}');if(!prior||Array.isArray(prior)||typeof prior!=='object')prior={};}catch(_){}
     if(old)localStorage.setItem(key+'-before-publishing-'+Date.now(),old);
     localStorage.setItem(key,JSON.stringify(thumbnailDraft(plan,prior)));
    }catch(error){event.preventDefault();const issue=host.storylensProblem?.(error);body.append(el('p',issue?.message||'The thumbnail brief could not be saved. Copy the brief above into Thumbnail Studio.'));}
   };
   brief.append(link,el('small','Opens a new draft. Choose Generate in Thumbnail Studio when ready. Your previous draft is backed up.'));
  }else brief.append(el('small','A packaging reference only. This workflow keeps Shorts and Reels without uploaded covers.'));
  body.append(brief);
  const label=el('label','Thumbnail wording to compare (optional)'),thumb=el('input');thumb.maxLength=300;thumb.placeholder='Type the wording on your chosen image';label.append(thumb);body.append(label);
  const notes=el('ul',undefined,'discovery-checks');notes.setAttribute('aria-live','polite');body.append(notes);
  function update(){
   const result=checks(title.value,thumb.value);
   notes.replaceChildren(...(result.length?result:['Title length and wording checks passed. These checks do not assess the image.']).map(text=>el('li',text)));
  }
  thumb.oninput=update;title.addEventListener('input',update);update();
  const actions=el('div',undefined,'inline');actions.append(button('Save reviewed text',save));if(review)actions.append(button('Refresh review',review));body.append(actions,el('small','Review title, description, hashtags and thumbnail together before choosing Post now or Schedule. No ranking guarantee.'));
  panels.set(container,{signature,update,lock:value=>buttons.forEach(b=>b.disabled=value),weeklyLock:weekly?.lock,detach:()=>title.removeEventListener('input',update)});
 }
 const api={checks,thumbnailDraft,render};host.StorylensDiscovery=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
