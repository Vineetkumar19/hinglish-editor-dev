(()=>{
const $=id=>document.getElementById(id),model=window.storylensPanel,token=document.documentElement.dataset.token,q=new URLSearchParams(location.search);
const host=model.hosts.includes(q.get('host'))?q.get('host'):'aftereffects',nonce=q.get('nonce')||'',reelOrigin='http://127.0.0.1:8894',hostNames={premiere:'Premiere Pro',aftereffects:'After Effects',capcut:'CapCut'};
const textOnly=q.get("browser")==="1"&&q.get("tool")==="textEffects"&&q.get("textOnly")==="1";
if(textOnly)document.documentElement.classList.add("caption-text-only");
const labels={animationPresets:'Presets',clean:'Smart Clean',script:'Smart Edit',captions:'Auto Captions',reelRecreate:'Reel Recreate',broll:'Add B-roll',visuals:'Smart Visuals',zoom:'Smart Zoom',sound:'Sound Design',beats:'Beat Studio',cinematic:'Cinematic Footage',downloader:'Downloader',photos:'Photo Collector',voiceover:'Voice Clone',imageDownload:'Image Downloader',templateText:'Template Text',templateAligner:'Template Aliner',copyPaste:'Copy Paste',templateImport:'Import Template'};
let context=null,mode='clean',busy=false,current=null,visualSources=null,visualChoosing=false,serial=0;const pending=new Map();
let effectsView=null,photoWatch=null,copyPasteView=null,templateImportView=null,templateAlinerView=null,templateTextView=null,copyActivation=null;
let animationPresetView=null,effectsLibraryView=null,presetView=null,caption3dView=null,captionPatternView=null;
let browserNativeListener=null,presetReady=Promise.resolve();
const isEditingBusy=()=>!!browserNativeListener?.isRunning()||!!captionPatternView?.isRunning()||!!animationPresetView?.isRunning()||!!caption3dView?.isRunning()||!!presetView?.isRunning()||!!effectsLibraryView?.isRunning()||!!effectsView?.isRunning()||!!templateTextView?.isRunning()||busy||!!templateImportView?.isRunning()||!!templateAlinerView?.isRunning();
const brollNativeLink=host==='capcut'?null:window.storylensTimedChoicePanel?.create({api,native,isBusy:isEditingBusy,onError:error});
window.addEventListener('beforeunload',()=>brollNativeLink?.stop());
$('hostLabel').textContent=hostNames[host];$('capcutNote').hidden=host!=='capcut';$('capcutPicker').hidden=host!=='capcut';
async function api(path,body){const r=await window.storylensFetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Hinglish-Token':token},...(body?{body:JSON.stringify(body)}:{})});return window.storylensResponse(r);}
function error(value){const box=$('error');box.hidden=false;box.textContent=window.storylensError(value);const detail=document.getElementById('storylensErrorDetails');if(detail)box.append(detail);}
function clearError(){$('error').hidden=true;$('error').replaceChildren();window.storylensClearError?.();}
if(host==='aftereffects'&&!window.storylensPresetLibrary){
 $('effectsHome').hidden=false;
 effectsView=window.storylensCinematicText?.({native:async(action,payload={})=>native('cinematicText',{...payload,action}),isBusy:()=>!!effectsLibraryView?.isRunning()||!!templateTextView?.isRunning()||busy||!!templateImportView?.isRunning()||!!templateAlinerView?.isRunning(),showError:error,clearError});
 $('effectsHome').onclick=()=>{if(isEditingBusy())return;$('effectsSection').hidden=false;document.querySelector('main').hidden=true;$('storylensHome').setAttribute('aria-pressed','false');$('effectsHome').setAttribute('aria-pressed','true');effectsView?.select();};
}
$('storylensHome').onclick=()=>{if(isEditingBusy())return;effectsView?.hide();$('effectsSection').hidden=true;document.querySelector('main').hidden=false;$('storylensHome').setAttribute('aria-pressed','true');$('effectsHome').setAttribute('aria-pressed','false');};
$('effectsCopyPaste').onclick=()=>{if(isEditingBusy())return;$('storylensHome').onclick();select('copyPaste');};
if(host==='aftereffects'&&!window.storylensPresetLibrary&&window.storylensEffectsLibrary){
 effectsLibraryView=window.storylensEffectsLibrary?.({native,isBusy:()=>!!effectsView?.isRunning()||!!templateTextView?.isRunning()||busy||!!templateImportView?.isRunning()||!!templateAlinerView?.isRunning(),clearError});
 $('effectsLibraryHome').hidden=false;$('effectsHome').textContent='Text';
 $('effectsLibraryHome').onclick=()=>{if(isEditingBusy())return;effectsView?.hide();$('effectsSection').hidden=true;$('effectsTemplatesSection').hidden=false;document.querySelector('main').hidden=true;$('storylensHome').setAttribute('aria-pressed','false');$('effectsHome').setAttribute('aria-pressed','false');$('effectsLibraryHome').setAttribute('aria-pressed','true');effectsLibraryView.select();};
 for(const id of ['storylensHome','effectsHome'])$(id).addEventListener('click',()=>{if(effectsLibraryView?.isRunning())return;effectsLibraryView?.hide();$('effectsTemplatesSection').hidden=true;$('effectsLibraryHome').setAttribute('aria-pressed','false');});
}
if(host==='aftereffects'&&window.storylensPresetLibrary){
 $('presetSlider').hidden=false;document.querySelector('header').classList.add('preset-header');
 presetView=window.storylensPresetLibrary({textOnly,extraTabs:window.storylensAnimationPresets?[$('animationPresetsHome')]:[],native:async(action,payload={})=>action==='media'?native('copyPaste',{action:payload.media_action,fit:'fill'}):native('presetLibrary',{...payload,action}),isBusy:()=>!!animationPresetView?.isRunning()||busy||!!effectsView?.isRunning()||!!effectsLibraryView?.isRunning()||!!templateTextView?.isRunning()||!!templateImportView?.isRunning()||!!templateAlinerView?.isRunning(),showError:error,clearError,onSelect:()=>{$('animationPresetsHome').setAttribute('aria-pressed','false');$('presetSection').hidden=false;$('effectsSection').hidden=true;$('effectsTemplatesSection').hidden=true;document.querySelector('main').hidden=true;animationPresetView?.hide();$('storylensHome').setAttribute('aria-pressed','false');}});
 $('storylensHome').onclick=()=>{if(isEditingBusy())return;if(mode==='animationPresets')select('clean');presetView.hide();$('presetSection').hidden=true;document.querySelector('main').hidden=false;$('storylensHome').setAttribute('aria-pressed','true');};
 if(q.get('browser')!=='1'||['presetLibrary','textEffects','effectsLibrary'].includes(q.get('tool')))presetReady=Promise.resolve().then(()=>presetView.init());
}
function native(action,payload={}){if(q.get('browser')==='1')return window.storylensBrowserNative.request(host,action,payload);return new Promise((resolve,reject)=>{if(host==='capcut')return reject(Error('This operation uses the CapCut saved-project companion.'));const id=String(++serial),timer=setTimeout(()=>{if(action==='templateText'&&payload.action==='apply'){window.dispatchEvent(new CustomEvent('storylens-native-waiting',{detail:{action,payload}}));return;}pending.delete(id);reject(Error('The editor did not answer. Open the installed Storylens panel in your editor and reconnect.'));},action==='context'&&payload.appearance_cache===true?1800000:action==='import'&&payload.type==='reel_recreate'?600000:action==='templateText'?600000:['animationPresets','caption3d','presetLibrary','effectsLibrary','cinematicText','templateAlign','copyPaste','templateImport','imageDownload','downloadImport'].includes(action)?120000:15000);pending.set(id,{resolve,reject,timer});const message={type:'storylens-host-request',id,nonce,action,payload};if(window.uxpHost)window.uxpHost.postMessage(message);else if(window.parent!==window)window.parent.postMessage(message,'*');else{clearTimeout(timer);pending.delete(id);reject(Error('Open Storylens inside '+hostNames[host]+' to access the active timeline.'));}});}
window.addEventListener('message',event=>{const d=event.data;if(d?.type==='storylens-shortcut-state'&&d.nonce===nonce&&event.source===window.parent){copyPasteView?.shortcutState(d.state||{});return;}if(d?.type==='storylens-shortcut'&&d.nonce===nonce&&event.source===window.parent){if(copyPasteView?.isEnabled())copyPasteView.shortcut(d.event);return;}if(d?.type==='storylens-file-paste'&&d.nonce===nonce&&event.source===window.parent){if(d.phase!=='keyboard')select('copyPaste');copyPasteView?.filePaste(d);return;}if(d?.type!=='storylens-host-response'||d.nonce!==nonce||(!window.uxpHost&&event.source!==window.parent))return;const task=pending.get(d.id);if(!task)return;clearTimeout(task.timer);pending.delete(d.id);d.error?task.reject(Object.assign(Error(d.error),{code:d.code,details:d.details})):task.resolve(d.result);});
if(host==='aftereffects'&&window.storylensAnimationPresets){$('animationPresetsHome').hidden=false;$('animationPresetsHome').onclick=()=>{if(isEditingBusy())return;select('animationPresets');};}
if(host==='aftereffects')animationPresetView=window.storylensAnimationPresets?.({native,isBusy:()=>!!caption3dView?.isRunning()||!!presetView?.isRunning()||!!effectsLibraryView?.isRunning()||!!effectsView?.isRunning()||!!templateTextView?.isRunning()||busy||!!templateImportView?.isRunning()||!!templateAlinerView?.isRunning(),showError:error,clearError});
if(host==='aftereffects')templateTextView=window.storylensTemplateText?.({native,api,clearError,isBusy:()=>busy||!!templateImportView?.isRunning()||!!templateAlinerView?.isRunning()});
templateAlinerView=window.storylensTemplateAliner?.({host,native,showError:error,clearError,isBusy:()=>busy||!!templateTextView?.isRunning()||!!templateImportView?.isRunning()});
if(host==='aftereffects')templateImportView=window.storylensTemplateImport?.({observe:q.get('browser')!=='1',native,showError:error,clearError,isBusy:()=>busy||!!templateTextView?.isRunning()||!!templateAlinerView?.isRunning()});
if(host==='aftereffects')copyPasteView=window.storylensCopyPaste?.({root:$('copyPasteSection'),host,native,isBusy:isEditingBusy,clearError,showError:error,shortcuts:false,onAttention:()=>select('copyPaste'),onEnabled:copyPasteState,keyboard:q.get('browser')==='1'?null:enabled=>native('shortcutWatch',{enabled})});
window.storylensImageDownload?.({token,api,native,clearError,showError:error,captureProject:async()=>{const project=await native('projectContext');return api('/api/panel/context',{...project,script:$('sharedScript').value,content_format:$('contentFormat').value});},enableCopy:async()=>{if(copyPasteView&&!copyPasteView.isShortcutReady())await copyPasteView.setEnabled(true);if(copyPasteView&&!copyPasteView.isShortcutReady())throw Error('The image is in Downloads. Reopen Copy Paste to reconnect the mouse shortcuts.');}});
function copyPasteState(enabled,ready){for(const button of $('tools').querySelectorAll('button'))if(button.dataset.mode==='copyPaste'){button.textContent='Copy Paste';button.setAttribute('aria-pressed',String(mode==='copyPaste'));}}
async function capture(){clearError();$('connection').textContent='Reading '+hostNames[host]+'…';let value;try{
if(host==='capcut')value=await api('/api/panel/capcut-context',{project_id:$('capcutProject').value,script:$('sharedScript').value,content_format:$('contentFormat').value});
else{value=await native('context');value.host=host;const saved=localStorage.getItem('storylens.panel.'+host+'.'+value.project_id+'.'+value.sequence_id);if(saved){try{const old=JSON.parse(saved);if(!$('sharedScript').value)$('sharedScript').value=old.script||'';$('contentFormat').value=old.content_format||'short';}catch(_){}}
 value=await api('/api/panel/context',{...value,script:$('sharedScript').value,content_format:$('contentFormat').value});}
context=value;$('contextName').textContent=context.name||context.sequence_id;$('connection').textContent='Connected';persist();$('status').textContent='Current timeline connected. Choose your tool.';return context;}catch(e){$('connection').textContent='Check timeline';throw e;}}
function persist(){if(!context)return;try{localStorage.setItem('storylens.panel.'+host+'.'+context.project_id+'.'+context.sequence_id,JSON.stringify({script:$('sharedScript').value,content_format:$('contentFormat').value}));}catch(_){};}
let photoDownloadQueue=Promise.resolve();
async function importPhotoDownload(id){
 const project=await native('projectContext'),saved=await api('/api/panel/context',{...project,script:$('sharedScript').value,content_format:$('contentFormat').value});
 const manifest=await api('/api/panel/photos',{id,host,context_id:saved.id});
 const receipt=await native('import',manifest);
 if(receipt?.status!=='done')throw Object.assign(Error('The photo is saved, but After Effects could not confirm its project folder. Press the same photo again to retry.'),{details:receipt?.error});
 await api('/api/panel/photo-receipt',{id,host,receipt});return receipt;
}
async function importPhotos(id){
 clearError();
 if(host==='capcut'){await api('/api/photos/open-folder',{id});$('receipt').textContent='Open this collection’s images in CapCut from the saved folder.';return;}
 const project=await native('projectContext'),saved=await api('/api/panel/context',{...project,script:$('sharedScript').value,content_format:$('contentFormat').value});
 const watcher={id,context_id:saved.id,last:''};photoWatch=watcher;
 async function transfer(){if(photoWatch!==watcher)return;try{
  const manifest=await api('/api/panel/photos',{id,host,context_id:watcher.context_id});
  const signature=JSON.stringify(manifest.photos.map(p=>[p.id,p.path,p.origin]));
  if(signature!==watcher.last){const receipt=await native('import',manifest);if(receipt?.status!=='done')throw Error(receipt?.error||'The editor has not confirmed the photo import. Saved files are kept.');
   await api('/api/panel/photo-receipt',{id,host,receipt});watcher.last=signature;
   $('receipt').textContent=`${receipt.original_count||0} originals · ${receipt.preview_count||0} labelled previews in Images / ${receipt.folder.name}. Matching originals replace these same items when ready.`;}
  const job=await api('/api/photos/job?id='+id);
  if(!['done','failed','cancelled','interrupted','archived'].includes(job.status))setTimeout(transfer,2500);
  else if(mode==='photos'&&$('utilityFrame').contentWindow.localStorage.getItem('storylens-photo-job')===id)$('utilityFrame').contentWindow.location.reload();
 }catch(e){error(e);photoWatch=null;}}
 await transfer();
}
async function importManifest(manifest){if(!manifest)throw Error('This result is not ready for import.');if(host==='capcut'){if(manifest.type!=='capcut')throw Error('Use the CapCut project handoff for this result.');const response=await api('/api/editors/action',{id:manifest.task_id,action:'open-editor'});$('receipt').textContent=response.message;return;}
const receipt=await native('import',manifest);if(!receipt?.ok)throw Error('The editor did not confirm this import. Your saved output is kept.');$('receipt').textContent=receipt.message||'Editor confirmed the import.';return receipt;}
async function importFolder(result,kind='',asset=''){if(result.kind&&result.path)asset=result.path;const manifest=await api('/api/panel/import',{host,context_id:context?.id,folder:result.folder,mode:kind,asset});return importManifest(manifest);}
async function chooseBroll(row,state){
 const folder=current.result.folder;
 if(!context)await capture();
 const timed=host==='premiere'||host==='aftereffects';
 const response=await api('/api/panel/broll-choice',{context_id:context.id,folder,project:row.project,slot_id:row.slot_id,candidate_id:state==='selected'?row.candidate_id:null,state,...(timed?{delivery:'active_timeline'}:{})});
 if(response.manifest){
  if(timed&&response.manifest.type!=='timed_choice')throw Error('The saved choice is kept. Reopen Storylens when safe to enable individual timeline replacement; no new timeline was imported.');
  const receipt=await importManifest(response.manifest);
  if(timed)await api('/api/panel/broll-choice',{context_id:context.id,delivery:'receipt',operation_id:response.manifest.operation_id,receipt});
 }else $('receipt').textContent=response.message||'Choice saved. Existing editor clips are kept; remove them in the editor if needed.';
 const refreshed=await api('/api/panel/broll-candidates?context_id='+encodeURIComponent(context.id)+'&folder='+encodeURIComponent(folder));
 brollCards(refreshed.choices);
}
function brollCards(choices){
 $('choices').replaceChildren();const slots=new Set();
 for(const row of choices||[]){
  if(!slots.has(row.slot_id)){
   slots.add(row.slot_id);const group=document.createElement('article');group.className='asset';
   const heading=document.createElement('p');heading.textContent=`${row.keyword} · ${Number(row.start).toFixed(2)}–${Number(row.end).toFixed(2)}s`;
   const skip=document.createElement('button');skip.textContent=row.choice?.state==='no_broll'?'No B-roll selected':'No B-roll';
   skip.onclick=()=>chooseBroll(row,'no_broll').catch(error);group.append(heading,skip);$('choices').append(group);
  }
  const card=document.createElement('article');card.className='asset';
  if(row.path){const media=document.createElement('video');media.controls=true;media.preload='metadata';media.src='/api/panel/media?path='+encodeURIComponent(row.path)+'&token='+encodeURIComponent(token);card.append(media);}
  const label=document.createElement('p');label.textContent=row.keyword+(row.selectable?'':': '+(row.issue?.message||'This video still needs a checked source window.'));
  if(row.issue?.details){const details=document.createElement('details'),summary=document.createElement('summary'),body=document.createElement('pre');summary.textContent='Technical details';body.textContent=row.issue.details;details.append(summary,body);card.append(details);}
  const use=document.createElement('button');use.textContent=host==='capcut'?'Use in new project':'Use at keyword';use.disabled=!row.selectable;
  use.onclick=async()=>{use.disabled=true;try{await chooseBroll(row,'selected');}catch(e){error(e);}finally{use.disabled=!row.selectable;}};
  card.append(label,use);$('choices').append(card);
 }
}
async function chooseVisual(bank,mediaId,importSelected){
 if(visualChoosing)return;visualChoosing=true;
 try{
  const baseline=visualSources;
  if(importSelected)await capture();
  const response=await api('/api/panel/visual-source-choice',{type:'smart_visuals.source_bank.select',version:1,
   context_id:context?.id,job_id:baseline.job_id,project_path:baseline.project_path,
   base_manifest:baseline.manifest_path,base_manifest_sha256:baseline.manifest_sha256,
   choices:{[String(bank.slot_index)]:mediaId},import_selected:importSelected});
  // Keep the advanced saved baseline even if the host import fails.
  visualSources=response;
  if(response.native_manifest)await importManifest(response.native_manifest);
  else $('receipt').textContent='No visual saved for this subject. No image was inserted.';
 }finally{visualChoosing=false;visualCards(visualSources);}
}
function visualCards(descriptor){
 visualSources=descriptor;$('choices').replaceChildren();
 for(const bank of descriptor?.banks||[]){
  const group=document.createElement('article');group.className='asset';
  const heading=document.createElement('p');heading.textContent=`${bank.entity} · ${Number(bank.anchor.start_seconds).toFixed(2)}–${Number(bank.anchor.end_seconds).toFixed(2)}s`;
  const skip=document.createElement('button');skip.textContent=bank.selection?.state==='no_visual'?'No visual selected':'No visual';
  skip.onclick=()=>chooseVisual(bank,'',false).catch(error);group.append(heading,skip);
  if(!bank.choices.length){const empty=document.createElement('p');empty.textContent='No matching source image. Saved research is kept.';group.append(empty);}
  else if(bank.choices.length<bank.target){const partial=document.createElement('p');partial.textContent=`${bank.choices.length} of ${bank.target} source images available.`;group.append(partial);}
  $('choices').append(group);
  for(const row of bank.choices){
   const card=document.createElement('article');card.className='asset';
   const image=document.createElement('img');image.alt=bank.entity;
   image.src='/api/panel/visual-source-media?'+new URLSearchParams({job_id:descriptor.job_id,project_path:descriptor.project_path,manifest_sha256:descriptor.manifest_sha256,asset_id:row.asset_id,token});
   const add=document.createElement('button');add.textContent='Import source image';
   add.onclick=async()=>{add.disabled=true;try{await chooseVisual(bank,row.media_id,true);}catch(e){error(e);}finally{add.disabled=false;}};
   card.append(image,add);$('choices').append(card);
  }
  if(bank.unavailable_choices?.length){const details=document.createElement('details'),summary=document.createElement('summary'),body=document.createElement('pre');summary.textContent='Technical details';body.textContent=bank.unavailable_choices.map(r=>r.reason).join('\n');details.append(summary,body);group.append(details);}
 }
}
async function listenSound(row,audio){
 const result=await api('/api/panel/sound-audition',{context_id:context?.id,job_id:row.job_id,candidate_id:row.id});
 if(result.status!=='ready')throw Object.assign(Error(result.notice||'This audition could not finish.'),{code:result.error_code,details:result.technical_details});
 document.querySelectorAll('audio').forEach(a=>{if(a!==audio)a.pause()});audio.hidden=false;
 audio.src=result.preview||('/api/panel/sound-audition-media?'+new URLSearchParams({job_id:row.job_id,audition_id:result.id,token}));
 try{await audio.play();}catch(_){$('receipt').textContent='Audition prepared. Press Play to listen.';}
}
async function importOriginalSound(row,insert=false){
 await capture();
 const result=await api('/api/panel/sound-original',{context_id:context.id,job_id:row.job_id,candidate_id:row.id,insert});
 await importManifest(result.manifest);
}
function soundCards(review){
 $('choices').replaceChildren();
 const box=document.createElement('section');box.className='sound-choice-box';
 const picker=document.createElement('select');picker.setAttribute('aria-label','Sound event');
 for(const group of review.groups){const o=document.createElement('option');o.value=group.id;o.textContent=Number(group.timeline.start).toFixed(2)+'s · '+(group.intent||group.kind);picker.append(o);}
 const list=document.createElement('div');box.append(picker,list);$('choices').append(box);
 if(review.folders?.length){
  const folders=document.createElement('select');folders.setAttribute('aria-label','Sound keyword folder');
  for(const group of review.folders)folders.add(new Option(group.name+' ('+group.candidates.length+' sounds)',group.id));
  const chooseFolder=()=>{const folder=review.folders.find(f=>f.id===folders.value);picker.replaceChildren();for(const group of review.groups.filter(g=>folder.events.includes(g.id)))picker.add(new Option(Number(group.timeline.start).toFixed(2)+'s · '+group.intent,group.id));show();};
  folders.onchange=chooseFolder;box.prepend(folders);chooseFolder();
  const pack=document.createElement('button');pack.textContent='Import folders + draft timeline';
  pack.onclick=async()=>{pack.disabled=true;try{await importFolder({folder:review.folder},'sound');}catch(e){error(e);}finally{pack.disabled=false;}};box.prepend(pack);
 }
 function show(){list.replaceChildren();const group=review.groups.find(g=>g.id===picker.value);if(!group)return;
  if(!group.candidates.length){list.textContent='No matching sounds for this event.';return;}
  for(const candidate of group.candidates){const row={...candidate,job_id:review.job_id},card=document.createElement('div');card.className='sound-choice-row';
   const label=document.createElement('span');label.textContent=row.name;
   const audio=document.createElement('audio');audio.controls=true;audio.preload='none';audio.hidden=true;
   const listen=document.createElement('button');listen.textContent='Listen';listen.onclick=async()=>{listen.disabled=true;try{await listenSound(row,audio);}catch(e){error(e);}finally{listen.disabled=false;}};
   const add=document.createElement('button');add.textContent='Import';add.onclick=async()=>{add.disabled=true;try{await importOriginalSound(row);}catch(e){error(e);}finally{add.disabled=false;}};
   const place=document.createElement('button');place.textContent='At playhead';place.title='Use a spare audio track in Premiere Pro';place.onclick=async()=>{place.disabled=true;try{await importOriginalSound(row,true);}catch(e){error(e);}finally{place.disabled=false;}};
   if(host==='capcut'){place.hidden=true;add.textContent='Get sound';add.onclick=async()=>{add.disabled=true;try{const data=await api('/api/panel/sound-audition',{context_id:context?.id,job_id:row.job_id,candidate_id:row.id});if(!data.download)throw Error('Use the saved sound review to download the original recording.');const a=document.createElement('a');a.href=data.download;a.download=data.name||'sound.wav';document.body.append(a);a.click();a.remove();}catch(e){error(e);}finally{add.disabled=false;}};}
   card.append(label,listen,add,place,audio);list.append(card);
  }
 }
 picker.onchange=show;show();
}

function cards(choices){if(mode==='broll')return brollCards(choices);if(mode==='visuals')return visualCards(current.visual_sources);if(mode==='sound'&&current.sound_review)return soundCards(current.sound_review);$('choices').replaceChildren();for(const row of choices||[]){const card=document.createElement('article');card.className='asset';const label=document.createElement('p');label.textContent=row.keyword||row.name;let media;if(row.kind==='image'){media=document.createElement('img');media.alt=row.keyword||row.name;}else if(row.kind==='audio'){media=document.createElement('audio');media.controls=true;}else{media=document.createElement('video');media.controls=true;media.preload='metadata';}media.src='/api/panel/media?path='+encodeURIComponent(row.path)+'&token='+encodeURIComponent(token);const add=document.createElement('button');add.textContent='Add to '+hostNames[host];add.onclick=async()=>{add.disabled=true;try{await importFolder(current.result,'',row.path);}catch(e){error(e);}finally{add.disabled=false;}};card.append(media,label,add);$('choices').append(card);}}
function createCaptionPatternView(){return window.storylensCaptionPatterns?.({root:$('captionSettings'),style:$('captionStyle'),button:$('run'),native,readScript:()=>$('sharedScript').value,onStatus:s=>{$('status').textContent=s;},showError:error,clearError,isBusy:isEditingBusy});}
async function ensureNativeCaptionPattern(){
 if(host!=='aftereffects'||!['caption_1','caption_1_ae','caption_2','caption_3','caption_4','caption_6'].includes($('captionStyle').value))return;
 const id=$('captionStyle').value==='caption_1_ae'?'caption_1':$('captionStyle').value;
 if(captionPatternView?.supports?.(id))return;
 if(captionPatternView?.isRunning?.())throw Error('Wait for the current caption request to finish.');
 if(!window.storylensCaptionPatterns?.supportedStyles?.includes(id)){
  if(!window.storylensCaptionPatternsLoading)window.storylensCaptionPatternsLoading=new Promise((resolve,reject)=>{
   const script=document.createElement('script'),message='Caption controls could not load. Close and reopen only the Storylens panel, then retry Generate captions.';
   const finish=e=>{clearTimeout(timer);script.remove();e?reject(Error(message)):resolve();};
   const timer=setTimeout(()=>finish(true),15000);script.src='caption-patterns.js?v=20261029-native6-1';script.onload=()=>finish(false);script.onerror=()=>finish(true);document.head.append(script);
  }).finally(()=>{window.storylensCaptionPatternsLoading=null;});
  await window.storylensCaptionPatternsLoading;
 }
 if(!window.storylensCaptionPatterns?.supportedStyles?.includes(id))throw Error('Updated caption controls are unavailable. Close and reopen only the Storylens panel.');
 for(const row of $('captionSettings').querySelectorAll('.cp-settings'))row.remove();
 captionPatternView=createCaptionPatternView();captionPatternView?.sync(caption3dView?.isStandard()!==false);
 if(!captionPatternView?.isSelected())throw Error('Select a native caption style and retry Generate captions.');
}
async function run(){if(isEditingBusy())return;if(mode==='captions'&&host==='aftereffects'){try{await ensureNativeCaptionPattern();}catch(e){error(e);return;}}const fixedPattern=mode==='captions'&&host==='aftereffects'&&captionPatternView?.isSelected();if(fixedPattern&&captionPatternView.hasPending())return captionPatternView.retry();if(fixedPattern)return captionPatternView.usesScriptTiming()?captionPatternView.generateScript():captionPatternView.generateSpeech();busy=true;$('run').disabled=true;clearError();$('receipt').textContent='';try{await capture();const request=model.request(mode,{script:$('sharedScript').value,content_format:$('contentFormat').value},context,{caption_style:$('captionStyle').value,sound_action:$('soundAction').value});persist();busy=true;$('run').disabled=true;$('progress').hidden=false;$('choices').replaceChildren();$('importResult').hidden=true;
let job=await api('/api/panel/run',request);while(['queued','running'].includes(job.status)){$('status').textContent=job.stage;$('progress').value=job.progress||0;await new Promise(r=>setTimeout(r,850));job=await api('/api/panel/job?id='+job.id);}
if(job.status!=='complete')throw Object.assign(Error(job.error||job.stage),{code:job.error_code,details:job.error_details});current=job;cards(job.choices);$('status').textContent=job.sound_review?'Review the sound alternatives. Listen, then import original recordings into the project bin.':job.visual_sources?'Review raw source images. Import only your choices; no lettering or automatic placement is added.':job.choices?.length?`${job.choices.length} source-backed options ready. Choose which to use.`:job.stage;$('importResult').hidden=!job.result||['broll','visuals'].includes(mode)||!!job.sound_review;
$('importResult').textContent=job.review_required?'Add review draft to editor':'Add result to editor';
if(job.auto_import&&!job.review_required&&job.manifest)await importManifest(job.manifest);else if(!job.choices?.length&&!job.visual_sources&&!job.sound_review)$('status').textContent=job.review_required?job.stage:'Result ready for review. Add it when you choose.';
}catch(e){error(e);}finally{busy=false;$('run').disabled=false;$('progress').hidden=true;}}
function select(next,preserveWorkspace=false){$('tools').hidden=next==='animationPresets';$('animationPresetsHome').setAttribute('aria-pressed',String(next==='animationPresets'));$('animationPresetSection').hidden=next!=='animationPresets';if(next==='animationPresets')animationPresetView?.open();else animationPresetView?.hide();if(presetView&&!preserveWorkspace){presetView.hide();$('presetSection').hidden=true;document.querySelector('main').hidden=false;$('storylensHome').setAttribute('aria-pressed','true');}if(next==='animationPresets')$('storylensHome').setAttribute('aria-pressed','false');mode=next;$('templateTextSection').hidden=mode!=='templateText';document.body.dataset.mode=mode;$('imageDownloadSection').hidden=mode!=='imageDownload';clearError();$('status').textContent='';$('captionSettings').append(...(mode==='captions'?[$('run')]:[]));if(mode!=='captions')$('runControls').append($('run'));$('run').hidden=['zoom','broll','visuals'].includes(mode);$('toolTitle').hidden=mode!=='sound';$('templateAlinerSection').hidden=mode!=='templateAligner';$('sharedSettings').hidden=['animationPresets','templateAligner','copyPaste','templateImport','imageDownload','reelRecreate','voiceover'].includes(mode);$('copyPasteSection').hidden=mode!=='copyPaste';$('templateImportSection').hidden=mode!=='templateImport';$('templateAlinerSettings').hidden=host!=='aftereffects'||mode!=='templateAligner';for(const b of $('tools').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.mode===mode));const utility=['beats','cinematic','downloader','photos','reelRecreate','voiceover'].includes(mode);$('editingControls').hidden=utility||['animationPresets','templateAligner','copyPaste','templateImport','imageDownload','templateText'].includes(mode);$('utility').hidden=!utility;$('toolTitle').textContent=labels[mode];$('run').textContent=mode==='captions'?'Generate captions':'Run '+labels[mode];$('captionSettings').hidden=mode!=='captions';if(mode==='captions')caption3dView?.sync();$('soundSettings').hidden=mode!=='sound';$('choiceHint').hidden=true;$('savedBrollControls').hidden=mode!=='broll';if(mode==='broll')refreshBroll().catch(error);$('toolDescription').textContent=mode==='clean'?'Remove silent sections from a new copy of the current timeline.':mode==='broll'||mode==='visuals'?`${model.choiceCount($('contentFormat').value)} options per keyword, when matching sources are available. You choose what to add.`:'Uses the current timeline and your shared script.';
$('savedVisualControls').hidden=mode!=='visuals';if(mode==='visuals')refreshVisuals().catch(error);
$('savedSoundControls').hidden=mode!=='sound';if(mode==='sound')refreshSound().catch(error);
if(utility){const frame=$('utilityFrame');frame.hidden=false;frame.src=mode==='reelRecreate'?reelOrigin+'/reel-recreate.html?embedded=1&host='+host+'&panel=1&reel_nonce='+encodeURIComponent(nonce)+(q.get('reel_job')?'&job='+encodeURIComponent(q.get('reel_job')):''):(mode==='cinematic'?'cinematic-footage':mode)+'.html?embedded=1&host='+host+'&panel=1';frame.title=labels[mode];$('useSelected').hidden=mode!=='cinematic';$('useMusic').hidden=mode!=='beats';}}
function patchUtility(){const frame=$('utilityFrame'),win=frame.contentWindow;if(mode==='reelRecreate')return;const doc=frame.contentDocument;if(!doc)return;const style=doc.createElement('style');style.textContent='body>header,main>.intro,main>h1,.result-actions>.secondary{display:none!important}main{padding:0!important}';doc.head.append(style);
if(win.storylensEditors&&mode!=='downloader'){const nativeRender=(container,result)=>{container.replaceChildren();if(!result?.folder)return;const button=doc.createElement('button');button.textContent='Add to '+hostNames[host];button.className='editor-logo-button';button.dataset.hostNative='1';button.onclick=()=>importFolder(result).catch(error);container.append(button);};win.storylensEditors.render=nativeRender;
const currentResult=()=>{const save=doc.querySelector('#saveMedia');if(save?.href){const u=new URL(save.href);return api('/api/downloader/job?id='+u.searchParams.get('id')).then(job=>job.result.assets[u.searchParams.get('kind')]);}const video=doc.querySelector('#preview');if(video?.src){const id=video.src.split('/').pop().split('?')[0];return api('/api/cinematic/jobs/'+id).then(job=>job.result);}return Promise.resolve(null);};const refresh=()=>{for(const node of doc.querySelectorAll('.editor-exports')){if(node.querySelector('[data-host-native]'))continue;currentResult().then(result=>{if(result&&!node.querySelector('[data-host-native]'))nativeRender(node,result);}).catch(error);}};refresh();new MutationObserver(refresh).observe(doc.body,{childList:true,subtree:true});}
if(mode==='beats'){const button=doc.createElement('button');button.textContent='Add beat markers to '+hostNames[host];button.onclick=async()=>{try{const plan=win.storylensBeatPlan;if(!plan)throw Error('Detect the music beats first.');const response=await native('markBeats',{...plan,sequence_id:context?.sequence_id});$('receipt').textContent=response.message;}catch(e){error(e);}};doc.querySelector('#results')?.append(button);}
if(mode==='downloader'&&host!=='capcut'){
 const captureTarget=async()=>{const project=await native('projectContext');return api('/api/panel/context',{...project,script:$('sharedScript').value,content_format:$('contentFormat').value});};
 win.storylensDownloadTarget=captureTarget;
 let deliveryQueue=Promise.resolve();
 win.addEventListener('storylens-download-ready',event=>{
  const d=event.detail||{};if(!/^[a-f0-9]{32}$/.test(d.id||'')||!['video','audio'].includes(d.kind))return;
  const respond=value=>win.dispatchEvent(new win.CustomEvent('storylens-download-delivery',{detail:{id:d.id,kind:d.kind,folder:d.kind==='video'?'Video':'Sound',...value}}));
  deliveryQueue=deliveryQueue.catch(()=>{}).then(async()=>{try{
   respond({pending:true});const target=d.context_id?{id:d.context_id}:await captureTarget();
   const manifest=await api('/api/panel/download-import',{id:d.id,kind:d.kind,context_id:target.id});
   const receipt=await native('downloadImport',manifest);if(!receipt?.ok)throw Object.assign(Error(receipt?.error||'The downloaded media is saved. Select Video or Audio to retry.'),{code:receipt?.code,details:receipt?.details});
   await api('/api/panel/download-receipt',{id:d.id,kind:d.kind,context_id:target.id,receipt});respond({pending:false,warning:receipt.ui_cleanup?.ok===false?receipt.ui_cleanup.message:null});
  }catch(e){respond({error:{message:e.message,code:e.code,details:e.details}});}});
 });
}
if(mode==='photos'){
 win.addEventListener('storylens-photo-download',event=>{
  const detail=event.detail||{};if(!/^[a-f0-9]{12}$/.test(detail.id||'')||String(detail.id)!==win.localStorage.getItem('storylens-photo-job'))return;
  photoDownloadQueue=photoDownloadQueue.catch(()=>{}).then(async()=>{if(String(detail.id)!==win.localStorage.getItem('storylens-photo-job'))return;try{const receipt=host!=='capcut'?await importPhotoDownload(detail.id):null;const photo_ids=receipt?['imported','upgraded','already_present'].flatMap(key=>(receipt[key]||[]).map(row=>row.photo_id)):[detail.item];win.dispatchEvent(new win.CustomEvent('storylens-photo-transfer',{detail:{id:detail.id,item:detail.item,name:detail.name,photo_ids}}));}catch(e){win.dispatchEvent(new win.CustomEvent('storylens-photo-transfer',{detail:{id:detail.id,item:detail.item,error:{message:e.message,code:e.code,details:e.details}}}));}});
 });
}}

window.addEventListener('message',async event=>{const frame=$('utilityFrame'),data=event.data;if(mode!=='reelRecreate'||event.source!==frame.contentWindow||event.origin!==reelOrigin||data?.type!=='storylens-reel-import'||data.nonce!==nonce||!data.id)return;try{const result=await native('import',data.result);event.source.postMessage({type:'storylens-reel-import-result',nonce,id:data.id,result},reelOrigin)}catch(error){event.source.postMessage({type:'storylens-reel-import-result',nonce,id:data.id,error:{message:error.message,code:error.code,details:error.details}},reelOrigin)}});
window.addEventListener('message',event=>{const frame=$('utilityFrame');if(event.source!==frame.contentWindow||event.origin!==location.origin||event.data?.type!=='storylens-tool-height')return;const height=Number(event.data.height);if(Number.isFinite(height)&&height>0&&height<30000)frame.style.height=Math.max(60,Math.ceil(height))+'px';});
$('utilityFrame').onload=patchUtility;
$('useSelected').onclick=async()=>{try{const result=await native('selectedMedia');$('utilityFrame').contentWindow.dispatchEvent(new CustomEvent('storylens-native-shots',{detail:result.paths}));$('receipt').textContent=result.paths.length+' selected clips added.';}catch(e){error(e);}};
$('useMusic').onclick=async()=>{try{const music=await native('music'),doc=$('utilityFrame').contentDocument;const fields=mode==='cinematic'?{musicPath:music.path,musicIn:music.source_in,musicOut:music.source_out,fps:music.fps}:{path:music.path,sourceIn:music.source_in,sourceOut:music.source_out,start:music.timeline_start,fps:music.fps};for(const [id,value] of Object.entries(fields)){const el=doc.getElementById(id);if(el){el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}));}}}catch(e){error(e);}};
if(host==='aftereffects')captionPatternView=createCaptionPatternView();
if(host==='aftereffects')caption3dView=window.storylens3DCaptions?.({root:$('captionSettings'),native,isBusy:isEditingBusy,showError:error,clearError,onFamilyChange:standard=>{captionPatternView?.sync(standard);$('captionStyle').hidden=!standard;if(mode==='captions')$('run').hidden=!standard;}});
$('capture').onclick=()=>capture().catch(error);$('sharedScript').oninput=persist;$('contentFormat').onchange=()=>{persist();select(mode);};$('run').onclick=run;$('importResult').onclick=()=>importFolder(current.result,current.mode).catch(error);
async function capcutProjects(){const response=await api('/api/editors/capcut-projects');$('capcutProject').replaceChildren(new Option('Choose a saved project',''));for(const p of response.projects)$('capcutProject').add(new Option(p.name,p.id));}
$('refreshCapcut').onclick=()=>capcutProjects().catch(error);
async function openSoundReview(jobId){if(!jobId)throw Error('Choose a completed sound review first.');clearError();const response=await api('/api/panel/sound-review?job_id='+encodeURIComponent(jobId));current={mode:'sound',engine_id:jobId,sound_review:response};soundCards(response);$('importResult').hidden=true;$('status').textContent='Listen to the saved alternatives. Import only the original recordings you choose into the project bin.';}
async function refreshSound(){const response=await api('/api/panel/sound-results');$('savedSound').replaceChildren(new Option('Choose a saved review',''));for(const row of response.results)$('savedSound').add(new Option(row.name,row.job_id));}
$('refreshSounds').onclick=()=>refreshSound().catch(error);$('openSounds').onclick=()=>openSoundReview($('savedSound').value).catch(error);
async function refreshBroll(){const response=await api('/api/panel/broll-results');$('savedBroll').replaceChildren(new Option('Choose a saved result',''));for(const row of response.results)$('savedBroll').add(new Option(row.name+(row.collecting?' · still collecting':''),row.folder));}
$('refreshBroll').onclick=()=>refreshBroll().catch(error);
$('openBroll').onclick=async()=>{clearError();try{const folder=$('savedBroll').value;if(!folder)throw Error('Choose a saved B-roll collection first.');if(!context||context.sequence_id==='_project_')await capture();const response=await api('/api/panel/broll-candidates?context_id='+encodeURIComponent(context.id)+'&folder='+encodeURIComponent(folder));current={mode:'broll',result:{folder},choices:response.choices};brollCards(response.choices);$('importResult').hidden=true;if(brollNativeLink)await brollNativeLink.start(context);$('status').textContent=host==='capcut'?'Each choice prepares a new editable CapCut project at the spoken timestamp.':'Choices insert at the spoken timestamp. Another option replaces the same item and preserves your edits. This timeline is also connected to the browser review.';}catch(e){error(e);}};
async function refreshVisuals(){const response=await api('/api/panel/visual-results');$('savedVisual').replaceChildren(new Option('Choose a saved review',''));for(const row of response.results)$('savedVisual').add(new Option(row.name,JSON.stringify({job_id:row.job_id,project_path:row.project_path})));}
$('refreshVisuals').onclick=()=>refreshVisuals().catch(error);
$('openVisuals').onclick=async()=>{clearError();try{if(!$('savedVisual').value)throw Error('Choose a completed visual review first.');const selected=JSON.parse($('savedVisual').value);const response=await api('/api/panel/visual-sources?'+new URLSearchParams(selected));current={mode:'visuals',engine_id:response.job_id,visual_sources:response};visualCards(response);$('importResult').hidden=true;$('status').textContent='Review original source images. Your choices import into the project bin; you decide where to place them.';}catch(e){error(e);}};
async function refreshCaptionStyles(){
 let previous=$('captionStyle').value||captionPatternView?.preferredStyle()||'caption_2';
 if(captionPatternView){if(previous==='caption_1_ae')previous='caption_1';if(previous==='caption_3')previous='caption_4';if(previous==='serif_circle_draft')previous='caption_6';}
 const catalogue=await api('/api/captions/auto2/catalog'),all=catalogue.styles||[],nativeIds=['caption_1','caption_2','caption_4','caption_6'],styles=captionPatternView?nativeIds.map(style=>({style})):all;
 if(captionPatternView&&all.some(s=>s.style===previous&&/^caption\s*3.*previous.*reference/i.test(s.name||'')))previous='caption_4';
 $('captionStyle').replaceChildren();
 for(const style of styles){const nativePattern=captionPatternView&&nativeIds.includes(style.style),option=nativePattern?captionPatternView.option(style.style):new Option(style.name,style.style);option.disabled=nativePattern?false:!style.available;$('captionStyle').add(option);}
 if(styles.some(s=>s.style===previous))$('captionStyle').value=previous;else if(captionPatternView)$('captionStyle').value='caption_2';
 captionPatternView?.sync(caption3dView?.isStandard()!==false);
}

(async()=>{try{const config=await api('/api/panel/config');for(const tool of model.tools){if(tool==='reelRecreate'&&!['aftereffects','premiere'].includes(host))continue;const b=document.createElement('button');b.type='button';b.dataset.mode=tool;b.innerHTML=window.storylensIcon(tool)+'<span></span>';b.querySelector('span').textContent=labels[tool];b.onclick=()=>{if(isEditingBusy())return;select(tool);if(['zoom','broll','visuals'].includes(tool))return run();};$('tools').append(b);}if(host==='aftereffects'){for(const tool of ['templateAligner','templateImport',...(config.template_text?['templateText']:[])]){const tile=document.createElement('button');tile.type='button';tile.dataset.mode=tool;tile.textContent=labels[tool];tile.onclick=()=>{if(isEditingBusy())return;select(tool);};$('tools').append(tile);}const copy=document.createElement('button');copy.type='button';copy.dataset.mode='copyPaste';copy.textContent='Copy Paste';copy.onclick=async()=>{select('copyPaste');if(!copyPasteView.isEnabled()||!copyPasteView.isShortcutReady()){if(!copyActivation)copyActivation=copyPasteView.setEnabled(true).finally(()=>{copyActivation=null;});await copyActivation;}};$('tools').append(copy);const image=document.createElement('button');image.type='button';image.dataset.mode='imageDownload';image.textContent='Image Downloader';image.onclick=()=>{if(isEditingBusy())return;select('imageDownload');};$('tools').append(image);}await refreshCaptionStyles();window.setInterval?.(()=>refreshCaptionStyles().catch(error),5000);window.addEventListener('focus',()=>refreshCaptionStyles().catch(error));if(mode==='clean')select('clean',true);if(host==='capcut'){await capcutProjects();$('connection').textContent='CapCut companion';}else $('connection').textContent='Ready';}catch(e){$('connection').textContent='Not connected';error(e);const load=$('browserLoadStatus');if(load)load.textContent=window.storylensProblem(e).message;}})();

/* Browser-native workbench initialization */
if(q.get('browser')!=='1'&&window.parent!==window){
 setTimeout(()=>{browserNativeListener=window.storylensBrowserNative.listen({host,native,isBusy:isEditingBusy,onError:error});},1500);
 window.addEventListener('beforeunload',()=>browserNativeListener?.stop());
}else if(q.get('browser')==='1'){
 document.body.classList.add('browser-native-tool');
 const style=document.createElement('style');style.textContent='.browser-native-tool header,.browser-native-tool #tools{display:none!important}.browser-native-tool main{padding:6px 0}';document.head.append(style);
 const wanted=q.get('tool')||'templateImport',loading=document.createElement('p');loading.id='browserLoadStatus';loading.setAttribute('role','status');loading.textContent='Loading…';document.body.prepend(loading);
 style.textContent+='.browser-native-tool:not([data-browser-ready]) main,.browser-native-tool:not([data-browser-ready]) #presetSection{visibility:hidden}';
 const loaded=()=>{document.body.dataset.browserReady='true';loading.remove();};
 const ready=setInterval(()=>{if(!$('tools').children.length)return;clearInterval(ready);if(['presetLibrary','textEffects','effectsLibrary'].includes(wanted)){if(!textOnly)document.querySelector('header').style.setProperty('display','flex','important');presetReady.then(()=>presetView?presetView.open(wanted==='textEffects'?'Text':wanted==='effectsLibrary'?'Effects':null):(wanted==='textEffects'?$('effectsHome').click():$('effectsLibraryHome').click())).catch(error).finally(loaded);}else{select(wanted);loaded();}},200);
 window.addEventListener('beforeunload',()=>clearInterval(ready));
}
})();

