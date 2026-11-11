/* Minimal CEP shell. Only named host operations can cross the local web bridge. */
(()=>{
 const frame=document.getElementById('storylensPanel'),status=document.getElementById('shellStatus');
 const bridge=window.HINGLISH_BRIDGE||'http://127.0.0.1:8765',origin=new URL(bridge).origin;
 const host=document.documentElement.dataset.host,nonce=String(Date.now())+'-'+Math.random().toString(36).slice(2);
 const calls={context:'storylensPanelContext',projectContext:'storylensPanelProjectContext',import:'storylensPanelImport',selectedMedia:'storylensPanelSelectedMedia',music:'storylensPanelMusic',markBeats:'storylensPanelMarkBeats',applyBeatEffects:'storylensPanelBeatEffects',downloadImport:'storylensPanelDownloadImport'};
 if(host==='aftereffects'){calls.templateText='storylensPanelTemplateText';calls.templateAlign='storylensPanelTemplateAlign';calls.templateFonts='storylensPanelTemplateFonts';calls.templateCollapseFolders='storylensPanelFolderCleanupContext';calls.copyPaste='storylensPanelCopyPaste';calls.templateImport='storylensPanelTemplateImport';calls.imageDownload='storylensPanelImageDownload';}
 const importFolderCleanups=new Map();
 let shortcutWatcher=null,shortcutEnabled=false,shortcutGeneration=0;
 async function shortcutWatch(enabled){
  const generation=++shortcutGeneration;shortcutEnabled=false;
  if(!enabled)return shortcutWatcher?await shortcutWatcher.stop():{ok:true,enabled:false};
  if(window.HINGLISH_SHORTCUTS_ALLOWED!==true)return {ok:false,enabled:false,message:'Buttons are ready. Explorer-focused shortcuts need approval for the scoped listener.'};
  if(!shortcutWatcher){const path=require('path'),modulePath=path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','shortcut-listener.cjs');delete require.cache[require.resolve(modulePath)];const factory=require(modulePath);
   shortcutWatcher=factory.createShortcutWatcher({root:window.HINGLISH_APP_ROOT,onShortcut:event=>{if(shortcutEnabled)frame.contentWindow.postMessage({type:'storylens-shortcut',nonce,event},origin);},onState:state=>{if(shortcutEnabled&&!state.enabled){shortcutEnabled=false;frame.contentWindow.postMessage({type:'storylens-shortcut-state',nonce,state},origin);}}});}
  const result=await shortcutWatcher.setEnabled(true);if(generation!==shortcutGeneration)return {ok:true,enabled:false};shortcutEnabled=result.ok&&result.enabled;return result;
 }
 function copyPasteKeys(enabled){
  const keys=[]; // Native Adobe bindings stay reserved; the approved listener owns custom chords.
  if(typeof window.__adobe_cep__.registerKeyEventsInterest!=='function')return {ok:false,enabled:false,scope:'panel',message:'Use Copy and Paste buttons in this host.'};
  window.__adobe_cep__.registerKeyEventsInterest(JSON.stringify(keys));
  return {ok:true,enabled:false,scope:'panel',message:'Panel focus only; AE and Explorer shortcuts stay unchanged.'};
 }
 window.addEventListener('beforeunload',()=>{shortcutGeneration++;shortcutEnabled=false;shortcutWatcher?.stop();if(host==='aftereffects')copyPasteKeys(false);});
 function evalHost(code){return new Promise((resolve,reject)=>window.__adobe_cep__.evalScript(code,raw=>{try{const answer=JSON.parse(raw);if(answer.error)reject(Object.assign(Error(answer.error),{code:answer.code,details:answer.details}));else resolve(answer);}catch(e){reject(Error('The editor could not finish this operation. '+String(raw).slice(0,160)));}}));}
 window.addEventListener('message',async event=>{
  const message=event.data;
  if(event.source!==frame.contentWindow||event.origin!==origin||message?.type!=='storylens-host-request'||message.nonce!==nonce||(!calls[message.action]&&!(host==='aftereffects'&&['clipboardWatch','copyPasteKeys','explorerSelection','shortcutWatch'].includes(message.action))))return;
  try{
   let payload=message.payload||{};
   if(['clipboardWatch','copyPasteKeys','explorerSelection','shortcutWatch'].includes(message.action)){
    let result;
    if(message.action==='clipboardWatch')result={ok:true,enabled:false,message:'Native Ctrl+C/V are unchanged.'};
    else if(message.action==='shortcutWatch')result=await shortcutWatch(payload.enabled===true);
    else if(message.action==='copyPasteKeys')result=copyPasteKeys(payload.enabled===true);
    else{const path=require('path'),modulePath=path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','explorer-selection.cjs');delete require.cache[require.resolve(modulePath)];const reader=require(modulePath);result=await reader.readExplorerSelection(window.HINGLISH_APP_ROOT,undefined,payload.window_handle||0);}
    frame.contentWindow.postMessage({type:'storylens-host-response',nonce,id:message.id,result},origin);return;
   }
   if(message.action==='context'){
    if(!window.HINGLISH_APP_ROOT)throw Error('Reinstall the Storylens panel with the local runtime location.');
    const fs=require('fs'),path=require('path'),folder=path.join(window.HINGLISH_APP_ROOT,'cache','editor-panel','exports');fs.mkdirSync(folder,{recursive:true});
    const requested=payload;
    payload={output_path:path.join(folder,'timeline-'+Date.now()+'.xml')};
    if(requested.appearance_cache===true){
     if(!/^[a-f0-9]{32}$/.test(requested.capture_id||''))throw Error('Use a new saved handoff revision for the appearance cache.');
     payload.appearance_cache_path=path.join(folder,'appearance-'+requested.capture_id+'.mp4');
     payload.appearance_preset=path.join(process.env.ProgramFiles||'C:/Program Files','Adobe','Adobe Premiere Pro 2026','MediaIO','systempresets','4E49434B_48323634','00 - Match Source - High bitrate.epr');
    }
   }
   if(message.action==='imageDownload'){
    const fs=require('fs'),path=require('path'),crypto=require('crypto'),base=fs.realpathSync(path.join(window.HINGLISH_APP_ROOT,'output','image-downloads','Downloads')),file=fs.realpathSync(payload.path),relative=path.relative(base,file);
    if(!relative||relative.startsWith('..')||path.isAbsolute(relative)||!fs.statSync(file).isFile()||fs.statSync(file).size>100*1024*1024||crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')!==payload.sha256)throw Error('The saved image changed. Download it again before importing.');
   }
   if(host==='aftereffects'&&message.action==='copyPaste'&&payload.action==='pasteFiles'){
    const path=require('path'),helper=require(path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','subject-framing.cjs'));
    if(!payload.paths||payload.paths.length!==1)throw Error('Copy one local picture or video.');
    payload={...payload,framing:await helper.analyzeMedia(window.HINGLISH_APP_ROOT,payload.paths[0])};
   }
   let nativeCode=calls[message.action]+'('+JSON.stringify(payload)+')';
   if(host==='premiere'&&message.action==='import'&&payload.type==='reel_recreate'){
    const path=require('path'),helper=require(path.join(window.HINGLISH_APP_ROOT,'editor_plugins/premiere-reel-recreate/bridge.cjs'));
    const prepared=await helper.prepare(window.HINGLISH_APP_ROOT,payload);
    nativeCode='(function(){try{$.evalFile(new File('+JSON.stringify(path.join(window.HINGLISH_APP_ROOT,'editor_plugins/premiere-reel-recreate/reel-recreate.jsx'))+'));return StorylensPremiereReel.build('+JSON.stringify(prepared)+');}catch(e){return storylensPanelJSON({error:String(e)});}})()';
   }
   if(message.action==='import'&&payload.type==='timed_choice'){
    if(!window.HINGLISH_APP_ROOT)throw Error('Reopen the Storylens panel to connect its local runtime.');
    const path=require('path'),modulePath=path.join(window.HINGLISH_APP_ROOT,'editor_plugins/shared/timed-choice-client.cjs');
    delete require.cache[require.resolve(modulePath)];
    nativeCode=require(modulePath).nativeCode(window.HINGLISH_APP_ROOT,host,payload);
   }
   // AE can retain the original ScriptPath globals after the panel is reopened.
   // Load only the Aliner functions/models; do not reset import or Copy Paste state.
   if(host==='aftereffects'&&(['templateText','templateAlign','copyPaste','templateImport','imageDownload'].includes(message.action)||message.action==='import'&&payload.type==='photos')){
    if(!window.HINGLISH_APP_ROOT)throw Error('Reinstall Storylens with its local runtime location.');
    const path=require('path'),root=window.HINGLISH_APP_ROOT;
    const runtimeError=message.action==='templateText'?{error:'Template Text could not load. Reopen Storylens and retry; your project is unchanged.',code:'template_text_native'}:message.action==='imageDownload'?{error:'The image is saved. Reopen Storylens, then add it to Downloads.',code:'image_download_native'}:message.action==='templateImport'?{error:'Import Template could not load its current files. Reopen Storylens and try again.',code:'template_import_native'}:message.action==='import'?{error:'The photo is saved, but its editor folder could not be updated. Reopen Storylens and press that photo again.',code:'photo_import_native'}:message.action==='copyPaste'?{error:'Copy Paste could not load its current files. Reopen Storylens and try again.',code:'copy_paste_native'}:{error:'Template Aliner could not load its current files. Reopen Storylens and try again.',code:'template_aliner'};
    const files=message.action==='templateText'?['editor_plugins/template-text/model.js','editor_plugins/template-text/host.jsx']:message.action==='imageDownload'?['editor_plugins/shared/image-download-import.jsx']:message.action==='templateImport'?['editor_plugins/shared/template-import-model.js','editor_plugins/shared/aftereffects-template-import.jsx']:message.action==='import'?['editor_plugins/shared/photo-import.jsx']:message.action==='copyPaste'?['editor_plugins/copy-paste/model.js','editor_plugins/copy-paste/framing.jsx','editor_plugins/copy-paste/host.jsx']:['editor_plugins/template-assembler/model.js','editor_plugins/shared/template-aliner-model.js','editor_plugins/shared/aftereffects-template-aliner.jsx'];
    nativeCode='(function(){try{'+files.map(file=>'$.evalFile(new File('+JSON.stringify(path.join(root,...file.split('/')))+'));').join('')+'return '+nativeCode+';}catch(e){var problem='+JSON.stringify(runtimeError)+';problem.details=String(e);return hJSON(problem);}})()';
   }
   if(message.action==='downloadImport'){
    if(!/^[a-f0-9]{32}$/.test(payload.id||'')||!['video','audio'].includes(payload.kind))throw Error('Choose a saved download output.');
    const fs=require('fs'),path=require('path'),base=fs.realpathSync(path.join(window.HINGLISH_APP_ROOT,'output','downloads',payload.id)),file=fs.realpathSync(payload.path),relative=path.relative(base,file);
    if(payload.host!==host||!relative||relative.startsWith('..')||path.isAbsolute(relative)||fs.statSync(file).size!==payload.bytes)throw Error('The downloaded media changed or belongs to another editor. Select its output again.');
    const script=path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','download-import.jsx'),serializer=host==='aftereffects'?'hJSON':'storylensPanelJSON';
    nativeCode='(function(){try{$.evalFile(new File('+JSON.stringify(script)+'));return '+nativeCode+';}catch(e){return '+serializer+'({error:"The download is saved. Select Video or Audio to retry adding it.",code:"download_delivery",details:String(e)});}})()';
   }
   let result=await evalHost(nativeCode);
   if(host==='aftereffects'&&message.action==='copyPaste'&&['copy','copyFile'].includes(payload.action)&&result.copied&&result.clipboard){
    const path=require('path'),helper=require(path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','subject-framing.cjs'));
    const framing=await helper.analyzeMedia(window.HINGLISH_APP_ROOT,result.clipboard.file);
    result=await evalHost('storylensPanelCopyPaste('+JSON.stringify({action:'rememberFraming',clipboard:{id:result.clipboard.id,file:result.clipboard.file},framing})+')');
   }
   if(host==='aftereffects'&&(['templateAlign','templateCollapseFolders','imageDownload','downloadImport'].includes(message.action)||message.action==='templateText'&&payload.action==='apply'||message.action==='templateImport'&&!result.running&&result.imported>0&&['complete','stopped','needs_attention'].includes(result.state))&&result.ok){
    try{const path=require('path'),cleanupFile=path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','project-folder-cleanup.cjs');
     if(message.action==='templateText')delete require.cache[require.resolve(cleanupFile)];
     const cleanup=require(cleanupFile);
     if(message.action==='templateImport'){
      const key=String(result.project_id)+'|'+String(result.batch_id);
      if(!importFolderCleanups.has(key))importFolderCleanups.set(key,cleanup.finishFolderCleanup(host,message.action,payload,{...result},projectId=>cleanup.runFolderCleanup(window.HINGLISH_APP_ROOT,projectId)).then(answer=>{if(!answer.ui_cleanup?.ok)importFolderCleanups.delete(key);return answer;}));
      result.ui_cleanup=(await importFolderCleanups.get(key)).ui_cleanup;
     }else await cleanup.finishFolderCleanup(host,message.action,payload,result,projectId=>cleanup.runFolderCleanup(window.HINGLISH_APP_ROOT,projectId));
    }catch(e){result.ui_cleanup={ok:false,message:'Folder cleanup could not finish. Your timeline is kept; try Collapse folders.',details:String(e.message||e)};}
   }
   frame.contentWindow.postMessage({type:'storylens-host-response',nonce,id:message.id,result},origin);
  }catch(error){
   if(host==='aftereffects'&&message.action==='templateAlign')try{const fs=require('fs'),path=require('path'),folder=path.join(window.HINGLISH_APP_ROOT,'cache','editor-panel');fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,'template-aliner-last-error.json'),JSON.stringify({time:new Date().toISOString(),error:error.message,code:error.code,details:error.details},null,2));}catch(_){}
   frame.contentWindow.postMessage({type:'storylens-host-response',nonce,id:message.id,error:error.message,code:error.code,details:error.details},origin);
  }
 });
 async function connect(){
  try{const r=await fetch(bridge+'/api/health');if(!r.ok)throw Error();status.hidden=true;document.getElementById('reconnect').hidden=true;frame.hidden=false;frame.src=bridge+'/editor-panel.html?host='+host+'&nonce='+encodeURIComponent(nonce)+'&reel_job='+encodeURIComponent(window.HINGLISH_REEL_JOB||'');}
  catch(_){status.hidden=false;document.getElementById('reconnect').hidden=false;status.textContent='Start Storylens locally, then press Reconnect. The editor panel uses the same local engine.';}
 }
 document.getElementById('reconnect').onclick=connect;connect();
})();


