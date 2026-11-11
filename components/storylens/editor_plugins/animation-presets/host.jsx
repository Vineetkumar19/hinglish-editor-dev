/* Native FFX application. Selection, not the receiving layer, controls applyPreset. */
function storylensAnimationPresets(p){
 var comp,selected=[],made=null,started=false,oldTime=0,i;
 function reject(message){var error=Error(message);error.storylensExpected=true;throw error;}
 try{
  comp=app.project.activeItem;
  if(!(comp instanceof CompItem))reject('Open your video composition, then choose a preset.');
  if(p.action!=='adjustment'&&p.action!=='apply')reject('Choose a preset or Create adjustment layer.');
  oldTime=comp.time;selected=comp.selectedLayers.slice(0);
  var file=null;
  if(p.action==='apply'){
   var normalized=String(p.path||'').replace(/\\/g,'/'),parts=normalized.split('/');
   if(normalized.toLowerCase().indexOf('d:/editing/after effects presets/')!==0||!/\.ffx$/i.test(normalized))reject('Refresh and choose a preset from your library.');
   for(i=0;i<parts.length;i++)if(parts[i]==='..')reject('Refresh and choose a preset from your library.');
   file=new File(normalized);if(!file.exists)reject('This preset is missing. Refresh the library and choose it again.');
   if(p.target!=='selected'&&p.target!=='adjustment')reject('Choose Selected layer or New adjustment layer.');
   if(p.target==='selected'){
    if(!selected.length)reject('Select a layer on your timeline, or choose New adjustment layer.');
    for(i=0;i<selected.length;i++)if(selected[i].locked||!(selected[i] instanceof AVLayer))reject('Select unlocked video, text, shape or adjustment layers, then try again.');
   }
  }
  app.beginUndoGroup('Storylens Presets');started=true;
  if(p.action==='adjustment'||p.target==='adjustment'){
   made=comp.layers.addSolid([1,1,1],p.action==='apply'?'Adjustment - '+p.name:'Adjustment Layer',comp.width,comp.height,comp.pixelAspect,comp.duration);
   made.adjustmentLayer=true;made.startTime=0;made.inPoint=oldTime;made.outPoint=comp.duration;
   if(selected.length)made.moveBefore(selected[0]);
   for(i=1;i<=comp.numLayers;i++)comp.layer(i).selected=false;
   made.selected=true;
  }
  if(p.action==='apply'){
   // One call applies once to every selected target, retaining authored keys/expressions.
   comp.time=oldTime;(made||selected[0]).applyPreset(file);
  }
  if(!made){for(i=1;i<=comp.numLayers;i++)comp.layer(i).selected=false;for(i=0;i<selected.length;i++)selected[i].selected=true;}
  return JSON.stringify({ok:true,action:p.action,name:p.name||'',layers:made?1:selected.length,adjustment:!!made,time:oldTime,project_id:String(storylensProjectId())});
 }catch(e){
  // AE/plugin failures may have partially applied a preset. Never retry automatically.
  return JSON.stringify({error:started?'The preset step did not finish. Check the timeline before retrying; After Effects Undo can restore the previous state.':e.storylensExpected?String(e.message||e):'Presets could not read this timeline. Open your video composition and try again.',code:'animation_presets',details:String(e),partial:started});
 }finally{if(started&&comp instanceof CompItem){try{comp.time=oldTime;}catch(_){}if(!made)try{for(i=1;i<=comp.numLayers;i++)comp.layer(i).selected=false;for(i=0;i<selected.length;i++)selected[i].selected=true;}catch(_){}}if(started)app.endUndoGroup();}
}
