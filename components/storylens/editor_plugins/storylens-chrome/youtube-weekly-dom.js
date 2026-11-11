// Fixed controls measured in Studio on31Oct2026. No model-provided selectors.
(()=>{
 if(window.__storylensWeeklyInstalled)return;window.__storylensWeeklyInstalled=true;
 let prepared=null,committed=false,startingCopy=null;
 const visible=e=>!!e&&e.getBoundingClientRect().width>0&&e.getBoundingClientRect().height>0;
 const all=s=>[...document.querySelectorAll(s)].filter(visible);
 const text=e=>(e?.innerText||'').trim();
 function state(job){
  if(job.action!=='youtube_weekly_metadata'||!/^UC[\w-]{22}$/.test(job.channel_id)||! /^[\w-]{11}$/.test(job.video_id)||location.pathname!==`/video/${job.video_id}/edit`)throw Error('The exact weekly video details page is not open.');
  const homes=all('a#home-button');
  if(homes.length!==1||new URL(homes[0].href).pathname!==`/channel/${job.channel_id}`)throw Error('Studio is showing a different channel. No weekly changes were saved.');
  if(/Verify that it.s you|sign in to continue/i.test(document.body.innerText))throw Error('Complete Studio sign-in yourself.');
  const fields={title:all('#title-textarea [contenteditable="true"]'),description:all('#description-textarea [contenteditable="true"]')};
  if(Object.values(fields).some(rows=>rows.length!==1))throw Error('Studio has not loaded the exact title and description.');
  const saves=all('button,[role="button"]').filter(e=>e.getAttribute('aria-label')==='Save');
  if(saves.length!==1)throw Error('The Studio Save button is ambiguous or unavailable.');
  const visibility=all('ytcp-video-metadata-visibility #icon-and-type');
  if(visibility.length!==1||text(visibility[0])!=='Public')throw Error('This video is not confirmed Public. Weekly changes never alter visibility.');
  return {fields:Object.fromEntries(Object.entries(fields).map(([k,v])=>[k,v[0]])),save:saves[0],visibility:'Public'};
 }
 const matches=(fields,copy)=>Object.keys(fields).every(k=>text(fields[k])===String(copy[k]).trim());
 const disabled=e=>e.disabled||e.getAttribute('aria-disabled')==='true';
 function uploadInput(job){
  const inputs=[...document.querySelectorAll('ytcp-thumbnail-uploader input#file-loader[type="file"]')];
  if(inputs.length!==1||inputs[0].accept!=='image/jpeg,image/png')throw Error('The reviewed Studio thumbnail input is unavailable.');
  const token=job.video_id+'-weekly-thumbnail';inputs[0].setAttribute('data-storylens-thumbnail',token);
  return {input:inputs[0],selector:`input[type="file"][data-storylens-thumbnail="${token}"]`};
 }
 function thumbnailLoaded(){
  const previews=all('ytcp-thumbnail-uploader button[aria-label="Uploaded thumbnail"]');
  const image=previews.length===1&&previews[0].querySelector('img');
  return !!image&&image.complete&&image.naturalWidth>0&&!/Uploading/i.test(text(previews[0]));
 }
 chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(sender.id!==chrome.runtime.id||message.source!=='storylens-youtube-weekly')return;
  (async()=>{
   const {action,job}=message,s=state(job);
   if(action==='discard'){
    if(committed)throw Error('A submitted weekly save cannot be discarded automatically.');
    const original=startingCopy||job.expected_metadata;
    if(!Object.keys(s.fields).every(k=>[job.metadata[k].trim(),original[k].trim()].includes(text(s.fields[k]))))throw Error('Manual changes were detected; nothing was discarded.');
    if(disabled(s.save))return {discarded:false};
    const undo=all('button').filter(e=>e.getAttribute('aria-label')==='Undo changes');
    if(undo.length!==1||disabled(undo[0]))throw Error('Studio cannot discard the unfinished weekly changes.');
    undo[0].click();return {discarded:true};
   }
   if(action==='inspect'){
    if(!disabled(s.save))throw Error('Studio has unsaved manual changes. Waiting until they are saved or discarded.');
    startingCopy=Object.fromEntries(Object.entries(s.fields).map(([key,field])=>[key,text(field)]));
    if(matches(s.fields,job.metadata))return {already_matches:true};
    return {already_matches:false};
   }
   if(action==='field'){
    if(!['title','description'].includes(job.copy_field))throw Error('Unsupported weekly text field.');
    const token=job.video_id+'-weekly-'+job.copy_field;
    s.fields[job.copy_field].setAttribute('data-storylens-input',token);
    return {control:{selector:`[contenteditable="true"][data-storylens-input="${token}"]`}};
   }
   if(action==='thumbnail'){
    if(!job.thumbnail)throw Error('No weekly thumbnail was approved.');
    return {control:{selector:uploadInput(job).selector}};
   }
   if(action==='ready'||action==='commit'){
    if(!matches(s.fields,job.metadata))throw Error('The entered weekly text differs from the approved package.');
    if(job.thumbnail){
     const f=uploadInput(job).input.files?.[0];
     if(!f||f.name!==job.thumbnail.path.split(/[\\/]/).pop()||f.size!==job.thumbnail.bytes||!thumbnailLoaded())throw Error('Studio has not loaded the approved weekly thumbnail.');
    }
    if(disabled(s.save))throw Error('Studio has not enabled Save for this weekly package.');
    const stamp=JSON.stringify([job.id,job.channel_id,job.video_id,job.metadata,job.thumbnail]);
    if(action==='ready'){prepared=stamp;return {ready:true};}
    if(prepared!==stamp)throw Error('This weekly package was not prepared for the exact video.');
    prepared=null;committed=true;s.save.click();return {};
   }
   if(action==='verify'||action==='settled'){
    if(action==='verify'&&committed)throw Error('Reload Studio before verifying the saved weekly package.');
    if(!matches(s.fields,job.metadata)||!disabled(s.save))throw Error('Studio has not confirmed the saved weekly text after reload.');
    if(job.thumbnail&&!thumbnailLoaded())throw Error('Studio has not confirmed the uploaded thumbnail after reload.');
    return {video_id:job.video_id,channel_id:job.channel_id,metadata:job.metadata,
      visibility:s.visibility,save_disabled:true,reloaded:action==='verify',thumbnail_saved:!!job.thumbnail};
   }
   throw Error('Unsupported weekly Studio action.');
  })().then(value=>reply({ok:true,...value})).catch(error=>reply({ok:false,error:error.message}));return true;
 });
})();
