(() => {
 'use strict';
 const $=id=>document.getElementById(id),all=s=>[...document.querySelectorAll(s)],node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 let token='',profile='cricket',mode='long',connected=false,busy=false,snapshot=null,records=[],current=null,longDraft=null,selectedClip=1,signIn=null;
 const refreshing=new Set();
 const dirty=new Set(),remembered=new Map(),requests=new Map();
 const liveProgress=new Map(),taskIds=new Map();
 const taskKey=value=>typeof value==='string'?value:value?.id||null;
 const queryDrafts=(new URLSearchParams(location.search).get('drafts')||'').split(',').filter(id=>/^[A-Za-z0-9_-]{1,80}$/.test(id));
 let handoffApplied=false,longDirty=false,shortsOptedIn=false;
 const active=d=>d&&['working','queued','cancelling'].includes(d.status);
 const canCancel=d=>d&&!['cancelled','cancelling'].includes(d.status)&&!Object.values(d.jobs_by_platform||{}).some(ids=>ids.length);
 const availableMode=value=>profile==='gaming'?['shorts','highlights'].includes(value):['long','shorts'].includes(value);
 const basename=path=>String(path||'').split(/[\\/]/).pop();
 const storageKey=kind=>'storylens-simple-'+kind+'-'+profile;
 const emptyView=value=>localStorage.getItem(storageKey('cleared-'+value))==='true';
 const dismissed=()=>{try{return JSON.parse(localStorage.getItem(storageKey('dismissed'))||'[]');}catch(_){return [];}};
 const keyFor=value=>{const signature=JSON.stringify([profile,value]);if(!requests.has(signature))requests.set(signature,crypto.randomUUID());return requests.get(signature);};
 function problem(error){const issue=window.storylensProblem?window.storylensProblem(error):{message:String(error.message||error)};$('problem').replaceChildren(node('p',issue.message.replaceAll('Publishing Studio','Connections')));const details=window.storylensDetails?.(issue);if(details)$('problem').append(details);}
 const readTimeout=()=>globalThis.AbortSignal?.timeout(10000);
 async function api(action,body={},scope=profile){const response=await fetch('/api/publisher/prepare-post',{...(action==='list'?{signal:readTimeout()}:{}),method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},body:JSON.stringify({...body,action,profile:scope})});const data=await response.json();if(!response.ok){const error=Error(data.error||'Storylens could not complete this step.');error.code=data.error_code;error.details=data.error_details;throw error;}return data;}
 async function guard(work,label='Updating your selection'){if(busy)return;busy=true;controls();$('problem').replaceChildren();$('actionProgress').hidden=false;$('actionProgress').replaceChildren(meter(label,null,label),node('span','0/1 complete · '+label));try{await work();}catch(error){problem(error);}finally{busy=false;$('actionProgress').hidden=true;controls();}}
 function inputSettings(){return {source:$('source').value,thumbnail:$('thumbnail').value,count:$('count').value,minutes:$('minutes').value,savedCount:$('savedCount').value,mode};}
 function declarations(){const result={};for(const [key,id] of [['made_for_kids','audience'],['synthetic_media','synthetic']]){if(!$(id).value)throw Error('Choose audience and altered-content declarations first.');result[key]=$(id).value==='yes';}return result;}
 function renderMode(){
  if(!availableMode(mode))mode=profile==='gaming'?'highlights':'long';
  all('[data-profile]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.profile===profile)));
  all('[data-mode]').forEach(b=>{b.hidden=!availableMode(b.dataset.mode);b.setAttribute('aria-pressed',String(b.dataset.mode===mode));});
  document.dispatchEvent(new CustomEvent('storylens-publishing-profile',{detail:profile}));
  document.querySelector('.source-grid').className='source-grid'+(mode==='long'?'':' '+mode);
  $('thumbnailField').hidden=mode==='shorts';$('countField').hidden=mode!=='shorts';$('minutesField').hidden=mode!=='highlights';
  $('thumbnail').placeholder='Optional: choose a thumbnail or paste its full path';
  $('longPost').hidden=$('longSchedule').hidden=mode!=='long';$('run').hidden=false;
  $('cancelLong').hidden=mode!=='long';
  $('reviewHeading').textContent=mode==='long'?'Want to create Shorts?':mode==='highlights'?'Highlights':'Shorts & Reels';
  $('savedCountField').hidden=$('startSaved').hidden=mode!=='long';
  $('saved').hidden=mode==='highlights';
  renderSaved();renderReview();controls();
 }
 function renderSaved(){
  const previous=$('saved').value;
  const options=records.filter(d=>d.status!=='cancelled'&&(mode==='long'?d.mode==='long'&&d.stages?.speech:d.mode===mode));
  $('saved').replaceChildren(node('option',mode==='long'?'Select a saved Long video':'Select a saved preparation'),...options.map(d=>{const o=node('option',basename(d.source.path)+(d.status==='failed'?' · needs attention':''));o.value=d.id;return o;}));
  $('saved').firstChild.value='';
  $('saved').value=options.some(d=>d.id===previous)?previous:mode!=='long'&&current&&options.some(d=>d.id===current.id)?current.id:'';
  const highlights=records.filter(d=>d.status!=='cancelled'&&d.mode==='highlights'&&d.stages?.highlights?.video),chosen=$('savedHighlights').value;
  $('savedHighlights').replaceChildren(node('option','Select saved Highlights'),...highlights.map(d=>{const o=node('option',basename(d.source.path));o.value=d.id;return o;}));$('savedHighlights').firstChild.value='';
  $('savedHighlights').value=highlights.some(d=>d.id===chosen)?chosen:highlights.find(d=>d.id===current?.id)?.id||'';
  $('highlightShorts').hidden=profile!=='gaming'||mode!=='highlights';
 }
 function controls(){
  const disabled=busy||!connected,hasSource=Boolean($('source').value.trim()),sameLong=longDraft&&longDraft.source.path.toLowerCase()===$('source').value.trim().toLowerCase();
  const longLocked=active(longDraft)||Boolean(longDraft?.jobs_by_platform?.youtube?.length),longCopy=longDraft?.stages?.['copy:youtube:1'];
  for(const id of ['longPost','longSchedule'])$(id).disabled=disabled||!snapshot?.release_actions_supported||!longCopy||longLocked||!sameLong||Boolean(longDraft?.cancel_requested);
  for(const id of ['longTitle','longDescription','longTags'])$(id).disabled=disabled||!longCopy||longLocked;
  $('run').disabled=disabled||!hasSource||active(mode==='long'?longDraft:current);
  $('clear').disabled=busy||active(current)||active(longDraft);$('clearReview').disabled=busy||active(current);
  $('startSaved').disabled=disabled||!$('saved').value||active(current);
  $('cancelLong').disabled=disabled||!snapshot?.cancel_preparation_supported||!(longDraft?canCancel(longDraft):hasSource);
  $('cancelReview').disabled=disabled||!snapshot?.cancel_preparation_supported||!(current?canCancel(current):mode==='long'?Boolean($('saved').value):hasSource);
  for(const [id,draft] of [['cancelLong',longDraft],['cancelReview',current]])$(id).title=draft&&Object.values(draft.jobs_by_platform||{}).some(ids=>ids.length)?'Already submitted. Check Scheduled posts.':'Cancel this preparation; completed files are kept.';
  const highlight=records.find(d=>d.id===$('savedHighlights').value);
  $('startHighlightShorts').disabled=disabled||!snapshot?.highlights_source_supported||!highlight?.stages?.highlights?.video||active(highlight);
  $('savedHighlights').disabled=$('highlightShortsCount').disabled=disabled;
  for(const id of ['pickVideo','pickThumbnail','source','thumbnail','count','minutes','savedCount','saved'])$(id).disabled=disabled;
  all('[data-profile],[data-mode]').forEach(b=>b.disabled=busy||!token);
  $('clip').disabled=disabled||!current;
  for(const platform of ['youtube','instagram']){
   for(const id of platform==='youtube'?['title','description','tags']:['caption'])$(id).disabled=disabled||!current?.stages?.[`copy:${platform}:${selectedClip}`]||active(current)||Boolean(current.jobs_by_platform?.[platform]?.length);
  }
  for(const [id,action] of [['postClips','post_now'],['scheduleClips','schedule']])$(id).disabled=disabled||!snapshot?.release_actions_supported||!canPostClips(action);
  for(const id of ['discoveryReview','discoveryResearch'])$(id).disabled=disabled||active(current)||active(longDraft);
  const cover=mode==='long'?longDraft:mode==='highlights'?current:null;
  $('saveThumbnail').disabled=disabled||cover?.status!=='prepared'||Boolean(cover?.jobs_by_platform?.youtube?.length)||cover?.source?.path.toLowerCase()!==$('source').value.trim().toLowerCase();
 }
 function platformsForClips(){return current?.mode==='highlights'?['youtube']:['youtube','instagram'];}
 function submitted(platform){const jobs=(current?.jobs||[]).filter(job=>job.platform===platform);return jobs.length>0&&jobs.every(job=>!['draft','blocked','uploaded_private'].includes(job.status));}
 function canPostClips(action){
  if(!current||active(current))return false;
  const platforms=platformsForClips(),jobs=(current.jobs||[]).filter(job=>platforms.includes(job.platform));
  if(jobs.some(job=>['needs_review','cancelled'].includes(job.status)||job.status==='blocked'&&Object.keys(job.remote||{}).length))return false;
  if(platforms.some(p=>current.release_actions?.[p]&&current.release_actions[p]!==action)||jobs.some(job=>job.release_action&&job.release_action!==action))return false;
  return platforms.every(p=>Array.from({length:current.count},(_,i)=>current.stages?.[`copy:${p}:${i+1}`]).every(Boolean))&&platforms.some(p=>!submitted(p));
 }
 function stageName(key){const [kind,p,n]=key.split(':');return kind==='weekly'?'Weekly SEO plan':kind==='discovery'?'SEO review':kind==='copy'?`${p==='youtube'?'YouTube':'Instagram'} ${n}`:kind==='render'?`Clip ${p}`:({inspect:'Source',speech:'Transcript',selection:'Clip selection','highlight-signals':'Gameplay scan','highlight-selection':'Highlights selection',highlights:'Highlights',posting:'YouTube upload'})[key]||key.replace('context:','Context ');}
 function meter(label,value,text){
  const wrap=node('div'),bar=node('progress'),motion=node('span');wrap.className='stage-meter'+(value===null?' indeterminate':'');bar.max=100;
  bar.setAttribute('aria-label',label);bar.setAttribute('aria-valuetext',text);if(value!==null)bar.value=value;
  motion.className='meter-motion';motion.hidden=value!==null;motion.setAttribute('aria-hidden','true');wrap.append(bar,motion);return wrap;
 }
 function renderStageBoxes(container,draft,fallbackMode,fallbackCount=1){
  const keys=window.StorylensStageProgress.plan(draft,fallbackMode,fallbackCount),live=liveProgress.get(draft?.id),cards=[];
  const done=keys.filter(key=>Object.prototype.hasOwnProperty.call(draft?.stages||{},key)).length,counter=$(container===$('longStages')?'longProgressCount':'reviewProgressCount');
  counter.textContent=`${done}/${keys.length} steps complete · ${keys.length-done} remaining`;
  for(const key of keys){
   const value=window.StorylensStageProgress.measure(key,draft,live),card=node('div'),label=node('span',stageName(key)+(value.state==='done'?' ✓':'')),detail=node('span',value.text);
   card.className='stage-card '+value.state;card.dataset.stage=key;label.className='stage-label';detail.className='stage-detail';
   card.append(label,meter(stageName(key),value.percent,value.text),detail);
   if(value.state==='active'&&live){
    const age=Math.max(0,Math.floor(Date.now()/1000-live.changed_at)),fresh=node('span',age<10?'Progress just updated':'Last update '+(age<60?age+'s':Math.floor(age/60)+'m '+age%60+'s')+' ago');
    fresh.className='stage-freshness';card.append(fresh);card.title=live.message;
   }
   cards.push(card);
  }
  container.replaceChildren(...cards);
 }
 async function refreshLiveProgress(){
  const drafts=[current,longDraft].filter(d=>d?.status==='working');if(!drafts.length)return;
  try{
   const data=await publisherApi(''),tasks=(data.tasks||[]).filter(t=>t.status==='working'&&t.message&&t.message!=='Preparing…');
   for(const draft of drafts){
    const id=taskKey(taskIds.get(draft.id)),task=id?tasks.find(t=>t.id===id):drafts.length===1&&tasks.length===1?tasks[0]:null;
    if(!task)continue;
    const previous=liveProgress.get(draft.id),message=String(task.message),stage=draft.current_stage;
    liveProgress.set(draft.id,{task:task.id,stage,message,changed_at:previous?.task===task.id&&previous.stage===stage&&previous.message===message?previous.changed_at:Date.now()/1000});
   }
  }catch(_){/* Saved stage results remain visible if live activity is unavailable. */}
 }
 function progress(container,draft){
  container.replaceChildren();if(!draft)return;
  const activity=draft.status==='working'&&draft.current_stage?window.StorylensStageProgress.activity(draft.current_stage,liveProgress.get(draft.id)?.message||''):draft.status==='queued'?'Waiting for the processing queue':draft.message||'';
  container.append(node('span',activity));
  for(const [key,issue] of Object.entries(draft.errors||{})){
   const details=node('details'),summary=node('summary',stageName(key)+' · '+(issue.error||'Needs attention'));details.append(summary);
   if(issue.error_details){const technical=node('details');technical.append(node('summary','Technical details'),node('pre',issue.error_details));details.append(technical);}container.append(details);
  }
 }
 function receipts(container,jobs){
  container.replaceChildren();
  for(const job of jobs){
   const row=node('div');row.className='delivery-row';
   const when=new Date(job.due*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
   const label=({uploading:'Uploading',uploaded_private:job.release_action?'Preparing release':'Private upload saved',processing:job.release_message||'Verifying',scheduled:'Scheduled · verified',published:'Published · verified',needs_review:'Needs attention',blocked:'Needs attention',ready:'Queued locally'})[job.status]||job.status.replaceAll('_',' ');
   row.append(node('p',`${job.prepare_post_index||1} · ${label}${job.release_action==='schedule'?' · '+when+' IST':''}`));
   const complete=['scheduled','published'].includes(job.status)||job.status==='uploaded_private'&&!job.release_action,waiting=['draft','ready','cancelled','blocked','needs_review'].includes(job.status),text=complete?'100% · 1/1 complete':'0/1 complete · '+(waiting?label:job.status==='uploading'?'Uploading your video':'Checking the platform result');
   row.className+=' '+(complete?'done':waiting?'pending':'active');row.append(meter((job.platform==='youtube'?'YouTube':'Instagram')+' post '+(job.prepare_post_index||1),complete?100:waiting?0:null,text),node('span',text));
   if(job.error){const details=node('details');details.append(node('summary',job.error));if(job.error_details)details.append(node('pre',job.error_details));row.append(details);}
   if(job.remote?.url&&/^https:\/\/(www\.)?(youtube\.com|instagram\.com)\//.test(job.remote.url)){const a=node('a','View post');a.href=job.remote.url;a.target='_blank';a.rel='noopener';row.append(a);}
   container.append(row);
  }
 }
 function renderLong(){
  const empty=emptyView('long')&&!longDraft;
  $('longProgress').hidden=mode!=='long'||!longDraft;$('longReceipt').hidden=mode!=='long'||!longDraft;$('longProgressCount').hidden=mode!=='long';
  $('longProgressCount').hidden=mode!=='long'||empty;
  $('longStages').hidden=mode!=='long'||empty;if(mode==='long')renderStageBoxes($('longStages'),longDraft,'long');
  progress($('longProgress'),longDraft);receipts($('longReceipt'),(longDraft?.jobs||[]).filter(j=>j.platform==='youtube'));
  $('longMetadata').hidden=mode!=='long'||empty;
  const copy=longDraft?.stages?.['copy:youtube:1']?.metadata;
  if(!longDirty){$('longTitle').value=copy?.title||'';$('longDescription').value=copy?.description||'';$('longTags').value=copy?.tags?.join(', ')||'';}
  $('longCopyState').textContent=copy?'Ready to review':longDraft?'Preparing…':'Waiting for video';
  renderDiscovery('longDiscovery',longDraft,1,true);
 }
 function renderDiscovery(host,draft,index,long=false){
  const fields=long?{title:'longTitle',description:'longDescription',tags:'longTags'}:{title:'title',description:'description',tags:'tags'};
  window.StorylensDiscovery?.render($(host),{copy:draft?.stages?.[`copy:youtube:${index}`],id:(draft?.id||'')+':'+index,mode:draft?.mode,
   title:$(fields.title),description:$(fields.description),tags:$(fields.tags),
   locked:busy||!connected||active(draft)||Boolean(draft?.jobs_by_platform?.youtube?.length),
   review:()=>guard(async()=>{await saveEdits();const result=await api('review-discovery',{id:draft.id,index,live_research:$('discoveryResearch').checked===true});if(taskKey(result.task))taskIds.set(draft.id,taskKey(result.task));await refresh();},'Refreshing the SEO and thumbnail review'),
   weeklyLocked:busy||!connected||active(draft),preparation:draft,
   weeklyPlans:(snapshot?.weekly_seo_plans||[]).filter(p=>p.preparation===draft?.id),
   generateWeekly:weeks=>guard(async()=>{if(!snapshot?.weekly_seo_supported)throw Error('Restart Storylens after current work finishes to enable weekly SEO plans. Your prepared video is kept.');await saveEdits();const result=await api('generate-weekly-seo',{id:draft.id,index,weeks});if(taskKey(result.task))taskIds.set(draft.id,taskKey(result.task));await refresh();},'V8 is preparing the weekly SEO plan'),
   enableWeekly:values=>guard(async()=>{if(!snapshot?.weekly_seo_supported)throw Error('Restart Storylens after current work finishes to enable weekly SEO plans.');await saveEdits();await api('weekly-seo-enable',{...values,id:draft.id,authorize:true});await refresh();},'Saving your approved weekly browser plan'),
   pauseWeekly:key=>guard(async()=>{await api('weekly-seo-pause',{id:key});await refresh();},'Pausing future weekly changes'),
   apply:values=>{if(busy||!connected||active(draft)||draft?.jobs_by_platform?.youtube?.length)return;for(const [key,value] of Object.entries(values)){$(fields[key]).value=Array.isArray(value)?value.join(', '):value;$(fields[key]).oninput();}},
   save:()=>guard(async()=>{await saveEdits();await refresh();},'Saving reviewed publishing text')});
 }
 function renderReview(){
  renderLong();const d=current;
  $('reviewSection').hidden=mode==='highlights'&&!d;
  $('highlightShorts').hidden=profile!=='gaming'||mode!=='highlights';
  $('reviewBody').hidden=mode==='long'&&!shortsOptedIn||mode!=='long'&&emptyView(mode)&&!current;$('clip').hidden=$('cancelReview').hidden=$('clearReview').hidden=mode==='long'&&!shortsOptedIn;
  const count=d?.count||Math.max(1,Math.min(40,Number(mode==='long'?$('savedCount').value:mode==='shorts'?$('count').value:1)||1));
  if(selectedClip>count)selectedClip=1;
  $('clip').replaceChildren(...Array.from({length:count},(_,i)=>{const option=node('option',(d?.mode==='highlights'?'Video ':'Clip ')+(i+1));option.value=String(i+1);return option;}));$('clip').value=String(selectedClip);
  if(!d){
   for(const id of ['title','description','tags','caption','clipPath','reviewStatus'])$(id).value!==undefined?$(id).value='':$(id).textContent='';
   for(const id of ['youtubeReceipt','instagramReceipt'])$(id).replaceChildren();
   renderStageBoxes($('stages'),null,mode==='long'?'shorts':mode,count);
   $('youtubeState').textContent=$('instagramState').textContent='Waiting for clips';
   $('instagramMetadata').hidden=mode==='highlights';$('metadata').classList.toggle('single',mode==='highlights');
   renderDiscovery('clipDiscovery',null,1);controls();return;
  }
  progress($('reviewStatus'),d);renderStageBoxes($('stages'),d,d.mode,d.count);
  const yt=d.stages?.[`copy:youtube:${selectedClip}`],ig=d.stages?.[`copy:instagram:${selectedClip}`];
  for(const [id,value,platform] of [['title',yt?.metadata.title,'youtube'],['description',yt?.metadata.description,'youtube'],['tags',yt?.metadata.tags?.join(', '),'youtube'],['caption',ig?.metadata.instagram_caption,'instagram']])if(!dirty.has(platform))$(id).value=value||'';
  $('youtubeState').textContent=yt?'Ready':'Preparing…';$('instagramState').textContent=ig?'Ready':'Preparing…';
  $('instagramMetadata').hidden=d.mode!=='shorts';$('metadata').classList.toggle('single',d.mode!=='shorts');
  const output=d.stages?.[`render:${selectedClip}`]||d.stages?.highlights;$('clipPath').textContent=output?.video?.path||d.source.path;
  for(const p of ['youtube','instagram'])receipts($(p+'Receipt'),(d.jobs||[]).filter(j=>j.platform===p));
  renderDiscovery('clipDiscovery',d,selectedClip);
  controls();
 }
 async function saveEdits(){
  const cover=mode==='long'?longDraft:mode==='highlights'?current:null;
  if(cover?.status==='prepared'&&!cover.jobs_by_platform?.youtube?.length&&cover.source.path.toLowerCase()===$('source').value.trim().toLowerCase()&&($('thumbnail').value.trim()!==(cover.thumbnail?.path||''))){
   const updated=await api('edit-thumbnail',{id:cover.id,path:$('thumbnail').value.trim()});
   if(mode==='long')longDraft={...longDraft,...updated};else current={...current,...updated};
  }
  if(longDirty&&longDraft){await api('edit',{id:longDraft.id,platform:'youtube',index:1,metadata:{title:$('longTitle').value,description:$('longDescription').value,tags:$('longTags').value.split(',').map(t=>t.trim()).filter(Boolean)}});longDirty=false;}
  if(!current||!dirty.size)return;
  for(const platform of [...dirty]){
   const metadata=platform==='youtube'?{title:$('title').value,description:$('description').value,tags:$('tags').value.split(',').map(t=>t.trim()).filter(Boolean)}:{instagram_caption:$('caption').value};
   await api('edit',{id:current.id,platform,index:selectedClip,metadata});dirty.delete(platform);
  }
 }
 function setCurrent(draft){current=draft;selectedClip=1;dirty.clear();if(draft){localStorage.removeItem(storageKey('cleared-'+draft.mode));localStorage.setItem(storageKey('review'),draft.id);if(draft.mode==='highlights')$('savedHighlights').value=draft.id;}renderReview();}
 function renderAccounts(accounts){
  const yt=accounts.youtube||{},ig=accounts.instagram||{};
  $('youtubeAccount').textContent=String(yt.handle||yt.name||yt.id||'').trim()||'Not connected';
  $('instagramAccount').textContent=ig.id?'@'+String(ig.id).trim().replace(/^@/,''):String(ig.name||'').trim()||'Not connected';
 }
 async function loadAccounts(scope){
  try{
   const response=await fetch('/api/publisher?profile='+scope,{headers:{'X-Hinglish-Token':token},signal:readTimeout()});
   if(!response.ok)throw Error('Could not read channel connections.');
   const {accounts}=await response.json();
   if(scope===profile&&!snapshot?.accounts&&accounts)renderAccounts(accounts);
  }catch(_){
   if(scope===profile&&!snapshot?.accounts)$('youtubeAccount').textContent=$('instagramAccount').textContent='Unavailable';
  }
 }
 async function refresh(){
  const scope=profile;
  if(!token||refreshing.has(scope))return;
  refreshing.add(scope);
  try{
   const data=await api('list',{},scope);if(scope!==profile)return;
   snapshot=data;records=data.preparations;connected=true;
   renderAccounts(data.accounts||{});
   const hiddenIds=dismissed();for(let n=queryDrafts.length-1;n>=0;n--)if(hiddenIds.includes(queryDrafts[n]))queryDrafts.splice(n,1);
   if(queryDrafts.length&&!handoffApplied){
    const handoff=records.find(d=>d.id===queryDrafts[0]&&d.status!=='cancelled'&&availableMode(d.mode));
    if(handoff){
     mode=handoff.mode;handoffApplied=true;
     if(mode==='long'){longDraft=handoff;localStorage.setItem(storageKey('long'),handoff.id);current=null;$('source').value=handoff.source.path;$('thumbnail').value=handoff.thumbnail?.path||'';}
     else setCurrent(handoff);
     renderMode();
    }
   }
   const selectedLong=longDraft?.id||localStorage.getItem(storageKey('long')),savedLong=records.find(d=>d.id===selectedLong);
   if(savedLong?.status==='cancelled'){localStorage.removeItem(storageKey('long'));if($('source').value===savedLong.source.path)$('source').value=$('thumbnail').value='';}
   longDraft=savedLong?.status==='cancelled'?null:savedLong||null;
   if(longDraft&&mode==='long'&&!$('source').value){$('source').value=longDraft.source.path;$('thumbnail').value=longDraft.thumbnail?.path||'';}
   if(current)current=records.find(d=>d.id===current.id)||current;
   if(current?.status==='cancelled'){localStorage.removeItem(storageKey('review'));if(mode!=='long'&&$('source').value===current.source.path)$('source').value=$('thumbnail').value='';current=null;dirty.clear();}
   if(!current&&!queryDrafts.length){const savedId=localStorage.getItem(storageKey('review')),saved=records.find(d=>d.id===savedId&&d.status!=='cancelled'&&d.mode===(mode==='long'?'shorts':mode));if(saved&&(mode!=='long'||localStorage.getItem(storageKey('shorts-optin'))===saved.id)){if(mode==='long')shortsOptedIn=true;setCurrent(saved);}}
   const decl=data.declarations||{};
   for(const [key,id] of [['made_for_kids','audience'],['synthetic_media','synthetic']])if(typeof decl[key]==='boolean')$(id).value=decl[key]?'yes':'no';
   $('declarations').hidden=Boolean($('audience').value&&$('synthetic').value);
   $('status').textContent=!data.simple_source_supported?'The simplified posting controls need the updated backend. Saved posts are kept.':data.runtime?.service_online===false?'Local model is unavailable. Check model settings before starting a new video.':(profile==='gaming'?'Gaming':'Cricket')+' · '+(mode==='long'?'Long video':mode==='shorts'?'Shorts & Reels':'Highlights');
   if(queryDrafts.length&&!handoffApplied)$('status').textContent='This exact saved preparation is unavailable on the selected channel. No different video was selected or posted.';
   await refreshLiveProgress();renderSaved();renderReview();if(!$('connectionPanel').hidden)await refreshConnections();
  }catch(error){
   if(scope===profile)throw error;
  }finally{refreshing.delete(scope);}
 }
 async function publisherApi(action,body,scope=profile){
  const response=await window.storylensFetch('/api/publisher'+(action?'/'+action:'?profile='+scope),{method:action?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(action?{body:JSON.stringify({...body,profile:scope})}:{})});
  return window.storylensResponse(response);
 }
 async function refreshConnections(){
  const scope=profile,yt=snapshot?.accounts?.youtube||{},ig=snapshot?.accounts?.instagram||{};
  $('youtubeConnection').textContent='YouTube · '+(yt.connected?'Connected · '+(yt.name||yt.id):'Not connected');
  $('instagramConnection').textContent='Instagram · '+(ig.connected?'Connected · @'+String(ig.id).replace(/^@/,''):'Not connected');
  const [publisher,response]=await Promise.all([publisherApi(''),window.storylensFetch('/api/local-browser',{headers:{'X-Hinglish-Token':token}})]);
  const browser=await window.storylensResponse(response);if(scope!==profile)return;
  $('chromeConnection').textContent='Chrome publisher · '+(browser.connected?'Connected':'Not connected');signIn?.observe(publisher.tasks||[]);
 }
 function initializeConnections(){
  document.documentElement.dataset.token=token;
  const script=node('script');script.src='scheduled-posts.js?v=20261108-voice-settings';document.body.append(script);
  if(window.StorylensPublisherSignIn)signIn=window.StorylensPublisherSignIn.create({label:'Connect YouTube',button:$('connectYouTube'),status:$('youtubeSignInStatus'),link:$('openGoogleSignIn'),profile:()=>profile,clientFile:()=>'',start:(body,scope)=>publisherApi('connect-youtube',body,scope),refresh:()=>refreshConnections(),openWindow:()=>window.open('about:blank','_blank'),error:error=>window.storylensError(error)});
  if(location.hash==='#connections'){$('connectionPanel').hidden=false;$('connections').setAttribute('aria-expanded','true');}
 }
 $('connections').onclick=()=>guard(async()=>{$('connectionPanel').hidden=!$('connectionPanel').hidden;$('connections').setAttribute('aria-expanded',String(!$('connectionPanel').hidden));if(!$('connectionPanel').hidden)await refreshConnections();},'Checking channel connections');
 async function pick(field){
  const data=await api(field==='source'?'pick-video':'pick-thumbnail',{path:$(field).value});
  if(data.path)$(field).value=data.path;
 }

 async function prepare(value){
  const payload={mode:value.mode,count:value.mode==='shorts'?Number(value.count||1):1,minutes:Number(value.minutes||15),video:value.video,thumbnail:value.mode==='shorts'?'':value.thumbnail,visibility:'private',discovery_review:$('discoveryReview').checked===true,discovery_research:$('discoveryResearch').checked===true,...(value.parent?{source_preparation:value.parent}:{})};
  const previous=value.mode==='long'?longDraft:current;
  if(snapshot?.repeat_uploads_allowed&&previous?.mode===value.mode&&Object.values(previous.jobs_by_platform||{}).some(ids=>ids.length))requests.delete(JSON.stringify([profile,payload]));
  payload.request_id=keyFor(payload);
  const draft=await api('create',payload);
  if(value.mode==='long'){longDraft=draft;longDirty=false;localStorage.removeItem(storageKey('cleared-long'));localStorage.setItem(storageKey('long'),draft.id);localStorage.removeItem(storageKey('shorts-optin'));shortsOptedIn=false;current=null;renderReview();}
  else{if(mode==='long')localStorage.setItem(storageKey('shorts-optin'),draft.id);setCurrent(draft);}
  const started=await api('start',{id:draft.id});if(taskKey(started.task))taskIds.set(draft.id,taskKey(started.task));await refresh();
 }
 async function publishLong(action){
  if(!longDraft?.stages?.['copy:youtube:1']||active(longDraft))throw Error('Wait for the Long video’s title and description, then review them before posting.');
  if(longDraft.source.path.toLowerCase()!==$('source').value.trim().toLowerCase())throw Error('The selected file changed. Press Run to prepare and review it before posting.');
  const declaration=declarations();await saveEdits();await api('post',{id:longDraft.id,platform:'youtube',release_action:action,authorize:true,...declaration});await refresh();
 }
 async function postClips(action){
  if(!canPostClips(action))throw Error('Wait for both platforms’ copy, or check this batch’s saved posting result before retrying.');
  const decl=declarations();await saveEdits();
  const platforms=platformsForClips().filter(p=>!submitted(p));
  const results=await Promise.allSettled(platforms.map(platform=>api('post',{id:current.id,platform,release_action:action,authorize:true,...decl})));
  await refresh();
  const failures=results.flatMap((result,index)=>result.status==='rejected'?[{platform:platforms[index],error:result.reason}]:[]);
  if(failures.length){const error=Error(failures.map(item=>(item.platform==='youtube'?'YouTube':'Instagram')+': '+item.error.message).join(' ')+' Saved platform results are kept; retry continues the unfinished destination.');error.details=failures.map(item=>item.error.details||'').filter(Boolean).join('\n');throw error;}
  if(results.some(result=>!result.value.worker_enabled))problem(Error('The queue is saved, but the posting worker is paused. Open Connections to check its connection.'));
 }
 async function cancelPreparation(long){
  const draft=long?longDraft:current;
  if(draft){
   const result=await api('cancel',{id:draft.id});
   if(result.status==='cancelling'){if(long)longDraft=result;else current=result;await refresh();return;}
  }
  dirty.clear();
  if(long){longDraft=null;longDirty=false;localStorage.removeItem(storageKey('long'));$('source').value=$('thumbnail').value='';}
  else{localStorage.removeItem(storageKey('review'));localStorage.removeItem(storageKey('shorts-optin'));shortsOptedIn=false;setCurrent(null);$('saved').value='';if(mode!=='long')$('source').value=$('thumbnail').value='';}
  await refresh();
 }
 function clearScreen(reviewOnly=false){
  if(busy||active(current)||!reviewOnly&&active(longDraft))return;
  if(snapshot?.repeat_uploads_allowed)requests.clear();
  const cleared=[current,...(!reviewOnly?[longDraft]:[])].filter(Boolean),ids=new Set([...dismissed(),...cleared.map(d=>d.id)]);
  localStorage.setItem(storageKey('dismissed'),JSON.stringify([...ids]));
  for(const d of cleared){liveProgress.delete(d.id);taskIds.delete(d.id);}
  localStorage.removeItem(storageKey('review'));localStorage.removeItem(storageKey('shorts-optin'));
  localStorage.setItem(storageKey('cleared-'+mode),'true');
  current=null;selectedClip=1;shortsOptedIn=false;dirty.clear();$('saved').value='';$('savedHighlights').value='';
  if(!reviewOnly){longDraft=null;longDirty=false;localStorage.removeItem(storageKey('long'));$('source').value=$('thumbnail').value='';$('count').value=$('savedCount').value=$('highlightShortsCount').value='5';$('minutes').value='15';remembered.set(profile,inputSettings());}
  else if(mode!=='long')$('source').value=$('thumbnail').value='';
  for(let n=queryDrafts.length-1;n>=0;n--)if(ids.has(queryDrafts[n]))queryDrafts.splice(n,1);handoffApplied=true;
  if(typeof history!=='undefined'&&history.replaceState){const url=new URL(location.href);if(!queryDrafts.length)url.searchParams.delete('drafts');else url.searchParams.set('drafts',queryDrafts.join(','));history.replaceState(null,'',url);}
  $('problem').replaceChildren();$('status').textContent='Cleared. Saved posts remain in Scheduled posts.';renderSaved();renderReview();controls();
 }
 $('clear').onclick=()=>clearScreen();$('clearReview').onclick=()=>clearScreen(true);
 $('saveThumbnail').onclick=()=>guard(async()=>{await saveEdits();await refresh();$('status').textContent='Reviewed text and thumbnail selection saved for this prepared video.';},'Saving your thumbnail selection');
 $('cancelLong').onclick=()=>guard(()=>cancelPreparation(true),'Cancelling this Long video');
 $('cancelReview').onclick=()=>guard(()=>cancelPreparation(false),'Cancelling this preparation');
 $('pickVideo').onclick=()=>guard(()=>pick('source'),'Waiting for your video selection');$('pickThumbnail').onclick=()=>guard(()=>pick('thumbnail'),'Waiting for your thumbnail selection');
 $('longPost').onclick=()=>guard(()=>publishLong('post_now'),'Submitting the reviewed Long video');$('longSchedule').onclick=()=>guard(()=>publishLong('schedule'),'Scheduling the reviewed Long video');
 $('run').onclick=()=>guard(async()=>{await saveEdits();await prepare({mode,video:$('source').value,thumbnail:$('thumbnail').value,count:$('count').value,minutes:$('minutes').value});},'Starting your preparation');
 $('startSaved').onclick=()=>guard(async()=>{await saveEdits();const parent=records.find(d=>d.id===$('saved').value);if(!parent)throw Error('Select a saved Long video first.');current=null;dirty.clear();shortsOptedIn=true;renderReview();await prepare({mode:'shorts',video:parent.source.path,count:$('savedCount').value,parent:parent.id});},'Starting Shorts from your saved video');
 $('startHighlightShorts').onclick=()=>guard(async()=>{
  await saveEdits();const parent=records.find(d=>d.id===$('savedHighlights').value),video=parent?.stages?.highlights?.video?.path,count=$('highlightShortsCount').value;
  if(profile!=='gaming'||!video||active(parent))throw Error('Select finished Gaming Highlights first.');
  mode='shorts';current=null;dirty.clear();$('source').value=video;$('count').value=count;renderMode();
  await prepare({mode:'shorts',video,count,parent:parent.id});
 },'Starting Shorts from your finished Highlights');
 $('savedHighlights').onchange=controls;$('highlightShortsCount').oninput=controls;
 $('postClips').onclick=()=>guard(()=>postClips('post_now'),'Submitting your posting request');$('scheduleClips').onclick=()=>guard(()=>postClips('schedule'),'Submitting your schedule');
 all('[data-profile]').forEach(button=>button.onclick=()=>guard(async()=>{
  await saveEdits();remembered.set(profile,inputSettings());profile=button.dataset.profile;
  const saved=remembered.get(profile)||{source:'',thumbnail:'',count:'5',minutes:'15',savedCount:'5',mode:'long'};
  mode=saved.mode;for(const id of ['source','thumbnail','count','minutes','savedCount'])$(id).value=saved[id];
  current=null;longDraft=null;longDirty=false;shortsOptedIn=false;records=[];snapshot=null;connected=false;dirty.clear();$('youtubeAccount').textContent=$('instagramAccount').textContent='Connecting…';$('saved').value='';renderMode();void loadAccounts(profile);await refresh();
 }));
 all('[data-mode]').forEach(button=>button.onclick=()=>guard(async()=>{if(!availableMode(button.dataset.mode))return;await saveEdits();mode=button.dataset.mode;current=null;dirty.clear();$('saved').value='';renderMode();await refresh();}));
 $('saved').onchange=()=>guard(async()=>{await saveEdits();if(mode!=='long')setCurrent(records.find(d=>d.id===$('saved').value)||null);else{localStorage.removeItem(storageKey('review'));localStorage.removeItem(storageKey('shorts-optin'));shortsOptedIn=false;setCurrent(null);}controls();});
 $('clip').onchange=()=>guard(async()=>{const next=Number($('clip').value);try{await saveEdits();selectedClip=next;renderReview();}finally{$('clip').value=String(selectedClip);}});
 for(const id of ['title','description','tags','caption'])$(id).oninput=()=>{dirty.add(id==='caption'?'instagram':'youtube');controls();};
 for(const id of ['longTitle','longDescription','longTags'])$(id).oninput=()=>{longDirty=true;controls();};
 for(const id of ['source','thumbnail','count','minutes','savedCount'])$(id).oninput=controls;
 for(const id of ['count','savedCount'])$(id).oninput=()=>{if(!current)renderReview();else controls();};
 async function initialize(){
  $('actionProgress').hidden=false;
  $('actionProgress').replaceChildren(meter('Connecting',null,'Connecting to Storylens'),node('span','Connecting to Storylens'));
  try{
   const response=await fetch('/api/bridge',{signal:readTimeout()});
   const data=await response.json();
   if(response.ok===false||!data.token)throw Error('Could not connect to Storylens. Reopen Prepare and Post.');
   token=data.token;
   const requested=new URLSearchParams(location.search).get('profile');
   if(['cricket','gaming'].includes(requested))profile=requested;
   void loadAccounts(profile);
   initializeConnections();
   renderMode();
   await refresh();
  }catch(error){
   $('status').textContent=token?'Could not load publishing status. Retrying…':'Could not connect to Storylens.';
   if(!token)problem(error);
   controls();
  }finally{$('actionProgress').hidden=true;}
 }
 void initialize();
 setInterval(()=>{if(!busy&&token)refresh().catch(()=>{if(!connected)$('status').textContent='Could not load publishing status. Retrying…';});},5000);
})();
