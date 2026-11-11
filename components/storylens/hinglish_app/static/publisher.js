const publisherHandles=fetch('publisher-handles.json?v=20261028-compact-1').then(r=>r.ok?r.json():{}).then(d=>d.handles||{}).catch(()=>({}));
document.getElementById('preparePostLink')?.addEventListener('click',event=>{event.currentTarget.href='prepare-post.html?profile='+encodeURIComponent(window.creatorProfile?.value||'cricket');});
const $=s=>document.querySelector(s), token=document.documentElement.dataset.token;
let state=null,seenEvent=null,initialized=false,taskSignature="",noticeError="",browserState=null;
const handoffParams=new URLSearchParams(location.search),handoffProfile=handoffParams.get('profile');
const handoffDrafts=new Set((handoffParams.get('drafts')||'').split(',').filter(id=>/^[a-zA-Z0-9_-]{1,80}$/.test(id)));
const channelWorkspace=window.StorylensPublisherIntake.workspace();let intakeProfile=null;
function switchIntake(){const profile=window.creatorProfile?.value||'general',keys=['command','sourceMode','publishKind','publishDestinations','makeShorts'];
 const values=Object.fromEntries(keys.map(key=>[key,['makeShorts'].includes(key)?$('#'+key).checked:$('#'+key).value]));
 const restored=channelWorkspace.activate(profile,values);for(const key of keys){if(key==='sourceMode')continue;if(['makeShorts'].includes(key))$('#'+key).checked=restored[key];else $('#'+key).value=restored[key];}
 if(intakeProfile&&intakeProfile!==profile){handoffDrafts.clear();$('#publishingQueue').open=false;$('#readinessResult').replaceChildren();}intakeProfile=profile;syncSourceMode(restored.sourceMode);
}
function syncSourceMode(preferred){
 const allowed=window.StorylensPublisherIntake.sourceModes(window.creatorProfile?.value||'general');
 const source=$('#sourceMode'),wanted=typeof preferred==='string'?preferred:source.value;
 source.replaceChildren(...allowed.map(choice=>{const option=node('option',choice.label);option.value=choice.value;return option;}));
 source.value=allowed.some(choice=>choice.value===wanted)?wanted:'finished';
 const stream=source.value==='stream';$('#publishKind').disabled=stream;
 document.querySelector('label[for="command"]').textContent=stream?'Video path or YouTube stream link':'Full video path';
 if(stream)$('#makeShorts').checked=true;
}
async function api(action,body,profile=window.creatorProfile?.value||'general'){const r=await window.storylensFetch('/api/publisher'+(action?'/'+action:'?profile='+encodeURIComponent(profile)),{
  method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},
  body:body===undefined?undefined:JSON.stringify({...body,profile})});const d=await window.storylensResponse(r);if(!r.ok)throw Error(d.error);return d;}
function node(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function button(text,action){const e=node('button',text);e.onclick=()=>guard(action);return e;}
async function guard(action){try{noticeError='';await action();await refresh(false);}catch(e){noticeError=window.storylensError(e);$('#notice').textContent=noticeError;}}
function settings(){return {media_root:$('#mediaRoot').value,source_root:$('#sourceRoot').value,daily_time:state.settings.daily_time,shorts_count:$('#shortCount').value,
  visibility:$('#visibility').value,enabled:$('#enabled').checked,vision:state.settings.vision,
  youtube_public_api_ready:$('#audit').checked,s3_bucket:state.settings.s3_bucket,s3_region:state.settings.s3_region};}
async function refresh(force=false){const profile=window.creatorProfile?.value||'general';const [fetched,browserResponse,handles]=await Promise.all([api('',undefined,profile),window.storylensFetch('/api/local-browser',{headers:{'X-Hinglish-Token':token}}),publisherHandles]);if(browserResponse.ok)browserState=await window.storylensResponse(browserResponse);if(profile!==(window.creatorProfile?.value||'general'))return;state=fetched;if(!initialized||force){const s=state.settings;
  $('#mediaRoot').value=s.media_root;$('#sourceRoot').value=s.source_root||'';$('#shortCount').value=s.shorts_count;
  $('#visibility').value=s.visibility;$('#enabled').checked=s.enabled;
  $('#audit').checked=s.youtube_public_api_ready;initialized=true;}
  if(profile===handoffProfile&&!$('#command').value&&handoffDrafts.size){const sources=new Set(state.jobs.filter(j=>handoffDrafts.has(j.id)&&(j.profile||'general')===profile).map(j=>j.video));if(sources.size===1)$('#command').value=[...sources][0];}
  $('#publisherProfile').value=profile==='general'?'':profile;$('#notice').textContent=noticeError||(state.settings.enabled&&state.worker_enabled?'Automatic posting is on for authorized posts.':'Automatic posting is paused. Drafts stay saved.');
  const yt=(state.profile_accounts?.[profile]||state.accounts).youtube;const ig=browserState?.accounts?.[profile];$('#accounts').replaceChildren(node('p','YouTube: '+window.StorylensPublisherIntake.accountLabel(yt,handles)),node('p','Instagram: '+(ig?'@'+ig:'Not connected')));
  $('#files').replaceChildren(...state.files.map(f=>node('li',f.name+' · '+f.kind+(f.thumbnail?' · thumbnail matched':''))));
  $('#videoNames').replaceChildren(...state.files.map(f=>{const e=node('option');e.value=f.video;return e;}));
  const nextTasks=JSON.stringify(state.tasks);if(nextTasks!==taskSignature){taskSignature=nextTasks;$('#tasks').replaceChildren(...state.tasks.slice(-3).map(t=>{const row=node('article');row.append(node('p',t.status+': '+t.message));if(t.result?.job_ids){for(const id of t.result.job_ids)handoffDrafts.add(id);$('#publishingQueue').open=true;}if(t.result?.youtube){const report=t.result;if(report.profile===profile)$('#readinessResult').replaceChildren(...(report.youtube.state==='verified'?[]:[node('p',report.youtube.message)]),...(report.instagram.state==='verified'?[]:[node('p',report.instagram.message)]));if(report.youtube.state==='refresh_rejected'||report.youtube.state==='connection_unavailable'){const link=node('a','Reconnect YouTube');link.href=window.StorylensPublisherIntake.connectionLink(report.profile);$('#readinessResult').append(link);}if(report.youtube.technical){const d=node('details');d.append(node('summary','Technical details'),node('pre',JSON.stringify(report.youtube.technical,null,2)));row.append(d)}}if(t.can_stop)row.append(button('Stop after this step',()=>api('stop-task',{id:t.id})));if(t.can_resume)row.append(button('Resume preparation',()=>api('resume-task',{id:t.id})));if(t.status==='failed'){const details=window.storylensDetails(window.storylensJobError(t));if(details)row.append(details)}return row}));}
  youtubeSignIn.observe(state.tasks);
  renderMemory();
  const defaults=state.publishing_defaults||{};
  const savedDeclarations=typeof defaults.made_for_kids==='boolean'&&typeof defaults.synthetic_media==='boolean';
  if(savedDeclarations){$('#audience').value=defaults.made_for_kids?'yes':'no';$('#synthetic').value=defaults.synthetic_media?'yes':'no'}
  $('#audience').closest('.publish-row').hidden=savedDeclarations;
  // Preserve unsaved edits while polling.
  if(!document.activeElement?.closest('.queue-item'))renderQueue();

}
function renderQueue(){const selected=new Set([...document.querySelectorAll('.queue-select:checked')].map(e=>e.value));
  const history=new Set(['cancelled','published','uploaded_private']);const view=$('#queueView').value;
  const rows=state.jobs.filter(job=>(job.profile||'general')===(window.creatorProfile?.value||'general')&&(view==='all'||(view==='history'?history.has(job.status):!history.has(job.status))));
  $('#queueCount').textContent=rows.length+' '+(view==='history'?'past posts':view==='all'?'posts':'drafts / upcoming');
  $('#queue').replaceChildren(...rows.sort((a,b)=>Number(handoffDrafts.has(b.id))-Number(handoffDrafts.has(a.id))).map(job=>{const card=node('article',undefined,'queue-item');card.dataset.id=job.id;
    const label=node('label',undefined,'check'),pick=node('input');pick.type='checkbox';pick.className='queue-select';pick.value=job.id;
    if(handoffDrafts.has(job.id)){card.classList.add('publisher-handoff-draft');}
    pick.disabled=!['draft','blocked'].includes(job.status)||Object.keys(job.remote||{}).length>0;pick.checked=selected.has(job.id);
    label.append(pick,node('b',job.platform.toUpperCase()+' · '+job.metadata.title));card.append(label,node('p',
      job.status.replaceAll('_',' ')+' · '+new Date(job.due*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST','status'));
    if(job.error){const issue=window.storylensProblem({message:job.error,code:job.error_code,details:job.error_details});card.append(node('p',issue.message,'error'));const details=window.storylensDetails(issue);if(details)card.append(details)}
    if(job.review_file)card.append(button('Review generated clip',()=>api('review',{id:job.id})));
    if(job.remote?.url){const link=node('a','View on '+job.platform);if(/^https:\/\/(www\.)?(youtube\.com|instagram\.com)\//.test(job.remote.url)){link.href=job.remote.url;link.target='_blank';link.rel='noopener';card.append(link);}}
    if(['draft','ready','blocked'].includes(job.status)&&!Object.keys(job.remote||{}).length){
      const details=node('details'),title=node('input'),description=node('textarea'),caption=node('textarea');
      title.value=job.metadata.title;description.value=job.metadata.description;caption.value=job.metadata.instagram_caption;
      const rememberLabel=node('label',undefined,'check'),remember=node('input');remember.type='checkbox';
      rememberLabel.append(remember,document.createTextNode('Remember my changes as examples for future drafts'));
      details.open=handoffDrafts.has(job.id);
      details.append(node('summary','Edit title, description & caption'),node('label','Title'),title,node('label','YouTube description'),description,node('label','Instagram caption'),caption,
        rememberLabel,button('Save as draft',()=>api('edit',{id:job.id,remember:remember.checked,metadata:{...job.metadata,title:title.value,description:description.value,instagram_caption:caption.value}})));
      card.append(details,button('Cancel unstarted post',()=>api('cancel',{id:job.id})));}
    return card;}));if(!rows.length)$('#queue').append(node('p',view==='history'?'No completed posts in this profile.':'No drafts or upcoming posts.','muted'));}
function renderMemory(){
  $('#memoryList').replaceChildren(...((window.creatorProfile?.value||'general')==='general'?(state.memory||[]):(state.profile_memory?.[window.creatorProfile.value]||[])).map(m=>{
    const card=node('article',undefined,'queue-item'),head=node('p',m.scope.replaceAll('_',' ')+' · '+(m.active?'Active':'Disabled'),'status');
    const details=node('details');details.append(node('summary','Review saved preference'));
    for(const [key,label] of [['want','Want'],['avoid','Avoid'],['before','Rejected'],['after','Approved']]){
      if(m[key])details.append(node('p',label+': '+m[key]));
    }
    card.append(head,details,button(m.active?'Disable this preference':'Enable this preference',()=>api('memory-toggle',{id:m.id,active:!m.active})));
    return card;
  }));
}
$('#saveFeedback').onclick=()=>guard(async()=>{
  await api('feedback',{scope:$('#feedbackScope').value,want:$('#feedbackWant').value,avoid:$('#feedbackAvoid').value,
    before:$('#feedbackBefore').value,after:$('#feedbackAfter').value});
  $('#feedbackNotice').textContent='Saved locally. Future generation will use this preference; existing drafts stay editable.';
  for(const field of ['feedbackWant','feedbackAvoid','feedbackBefore','feedbackAfter'])$('#'+field).value='';
});
$('#saveFolders').onclick=()=>guard(async()=>{await api('settings',settings());await api('folders',{});});
$('#saveSettings').onclick=()=>guard(()=>api('settings',settings()));
$('#refresh').onclick=()=>guard(()=>refresh(true));
$('#prepare').onclick=()=>guard(async()=>{
  const profile=window.creatorProfile?.value||'general';
  const plan=window.StorylensPublisherIntake.intake({profile,path:$('#command').value,count:$('#shortCount').value,sourceMode:$('#sourceMode').value,platforms:$('#publishDestinations').value,kind:$('#publishKind').value,makeShorts:$('#makeShorts').checked});
  $('#prepare').disabled=true;try{
    if(plan.route==='chat'){
      if(window.assistantBusy)throw Error('Wait for the current local workflow to finish before preparing another.');
      const headers={'Content-Type':'application/json','X-Hinglish-Token':token};
      const created=await window.storylensFetch('/api/assistant/session',{method:'POST',headers,body:'{}'});const session=await window.storylensResponse(created);if(!created.ok)throw Error(session.error);
      const sent=await window.storylensFetch('/api/assistant/message',{method:'POST',headers,body:JSON.stringify({session:session.id,message:plan.message,profile,attachments:[]})});const result=await window.storylensResponse(sent);if(!sent.ok)throw Error(result.error);
      await window.storylensChat.open(session.id);
    }else{await api('settings',settings(),profile);await api('prepare',plan,profile);}
  }finally{$('#prepare').disabled=false;}
});
let importingVideo=false;
$('#chooseVideo').onclick=()=>{
 if(importingVideo)return;
 $('#videoFile').accept=$('#sourceMode').value==='stream'?'video/*,.mp4,.mov,.mkv,.webm,.mxf,.avi':'video/mp4,.mp4';
 $('#videoFile').click();
};
$('#videoFile').onchange=()=>guard(async()=>{
 const file=$('#videoFile').files[0];if(!file)return;
 const profile=window.creatorProfile?.value||'general',sourceMode=$('#sourceMode').value;
 window.StorylensPublisherIntake.pickedVideo('D:/'+file.name,sourceMode);
 if(file.size<=0)throw Error('This video file is empty. Choose the finished video.');
 importingVideo=true;$('#chooseVideo').disabled=true;
 try{
  const headers={'Content-Type':'application/json','X-Hinglish-Token':token};
  const created=await window.storylensFetch('/api/assistant/session',{method:'POST',headers,body:'{}'});
  const session=await window.storylensResponse(created);if(!created.ok)throw Error(session.error);
  const item=await new Promise((resolve,reject)=>{
   const xhr=new XMLHttpRequest();
   xhr.open('POST','/api/assistant/upload?session='+encodeURIComponent(session.id)+'&name='+encodeURIComponent(file.name)+'&kind=file');
   xhr.setRequestHeader('X-Hinglish-Token',token);xhr.setRequestHeader('Content-Type','application/octet-stream');
   xhr.upload.onprogress=e=>{if(e.lengthComputable)$('#fileImportStatus').textContent='Importing locally · '+Math.round(e.loaded/e.total*100)+'%';};
   xhr.onload=()=>window.storylensXHR(xhr).then(resolve,reject);
   xhr.onerror=()=>reject(Error('Local import stopped. Your original file is unchanged. Choose the file again.'));
   xhr.send(file);
  });
  const path=window.StorylensPublisherIntake.pickedVideo(item.path,sourceMode);
  if(profile!==(window.creatorProfile?.value||'general')||sourceMode!==$('#sourceMode').value)throw Error('The profile or source changed during import. The imported file is kept; choose it again for the correct profile.');
  $('#command').value=path;$('#command').dispatchEvent(new Event('input',{bubbles:true}));
  $('#fileImportStatus').textContent='Imported: '+file.name;
 }finally{importingVideo=false;$('#chooseVideo').disabled=false;$('#videoFile').value='';}
});
$('#publisherProfile').onchange=()=>{if($('#publisherProfile').value)window.creatorProfile?.select($('#publisherProfile').value);};
$('#queueView').onchange=()=>renderQueue();
$('#sourceMode').onchange=syncSourceMode;
$('#checkReadiness').onclick=()=>guard(async()=>{const profile=window.creatorProfile?.value||'general';if(profile==='general')throw Error('Choose Cricket or Gaming first.');await api('prepare',{operation:'diagnostics',online:true},profile);$('#readinessResult').textContent='Checking the selected accounts…';});
const youtubeSignIn=window.StorylensPublisherSignIn.create({label:'Connect YouTube',button:$('#connectYouTube'),status:$('#youtubeSignInStatus'),link:$('#openGoogleSignIn'),profile:()=>window.creatorProfile?.value||'general',clientFile:()=>'',start:(body,profile)=>api('connect-youtube',body,profile),refresh:()=>refresh(false),openWindow:()=>window.open('about:blank','_blank'),error:e=>window.storylensError(e)});
$('#connectInstagram').onclick=()=>window.open('/chrome.html','_blank');
$('#selectDrafts').onclick=()=>document.querySelectorAll('.queue-select:not(:disabled)').forEach(e=>e.checked=true);
$('#authorize').onclick=()=>guard(async()=>{if(!$('#audience').value||!$('#synthetic').value)throw Error('Choose the audience and synthetic-media declaration first.');
  const ids=[...document.querySelectorAll('.queue-select:checked')].map(e=>e.value);if(!ids.length)throw Error('Select the posts to authorize.');
  await api('authorize',{ids,authorize:true,made_for_kids:$('#audience').value==='yes',synthetic_media:$('#synthetic').value==='yes'});});
document.addEventListener('creator-profile',()=>{switchIntake();initialized=false;refresh(true).catch(e=>$('#notice').textContent=window.storylensError(e));});
Promise.resolve(window.creatorProfile?.ready).then(()=>{
  if(['cricket','gaming'].includes(handoffProfile))window.creatorProfile?.select(handoffProfile);
  switchIntake();
  if(handoffDrafts.size)$('#publishingQueue').open=true;
  if(location.hash==='#youtubeConnect'){
    $('#connectionSettings').open=true;
    $('#youtubeConnect').scrollIntoView({block:'center'});
  }
  return refresh();
}).catch(e=>$('#notice').textContent=window.storylensError(e));setInterval(()=>refresh().catch(()=>{}),6000);

try { const c=sessionStorage.getItem("hinglish.publish.command"); if(c) {document.querySelector("#command").value=c;sessionStorage.removeItem("hinglish.publish.command");} } catch(_) {}
