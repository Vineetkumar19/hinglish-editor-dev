/* One click starts a native batch. Polling only observes that same batch. */
(()=>{
 window.storylensTemplateImport=function(options){
  const $=id=>document.getElementById(id),button=$('templateImport'),stop=$('templateImportStop'),status=$('templateImportStatus');
  let running=false,requesting=false,cleanupRetries=0;
  function display(result){
   running=result.running===true;button.disabled=running;stop.hidden=!running;
   status.textContent=result.message||(running?`Importing ${Math.min(result.imported+1,result.total)} of ${result.total}…`:
    result.state==='stopped'?`Stopped · ${result.imported} imported.`:
    result.state==='project_changed'?'Import stopped because the project changed. Open the intended project before importing again.':
    result.state==='needs_attention'?`Import stopped · ${result.imported} imported. Check Technical details before retrying.`:
    `${result.imported} templates imported. Ready for Template Aliner.`);
   if(result.skipped)status.textContent+=` ${result.skipped} unreadable templates skipped.`;
   if(result.relinked_media)status.textContent+=` ${result.relinked_media} source files reconnected.`;
   if(result.missing_media)status.textContent+=` ${result.missing_media} source files could not be located. See Technical details.`;
   if(result.ui_cleanup?.message)status.textContent+=' '+result.ui_cleanup.message;
   let details=(result.results||[]).filter(r=>r.status!=='imported'||r.missing_media).map(r=>r.name+': '+((r.status==='skipped'?(r.partial_kept?'Skipped; earlier partial kept aside. ':'Skipped; partial import rolled back. '):'')+(r.details||`${r.missing_media} missing source files`)+(r.recovery_details?'\n'+r.recovery_details:''))+(r.missing_paths||[]).map(p=>'\n  '+(p.path||p.name)+' — '+p.reason).join('')).join('\n');
   if(result.progress_warning)details+='\n'+result.progress_warning;
   if(result.ui_cleanup?.details)details+='\nFolder cleanup: '+result.ui_cleanup.details;
   $('templateImportDetails').hidden=!details;$('templateImportTechnical').textContent=details;
  }
  async function poll(){try{const result=await options.native('templateImport',{action:'status'});if(result.error)throw Object.assign(Error(result.error),result);display(result);if(running)setTimeout(poll,1000);else if(result.ui_cleanup?.ok===false&&cleanupRetries++<2)setTimeout(poll,2000);}catch(e){running=false;requesting=false;button.disabled=false;stop.hidden=false;status.textContent='Import status is unavailable. Check After Effects before starting another batch.';options.showError(e);}}
  async function start(){if(requesting||running||options.isBusy?.())return;requesting=true;cleanupRetries=0;button.disabled=true;options.clearError();status.textContent='Scanning LatestTemplete…';try{const result=await options.native('templateImport',{action:'start'});if(result.error)throw Object.assign(Error(result.error),result);display(result);if(running)setTimeout(poll,1000);else if(result.ui_cleanup?.ok===false&&cleanupRetries++<2)setTimeout(poll,2000);}catch(e){status.textContent='Import needs attention. Check the message below, then try again.';options.showError(e);}finally{requesting=false;button.disabled=running;}}
  button.onclick=start;
  stop.onclick=async()=>{stop.disabled=true;try{await options.native('templateImport',{action:'stop'});status.textContent='Stopping after the current template…';}catch(e){options.showError(e);}finally{stop.disabled=false;}};
  // Resume observation after a panel reload; never start a second import here.
  if(options.observe!==false){requesting=true;button.disabled=true;
  options.native('templateImport',{action:'status'}).then(result=>{if(result.error)throw Object.assign(Error(result.error),result);if(result.state&&result.state!=='idle')display(result);if(running)setTimeout(poll,1000);else if(result.ui_cleanup?.ok===false&&cleanupRetries++<2)setTimeout(poll,2000);}).catch(options.showError).finally(()=>{requesting=false;button.disabled=running;});
  }
  return {start,isRunning:()=>running||requesting};
 };
})();
