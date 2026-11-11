/* Category adapter over the selective transaction engine. Never open/save/reduce a project. */
if(typeof SLPreset==='undefined')SLPreset={};
SLPreset.pack = function (pack) {
    if (!pack) throw Error('Refresh and choose a local preset project.');
    var basePath = 'd:/editing/cinematics ae templates/';
    var categoryFolder = String(pack.category_folder || '');
    var filePath = String(pack.path || '');
    var backslash = String.fromCharCode(92);
    if (!categoryFolder) throw Error('Refresh and choose a local preset project.');
    if (categoryFolder.indexOf('/') >= 0) throw Error('Refresh and choose a local preset project.');
    if (categoryFolder.indexOf(backslash) >= 0) throw Error('Refresh and choose a local preset project.');
    if (categoryFolder.charAt(0) === '.') throw Error('Refresh and choose a local preset project.');
    filePath = filePath.split(backslash).join('/');
    var expectedPrefix = basePath + categoryFolder.toLowerCase() + '/';
    if(pack.category_name==='Documentary Templates'&&categoryFolder==='LatestUniqueTemplete')expectedPrefix='d:/editing/ae documentry style editing templates/latestuniquetemplete/';
    if (filePath.toLowerCase().indexOf(expectedPrefix) !== 0) throw Error('Refresh and choose a local preset project.');
    var parts = filePath.split('/');
    for (var pi = 0; pi < parts.length; pi++) {
        if (parts[pi] === '..') throw Error('Refresh and choose a local preset project.');
    }
    var extension = filePath.slice(filePath.lastIndexOf('.')).toLowerCase();
    var supported = false;
    if (extension === '.aep') supported = true;
    if (extension === '.aepx') supported = true;
    if (extension === '.aet') supported = true;
    if (!supported) throw Error('Refresh and choose a local preset project.');
    var projectFile = new File(filePath);
    if (!projectFile.exists) throw Error('Connect drive A and restore this preset project before retrying.');
    return projectFile;
};
SLPreset.folder=function(name){for(var i=1;i<=app.project.numItems;i++){var f=app.project.item(i);if(f instanceof FolderItem&&f.parentFolder===app.project.rootFolder&&f.name===name)return f;}f=app.project.items.addFolder(name);f.comment='Storylens Preset category';return f;};
SLPreset.groupFolder=function(pack,category){if(pack.category_name!=='Documentary Templates')return category;var names={documentary:'Documentary Edit',slideshows:'Slideshows',openers:'Openers'},name=names[pack.group_id];if(!name)throw Error('Refresh and choose a documentary section.');var marker='Storylens Preset group:'+pack.group_id;for(var i=1;i<=app.project.numItems;i++){var folder=app.project.item(i);if(folder instanceof FolderItem&&folder.parentFolder===category&&folder.comment===marker)return folder;}folder=app.project.items.addFolder(name);folder.parentFolder=category;folder.comment=marker;return folder;};
SLPreset.packFolder=function(pack){var category=SLPreset.groupFolder(pack,SLPreset.folder(pack.category_name||'Text')),marker='Storylens Preset pack:'+String(pack.id),folder=null;for(var i=1;i<=app.project.numItems;i++){var f=app.project.item(i);if(f instanceof FolderItem&&f.parentFolder===category&&String(f.comment||'')===marker){folder=f;break;}}if(!folder){folder=app.project.items.addFolder(pack.name||'Presets');folder.parentFolder=category;folder.comment=marker;}for(i=1;i<=app.project.numItems;i++){var oldFolder=app.project.item(i);if(!(oldFolder instanceof FolderItem)||oldFolder===folder||oldFolder.parentFolder!==app.project.rootFolder)continue;if(String(oldFolder.comment||'')==='Storylens Text temporary source'&&oldFolder.name==='Text preview source - '+pack.name){oldFolder.parentFolder=folder;oldFolder.name='Retained source assets';}}
return folder;};
SLPreset.rows=function(scope,profile,name){var out=[];for(var i=1;i<=app.project.numItems;i++){var c=app.project.item(i);if(!(c instanceof CompItem)||!SLCinematic.under(c,scope))continue;var used=0,users=c.usedIn||[];for(var j=0;j<users.length;j++)if(SLCinematic.under(users[j],scope))used++;var parts=SLCinematicSelection.locator(c,scope);parts.pop();if(parts.length)parts.shift();out.push({id:String(c.id),name:c.name,folder:parts.join('/'),text:profile==='documentaryCover'?false:SLCinematic.text(c,{}),usedBy:used,duration:c.duration,width:c.width,height:c.height});}return SLPresetModel.select(out,profile,name);};
SLPreset.annotate=function(data){var names={},i;for(i=0;i<(data.scenes||[]).length;i++){var r=data.scenes[i];names[r.name]=(names[r.name]||0)+1;}
 for(i=0;i<(data.scenes||[]).length;i++){r=data.scenes[i];r.full_name=r.name;r.group=(r.locator||[]).slice(1,-1).join(' / ');r.display_name=r.name.replace(/^Cinematic Lower Third /i,'Lower Third ').replace(/^Text Swap Transitions /i,'Text Swap ').replace(/^Comp (\d+) \/ Placeholder \d+$/i,'Scene $1').replace(/^Carousel /i,'');if(names[r.name]>1){var aspect='Wide';if(/vertical/i.test(r.group))aspect='Vertical';else if(/square/i.test(r.group))aspect='Square';else if(/horizontal/i.test(r.group))aspect='Wide';else if(r.width===r.height)aspect='Square';else if(r.width<r.height)aspect='Vertical';r.display_name+=' - '+aspect+(r.ordinal?' '+(r.ordinal+1):'');}}
 return data;
};
SLPreset.initializePaste=function(value,result){if(result.reused)return result;try{var target=SLCinematic.item(result.target_id),root=SLCinematic.item(result.composition_id),layer=null;for(var i=1;i<=target.numLayers;i++)if(String(target.layer(i).id)===result.layer_id)layer=target.layer(i);var state=SLCinematic.meta(root,SLCinematic.instancePrefix);state.category_name=value.pack.category_name;state.group_id=value.pack.group_id;state.group_name=value.pack.group_name;state.pack_name=value.pack.name;state.pack_id=value.pack.id;SLCinematic.setMeta(root,SLCinematic.instancePrefix,state);var scan=null;try{scan=SLCopyPasteModel.scan(SLCopyPaste.graph(root),root.id);}catch(e){result.holder_warning='This design needs a specific footage-holder mapping. Use its native holders until mapped.';result.holder_details=String(e);}
 root.comment=String(root.comment||'')+'\n[Storylens Copy Paste isolation v2]';if(scan){layer.comment=SLCopyPasteModel.writeState(layer.comment,{owner:layer.id,root:root.id,next:0,signature:scan.signature});result.slots=scan.slots.length;}else result.slots=0;SLCopyPaste.rememberTarget({comp:target,layer:layer,root:root});return result;}catch(pasteError){result.holder_warning='Preset added. Select its layer and use Paste to choose a footage holder.';result.holder_details=String(pasteError);return result;}
};
SLPreset.isSequence=function(pack){return pack.category_name==='MatchCut'||pack.category_name==='Speed Ramp';};
SLPreset.sequencePages=function(scope,pack,target){
 var rows=SLPreset.rows(scope,pack.profile||'generic'),pages=[],i;
 if(!rows.length)throw Error('No sequence scenes were found. Check this preset project.');
 // MatchCut contains alternate aspect versions, not thirty consecutive pages.
 // Choose one complete version by the destination's display aspect ratio.
 var chosen=null,best=1e20,ratio=target.width*(target.pixelAspect||1)/target.height;
 for(i=0;i<rows.length;i++){var c=SLCinematic.item(rows[i].id);if(!(c.duration>0))throw Error('Check this sequence: one scene has no duration.');var distance=Math.abs(Math.log((c.width*(c.pixelAspect||1)/c.height)/ratio));if(distance<best){best=distance;chosen=c;}}
 for(i=0;i<rows.length;i++){c=SLCinematic.item(rows[i].id);if(pack.profile!=='matchReveal'||c.parentFolder===chosen.parentFolder)pages.push(c);}
 return pages;
};
SLPreset.sequenceMaster=function(scope,pages){
 var candidates=[];
 for(var i=1;i<=app.project.numItems;i++){var c=app.project.item(i);if(!(c instanceof CompItem)||!SLCinematic.under(c,scope)||!(c.duration>0))continue;
  var seen={},pending=[c],count=0;while(pending.length){var node=pending.pop();if(seen[node.id])continue;seen[node.id]=true;for(var j=0;j<pages.length;j++)if(node===pages[j])count++;for(j=1;j<=node.numLayers;j++)if(node.layer(j).source instanceof CompItem)pending.push(node.layer(j).source);}
  if(count===pages.length&&pages.length>1)candidates.push(c);
 }
 candidates.sort(function(a,b){var preferredA=/final|master|render/i.test(a.name)?0:1,preferredB=/final|master|render/i.test(b.name)?0:1;return preferredA-preferredB||a.duration-b.duration||a.id-b.id;});return candidates.length?candidates[0]:null;
};
SLPreset.insertSequence=function(value){
 if(!SLPreset.isSequence(value.pack))throw Error('Choose an individual design from this section.');
 if(String(storylensProjectId())!==value.project_id)throw Error('The project changed. Choose your timeline and sequence again.');
 var prior=SLCinematicSelection.receipt(value.request_id);if(prior){var priorRoot=SLCinematic.item(prior.composition_id),priorState=SLCinematic.meta(priorRoot,SLCinematic.instancePrefix)||{};prior.sequence=true;prior.scene_count=priorState.scene_count;prior.sequence_source=priorState.sequence_source;prior.duration=priorRoot.duration;return prior;}
 var target=SLCinematic.item(value.composition_id);if(!(target instanceof CompItem)||!isFinite(value.time)||value.time<0||value.time>=target.duration)throw Error('Move the playhead inside your video timeline.');
 var clone=null,placed=null,oldDuration=target.duration,existingFolders={};for(var fi=1;fi<=app.project.numItems;fi++){var priorItem=app.project.item(fi);if(priorItem instanceof FolderItem)existingFolders[priorItem.id]=true;}
 try{return SLCinematicSelection.withSource(value.pack,function(scope,items,keep){
  try{
   var pages=SLPreset.sequencePages(scope,value.pack,target),source=SLPreset.sequenceMaster(scope,pages),authored=!!source,temporary=null,i;
   if(!source){
    var first=pages[0],duration=0,fps=first.frameRate;
    for(i=0;i<pages.length;i++)duration+=Math.ceil(pages[i].duration*fps-0.00001)/fps;
    if(duration>10800)throw Error('This sequence exceeds After Effects duration limits. Choose a smaller source pack.');
    source=app.project.items.addComp(value.pack.name+' - Complete sequence',first.width,first.height,first.pixelAspect||1,duration,fps);source.parentFolder=scope;items.push(source);temporary=source;
    var cursor=0;for(i=0;i<pages.length;i++){var page=pages[i],part=source.layers.add(page);part.startTime=cursor;part.inPoint=cursor;part.outPoint=cursor+page.duration;cursor+=Math.ceil(page.duration*fps-0.00001)/fps;}
   }
   SLCinematicSelection.validateAssets(source);
   clone=SLCinematic.clone(source,scope,value.request_id);var root=clone.root,backgrounds=SLCinematic.backgroundRows(root);
   root.comment=SLCinematic.instancePrefix+JSON.stringify({request_id:value.request_id,pack_id:value.pack.id,backgrounds:backgrounds,background_off:false,sequence:true,scene_count:pages.length,sequence_source:authored?'authored':'assembled'});
   if(value.background_off)SLCinematic.background(root,true);
   // Keep the full native project, folder hierarchy and alternate versions.
   // The placed graph is private, so later inserts cannot edit earlier ones.
   var parents={};for(i=0;i<items.length;i++)parents[items[i].id]=items[i].parentFolder;
   SLCinematicSelection.retainFootage(clone,items,keep);
   for(i=0;i<items.length;i++)if(items[i]!==scope&&parents[items[i].id])items[i].parentFolder=parents[items[i].id];
   var end=value.time+source.duration;if(end>10800)throw Error('This sequence would exceed After Effects timeline limits. Move the playhead earlier.');
   if(end>target.duration)target.duration=end;
   placed=target.layers.add(root);placed.name=value.pack.name+' - Complete sequence';placed.startTime=value.time;placed.inPoint=value.time;placed.outPoint=end;
   var scale=Math.min(target.width*(target.pixelAspect||1)/(source.width*(source.pixelAspect||1)),target.height/source.height)*100;placed.property('ADBE Transform Group').property('ADBE Scale').setValue([scale,scale]);
   placed.comment=SLCinematic.instancePrefix+JSON.stringify({request_id:value.request_id});
   for(i=0;i<clone.created.length;i++)if(clone.created[i] instanceof CompItem)clone.created[i].comment=String(clone.created[i].comment||'')+'\n[Storylens Cinematic owner='+placed.id+']';
   for(i=1;i<=target.numLayers;i++)target.layer(i).selected=target.layer(i)===placed;
   scope.parentFolder=clone.folder;scope.name='Source project - '+value.pack.name;
   for(i=0;i<items.length;i++)if(items[i]!==temporary)keep[items[i].id]=true;
   return SLPreset.initializePaste(value,{ok:true,sequence:true,sequence_source:authored?'authored':'assembled',scene_count:pages.length,duration:source.duration,request_id:value.request_id,project_id:value.project_id,composition_id:String(root.id),target_id:String(target.id),layer_id:String(placed.id),start:value.time,end:end,background_off:value.background_off===true});
  }catch(e){for(var key in keep)if(keep.hasOwnProperty(key))delete keep[key];if(placed)try{placed.remove();}catch(_){}target.duration=oldDuration;if(clone)for(var ri=clone.created.length-1;ri>=0;ri--)try{clone.created[ri].remove();}catch(_){}throw e;}
 });}catch(sequenceError){for(var clean=app.project.numItems;clean>=1;clean--){var empty=app.project.item(clean);if(empty instanceof FolderItem&&!existingFolders[empty.id]&&empty.numItems===0&&(empty.comment==='Storylens Preset category'||empty.comment==='Storylens Preset pack:'+String(value.pack.id)))try{empty.remove();}catch(_){}}throw sequenceError;}
};
SLPreset.insertCore=function(value){if(SLPreset.isSequence(value.pack))return SLPreset.insertSequence(value);if(value.pack.category_name==='Text')return SLPreset.initializePaste(value,SLCinematicSelection.insert(value));if(String(storylensProjectId())!==value.project_id)throw Error('The project changed. Choose the intended timeline and design again.');var previous=SLCinematicSelection.receipt(value.request_id);if(previous)return previous;var target=SLCinematic.item(value.composition_id);if(!(target instanceof CompItem)||value.time<0||value.time>=target.duration)throw Error('Move the playhead inside your video timeline.');var clone=null,placed=null;
 return SLCinematicSelection.withSource(value.pack,function(scope,items,keep){try{var rows=SLCinematic.rows(scope),matches=[];for(var i=0;i<rows.length;i++){var c=SLCinematic.item(rows[i].id);if(JSON.stringify(SLCinematicSelection.locator(c,scope))===JSON.stringify(value.scene.locator))matches.push(c);}var source=matches[value.scene.ordinal||0];if(!source)throw Error('The design changed. Refresh its gallery before adding it.');SLCinematicSelection.validateAssets(source);var fonts=SLCinematic.fonts(source),missing=[];for(i=0;i<fonts.length;i++)if(fonts[i].missing)missing.push(fonts[i].name);clone=SLCinematic.clone(source,scope,value.request_id);var root=clone.root;root.comment=SLCinematic.instancePrefix+JSON.stringify({request_id:value.request_id,pack_id:value.pack.id,category_name:value.pack.category_name,backgrounds:SLCinematic.backgroundRows(root),background_off:false});if(value.background_off)SLCinematic.background(root,true);SLCinematicSelection.retainFootage(clone,items,keep);
  placed=target.layers.add(root);placed.name=value.pack.name+' - '+source.name;placed.startTime=value.time;placed.inPoint=value.time;placed.outPoint=Math.min(target.duration,value.time+source.duration);var scale=Math.min(target.width*(target.pixelAspect||1)/(source.width*(source.pixelAspect||1)),target.height/source.height)*100;placed.property('ADBE Transform Group').property('ADBE Scale').setValue([scale,scale]);placed.comment=SLCinematic.instancePrefix+JSON.stringify({request_id:value.request_id});for(i=0;i<clone.created.length;i++)if(clone.created[i] instanceof CompItem)clone.created[i].comment=String(clone.created[i].comment||'').replace(/\n\[Storylens Cinematic owner=\d+\]/g,'')+'\n[Storylens Cinematic owner='+placed.id+']';for(i=1;i<=target.numLayers;i++)target.layer(i).selected=target.layer(i)===placed;
  return SLPreset.initializePaste(value,{ok:true,request_id:value.request_id,project_id:value.project_id,composition_id:String(root.id),target_id:String(target.id),layer_id:String(placed.id),start:placed.inPoint,end:placed.outPoint,background_off:value.background_off===true,missing_fonts:missing});
 }catch(e){for(var key in keep)if(keep.hasOwnProperty(key))delete keep[key];if(placed)try{placed.remove();}catch(_){}if(clone)for(i=clone.created.length-1;i>=0;i--)try{clone.created[i].remove();}catch(_){}throw e;}});
};
SLPreset.destination=function(){var projectId=String(storylensProjectId()),current=null,error=null,last=SLPreset.lastDestination;try{current=SLCinematic.currentComp();}catch(e){error=e;}var imported=false,at=current;for(var n=0;at&&n<40;n++){var comment=String(at.comment||'');if(comment.indexOf(SLCinematic.instancePrefix)===0||comment.indexOf('Storylens Cinematic Private:')===0||comment.indexOf('Storylens Preset pack:')===0||comment==='Storylens Text temporary source')imported=true;at=at.parentFolder;}if((!current||imported)&&last&&last.project_id===projectId){var previous=SLCinematic.item(last.composition_id);if(previous instanceof CompItem)current=previous;}if(!(current instanceof CompItem)){if(error)throw error;throw Error('Open your video composition on the timeline before adding a preset.');}if(imported&&(!last||last.project_id!==projectId||String(current.id)!==last.composition_id))throw Error('Open your video composition on the timeline before adding another preset.');SLPreset.lastDestination={project_id:projectId,composition_id:String(current.id)};return {ok:true,project_id:projectId,composition_id:String(current.id),time:current.time};};
SLPreset.reveal=function(result){if(result&&result.ok)result.project_item_id=String(result.composition_id);return result;};
SLPreset.insert=function(value){return SLPreset.reveal(SLPreset.insertCore(value));};
SLPreset.background=function(value){if(String(storylensProjectId())!==value.project_id)throw Error('The project changed. Select the inserted preset again.');var receipt=value.receipt,target=SLCinematic.item(receipt.target_id),root=SLCinematic.item(receipt.composition_id),meta=root&&SLCinematic.meta(root,SLCinematic.instancePrefix),layer=null;if(target instanceof CompItem)for(var i=1;i<=target.numLayers;i++)if(String(target.layer(i).id)===receipt.layer_id)layer=target.layer(i);if(!meta||!layer||layer.source!==root||meta.request_id!==receipt.request_id)throw Error('This preset changed or was undone. Select its current layer before changing the background.');var graph={},pending=[root];while(pending.length){var node=pending.pop();if(graph[node.id])continue;graph[node.id]=true;for(var gi=1;gi<=node.numLayers;gi++)if(node.layer(gi).source instanceof CompItem)pending.push(node.layer(gi).source);}for(var bi=0;bi<meta.backgrounds.length;bi++)if(!graph[meta.backgrounds[bi].composition_id])throw Error('A background reference no longer belongs to this preset. Check its current composition before retrying.');var users=root.usedIn||[],count=0;for(i=0;i<users.length;i++)for(var j=1;j<=users[i].numLayers;j++)if(users[i].layer(j).source===root)count++;for(bi=0;bi<meta.backgrounds.length;bi++){var backgroundComp=SLCinematic.item(meta.backgrounds[bi].composition_id);if(backgroundComp===root)continue;var bgUsers=backgroundComp.usedIn||[];for(var bu=0;bu<bgUsers.length;bu++)if(!graph[bgUsers[bu].id])count=2;}var clone=null,oldRoot=root,oldName=layer.name,folderFunction=SLCinematic.textFolder,oldLocked=layer.locked;
 try{if(layer.locked)throw Error('Unlock the selected preset, then use Remove BG.');if(count>1){SLCinematic.textFolder=function(){return SLPreset.packFolder({id:meta.pack_id,name:meta.pack_name||'Presets',category_name:meta.category_name||'Text',group_id:meta.group_id,group_name:meta.group_name});};clone=SLCinematic.clone(root,root.parentFolder,'preset-bg-'+layer.id+'-'+new Date().getTime());var copied=JSON.parse(JSON.stringify(meta));for(i=0;i<copied.backgrounds.length;i++){var item=clone.copies[copied.backgrounds[i].composition_id];if(!item)throw Error('A background dependency changed. Check this preset before retrying.');copied.backgrounds[i].composition_id=String(item.id);}root=clone.root;SLCinematic.setMeta(root,SLCinematic.instancePrefix,copied);for(i=0;i<clone.created.length;i++)if(clone.created[i] instanceof CompItem)clone.created[i].comment=String(clone.created[i].comment||'').replace(/\n\[Storylens Cinematic owner=\d+\]/g,'')+'\n[Storylens Cinematic owner='+layer.id+']';layer.replaceSource(root,false);layer.name=oldName;}
 var changed=SLCinematic.background(root,value.background_off===true);return {ok:true,changed:changed,background_off:value.background_off===true,receipt:{request_id:receipt.request_id,project_id:value.project_id,composition_id:String(root.id),target_id:String(target.id),layer_id:String(layer.id)}};
 }catch(e){if(clone){try{layer.replaceSource(oldRoot,false);layer.name=oldName;layer.locked=oldLocked;}catch(_){}for(i=clone.created.length-1;i>=0;i--)try{clone.created[i].remove();}catch(_){}}throw e;}finally{SLCinematic.textFolder=folderFunction;}};
function storylensPanelPreset(value){var undo=false,original={pack:SLCinematicSelection.pack,rows:SLCinematic.rows,folder:SLCinematic.textFolder,write:SLCinematicSelection.write};
 try{if(value.action==='fontStatus')return hJSON({ok:true,fonts:SLCinematic.fontStatus(value.names)});if(value.action==='galleryIdle')return hJSON({ok:true});if(value.action==='destination')return hJSON(SLPreset.destination());
  var pack=value.pack||{},category=pack.category_name||'Text';SLCinematicSelection.pack=SLPreset.pack;SLCinematic.rows=function(scope){return SLPreset.rows(scope,pack.profile||'generic',pack.name);};SLCinematic.textFolder=function(){return SLPreset.packFolder(pack);};SLCinematicSelection.write=function(folder,data){return original.write(folder,SLPreset.annotate(data));};
  app.beginUndoGroup(value.action==='buildGallery'?'Presets - Prepare previews':'Presets - Selected design');undo=true;
  if(value.action==='buildGallery')return hJSON(SLCinematicSelection.gallery(value));if(value.action==='insertSequence')return hJSON(SLPreset.reveal(SLPreset.insertSequence(value)));if(value.action==='insertChoice')return hJSON(SLPreset.insert(value));if(value.action==='background')return hJSON(SLPreset.background(value));
  if(value.action==='selectedBackground'){var comp=SLCinematic.currentComp(),selected=comp.selectedLayers||[];if(selected.length!==1||!(selected[0].source instanceof CompItem))throw Error('Select one inserted preset layer, then use Remove BG.');var source=selected[0].source,state=SLCinematic.meta(source,SLCinematic.instancePrefix);if(!state)return hJSON(SLCinematic.selectedBackground(value));return hJSON(SLPreset.background({project_id:String(storylensProjectId()),receipt:{request_id:state.request_id,target_id:String(comp.id),composition_id:String(source.id),layer_id:String(selected[0].id)},background_off:value.background_off}));}
  throw Error('Choose a design from the preset gallery.');
 }catch(e){var message=String(e.message||e);if(!/(?:open|unlock|choose|select|restore|refresh|check|install|activate|move|retry|shared)/i.test(message))message='This preset could not finish. Check Technical details and retry the unfinished step.';return hJSON({error:message,code:'preset_library',details:String(e)+' at line '+e.line});}
 finally{SLCinematicSelection.pack=original.pack;SLCinematic.rows=original.rows;SLCinematic.textFolder=original.folder;SLCinematicSelection.write=original.write;if(undo)app.endUndoGroup();}
}
