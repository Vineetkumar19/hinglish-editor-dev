// Runs approved weekly packages only; never uploads another video or changes visibility.
async function storylensWeeklyYouTubeTask(job,api,tab,switchTrace){
 let sharing=false,saveRequested=false,editsStarted=false;
 const pause=ms=>new Promise(r=>setTimeout(r,ms));
 const phase=async message=>{const r=await api('phase',{id:job.id,lease:job.lease,status:sharing?'sharing':'running',message});if(r.stop)throw Error('Weekly plan stopped before the next Studio action.');};
 const send=async(action,selection=job)=>{
  await phase('Weekly YouTube package: '+action);
  if(action==='commit')saveRequested=true;
  const r=await chrome.tabs.sendMessage(tab.id,{source:'storylens-youtube-weekly',action,job:selection});
  if(!r?.ok)throw Error(r?.error||'The weekly Studio controls are unavailable.');return r;
 };
 const load=async()=>{
  for(let i=0;i<50;i++){
   const current=await chrome.tabs.get(tab.id);
   if(current.status==='complete'&&current.url===`https://studio.youtube.com/video/${job.video_id}/edit`){
    await chrome.scripting.executeScript({target:{tabId:tab.id},files:['youtube-weekly-dom.js']});return;
   }
   await pause(500);
  }
  throw Error('Studio did not load this exact video’s details. No replacement upload was started.');
 };
 try{
 await chrome.tabs.update(tab.id,{url:`https://studio.youtube.com/video/${job.video_id}/edit`,active:true});await load();
 let inspected;
 for(let i=0;i<30;i++){
  try{inspected=await send('inspect');break;}catch(e){if(/different channel|changed since|unsaved manual|not confirmed Public|sign-in/i.test(e.message))throw e;await pause(500);}
 }
 if(!inspected)throw Error('Studio could not verify the saved weekly starting text.');
 if(!inspected.already_matches){
  for(const key of ['title','description']){
   const r=await send('field',{...job,copy_field:key});editsStarted=true;await studioType(tab.id,r.control,job.metadata[key],'Tab');
  }
 }
 if(job.thumbnail){
  const r=await send('thumbnail');editsStarted=true;await studioWeeklyThumbnail(tab.id,job,r.control);
 }
 if(!inspected.already_matches||job.thumbnail){
  let ready=false;
  for(let i=0;i<30;i++){try{await send('ready');ready=true;break;}catch(e){if(/differs|different channel/i.test(e.message))throw e;await pause(500);}}
  if(!ready)throw Error('Studio did not finish preparing the approved weekly package.');
  sharing=true;await phase('Saving the approved weekly package on the existing video.');await send('commit');
  // Wait for Studio's own save to settle before a reload can discard it.
  let saved=false;
  for(let i=0;i<40;i++){try{await send('settled');saved=true;break;}catch(e){await pause(500);}}
  if(!saved)throw Error('The weekly Save result is uncertain. Check this video before retrying; no upload was repeated.');
 }else{sharing=true;await phase('Requested text already present; checking the saved video.');}
 await chrome.tabs.reload(tab.id);await load();
 let receipt;
 for(let i=0;i<30;i++){try{receipt=await send('verify');break;}catch(e){if(/different channel|not confirmed Public/i.test(e.message))throw e;await pause(500);}}
 if(!receipt)throw Error('Studio did not verify the weekly package after reload. Future weeks need review.');
 await api('finish',{id:job.id,lease:job.lease,result:{status:'complete',...receipt,switch_trace:switchTrace,
  message:'Week '+job.week+' title, description and hashtags verified after Studio reload.'+(job.thumbnail?' Thumbnail save confirmed in Studio; independent pixel matching is not performed.':'')}});
 }catch(error){
  if(!saveRequested&&editsStarted){try{await chrome.tabs.sendMessage(tab.id,{source:'storylens-youtube-weekly',action:'discard',job});}catch(_){} }
  error.weekly_retryable=!saveRequested&&/unsaved manual|did not load|not loaded|did not finish preparing|controls are unavailable|could not establish connection|receiving end|message port|network|fetch|timed out|offline|complete studio sign-in/i.test(error.message||'');
  throw error;
 }
}
async function studioWeeklyThumbnail(tabId,job,control){
 if(!job.thumbnail||!/\.(?:jpe?g|png)$/i.test(job.thumbnail.path)||! /^input\[type="file"\]\[data-storylens-thumbnail="[\w-]+"\]$/.test(control?.selector||''))throw Error('The approved thumbnail file input is unavailable.');
 const tab=await chrome.tabs.get(tabId);
 if(tab.url!==`https://studio.youtube.com/video/${job.video_id}/edit`)throw Error('Thumbnail selection is limited to the exact approved video.');
 const target={tabId};let attached=false;
 try{
  await chrome.debugger.attach(target,'1.3');attached=true;
  const {root}=await chrome.debugger.sendCommand(target,'DOM.getDocument',{depth:0});
  const {nodeId}=await chrome.debugger.sendCommand(target,'DOM.querySelector',{nodeId:root.nodeId,selector:control.selector});
  if(!nodeId)throw Error('The measured Studio thumbnail input disappeared.');
  await chrome.debugger.sendCommand(target,'DOM.setFileInputFiles',{nodeId,files:[job.thumbnail.path]});
 }finally{if(attached)await chrome.debugger.detach(target).catch(()=>{});}
}
