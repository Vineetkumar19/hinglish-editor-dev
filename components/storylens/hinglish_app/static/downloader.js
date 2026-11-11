(()=>{
 const $=id=>document.getElementById(id),model=window.storylensDownloader,token=document.documentElement.dataset.token;
 const query=new URLSearchParams(location.search),host=query.get('host'),inPanel=query.get('panel')==='1'&&['aftereffects','premiere'].includes(host)&&window.parent!==window;
 const rows=new Map(),jobs=new Map();let submitting=false,polling=false,pending=null;
 const terminal=new Set(['complete','failed','cancelled','interrupted']);
 async function api(path,body){const response=await window.storylensFetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(body?{body:JSON.stringify(body)}:{})});return window.storylensResponse(response);}
 function showError(error){const box=$('downloadError');box.hidden=false;const text=document.createElement('p');text.textContent=window.storylensError(error);box.replaceChildren(text);const detail=window.storylensDetails({message:error.message,details:error.details||''});if(detail)box.append(detail);}
 function clearError(){$('downloadError').hidden=true;$('downloadError').replaceChildren();window.storylensClearError?.();}
 function element(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text)node.textContent=text;return node;}
 function action(label,callback){const node=element('button','queue-action',label);node.type='button';node.onclick=async()=>{node.disabled=true;try{await callback();}catch(error){showError(error);}finally{node.disabled=false;}};return node;}
 function saveForm(){try{localStorage.setItem('storylens.downloader.form',JSON.stringify(Object.fromEntries(['downloadDestination','downloadUrl','downloadMode','downloadQuality','audioFormat','sectionStart','sectionEnd'].map(id=>[id,$(id).value]))));}catch(_){}}
 function fields(){const links=$('downloadUrl').value.trim().split(/\s+/).filter(Boolean),platforms=links.map(value=>model.platform(value));const youtube=!platforms.length||platforms.includes('youtube');$('qualityField').hidden=$('downloadMode').value==='audio'||!youtube;$('audioField').hidden=$('downloadMode').value==='video';$('youtubeSection').hidden=!youtube;saveForm();}
 function mediaUrl(job,kind){return '/api/downloader/media?id='+encodeURIComponent(job.id)+'&kind='+kind+'&token='+encodeURIComponent(token);}
 function preview(job,kind){$('downloadResult').hidden=false;$('downloadTitle').textContent=job.title||job.result?.title||'Download';for(const k of ['video','audio']){const player=$(k+'Preview');player.pause();player.hidden=k!==kind;if(k===kind)player.src=mediaUrl(job,k);else player.removeAttribute('src');}}
 async function nativeImport(job,kind){const context=await window.storylensDownloadTarget();window.dispatchEvent(new CustomEvent('storylens-download-ready',{detail:{id:job.id,kind,context_id:context?.id||null}}));}
 window.addEventListener('storylens-download-delivery',event=>{const d=event.detail||{},row=rows.get(d.id);if(!row)return;row.delivery.textContent=d.error?'Saved; import needs retry.':d.pending?'Importing…':d.warning?'Imported; folder view unchanged.':'Imported.';if(d.error)showError(d.error);});
 function update(job,index,waiting){
  jobs.set(job.id,job);let row=rows.get(job.id);
  if(!row){const node=element('article','queue-row');node.dataset.job=job.id;const top=element('div','queue-top'),title=element('strong','queue-title'),state=element('span','queue-state');top.append(title,state);const meta=element('div','queue-meta muted'),bar=element('progress');bar.max=100;bar.setAttribute('aria-label','Download progress');const outputs=element('div','queue-outputs'),controls=element('div','queue-controls'),failure=element('div','queue-error'),delivery=element('div','muted queue-delivery');node.append(top,meta,bar,outputs,controls,failure,delivery);row={node,title,state,meta,bar,outputs,controls,failure,delivery,signature:''};rows.set(job.id,row);}
  row.title.textContent=job.title||job.result?.title||'Video '+(index+1);row.title.title=job.request.url;
  const progress=model.progress(job),running=job.status==='running';
  row.state.textContent=running?(progress.downloaded?'100% downloaded':progress.percent+'% downloaded'):job.status==='queued'?'Queued · '+waiting:job.status==='interrupted'?'Paused':job.status==='complete'?'Complete':job.status==='cancelled'?'Cancelled':'Failed';
  row.node.dataset.status=job.status;row.bar.hidden=!running;
  row.bar.setAttribute('aria-label',progress.downloaded?job.stage:'Download progress');
  if(progress.percent===null)row.bar.removeAttribute('value');else row.bar.value=progress.percent;
  const section=job.request.section;row.meta.textContent=[job.request.platform,job.request.mode,section?section.start+'–'+section.end+' sec':null,running?progress.stage:null].filter(Boolean).join(' · ');
  // Keep controls/player/focus stable while progress polls; rebuild only on asset/state changes.
  const signature=JSON.stringify([job.status,Object.keys(job.result?.assets||{}),job.saved_files,job.error]);
  if(signature!==row.signature){row.signature=signature;row.outputs.replaceChildren();row.controls.replaceChildren();row.failure.replaceChildren();
   for(const [kind,asset] of Object.entries(job.result?.assets||{})){
    if(!asset.saved_path&&job.status!=='complete')continue;
    const output=element('div','queue-output'),path=element('div','queue-path',asset.saved_path||asset.path);path.title=path.textContent;const actions=element('div','queue-imports');
    actions.append(action('Preview '+kind,()=>preview(job,kind)));
    if(inPanel)actions.append(action('Import '+kind+' in '+(host==='aftereffects'?'After Effects':'Premiere'),()=>nativeImport(job,kind)));
    else{const exports=element('span','editor-exports');window.storylensEditors.render(exports,asset);actions.append(exports);}
    output.append(path,actions);row.outputs.append(output);
   }
   if(['queued','running','interrupted'].includes(job.status))row.controls.append(action(job.status==='queued'?'Remove':'Cancel',async()=>{await api('/api/downloader/cancel',{id:job.id});await refresh();}));
   if(['failed','cancelled','interrupted'].includes(job.status))row.controls.append(action(job.status==='interrupted'?'Resume':'Retry',async()=>{await api('/api/downloader/retry',{id:job.id});await refresh();}));
   if(job.error){const text=element('p','',job.error.message||'This download stopped. Retry this item.');row.failure.append(text);const details=window.storylensDetails(job.error);if(details)row.failure.append(details);}
   if(job.result?.notice)row.outputs.append(element('div','muted',job.result.notice));
  }
  return row.node;
 }
 async function refresh(){if(polling)return;polling=true;try{const {jobs:list}=await api('/api/downloader/queue');if($('downloadStatus').textContent.startsWith('Connection interrupted.'))$('downloadStatus').textContent='';const container=$('downloadQueue');const ids=new Set(list.map(j=>j.id));for(const [id,row]of rows){if(!ids.has(id)){row.node.remove();rows.delete(id);jobs.delete(id);}}
   container.querySelector('.queue-empty')?.remove();let waiting=0;for(const [index,job]of list.entries()){if(job.status==='queued')waiting++;const node=update(job,index,waiting);const current=container.children[index];if(current!==node)container.insertBefore(node,current||null);}
   if(!list.length)container.append(element('p','queue-empty muted','Add links to start your queue.'));
   const active=list.find(j=>j.status==='running');
   $('queueSummary').textContent=[active?(active.source?'1 processing':'1 downloading'):null,waiting?waiting+' waiting':null,list.filter(j=>j.status==='complete').length?list.filter(j=>j.status==='complete').length+' complete':null].filter(Boolean).join(' · ');
  }finally{polling=false;}}
 $('downloadForm').onsubmit=async event=>{event.preventDefault();if(submitting)return;clearError();const text=$('downloadUrl').value.trim(),links=text.split(/\s+/).filter(Boolean),destination=$('downloadDestination').value.trim();if(!links.length){showError(Error('Paste a video link.'));return;}if(!destination){showError(Error('Choose a download folder first.'));$('downloadDestination').focus();return;}
  const extra={destination};if(links.some(url=>model.platform(url)==='youtube')){extra.start_time=$('sectionStart').value.trim();extra.end_time=$('sectionEnd').value.trim();}
  const input=JSON.stringify([links,destination,$('downloadQuality').value,$('downloadMode').value,$('audioFormat').value,extra]);
  if(!pending||pending.input!==input)pending={input,requests:links.map(url=>model.request(url,$('downloadQuality').value,$('downloadMode').value,$('audioFormat').value,{destination,...(model.platform(url)==='youtube'?extra:{}),submission_id:crypto.randomUUID()}))};
  try{localStorage.setItem('storylens.downloader.pending',JSON.stringify(pending));}catch(_){}
  submitting=true;$('startDownload').disabled=true;let count=0;
  try{const result=await api('/api/downloader/enqueue',{requests:pending.requests});count=result.jobs.length;$('downloadStatus').textContent=count+' added to queue.';if($('downloadUrl').value.trim()===text)$('downloadUrl').value='';pending=null;try{localStorage.removeItem('storylens.downloader.pending');}catch(_){}saveForm();await refresh();}
  catch(error){$('downloadStatus').textContent=count?count+' queued. Correct the remaining link, then try again.':'';showError(error);await refresh().catch(()=>{});}
  finally{submitting=false;$('startDownload').disabled=false;fields();}
 };
 $('browseDownloadFolder').onclick=async()=>{clearError();try{const value=await api('/api/pick?kind=folder');if(value.path){$('downloadDestination').value=value.path;await api('/api/downloader/settings',{destination:value.path});saveForm();}}catch(error){showError(error);}};
 $('closeDownloadPreview').onclick=()=>{for(const kind of ['video','audio']){$(kind+'Preview').pause();$(kind+'Preview').removeAttribute('src');}$('downloadResult').hidden=true;};
 for(const id of ['downloadUrl','downloadMode','downloadQuality','audioFormat','sectionStart','sectionEnd','downloadDestination'])$(id).addEventListener('input',fields);
 (async()=>{try{try{const values=JSON.parse(localStorage.getItem('storylens.downloader.form')||'{}');for(const [id,value] of Object.entries(values))if($(id)&&typeof value==='string')$(id).value=value;pending=JSON.parse(localStorage.getItem('storylens.downloader.pending')||'null');}catch(_){}const settings=await api('/api/downloader/settings');if(settings.destination)$('downloadDestination').value=settings.destination;fields();await refresh();}catch(error){showError(error);}finally{setInterval(()=>refresh().catch(error=>{$('downloadStatus').textContent='Connection interrupted. Saved queue is kept; reconnect to continue.';}),1200);}})();
})();
