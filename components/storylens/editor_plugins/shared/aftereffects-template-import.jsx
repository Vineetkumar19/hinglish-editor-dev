/* AE-only linked project imports. Never open, save or replace the owner project. */
// CEP evaluates this file inside each request function. A local var would hide
// the job from app.scheduleTask after that function returns.
if(typeof StorylensTemplateImportJob==='undefined')StorylensTemplateImportJob=null;
function storylensTemplateRepairMedia(item,projectPath,root,index){
 var result={relinked:0,missing:[]};
 function repair(proxy){
  var source=null,path='',needed=false;
  try{source=proxy?item.proxySource:item.mainSource;if(!source)return;
   if(proxy){needed=!!(source.missingFootagePath||source.file&&!source.file.exists);}
   else needed=!!(item.footageMissing||source.missingFootagePath||item.file&&!item.file.exists);
   if(!needed)return;
   path=String(source.missingFootagePath||(!proxy&&item.file?item.file.fsName:source.file?source.file.fsName:''));
   var name=path.replace(/\\/g,'/').split('/').pop().toLowerCase();try{name=decodeURI(name);}catch(_){}
   var choice=StorylensLibraryModel.mediaCandidate(path,index[name]||[],projectPath,root);
   if(!choice.path){result.missing.push({name:item.name,path:path,kind:proxy?'proxy':'source',reason:choice.reason});return;}
   var file=new File(choice.path);if(!file.exists)throw Error('The matched asset is no longer available.');
   var sequence=source.isStill===false&&/\d+\.(png|jpe?g|tiff?|tga|dpx|exr|bmp)$/i.test(file.name),useProxy=item.useProxy;
   if(proxy){if(sequence)item.setProxyWithSequence(file,false);else item.setProxy(file);item.useProxy=useProxy;}
   else if(sequence)item.replaceWithSequence(file,false);else item.replace(file);
   if(!proxy&&item.footageMissing)throw Error('After Effects still reports this source as missing.');
   result.relinked++;
  }catch(e){result.missing.push({name:item.name,path:path,kind:proxy?'proxy':'source',reason:String(e)});}
 }
 repair(false);repair(true);return result;
}
function storylensTemplateValidateAssets(items){
 var pending=items.slice(0),seen={},missing=[];
 while(pending.length){var item=pending.pop();if(!item||seen[item.id])continue;seen[item.id]=true;
  if(item instanceof FootageItem){
   try{var main=item.mainSource,file=item.file;if(item.footageMissing||main&&main.missingFootagePath||file&&!file.exists)missing.push({name:item.name,path:String(main&&main.missingFootagePath||file&&file.fsName||''),kind:'source',reason:'required_source_unavailable'});
    var proxy=item.proxySource;if(proxy&&(proxy.missingFootagePath||proxy.file&&!proxy.file.exists))missing.push({name:item.name,path:String(proxy.missingFootagePath||proxy.file.fsName),kind:'proxy',reason:'required_proxy_unavailable'});
   }catch(e){missing.push({name:item.name,path:'',kind:'inspection',reason:String(e)});}
  }else if(item instanceof CompItem){for(var k=1;k<=item.numLayers;k++){var child=item.layer(k).source;if(child)pending.push(child);}}
  else if(item instanceof FolderItem){for(k=1;k<=item.numItems;k++)pending.push(item.item(k));}
 }
 return missing;
}
function storylensTemplateImportSameProject(saved){try{return !!saved&&saved===app.project;}catch(_){return false;}}
function storylensTemplateRollbackImport(project,before){
 var added=[],ids={},i,j;
 for(i=1;i<=project.numItems;i++){var item=project.item(i);if(!before[item.id]){added.push(item);ids[item.id]=true;}}
 // Never remove a pre-existing item, nor new footage/comps already referenced by owner content.
 for(i=0;i<added.length;i++){
  item=added[i];var users=item.usedIn||[];for(j=0;j<users.length;j++)if(!ids[users[j].id])throw Error('An existing composition uses the partial import; it was kept.');
  if(item instanceof FolderItem)for(j=1;j<=item.numItems;j++)if(before[item.item(j).id])throw Error('A partial folder contains an existing item; it was kept.');
 }
 for(i=added.length-1;i>=0;i--){item=added[i];try{if(typeof isValid==='function'&&!isValid(item))continue;item.remove();}catch(e){if(typeof isValid!=='function'||isValid(item))throw e;}}
 return added.length;
}
function storylensTemplateKeepLegacyPartial(project,before,failed,destination){
 var added=[],ids={},roots=[],i,j;
 for(i=1;i<=project.numItems;i++){var item=project.item(i);if(!before[item.id]){added.push(item);ids[item.id]=true;}}
 if(added.length!==failed.items_added)throw Error('The partial inventory has changed; it was kept in place.');
 for(i=0;i<added.length;i++){item=added[i];if(!ids[item.parentFolder.id])roots.push(item);var users=item.usedIn||[];for(j=0;j<users.length;j++)if(!ids[users[j].id])throw Error('Existing content uses the partial template; it was kept in place.');if(item instanceof FolderItem)for(j=1;j<=item.numItems;j++)if(before[item.item(j).id])throw Error('The partial folder contains existing content.');}
 if(roots.length!==1||!(roots[0] instanceof FolderItem)||String(roots[0].name).toLowerCase()!==decodeURI(String(new File(failed.path).name)).toLowerCase())throw Error('The failed native project root could not be identified safely.');
 if(!(destination instanceof FolderItem)||destination.parentFolder!==project.rootFolder)throw Error('The import destination changed.');
 var bin=null;for(i=1;i<=destination.numItems;i++)if(destination.item(i) instanceof FolderItem&&String(destination.item(i).comment||'')==='Storylens template failed imports v1')bin=destination.item(i);
 if(!bin){bin=project.items.addFolder('Skipped templates');bin.comment='Storylens template failed imports v1';bin.parentFolder=destination;}
 roots[0].parentFolder=bin;return added.length;
}
function storylensTemplateReadFailureCache(){
 var settings=app.settings;
 if(settings.haveSetting('Storylens','templateImportFailuresMeta')){var parts=settings.getSetting('Storylens','templateImportFailuresMeta').split('|'),count=Number(parts[1]),raw='';if(!/^[AB]$/.test(parts[0])||count<1||count>100)throw Error('Invalid failure-cache metadata.');for(var i=0;i<count;i++)raw+=settings.getSetting('Storylens','templateImportFailures'+parts[0]+i);return JSON.parse(raw);}
 return settings.haveSetting('Storylens','templateImportFailures')?JSON.parse(settings.getSetting('Storylens','templateImportFailures')):[];
}
function storylensTemplateWriteFailureCache(failures){
 var settings=app.settings,meta=settings.haveSetting('Storylens','templateImportFailuresMeta')?settings.getSetting('Storylens','templateImportFailuresMeta'):'',slot=meta.charAt(0)==='A'?'B':'A';
 var raw=hJSON(failures.slice(-80)).replace(/[^\x20-\x7e]/g,function(c){return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);}),count=Math.ceil(raw.length/900);
 if(count>100)throw Error('Failure cache exceeds its storage budget.');
 for(var i=0;i<count;i++)settings.saveSetting('Storylens','templateImportFailures'+slot+i,raw.slice(i*900,(i+1)*900));
 // Commit the new generation only after all bounded pieces were written.
 settings.saveSetting('Storylens','templateImportFailuresMeta',slot+'|'+count);
}
function storylensPanelTemplateImport(request){
 var source='D:/Editing/AE documentry style editing templates/LatestUniqueTemplete',job=StorylensTemplateImportJob;
 function total(j){return j.target||Math.min(20,j.queue.length);}
 function snapshot(j){
  if(j&&!storylensTemplateImportSameProject(j.project))return {ok:true,state:'project_changed',running:false,total:total(j),processed:j.index,imported:0,results:[]};
  if(!j)return {ok:true,state:'idle',running:false,total:0,processed:0,imported:0,results:[]};
  var out={ok:true,state:j.state,running:j.running,total:total(j),processed:j.index,attempted:j.index,imported:j.imported,skipped:j.skipped||0,shortfall:Math.max(0,total(j)-j.imported),missing_media:j.missing,earlier_missing_media:j.earlierMissing||0,relinked_media:j.relinked||0,results:j.results,library_count:j.libraryCount,batch_id:j.batch,progress_warning:j.checkpoint_warning||j.cache_warning||'',project_id:storylensProjectId()};
  if(!j.running&&j.state==='complete'&&out.shortfall)out.message=j.imported+' of '+out.total+' templates imported. No more usable templates in this pass; successful imports are kept.';
  return out;
 }
 function failure(code,message,detail){return hJSON({error:message,code:code,details:String(detail||'')});}
 function signature(path){var file=new File(path),key=String(path).replace(/\\/g,'/').toLowerCase().slice(source.length+1).split('/')[0];return String(file.modified?file.modified.getTime():0)+'|'+String(file.length||0)+'|'+(packageStamp[key]||'');}
 try{
  request=request||{};var action=request.action||'status';
  if(action==='status')return hJSON(snapshot(job));
  if(action==='stop'){if(job&&job.running&&storylensTemplateImportSameProject(job.project))job.stop=true;return hJSON(snapshot(job));}
  if(action!=='start'&&action!=='preview')return failure('template_import_native','Choose Import Template or Stop.');
  if(job&&job.running&&storylensTemplateImportSameProject(job.project))return hJSON(snapshot(job));
  if(typeof SLTemplateLibraryImport!=='undefined'&&SLTemplateLibraryImport.running)return failure('template_import_native','The earlier template import is still running. Stop it before starting another batch.');
  var project=app.project;if(!project)return failure('template_import_target','Open an After Effects project, then press Import Template.');
  var library=new Folder(source);if(!library.exists)return failure('template_import_source','The template folder is unavailable. Reconnect drive A: and check LatestUniqueTemplete.');
  var rows=[],visited={},scanned=0,mediaIndex={},packageRows={},packageStamp={},checkpointTag='Storylens template import checkpoint v2|';
  function scan(folder,depth){if(depth>32||++scanned>12000)throw Error('Template library scan limit reached.');var identity=String(folder.fsName).toLowerCase();if(visited[identity]||folder.alias)return;visited[identity]=true;var files=folder.getFiles();for(var k=0;k<files.length;k++){var entry=files[k];if(entry instanceof Folder){if(!/auto.save|\.aep logs|^logs$/i.test(entry.name||''))scan(entry,depth+1);}else if(!entry.alias){var assetPath=String(entry.fsName).replace(/\\/g,'/'),packageKey=assetPath.slice(source.length+1).split('/')[0].toLowerCase();if(!packageRows[packageKey])packageRows[packageKey]=[];packageRows[packageKey].push(assetPath.toLowerCase()+'|'+String(entry.length||0)+'|'+String(entry.modified?entry.modified.getTime():0));if(/\.(aep|aepx|aet)$/i.test(entry.name))rows.push({path:entry.fsName,folder:'',modified:entry.modified?entry.modified.getTime():0});else{var name=String(entry.fsName).replace(/\\/g,'/').split('/').pop().toLowerCase();if(!mediaIndex[name])mediaIndex[name]=[];mediaIndex[name].push(entry.fsName);}}}}
  scan(library,0);for(var packageName in packageRows)if(packageRows.hasOwnProperty(packageName)){packageRows[packageName].sort();packageStamp[packageName]=StorylensLibraryModel.historyKey(packageRows[packageName].join('|'))+'|'+packageRows[packageName].length;}
  var chosen=StorylensLibraryModel.plan(rows,source),comments=[],i,dest=null,found=0,knownItems={},priorFootage=[],checkpoint=null;
  // Recover only the previous failed attempt when no subsequent owner edit changed its inventory.
  if(action==='start'&&job&&job.state==='needs_attention'&&storylensTemplateImportSameProject(job.project)&&job.results&&job.results.length){
   var failed=job.results[job.results.length-1];
   var uncommitted=0;for(var u=1;u<=project.numItems;u++)if(!job.knownItems[project.item(u).id])uncommitted++;
   if(failed.status==='failed'&&uncommitted===0){failed.status='skipped';failed.rollback_complete=true;}
   if(failed.status==='failed'&&failed.rollback_complete===false)return failure('template_import_recovery','A partial template is used by existing project content. Your project is kept. Undo the failed import before retrying.',failed.recovery_details);
   if(failed.status==='failed'&&failed.items_added>0&&failed.rollback_complete!==false){
    app.beginUndoGroup('Recover incomplete template import');try{
     if(typeof project.revision==='number'&&project.revision===job.revision){failed.rolled_back_items=storylensTemplateRollbackImport(project,job.knownItems);failed.rollback_complete=true;}
     else{failed.kept_partial_items=storylensTemplateKeepLegacyPartial(project,job.knownItems,failed,job.folder);failed.partial_kept=true;failed.recovery_details='Earlier partial import kept in Skipped templates; existing content was not deleted.';}
     failed.status='skipped';
    }finally{app.endUndoGroup();}
   }
  }
  for(i=1;i<=project.numItems;i++){var item=project.item(i);knownItems[item.id]=true;if(item instanceof FootageItem)priorFootage.push(item);comments.push(String(item.comment||''));if(item instanceof FolderItem&&item.parentFolder===project.rootFolder&&(item.name==='Import Template'||item.name==='All Project Files')){dest=item;found++;}}
  if(found>1)return failure('template_import_target','Keep one intended Import Template folder before importing.');
  if(dest){var lines=String(dest.comment||'').split(/\r?\n/);for(i=0;i<lines.length;i++)if(lines[i].indexOf(checkpointTag)===0)try{checkpoint=JSON.parse(lines[i].slice(checkpointTag.length));}catch(_){} }
  var resume=null;
  if(job&&storylensTemplateImportSameProject(job.project)&&!job.running&&job.imported<total(job)&&(job.state==='needs_attention'||job.state==='stopped'))resume={batch:job.batch,target:total(job),failed:job.failures||[],results:job.results||[]};
  else if(checkpoint&&checkpoint.imported<checkpoint.target)resume=checkpoint;
  var batchId=resume?String(resume.batch):String(Math.max(new Date().getTime(),job?Number(job.batch)+1:0,checkpoint?Number(checkpoint.batch)+1:0)),seed=0,seedFolders=[],failures=resume?(resume.failed||[]):[],seedResults=resume?(resume.results||[]):[];
  try{if(!resume)failures=storylensTemplateReadFailureCache();}catch(_){}
  for(i=1;i<=project.numItems;i++){item=project.item(i);if(resume&&item instanceof FolderItem&&('\n'+String(item.comment||'').split(/\r?\n/).join('\n')+'\n').indexOf('\nStorylens template batch|'+batchId+'\n')>=0){seed++;seedFolders.push(item);}}
  if(resume&&job&&job.results)for(i=0;i<job.results.length;i++){var priorResult=job.results[i];if((priorResult.status==='failed'||priorResult.status==='skipped')&&priorResult.path){var exists=false;for(var fi=0;fi<failures.length;fi++)if(failures[fi].path===priorResult.path)exists=true;if(!exists)failures.push({path:priorResult.path,signature:signature(priorResult.path)});}}
  var history=[];try{if(app.settings.haveSetting('Storylens','templateImportHistory'))history=app.settings.getSetting('Storylens','templateImportHistory').split('\n');}catch(_){}
  var pool=StorylensLibraryModel.batch(chosen,comments,history,Math.random,source,chosen.length),eligibleCount=0,filtered=[],knownRejected=[];eligibleCount=pool.length;
  for(i=0;i<pool.length;i++){var blocked=false;for(var f=0;f<failures.length;f++)if(pool[i].path===failures[f].path&&signature(pool[i].path)===failures[f].signature)blocked=true;if(!blocked)filtered.push(pool[i]);else knownRejected.push({name:pool[i].path,path:pool[i].path,status:'skipped',details:'Previously rejected unchanged source package.'});}
  pool=filtered;
  for(i=0;i<pool.length;i++){var p=String(pool[i].path).replace(/\\/g,'/'),base=String(library.fsName).replace(/\\/g,'/');pool[i].folder=p.slice(base.length+1).split('/')[0].replace(/\.(aep|aepx|aet)$/i,'');}
  var target=resume?resume.target:Math.min(20,eligibleCount),needed=Math.max(0,target-seed),queue=pool.slice(0,needed),reserve=pool.slice(needed);
  if(action==='preview')return hJSON({ok:true,state:'preview',running:false,total:target,already_imported:seed,library_count:chosen.length,selected:queue});
  var repaired=0,existingMissing=[],existingResults=[];
  app.beginUndoGroup('Relink imported template media');
  try{if(dest)dest.name='Import Template';for(i=0;i<priorFootage.length;i++){var prior=priorFootage[i],parent=prior.parentFolder,templatePath='',guard=0;
   while(parent&&parent!==project.rootFolder&&guard++<64){var tagged=String(parent.comment||'').match(/(?:^|\n)Storylens template library v1\|([^\r\n]+)/);if(tagged){templatePath=tagged[1];break;}parent=parent.parentFolder;}
   if(!templatePath)continue;var recovery=storylensTemplateRepairMedia(prior,templatePath,source,mediaIndex);repaired+=recovery.relinked;for(var z=0;z<recovery.missing.length;z++)existingMissing.push(recovery.missing[z]);
  }}finally{app.endUndoGroup();}
  if(existingMissing.length)existingResults.push({name:'Previously imported templates',status:'imported',missing_media:existingMissing.length,missing_paths:existingMissing});
  // A resumed batch counts only members whose assets are still available.
  // Keep any existing timeline references; mark rejected roots for future alignment.
  if(resume){var accepted=[],rejectTag='Storylens template rejected assets v2';seed=0;app.beginUndoGroup('Check resumed template sources');
   try{for(i=0;i<seedFolders.length;i++){var member=seedFolders[i],unavailable=storylensTemplateValidateAssets([member]),memberComment=String(member.comment||''),memberLines=memberComment.split(/\r?\n/),memberKeep=[];
    for(var ml=0;ml<memberLines.length;ml++)if(memberLines[ml]!==rejectTag)memberKeep.push(memberLines[ml]);
    if(unavailable.length){memberKeep.push(rejectTag);for(var sr=0;sr<seedResults.length;sr++)if(seedResults[sr].folder_id===member.id){seedResults[sr].status='excluded';seedResults[sr].details='Existing template has missing assets; not counted in the resumed batch. Its timeline layers are kept.';seedResults[sr].missing_media=unavailable.length;seedResults[sr].missing_paths=unavailable;}}
    else{accepted.push(member);seed++;}
    var nextComment=memberKeep.join('\n');if(nextComment!==memberComment)member.comment=nextComment;
   }}finally{app.endUndoGroup();}seedFolders=accepted;needed=Math.max(0,target-seed);queue=pool.slice(0,needed);reserve=pool.slice(needed);
  }

  if(!dest&&queue.length){app.beginUndoGroup('Import Template folder');try{dest=project.items.addFolder('Import Template');}finally{app.endUndoGroup();}}
  if(!queue.length&&!resume)return hJSON({ok:true,state:'complete',running:false,total:target,shortfall:target,skipped:knownRejected.length,processed:0,imported:0,relinked_media:repaired,missing_media:0,earlier_missing_media:existingMissing.length,results:existingResults.concat(knownRejected),library_count:chosen.length,message:knownRejected.length?'0 of '+target+' templates imported. No usable unimported templates remain; rejected sources were kept out.':chosen.length?'Existing templates checked. No new templates to import.':'No After Effects projects were found in LatestUniqueTemplete.'});
  knownItems[dest.id]=true;
  job={running:queue.length>0,stop:false,state:queue.length?'running':'complete',target:target,queue:queue,reserve:reserve,index:0,imported:seed,skipped:failures.length,failures:failures,missing:0,earlierMissing:existingMissing.length,relinked:repaired,results:seedResults.concat(existingResults),libraryCount:chosen.length,project:project,projectId:storylensProjectId(),folder:dest,active:project.activeItem,batch:batchId,folders:seedFolders,knownItems:knownItems,revision:project.revision};StorylensTemplateImportJob=job;
  job.checkpoint=function(){try{var old=String(dest.comment||'').split(/\r?\n/),keep=[];for(var k=0;k<old.length;k++)if(old[k].indexOf(checkpointTag)!==0&&old[k])keep.push(old[k]);keep.push(checkpointTag+hJSON({batch:this.batch,target:this.target,imported:this.imported,state:this.state,failed:this.failures.slice(-30)}));dest.comment=keep.join('\n');var cacheJSON=hJSON(this.failures);if(this.cacheWritten!==cacheJSON){try{storylensTemplateWriteFailureCache(this.failures);this.cacheWritten=cacheJSON;}catch(cacheError){this.cache_warning='This batch can finish, but rejected-source history could not be saved.';}} }catch(e){this.checkpoint_warning='Progress is kept in this AE session; project checkpoint could not be written.';}};
  job.finish=function(state){this.state=state;this.running=false;if(storylensTemplateImportSameProject(project)){this.checkpoint();try{for(var n=1;n<=project.numItems;n++)project.item(n).selected=false;for(n=0;n<this.folders.length;n++)this.folders[n].selected=true;if(this.active instanceof CompItem)this.active.openInViewer();}catch(_){}}};
  job.tick=function(){
   var self=StorylensTemplateImportJob;if(!self||!self.running)return;
   if(!storylensTemplateImportSameProject(project)){self.finish('project_changed');return;}
   if(self.stop){self.finish('stopped');return;}
   if(self.imported>=self.target||self.index>=self.queue.length){self.finish('complete');return;}
   var row=self.queue[self.index],before=self.knownItems,start=project.numItems,imported=null,undo=false,suppressed=false,renderingBefore=null,fileStarted=new Date().getTime(),result={name:row.folder,path:row.path,status:'failed'};
   if(typeof project.revision!=='number'||project.revision!==self.revision){before={};for(var n=1;n<=project.numItems;n++)before[project.item(n).id]=true;}
   try{
    if(typeof app.disableRendering==='boolean'){renderingBefore=app.disableRendering;app.disableRendering=true;}
    var file=new File(row.path);if(!file.exists)throw Error('The source project is no longer available.');
    app.beginUndoGroup('Import Template - '+row.folder);undo=true;app.beginSuppressDialogs();suppressed=true;result.stage='native-import';
    project.importFile(new ImportOptions(file));
    result.stage='inventory';var roots=[],added=[];
    for(n=1;n<=project.numItems;n++){var child=project.item(n);if(!before[child.id]){added.push(child);if(child.parentFolder===project.rootFolder||before[child.parentFolder.id])roots.push(child);}}
    if(roots.length===1&&roots[0] instanceof FolderItem)imported=roots[0];else if(roots.length){imported=project.items.addFolder(row.folder);for(n=0;n<roots.length;n++)roots[n].parentFolder=imported;}else throw Error('After Effects added no project items.');
    result.stage='grouping';imported.parentFolder=dest;if(imported.name!==row.folder)imported.name=row.folder;
    imported.comment=StorylensLibraryModel.marker(row.path)+'\n'+StorylensLibraryModel.packageMarker(row.path,source)+'\nStorylens template batch|'+batchId;
    result.stage='relinking';result.missing_paths=[];result.relinked_media=0;
    for(n=0;n<added.length;n++){child=added[n];if(child instanceof FootageItem){var recovery=storylensTemplateRepairMedia(child,row.path,source,mediaIndex);result.relinked_media+=recovery.relinked;for(var z=0;z<recovery.missing.length;z++)result.missing_paths.push(recovery.missing[z]);}}
    result.stage='validating-assets';
    var unresolved=storylensTemplateValidateAssets(added),missingKeys={};for(n=0;n<result.missing_paths.length;n++)missingKeys[result.missing_paths[n].kind+'|'+result.missing_paths[n].path]=true;
    for(n=0;n<unresolved.length;n++){var missingKey=unresolved[n].kind+'|'+unresolved[n].path;if(!missingKeys[missingKey]){result.missing_paths.push(unresolved[n]);missingKeys[missingKey]=true;}}
    result.missing_media=result.missing_paths.length;
    if(result.missing_media)throw Error('Required template source files are missing. This template was not accepted.');
    // Commit the count and inventory only after grouping and relinking finish.
    for(n=0;n<added.length;n++)before[added[n].id]=true;before[imported.id]=true;self.knownItems=before;self.folders.push(imported);self.imported++;
    result.status='imported';result.folder_id=imported.id;result.items_added=project.numItems-start;result.missing_media=result.missing_paths.length;self.missing+=result.missing_media;self.relinked+=result.relinked_media;result.stage='complete';
    try{history.push(StorylensLibraryModel.historyKey(row.path));app.settings.saveSetting('Storylens','templateImportHistory',history.slice(-80).join('\n'));}catch(_){}
   }catch(e){
    result.details=String(e);result.items_added=project.numItems-start;
    try{result.rolled_back_items=storylensTemplateRollbackImport(project,before);result.rollback_complete=true;result.status='skipped';self.skipped++;self.failures.push({path:row.path,signature:signature(row.path)});if(self.reserve.length)self.queue.push(self.reserve.shift());}
    catch(recoveryError){result.rollback_complete=false;result.recovery_details=String(recoveryError);self.state='needs_attention';self.running=false;}
   }finally{if(suppressed)app.endSuppressDialogs(false);if(undo)app.endUndoGroup();if(renderingBefore!==null)app.disableRendering=renderingBefore;}
   result.loading_ms=new Date().getTime()-fileStarted;self.results.push(result);self.index++;self.checkpoint();self.revision=project.revision;
   if(self.running)app.scheduleTask('StorylensTemplateImportJob.tick()',200,false);else self.finish('needs_attention');
  };
  job.checkpoint();job.revision=project.revision;if(job.running)app.scheduleTask('StorylensTemplateImportJob.tick()',200,false);return hJSON(snapshot(job));
 }catch(e){return failure('template_import_native','Template import could not finish. Your successful templates are kept. Check Technical details before retrying.',e);}
}
