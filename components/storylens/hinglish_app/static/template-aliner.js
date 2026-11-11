/* Small AE-only native action; never submits footage to an editing worker. */
(()=>{
 window.storylensTemplateAliner=function(options){
  const $=id=>document.getElementById(id),section=$('templateAlinerSection'),button=$('templateAliner'),box=$('templateAlinerChoices'),reset=$('templateAlinerReset'),status=$('templateAlinerStatus');
  section.hidden=options.host!=='aftereffects';if($('templateAlinerSettings'))$('templateAlinerSettings').hidden=section.hidden;if(section.hidden)return;
  let running=false;
  const fontButton=$('templateFontCheck'),fontDetails=$('templateFontDetails'),fontList=$('templateFontList'),fontStatus=$('templateFontStatus');
  const collapse=$('templateCollapseFolders'),collapseNow=$('templateCollapseNow'),folderStatus=$('templateFolderStatus'),folderDetails=$('templateFolderDetails'),folderTechnical=$('templateFolderTechnical');
  try{collapse.checked=localStorage.getItem('storylens.templateAliner.collapseFolders')!=='false';}catch(_){collapse.checked=true;}
  collapse.onchange=()=>{try{localStorage.setItem('storylens.templateAliner.collapseFolders',String(collapse.checked));}catch(_){}};
  function showCleanup(result){
   if(!result)return;
   folderStatus.textContent=result.message||'Folder cleanup needs attention. Your timeline is kept.';
   if(folderDetails){folderDetails.hidden=!result.details;folderTechnical.textContent=result.details||'';}
  }
  collapseNow.onclick=async()=>{
   if(running||options.isBusy?.())return;
   running=true;collapseNow.disabled=true;button.disabled=true;folderStatus.textContent='Closing Project folders…';
   try{const result=await options.native('templateCollapseFolders',{});if(result.error)throw Error(result.error);showCleanup(result.ui_cleanup);}
   catch(error){showCleanup({ok:false,message:'Folder cleanup could not finish. Your timeline is kept; try Collapse folders.',details:String(error.message||error)});}
   finally{running=false;collapseNow.disabled=false;button.disabled=false;}
  };
  function showFonts(report){
   if(!report)return;
   fontList.replaceChildren();fontDetails.hidden=false;
   if(!report.checked){fontStatus.textContent=report.notice||'Font check unavailable. Review the template text in After Effects.';return;}
   fontStatus.textContent=report.missing.length?report.missing.length+' missing font'+(report.missing.length===1?'':'s')+' · After Effects uses temporary substitutes. Appearance may differ. Original font choices are kept.':'All used fonts are available in After Effects.';
   for(const font of report.missing){const item=document.createElement('li');item.textContent=font.name+' · '+font.occurrences+' text use'+(font.occurrences===1?'':'s');fontList.append(item);}
  }
  fontButton.onclick=async()=>{if(running)return;options.clearError();fontButton.disabled=true;try{const result=await options.native('templateFonts',{});if(result.error)throw Error(result.error);showFonts(result.font_report);}catch(error){options.showError(error);}finally{fontButton.disabled=false;}};
  const time=value=>{const seconds=Math.max(0,Math.floor(Number(value)||0));return Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')};
  button.onclick=async()=>{
   if(running)return;
   options.clearError();
   try{
    if(options.isBusy?.())throw Error('Wait for the current editing operation to finish before aligning templates.');
    running=true;button.disabled=true;status.textContent='Creating a fresh template arrangement…';
    const result=await options.native('templateAlign',{collapse_folders:collapse.checked});
    if(result.error)throw Object.assign(Error(result.error),{code:result.code,details:result.details});
    if(result.needs_choices)throw Error('Reload the Storylens panel to use automatic composition selection.');
    if(!result.ok)throw Error('After Effects did not confirm the template alignment. Check the timeline before retrying.');
    showFonts(result.font_report);folderStatus.textContent='';showCleanup(result.ui_cleanup);status.textContent=(result.refreshed?'Fresh arrangement · ':'')+result.placements.length+(result.templates_found?' / '+result.templates_found:'')+' template'+(result.placements.length===1?'':'s')+' · '+time(result.covered_duration)+' covered'+(result.uncovered_duration>0?' · '+time(result.uncovered_duration)+' uncovered':'')+(result.variety_available===false?' · One template available; add more for variety.':'')+'. Undo: Edit > Undo Template Aliner.';
   }catch(error){options.showError(error);status.textContent=window.storylensProblem?window.storylensProblem(error).message:(error.message||'Alignment could not finish. Check the message below.');status.scrollIntoView?.({block:'nearest'});}
   finally{running=false;button.disabled=false;}
  };
  return {isRunning:()=>running};
 };
})();
