/* One intentional Run. Native edits happen only after a successful bounded plan. */
(()=>{window.storylensTemplateText=function(options){
 const $=id=>document.getElementById(id),run=$('templateTextRun'),stop=$('templateTextStop'),status=$('templateTextStatus'),details=$('templateTextDetails'),technical=$('templateTextTechnical');
 let running=false,job=null,generation=0,narration='';
 window.addEventListener?.('storylens-native-waiting',event=>{if(running&&event.detail?.action==='templateText'&&event.detail.payload?.action==='apply')status.textContent='After Effects is still applying text. Keep this panel open; another run is blocked until it finishes.';});
 function diagnostics(value){technical.textContent=typeof value==='string'?value:JSON.stringify(value,null,2);details.hidden=!technical.textContent;details.open=false;}
 function sharedScript(){const field=$('sharedScript');if(!field.value.trim()){$('sharedSettings').open=true;field.focus();throw Error('Paste your final spoken script in Script & timeline first.');}return field.value.trim();}
 function failed(error){const issue=window.storylensProblem?.(error);status.textContent=issue?.message||error.message||'Template Text stopped. Check the current composition and retry.';diagnostics(error.details||issue?.details||String(error));}
 $('templateTextNarration').onclick=async()=>{if(running||options.isBusy())return;try{const answer=await options.native('templateText',{action:'pickAudio'});if(answer.path){narration=answer.path;$('templateTextNarrationName').textContent=answer.path.split(/[\\/]/).pop();}}catch(e){failed(e);}};
 $('templateTextUseTimeline').onclick=()=>{if(!running){narration='';$('templateTextNarrationName').textContent='Timeline audio';}};
 stop.onclick=async()=>{if(!running)return;generation++;stop.disabled=true;try{if(job)await options.api('/api/panel/template-text-stop',{id:job});status.textContent='Stopped. Your project is unchanged.';}catch(e){failed(e);}finally{running=false;run.disabled=false;stop.hidden=true;stop.disabled=false;}};
 run.onclick=async()=>{
  if(running||options.isBusy())return;let version;
  try{
   const script=sharedScript();const config=await options.api('/api/panel/config');if(!config.template_text)throw Error('Template Text is not activated yet. Reopen Storylens after its installation finishes.');if(running||options.isBusy())return;options.clearError();running=true;run.disabled=true;stop.hidden=false;stop.disabled=false;job=null;version=++generation;diagnostics('');status.textContent='Reading placed template text…';
   const scan=await options.native('templateText',{action:'scan'});if(version!==generation)return;
   if(!scan.ok)throw Object.assign(Error(scan.error||'Open the final video composition and retry.'),{details:scan.details});
   try{localStorage.setItem('storylens.templateText.script.'+scan.snapshot.project_id+'.'+scan.snapshot.composition_id,script);}catch(_){}
   let state=await options.api('/api/panel/template-text-start',{snapshot:scan.snapshot,script,narration_path:narration});if(version!==generation){await options.api('/api/panel/template-text-stop',{id:state.id});return;}job=state.id;stop.disabled=false;
   while(['queued','running'].includes(state.status)){
    if(version!==generation)return;status.textContent=state.stage;await new Promise(resolve=>setTimeout(resolve,900));state=await options.api('/api/panel/template-text-job?id='+encodeURIComponent(job));
   }
   if(version!==generation)return;
   if(state.status!=='ready')throw Object.assign(Error(state.error?.message||state.stage||'Text planning stopped.'),{details:state.error?.details});
   const plan=await options.api('/api/panel/template-text-plan?id='+encodeURIComponent(job));if(version!==generation)return;
   stop.hidden=true;status.textContent='Applying text to private template copies…';
   const receipt=await options.native('templateText',{action:'apply',plan});
   if(!receipt.ok)throw Object.assign(Error(receipt.error||'After Effects did not confirm the text update.'),{details:receipt.details});
   try{await options.api('/api/panel/template-text-receipt',{id:job,receipt});}catch(e){status.textContent='Text updated in After Effects; saving its confirmation needs attention.';diagnostics(e.details||e.message);return;}
   const kept=plan.skipped?.length||0;status.textContent=receipt.changed+' text slots updated · '+receipt.hidden+' filler layers hidden'+(kept?' · '+kept+' kept for review':'')+'.';
   const review=[...(plan.warnings||[]),...(receipt.warnings||[])];if(receipt.ui_cleanup?.ok===false){status.textContent+=' Folder cleanup needs attention.';review.push(receipt.ui_cleanup.message||'Use Collapse folders in Template Aliner Settings.');if(receipt.ui_cleanup.details)review.push(receipt.ui_cleanup.details);}if(kept)review.push(...plan.skipped.map(s=>s.id+': '+s.reason));if(review.length)diagnostics(review.join('\n'));
  }catch(e){failed(e);}finally{if(version===generation){running=false;run.disabled=false;stop.hidden=true;stop.disabled=false;}}
 };
 return {isRunning:()=>running};
};})();
