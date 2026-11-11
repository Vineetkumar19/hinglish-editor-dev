/* Native Effects library; no rendering, model calls, project opening or saving. */
var SLEffects=typeof SLEffects==='undefined'?{}:SLEffects;
SLEffects.packPrefix='Storylens Effects Pack:';
SLEffects.instancePrefix='Storylens Effects Instance:';
SLEffects.fail=function(message){var e=new Error(message);e.userFacing=true;throw e;};
SLEffects.meta=function(item,prefix){try{var text=String(item.comment||'').split('\n')[0];return text.indexOf(prefix)===0?JSON.parse(text.slice(prefix.length)):null;}catch(_){return null;}};
SLEffects.item=function(id){return SLCopyPaste.item(id);};
SLEffects.under=function(item,folder){for(var p=item.parentFolder,n=0;p&&n<40;n++){if(p===folder)return true;if(p===app.project.rootFolder)return false;p=p.parentFolder;}return false;};
SLEffects.bin=function(pack){for(var i=1;i<=app.project.numItems;i++){var f=app.project.item(i),m=SLEffects.meta(f,SLEffects.packPrefix);if(f instanceof FolderItem&&m&&m.id===pack.id&&m.signature===pack.signature&&m.project_key===pack.project_key)return f;}return null;};
SLEffects.properties=function(group,fn,depth){if((depth||0)>40)SLEffects.fail('This effect has a property tree that is too deep. Choose a smaller scene.');for(var i=1;i<=group.numProperties;i++){var p=group.property(i);if(!p)continue;if(p.canSetExpression&&p.expression)fn(p);if(p.numProperties)SLEffects.properties(p,fn,(depth||0)+1);}};
SLEffects.assets=function(items,pack){for(var i=0;i<items.length;i++){var item=items[i];if(!(item instanceof FootageItem))continue;
 if(item.footageMissing){var missing=String(item.mainSource.missingFootagePath||''),base=missing.replace(/\\/g,'/').split('/').pop().toLowerCase(),matches=[];
  for(var j=0;j<(pack.media||[]).length;j++)if(String(pack.media[j]).replace(/\\/g,'/').split('/').pop().toLowerCase()===base)matches.push(pack.media[j]);
  if(matches.length===1)item.replace(new File(matches[0]));
  if(item.footageMissing)SLEffects.fail('A required effect asset is missing: '+item.name+'. Restore the template files, then refresh Effects.');
 }
 var proxy=item.proxySource;if(proxy&&(proxy.missingFootagePath||proxy.file&&!proxy.file.exists))SLEffects.fail('A required effect proxy is missing: '+item.name+'. Relink its proxy before retrying.');
}};
SLEffects.load=function(pack){var bin=SLEffects.bin(pack),items=[],i;if(bin){for(i=1;i<=app.project.numItems;i++)if(SLEffects.under(app.project.item(i),bin))items.push(app.project.item(i));SLEffects.assets(items,pack);return bin;}
 var source=String(pack.path||'').replace(/\\/g,'/');if(source.toLowerCase().indexOf('d:/editing/cinematics ae templates/effects templates/')!==0||/(?:^|\/)\.\.(?:\/|$)/.test(source)||!/\.(?:aep|aepx|aet)$/i.test(source))SLEffects.fail('Refresh Effects and choose a project from Effects templates.');
 var file=new File(pack.path);if(!file.exists)SLEffects.fail('The effect project is unavailable. Connect drive A and refresh Effects.');
 var before={},selection=app.project.selection||[];for(i=1;i<=app.project.numItems;i++)before[app.project.item(i).id]=true;
 try{
  app.project.importFile(new ImportOptions(file));
  for(i=1;i<=app.project.numItems;i++)if(!before[app.project.item(i).id])items.push(app.project.item(i));
  if(!items.length)SLEffects.fail('After Effects did not import this project. Check that the project opens correctly.');
  bin=app.project.items.addFolder('Effects - '+pack.name);
  for(i=0;i<items.length;i++)if(!items[i].parentFolder||items[i].parentFolder===app.project.rootFolder||before[items[i].parentFolder.id])items[i].parentFolder=bin;
  SLEffects.assets(items,pack);bin.comment=SLEffects.packPrefix+JSON.stringify({id:pack.id,signature:pack.signature,project_key:pack.project_key});return bin;
 }catch(e){
  // importFile can throw after creating items. Re-enumerate before rollback.
  var fresh=[];for(i=1;i<=app.project.numItems;i++)if(!before[app.project.item(i).id])fresh.push(app.project.item(i));
  var rollbackFailed=false;for(i=fresh.length-1;i>=0;i--)try{fresh[i].remove();}catch(_){try{if(SLEffects.item(fresh[i].id))rollbackFailed=true;}catch(ignored){}}
  if(rollbackFailed)SLEffects.fail('The effect import stopped and some imported items may remain. Review the Effects project folder or use native Undo before retrying.');throw e;
 }finally{var current=app.project.selection||[];for(i=0;i<current.length;i++)try{current[i].selected=false;}catch(_){}for(i=0;i<selection.length;i++)try{selection[i].selected=true;}catch(_){}}
};
SLEffects.outputs=function(bin){var rows=[];for(var i=1;i<=app.project.numItems;i++){var c=app.project.item(i);if(!(c instanceof CompItem)||!SLEffects.under(c,bin))continue;var used=0,users=c.usedIn||[];for(var j=0;j<users.length;j++)if(SLEffects.under(users[j],bin))used++;rows.push({id:String(c.id),name:c.name,duration:c.duration,width:c.width,height:c.height,used:used});}return SLEffectsModel.outputs(rows);};
SLEffects.clone=function(source,bin,owner,created){var names={},duplicates={},all=[],pending=[source],seen={},map={},i,j,k;
 for(i=1;i<=app.project.numItems;i++){var c=app.project.item(i);if(c instanceof CompItem&&SLEffects.under(c,bin)){if(names[c.name])duplicates[c.name]=true;else names[c.name]=c;}}
 function reference(prop){var refs=SLCopyPasteModel.referencedComps(prop.expression);if(refs.dynamic){for(var name in names)if(names.hasOwnProperty(name)){if(duplicates[name])SLEffects.fail('This effect has duplicate helper composition names. Give them unique names before adding it.');pending.push(names[name]);}}else for(var n=0;n<refs.names.length;n++){var key=refs.names[n];if(duplicates[key])SLEffects.fail('This effect has duplicate helper composition names. Give them unique names before adding it.');if(!names[key])SLEffects.fail('This effect refers to an unavailable composition: '+key+'. Restore the complete pack before retrying.');pending.push(names[key]);}}
 while(pending.length){c=pending.pop();if(seen[c.id])continue;seen[c.id]=true;all.push(c);if(all.length>500)SLEffects.fail('This effect uses more than 500 linked compositions. Choose a smaller effect.');for(j=1;j<=c.numLayers;j++){var l=c.layer(j);if(l.source instanceof CompItem)pending.push(l.source);SLEffects.properties(l,reference);}}
 var folder=app.project.items.addFolder(source.name+' - Effects '+owner);created.push(folder);
 for(i=0;i<all.length;i++){c=all[i];var copy=c.duplicate();created.push(copy);copy.name=c.name+' [Copy Paste '+owner+']';copy.parentFolder=folder;map[c.id]=copy;}
 var aliases={};for(i=0;i<all.length;i++)aliases[all[i].name]=map[all[i].id].name;
 for(i=0;i<all.length;i++){copy=map[all[i].id];for(j=1;j<=copy.numLayers;j++){l=copy.layer(j);var lock=l.locked,name=l.name;try{l.locked=false;if(l.source instanceof CompItem&&map[l.source.id]){l.replaceSource(map[l.source.id],false);l.name=name;}SLEffects.properties(l,function(p){var enabled=p.expressionEnabled,before=p.expression,after=SLCopyPasteModel.expression(before,aliases);if(after!==before){p.expression=after;p.expressionEnabled=enabled;if(enabled&&p.expressionError)SLEffects.fail('An effect expression could not be preserved. Check this template in After Effects before retrying.');}});}finally{l.locked=lock;}}}
 return map[source.id];
};
SLEffects.fonts=function(root){var seen={},pending=[root],names={},out=[];while(pending.length){var c=pending.pop();if(seen[c.id])continue;seen[c.id]=true;for(var i=1;i<=c.numLayers;i++){var l=c.layer(i),group=l.property('ADBE Text Properties');if(group){var text=group.property('ADBE Text Document'),docs=[text.value];for(var k=1;k<=text.numKeys;k++)docs.push(text.keyValue(k));for(k=0;k<docs.length;k++)if(docs[k].font)names[docs[k].font]=true;}if(l.source instanceof CompItem)pending.push(l.source);}}
 for(var name in names)if(names.hasOwnProperty(name)){var missing=true;try{var fonts=app.fonts.getFontsByPostScriptName(name);missing=!fonts.length||fonts[0].isSubstitute;}catch(_){}out.push({name:name,missing:missing});}return out;};
function storylensPanelEffects(value){var undo=false,target=null,inserted=null,created=[],oldSelected=[],wasRendering=null;
 try{
  SLCopyPaste.checkProject();if(typeof StorylensTemplateImportJob!=='undefined'&&StorylensTemplateImportJob&&StorylensTemplateImportJob.project===app.project&&StorylensTemplateImportJob.running)SLEffects.fail('Import Template is still running. Wait for it to finish before adding an effect.');
  if(!value||value.action!=='insert'||!/^[-a-zA-Z0-9_]{5,80}$/.test(value.request_id||''))SLEffects.fail('Choose an effect from the Effects library.');
  target=storylensCurrentComp();if(!(target instanceof CompItem))SLEffects.fail('Open your video composition, then choose an effect.');
  if(value.scene_id&&(String(value.project_id)!==String(storylensProjectId())||String(value.target_id)!==String(target.id)))SLEffects.fail('The project or timeline changed. Choose the effect again in the intended timeline.');
  for(var ci=1;ci<=app.project.numItems;ci++){var prior=app.project.item(ci);if(!(prior instanceof CompItem))continue;for(var i=1;i<=prior.numLayers;i++){var layer=prior.layer(i),meta=SLEffects.meta(layer,SLEffects.instancePrefix);if(meta&&meta.request_id===value.request_id){if(prior!==target)SLEffects.fail('This click already added the effect to '+prior.name+'. Return to that timeline to continue; no duplicate was added.');return hJSON({ok:true,reused:true,name:layer.name,slots:meta.slots,layer_id:String(layer.id),start:layer.inPoint});}}}
  if(!(target.time>=0&&target.time<target.duration))SLEffects.fail('Move the playhead inside your video timeline, then add the effect.');var time=target.time;
  if(SLEffects.meta(target,SLEffects.packPrefix)||SLEffects.meta(target,SLEffects.instancePrefix))SLEffects.fail('Open your video timeline first, then add the effect.');
  for(i=1;i<=app.project.numItems;i++){var possible=app.project.item(i);if(possible instanceof FolderItem&&SLEffects.meta(possible,SLEffects.packPrefix)&&SLEffects.under(target,possible))SLEffects.fail('Open your video timeline first, then add the effect.');}
  for(i=1;i<=target.numLayers;i++)if(target.layer(i).selected)oldSelected.push(target.layer(i));
  app.beginUndoGroup('Effects - Add template');undo=true;if(typeof app.disableRendering==='boolean'){wasRendering=app.disableRendering;app.disableRendering=true;}
  var bin=SLEffects.load(value.pack),outputs=SLEffects.outputs(bin),id=value.scene_id||outputs.selected,source=id&&SLEffects.item(id);
  if(!id){if(!outputs.choices.length)SLEffects.fail('No main effect composition was found. Check this pack in After Effects.');return hJSON({ok:true,needs_choice:true,choices:outputs.choices,project_id:String(storylensProjectId()),target_id:String(target.id)});}
  var allowed=false;for(i=0;i<outputs.choices.length;i++)if(outputs.choices[i].id===String(id))allowed=true;if(!allowed||!(source instanceof CompItem)||!SLEffects.under(source,bin))SLEffects.fail('The chosen effect composition changed. Refresh Effects and choose it again.');
  var fonts=SLEffects.fonts(source),missing=[];for(i=0;i<fonts.length;i++)if(fonts[i].missing)missing.push(fonts[i].name);if(missing.length)SLEffects.fail('Activate the template fonts, then reopen this pack: '+missing.join(', ')+'.');
  inserted=target.layers.add(source);var privateRoot=SLEffects.clone(source,bin,inserted.id,created);inserted.replaceSource(privateRoot,false);inserted.name=value.pack.name;inserted.startTime=time;inserted.inPoint=time;inserted.outPoint=Math.min(target.duration,time+source.duration);
  var scale=Math.min(target.width*target.pixelAspect/(source.width*source.pixelAspect),target.height/source.height)*100;inserted.property('ADBE Transform Group').property('ADBE Scale').setValue([scale,scale]);
  var scan=SLCopyPasteModel.scan(SLCopyPaste.graph(privateRoot),privateRoot.id);privateRoot.comment=String(privateRoot.comment||'')+'\n[Storylens Copy Paste isolation v2]';
  var metadata={request_id:value.request_id,pack_id:value.pack.id,slots:scan.slots.length};inserted.comment=SLEffects.instancePrefix+JSON.stringify(metadata);inserted.comment=SLCopyPasteModel.writeState(inserted.comment,{owner:inserted.id,root:privateRoot.id,next:0,signature:scan.signature});
  for(i=1;i<=target.numLayers;i++)target.layer(i).selected=target.layer(i)===inserted;
  SLCopyPaste.rememberTarget({comp:target,layer:inserted,root:privateRoot});
  return hJSON({ok:true,name:value.pack.name,request_id:value.request_id,project_id:String(storylensProjectId()),target_id:String(target.id),layer_id:String(inserted.id),composition_id:String(privateRoot.id),slots:scan.slots.length,start:inserted.inPoint,end:inserted.outPoint,fonts:fonts,message:scan.slots.length?'Effect added. Copy your video and paste into the selected effect.':'Effect added. No standard video placeholder was detected; this pack needs a holder mapping.'});
 }catch(e){if(inserted)try{inserted.remove();}catch(_){}for(var n=created.length-1;n>=0;n--)try{created[n].remove();}catch(_){}for(n=0;n<oldSelected.length;n++)try{oldSelected[n].selected=true;}catch(_){}return hJSON({error:e.userFacing?String(e.message):'The effect could not be added. Check that its project and assets are available, then retry.',code:'effects_library',details:String(e)+' at line '+e.line});}
 finally{if(target)try{target.openInViewer();}catch(_){}if(wasRendering!==null)app.disableRendering=wasRendering;if(undo)app.endUndoGroup();}
}
