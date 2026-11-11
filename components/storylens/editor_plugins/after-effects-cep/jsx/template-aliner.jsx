/* Imported-folder alignment only. No import, render, save, source edit or model call. */
function storylensTemplateFontReport(sources){
 var result={checked:false,missing:[],policy:'native-substitution',source_fonts_changed:false},ids={},seen={},i,j;
 function visit(comp){if(ids[comp.id])return;ids[comp.id]=true;for(var k=1;k<=comp.numLayers;k++){var source=comp.layer(k).source;if(source instanceof CompItem)visit(source);}}
 try{
  if(!app.fonts||typeof app.project.usedFonts==='undefined'){result.notice='Font check is unavailable in this After Effects version. Check Window > Character for missing fonts.';return result;}
  for(i=0;i<sources.length;i++)visit(sources[i]);
  var fonts=app.project.usedFonts;
  for(i=0;i<fonts.length;i++){
   var font=fonts[i].font;if(!font.isSubstitute)continue;
   var count=0;for(j=0;j<fonts[i].usedAt.length;j++){var layer=app.project.layerByID(fonts[i].usedAt[j].layerID);if(layer&&ids[layer.containingComp.id])count++;}
   if(!count)continue;
   var name=String(font.postScriptName),row=seen[name];
   if(row)row.occurrences+=count;else{row={name:name,family:String(font.familyName||name),style:String(font.styleName||''),occurrences:count};seen[name]=row;result.missing.push(row);}
  }
  result.missing.sort(function(a,b){return a.name<b.name?-1:a.name>b.name?1:0;});result.checked=true;
 }catch(e){result.notice='The font check could not finish. After Effects can still use its temporary substitutes; review the template text.';result.details=String(e);}
 return result;
}
function storylensPanelTemplateFonts(){try{var comp=storylensCurrentComp();return hJSON({ok:true,font_report:storylensTemplateFontReport([comp])});}catch(e){return hJSON({error:String(e.message||e),code:'template_fonts',details:String(e)});}}
function storylensPanelFolderCleanupContext(){
 try{return hJSON({ok:true,project_id:storylensProjectId()});}
 catch(e){return hJSON({error:'The After Effects project could not be read. Open the intended project and try Collapse folders.',code:'template_folder_cleanup',details:String(e)});}
}
if(typeof StorylensTemplateAlignLastTarget==='undefined')StorylensTemplateAlignLastTarget=null;
function storylensTemplateAlignTarget(){
 var project=app.project,candidate=null,i,j;
 // The Project bin may own selection while a video composition is still open.
 try{if(app.activeViewer&&typeof ViewerType!=='undefined'&&app.activeViewer.type===ViewerType.VIEWER_COMPOSITION)app.activeViewer.setActive();}catch(_){}
 if(project.activeItem instanceof CompItem)return project.activeItem;
 try{candidate=storylensCurrentComp();if(candidate instanceof CompItem)return candidate;}catch(_){}
 if(StorylensTemplateAlignLastTarget&&StorylensTemplateAlignLastTarget.project===project){for(i=1;i<=project.numItems;i++)if(project.item(i) instanceof CompItem&&project.item(i).id===StorylensTemplateAlignLastTarget.id)return project.item(i);}
 var matches=[];for(i=1;i<=project.numItems;i++){candidate=project.item(i);if(!(candidate instanceof CompItem))continue;for(j=1;j<=candidate.numLayers;j++)if(String(candidate.layer(j).comment||'').indexOf('Storylens Template Aliner v1 | folder=')===0){matches.push(candidate);break;}}
 if(matches.length===1)return matches[0];
 throw Error('Open the main video composition on the timeline, then press Template Aliner.');
}
function storylensPanelTemplateAlign(request){
 var created=[],previousLayers=[],previousOrder=[],removalStarted=false,undo=false,tag='Storylens Template Aliner v1',rollback=true,renderingBefore=null;
 var clockStart=new Date().getTime(),clockLast=clockStart,performance={};
 function lap(name){var now=new Date().getTime();performance[name]=now-clockLast;clockLast=now;}
 function find(id){if(typeof app.project.itemByID==='function'){try{return app.project.itemByID(Number(id));}catch(_){return null;}}for(var i=1;i<=app.project.numItems;i++)if(String(app.project.item(i).id)===String(id))return app.project.item(i);return null;}
 function nested(folder,target){var p=target.parentFolder,visited={};while(p&&String(p.id)!==String(app.project.rootFolder.id)&&!visited[p.id]){if(String(p.id)===String(folder.id))return true;visited[p.id]=true;p=p.parentFolder;}return false;}
 function depends(source,target,seen){if(source===target)return true;seen=seen||{};if(seen[source.id])return false;seen[source.id]=true;
  for(var i=1;i<=source.numLayers;i++){var next=source.layer(i).source;if(next instanceof CompItem&&depends(next,target,seen))return true;}return false;}
 function projectBoundary(folder){return /Storylens template (?:library|package|batch)(?: v1)?\|/.test(String(folder.comment||''))||/\.ae(?:px?|t)$/i.test(String(folder.name||''));}
 function inCollection(folder){var parent=folder.parentFolder,visited={};while(parent&&!visited[parent.id]&&String(parent.id)!==String(app.project.rootFolder.id)){if(/^(?:all[ _-]*(?:project[ _-]*files|templates|templetes)|import[ _-]*template)$/i.test(String(parent.name||'')))return true;visited[parent.id]=true;parent=parent.parentFolder;}return false;}
 function compositions(folder){var out=[];function walk(f){for(var i=1;i<=f.numItems;i++){var item=f.item(i);if(item instanceof FolderItem){if(!projectBoundary(item))walk(item);}else if(item instanceof CompItem)out.push(item);}}walk(folder);return out;}
 function describe(comps){var ids={},out=[],edges={},parents={},queuedIds={},i,j,item;for(i=0;i<comps.length;i++)ids[comps[i].id]=true;
  // Read native edges once. Ranking every candidate must not revisit native
  // layer/property objects for all of its overlapping descendants.
  for(i=0;i<comps.length;i++){item=comps[i];var children=[],unique={};for(j=1;j<=item.numLayers;j++){var child=item.layer(j).source;if(child&&child instanceof CompItem&&ids[child.id]&&!unique[child.id]){unique[child.id]=true;children.push(String(child.id));parents[child.id]=(parents[child.id]||0)+1;}}edges[item.id]=children;}
  if(app.project.renderQueue)for(j=1;j<=app.project.renderQueue.numItems;j++)queuedIds[app.project.renderQueue.item(j).comp.id]=true;
  function descendants(id){var seen={},pending=[String(id)],total=-1;while(pending.length){var current=pending.pop();if(seen[current])continue;seen[current]=true;total++;var children=edges[current]||[];for(var k=0;k<children.length;k++)if(!seen[children[k]])pending.push(children[k]);}return total;}
  for(i=0;i<comps.length;i++){item=comps[i];out.push({id:item.id,name:item.name,duration:item.duration,fps:item.frameRate,width:item.width,height:item.height,pixelAspect:item.pixelAspect,usedBy:parents[item.id]||0,renderQueued:!!queuedIds[item.id],numLayers:item.numLayers,descendants:descendants(item.id)});}
  return out;}
 try{
  if(typeof StorylensTemplateImportJob!=='undefined'&&StorylensTemplateImportJob&&StorylensTemplateImportJob.running)throw Error('Wait for Import Template to finish before aligning templates.');
  request=request||{};var target=storylensTemplateAlignTarget(),projectId=storylensProjectId(),expected=request.expected,i,j;
  if(expected&&expected.project_id!==projectId)throw Error('The project changed. Read the template folders again.');
  if(expected&&String(expected.composition_id)!==String(target.id))throw Error('The video composition changed. Open the intended composition and read the folders again.');
  for(i=1;i<=target.numLayers;i++){var oldLayer=target.layer(i),oldComment=String(oldLayer.comment||'');if(oldComment.indexOf(tag+' | folder=')===0){if(oldLayer.locked)throw Error('Unlock the previous Storylens template layers before refreshing the alignment.');previousLayers.push(oldLayer);}}
  previousLayers.sort(function(a,b){return a.inPoint-b.inPoint;});
  for(i=0;i<previousLayers.length;i++){var oldFolder=/folder=(\d+)/.exec(String(previousLayers[i].comment||''));if(oldFolder)previousOrder.push(oldFolder[1]);}
  var folders=[],root=app.project.rootFolder,seen={},candidate,collectionSeen={},folderSeen={};
  function collection(folder){return /^(?:all[ _-]*(?:project[ _-]*files|templates|templetes)|import[ _-]*template)$/i.test(String(folder.name||''));}
  function failedImport(folder){var guard=0;while(folder&&guard++<64){if(/Storylens template (?:failed imports v1|rejected assets v2)/.test(String(folder.comment||'')))return true;folder=folder.parentFolder;}return false;}
  function add(folder){if(!(folder instanceof FolderItem)||folderSeen[folder.id]||failedImport(folder))return;folderSeen[folder.id]=true;folders.push(folder);}
  function expand(folder){
   if(collectionSeen[folder.id])return;collectionSeen[folder.id]=true;
   for(var n=1;n<=folder.numItems;n++){var child=folder.item(n);if(!(child instanceof FolderItem))continue;if(collection(child))expand(child);else add(child);}
  }
  if(expected&&expected.folder_ids){
   for(i=0;i<expected.folder_ids.length;i++){candidate=find(expected.folder_ids[i]);if(!(candidate instanceof FolderItem))throw Error('A template folder changed. Read the folders again.');if(collection(candidate))expand(candidate);else add(candidate);}
  }else{
   // Discover every project boundary, not just the single most recent batch.
   // A later partial import must not hide the rest of the existing twenty.
   for(i=1;i<=app.project.numItems;i++){candidate=app.project.item(i);if(!(candidate instanceof FolderItem))continue;
    if(collection(candidate))expand(candidate);
    else if(/Storylens template (?:library|package|batch)(?: v1)?\|/.test(String(candidate.comment||''))||projectBoundary(candidate)&&inCollection(candidate))add(candidate);
   }
   if(typeof StorylensTemplateImportJob!=='undefined'&&StorylensTemplateImportJob&&StorylensTemplateImportJob.project===app.project){var importedFolders=StorylensTemplateImportJob.folders||[];for(i=0;i<importedFolders.length;i++){candidate=find(importedFolders[i].id);if(candidate instanceof FolderItem)add(candidate);}}
   if(!folders.length)for(i=1;i<=root.numItems;i++){candidate=root.item(i);if(candidate instanceof FolderItem){if(collection(candidate))expand(candidate);else add(candidate);}}
   // Prefer recent imports when more than twenty are already present, without excluding older ones from a partial batch.
   folders.sort(function(a,b){var am=/Storylens template batch\|(\d+)/.exec(String(a.comment||'')),bm=/Storylens template batch\|(\d+)/.exec(String(b.comment||''));return Number(bm?bm[1]:0)-Number(am?am[1]:0)||SLTemplateAlinerModel.natural(a.name,b.name)||a.id-b.id;});
  }
  var ordered=[];for(i=0;i<folders.length;i++){candidate=folders[i];if(seen[candidate.id]||nested(candidate,target))continue;
   var covered=false;for(j=0;j<folders.length;j++)if(j!==i&&nested(folders[j],candidate)&&!projectBoundary(candidate)){covered=true;break;}
   if(!covered){seen[candidate.id]=true;ordered.push(candidate);}}
  if(!expected&&ordered.length>20)ordered=ordered.slice(0,20);
  if(ordered.length>200)throw Error('Select up to 200 template folders for one alignment.');
  lap('discovery_ms');
  var rows=[],questions=[],at=0,folderIds=[],targetInfo={width:target.width,height:target.height,fps:target.frameRate,duration:target.duration},choices=request.choices||{},scanned=0;
  for(i=0;i<ordered.length;i++)folderIds.push(ordered[i].id);
  for(i=0;i<ordered.length;i++){
   var folder=ordered[i],comps=compositions(folder);scanned++;
   if(!comps.length)continue;
   var answer=SLTemplateAlinerModel.choose(describe(comps),folder.name,targetInfo,choices[String(folder.id)]);
   if(answer.selected===null){questions.push({folder_id:folder.id,folder:folder.name,compositions:answer.comps});continue;}
   var source=find(answer.selected);
   if(depends(source,target,{}))throw Error('Template '+folder.name+' depends on the video composition and would create a circular composition.');
   if(!isFinite(source.duration)||source.duration*target.frameRate<1-1e-6)throw Error('Template '+folder.name+' is shorter than one video frame.');
   rows.push({folder:folder.name,folderId:folder.id,comp:{id:source.id,name:source.name,duration:source.duration}});at+=Math.floor(source.duration*target.frameRate+1e-5)/target.frameRate;
  }
  expected={project_id:projectId,composition_id:String(target.id),folder_ids:folderIds};
  if(questions.length)return hJSON({ok:false,needs_choices:true,questions:questions,expected:expected,duration:target.duration});
  if(!rows.length)throw Error('Select imported template folders, then open the video composition and press Template Aliner.');
  var plan=SLTemplateAlinerModel.fresh(rows,targetInfo,previousOrder,Math.random),placements=[],fontSources=[];
  for(i=0;i<plan.segments.length;i++)fontSources.push(find(rows[plan.segments[i].rowIndex].comp.id));
  lap('ranking_ms');
  var fontReport=storylensTemplateFontReport(fontSources);
  lap('font_check_ms');
  if(typeof app.disableRendering==='boolean'){renderingBefore=app.disableRendering;app.disableRendering=true;}
  app.beginUndoGroup('Template Aliner');undo=true;
  for(i=0;i<plan.segments.length;i++){
   var segment=plan.segments[i],row=rows[segment.rowIndex];source=find(row.comp.id);
   var layer=target.layers.add(source);created.push(layer);layer.moveToBeginning();
   layer.name=('0'+(i+1)).slice(-2)+' | '+row.folder+' | '+source.name;
   layer.comment=tag+' | folder='+row.folderId+' | source='+source.id;
   layer.startTime=segment.start;layer.inPoint=segment.start;layer.outPoint=segment.end;layer.audioEnabled=false;
   var transform=layer.property('ADBE Transform Group'),scale=100*Math.min(target.width*target.pixelAspect/(source.width*source.pixelAspect),target.height/source.height);
   transform.property('ADBE Anchor Point').setValue([source.width/2,source.height/2]);transform.property('ADBE Position').setValue([target.width/2,target.height/2]);transform.property('ADBE Scale').setValue([scale,scale]);
   placements.push({folder:row.folder,source_comp_id:source.id,name:source.name,start:segment.start,end:segment.end,trimmed:segment.trimmed});
  }
  // Build the complete replacement first. An add/transform failure leaves the old layout in place.
  for(i=previousLayers.length-1;i>=0;i--){removalStarted=true;previousLayers[i].remove();}
  StorylensTemplateAlignLastTarget={project:app.project,id:target.id};
  lap('placement_ms');performance.total_ms=new Date().getTime()-clockStart;
  return hJSON({ok:true,project_id:projectId,composition_id:String(target.id),name:target.name,duration:target.duration,fps:target.frameRate,
   templates_found:rows.length,discovered_folders:ordered.length,refreshed:true,replaced_layers:previousLayers.length,variety_available:plan.variety_available,full_template_animations:true,
   placements:placements,covered_duration:plan.covered_duration,uncovered_duration:plan.uncovered_duration,
   repeated:false,unused_folders:Math.max(0,rows.length-plan.segments.length),original_audio_preserved:true,template_audio_muted:true,saved:false,font_report:fontReport,performance:performance});
 }catch(error){
  for(var k=created.length-1;k>=0;k--)try{created[k].remove();}catch(_){rollback=false;}
  if(removalStarted)rollback=false;
  var message=String(error.message||error);
  if(/TypeError|ReferenceError|SyntaxError|undefined|not a function|not an object|does not have a value|not defined/i.test(message))message='Template Aliner could not read the current composition or template data. Reopen Storylens once, then try again; Technical details keeps the original error.';
  if(created.length)message='Template Aliner could not finish. '+(rollback?'New template layers were rolled back. The previous alignment and original video are kept.':'The previous alignment could not be fully restored. Choose Edit > Undo Template Aliner before retrying.');
  return hJSON({error:message,code:'template_aliner',details:String(error),rollback_complete:rollback});
 }finally{if(undo)app.endUndoGroup();if(renderingBefore!==null)app.disableRendering=renderingBefore;}
}
