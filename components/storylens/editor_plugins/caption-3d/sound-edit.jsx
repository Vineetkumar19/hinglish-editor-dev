/* Selected audio edits stage only the title source, then retain the fitted outer layer. */
(function(global){
 function layerNamed(c,name){for(var i=1;i<=c.numLayers;i++)if(c.layer(i).name===name)return c.layer(i);return null;}
 function context(c,l){return {project_id:storylensProjectId(),comp_id:String(c.id),layer_id:String(l.id),source_id:String(l.source.id),time:c.time};}
 function selected(){
  var c=app.project&&app.project.activeItem;if(!(c instanceof CompItem)||c.selectedLayers.length!==1)throw Error('Select one outer 3D caption precomp in your timeline.');var l=c.selectedLayers[0];if(!(l.source instanceof CompItem))throw Error('Select the outer title precomp.');if(l.locked)throw Error('Unlock the selected title first.');
  if(/^3D[23] Surface Precomp$/.test(String(l.comment||'')))return global.StorylensSurfaceTitles.describe();
  var source=l.source,main=layerNamed(source,'EDIT - MAIN'),sub=layerNamed(source,'EDIT - SUBTITLE'),camera=layerNamed(source,'CAMERA - Near and far');if(!main||!sub||!camera)throw Error('Select a Storylens 3D1, 3D2 or 3D3 title precomp.');
  var tag=String(source.comment||'').match(/\[Storylens 3D1 (boost|look|clicks|standout)\]/),variant=tag?tag[1]:'';
  if(!variant){var name=String(source.name).toUpperCase();if(name.indexOf('BOOST')>=0)variant='boost';else if(name.indexOf('PROFESSIONAL')>=0)variant='look';else if(name.indexOf('CLICKS')>=0)variant='clicks';else if(name.indexOf('STAND OUT')>=0)variant='standout';else throw Error('The selected 3D1 title cannot be identified safely.');}
  var solid=String(source.comment||'').match(/\[Storylens solid 3d ([0-9.]+) [a-f0-9]*\]/),solidDepth=solid?Number(solid[1]):100;var a=main.property('ADBE Text Properties').property('ADBE Text Document').value,b=sub.property('ADBE Text Properties').property('ADBE Text Document').value,audio=global.StorylensCaptionSounds.state(source);
  return {ok:true,plan:{family:'3d1',variant:variant,text:a.text+'\n'+b.text,motion:'line-slide',depth:solidDepth,surface:'right',delay:.35,format:source.width>source.height?'horizontal':'vertical',sound_mode:audio?audio.mode:'pop_click',sound_fx:audio?audio.enabled:true},geometry:{pose:{pitch:0,turn:0,roll:0,seam:0}},context:context(c,l)};
 }
 function strip(c){for(var i=c.numLayers;i>=1;i--){var l=c.layer(i);if(/^SFX - /.test(l.name)&&l.source&&/^Storylens Caption SFX /.test(String(l.source.comment||'')))l.remove();}}
 function hasAudio(c){for(var i=1;i<=c.numLayers;i++){var l=c.layer(i);if(/^SFX - /.test(l.name)&&l.source&&/^Storylens Caption SFX /.test(String(l.source.comment||'')))return true;}return false;}
 function update(patch,request){
  var info=selected(),c=app.project.activeItem,l=c.selectedLayers[0],old=l.source,state=global.StorylensCaptionSounds.state(old);
  if(storylensProjectId()!==request.project_id||String(c.id)!==String(request.comp_id)||String(l.id)!==String(request.layer_id))throw Error('Select the same title in the same project, then retry.');
  if(state&&state.update===request.request_id)return {ok:true,reused:true,context:info.context};if(String(old.id)!==String(request.source_id))throw Error('The title changed. Use Edit selected again.');
  var name=old.name,root=old.parentFolder,made=[],extra=[],obsolete=[old],stage=null,committed=false;app.beginUndoGroup('Change caption sound');
  try{
   stage=old.duplicate();made.push(stage);stage.parentFolder=root;strip(stage);
   // Migrate only old generated sound layers inside a text surface, leaving its text and pose intact.
   for(var i=1;i<=stage.numLayers;i++){var plane=stage.layer(i);if(plane.source instanceof CompItem&&hasAudio(plane.source)){var original=plane.source,copy=original.duplicate();made.push(copy);obsolete.push(original);copy.parentFolder=original.parentFolder;strip(copy);plane.replaceSource(copy,false);}}
   var count=0;if(patch.sound_fx!==false)count=global.StorylensCaptionSounds.add(stage,0,global.StorylensCaptionSounds.events(patch.sound_mode,patch.delay),root,{items:extra,layers:[]});global.StorylensCaptionSounds.mark(stage,patch.sound_mode,patch.sound_fx!==false,request.request_id);
   l.replaceSource(stage,false);committed=true;var cleanup=[];for(var i=0;i<obsolete.length;i++)try{if(obsolete[i].usedIn.length===0)obsolete[i].remove();}catch(e){cleanup.push(String(e));}stage.name=name;
   return {ok:true,sound_updated:true,sounds:count,context:context(c,l),cleanup:cleanup};
  }catch(e){if(!committed){for(var i=made.length-1;i>=0;i--)try{made[i].remove();}catch(_){}for(var i=extra.length-1;i>=0;i--)try{if(extra[i].usedIn.length===0)extra[i].remove();}catch(_){}throw e;}return {ok:true,sound_updated:true,context:context(c,l),warning:'The sound changed, but an old unused source remains.'};}
  finally{app.endUndoGroup();}
 }
 global.StorylensCaptionAudioEdit={describe:selected,update:update};
})(typeof $!=='undefined'?$.global:this);
