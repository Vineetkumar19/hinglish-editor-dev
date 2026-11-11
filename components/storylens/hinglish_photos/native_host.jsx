/* Stable collection/photo identities shared by standalone and docked imports. */
function storylensPhotoJSON(v){
 function s(x){return '"'+String(x).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t')+'"';}
 if(v===null)return 'null';if(typeof v==='string')return s(v);if(typeof v==='number'||typeof v==='boolean')return String(v);
 var a=[],i;if(v instanceof Array){for(i=0;i<v.length;i++)a.push(storylensPhotoJSON(v[i]));return '['+a.join(',')+']';}
 for(i in v)if(v.hasOwnProperty(i))a.push(s(i)+':'+storylensPhotoJSON(v[i]));return '{'+a.join(',')+'}';
}
function storylensPhotoImportAE(m){
 var result={status:'running',host:'aftereffects',collection_id:m.id,imported:[],upgraded:[],already_present:[],preview_count:0,original_count:0},undo=false;
 try{
  if(!app.project)throw Error('Open an After Effects project before importing photos.');
  var projectPath=app.project.file?app.project.file.fsName:'',root=app.project.rootFolder.id;
  result.project={path:projectPath,root:root,name:app.project.file?app.project.file.name:'Untitled project'};
  if(m.expected&&(m.expected.path!==projectPath||m.expected.root!==root))throw Error('The active After Effects project changed. Choose the intended project and retry.');
  var rows=m.photos||[],i,item,images=null,folder=null,highest=0,known={},byPath={};
  if(!m.photos)for(i=0;i<m.paths.length;i++)rows.push({id:i+1,path:m.paths[i],origin:'original'});
  function oldPhotoRoot(candidate){for(var n=1;n<=candidate.numItems;n++){var child=candidate.item(n);if(child instanceof FolderItem&&(/^Screenshot\s+\d+$/i.test(child.name)||String(child.comment||'').indexOf('storylens-photos:')===0))return true;}return false;}
  for(i=1;i<=app.project.numItems;i++){item=app.project.item(i);if(item instanceof FolderItem&&item.parentFolder===app.project.rootFolder&&(item.name==='Photo Collector'||item.name==='Images'&&oldPhotoRoot(item))){if(images)throw Error('Keep one intended root Photo Collector folder.');images=item;}}
  if(rows.length){
   app.beginUndoGroup('Storylens — import photos');undo=true;
   if(!images)images=app.project.items.addFolder('Photo Collector');else images.name='Photo Collector';
   for(i=1;i<=app.project.numItems;i++){item=app.project.item(i);if(item instanceof FolderItem&&item.parentFolder===images){if(item.comment==='storylens-photos:'+m.id)folder=item;var number=/^Screenshot\s+(\d+)$/i.exec(item.name);if(number)highest=Math.max(highest,parseInt(number[1],10));}}
   if(!folder){folder=app.project.items.addFolder('Screenshot '+(highest+1));folder.parentFolder=images;folder.comment='storylens-photos:'+m.id;}
   for(i=1;i<=app.project.numItems;i++){item=app.project.item(i);if(item instanceof FootageItem&&item.file&&item.parentFolder===folder){byPath[item.file.fsName.toLowerCase()]=item;known[String(item.comment||'')]=item;}}
   for(i=0;i<rows.length;i++){
    var row=rows[i],prefix='storylens-photo:'+m.id+':'+row.id+':',origin=row.origin==='screenshot-preview'?'screenshot-preview':'original',file=new File(row.path),footage=known[prefix+'original']||known[prefix+'screenshot-preview']||byPath[file.fsName.toLowerCase()],action='already_present';
    if(!file.exists)throw Error('A saved photo is missing. Reopen its collection in Storylens.');
    if(footage&&String(footage.comment)===prefix+'original'&&origin==='screenshot-preview')origin='original';
    else if(footage&&footage.file.fsName.toLowerCase()!==file.fsName.toLowerCase()){footage.replace(file);action='upgraded';}
    else if(!footage){var options=new ImportOptions(file);options.sequence=false;footage=app.project.importFile(options);footage.parentFolder=folder;action='imported';}
    footage.comment=prefix+origin;footage.name=/^Image [1-9]\d{0,3}$/.test(String(row.display_name||''))?row.display_name:(origin==='screenshot-preview'?'PREVIEW - ':'')+'Photo '+row.id+' ('+footage.width+'x'+footage.height+')';
    known[prefix+origin]=footage;byPath[footage.file.fsName.toLowerCase()]=footage;
    result[action].push({photo_id:row.id,path:footage.file.fsName,id:footage.id,width:footage.width,height:footage.height,origin:origin});
    if(origin==='screenshot-preview')result.preview_count++;else result.original_count++;
   }
   result.folder={name:folder.name,id:folder.id,parent:'Photo Collector',parent_id:images.id};folder.selected=true;
  }
  result.status='done';
 }catch(error){result.status='failed';result.error=String(error);}finally{if(undo)app.endUndoGroup();}
 return result;
}
function storylensPhotoImportPremiere(m){
 var r={status:'running',host:'premiere',collection_id:m.id,imported:[],upgraded:[],already_present:[],preview_count:0,original_count:0};
 try{
  if(!app.project)throw Error('Open a Premiere Pro project before importing photos.');
  var root=app.project.rootItem,projectPath=app.project.path||'',i,images=null,folder=null,highest=0;
  r.project={path:projectPath,root:root.nodeId,name:app.project.name};
  if(m.expected&&(m.expected.path!==projectPath||String(m.expected.root)!==String(root.nodeId)))throw Error('The active Premiere project changed. Choose the intended project and retry.');
  function oldPhotoRoot(candidate){for(var n=0;n<candidate.children.numItems;n++){var child=candidate.children[n];if(child.type===2&&/^Screenshot\s+\d+$/i.test(child.name))return true;}return false;}
  for(i=0;i<root.children.numItems;i++){var item=root.children[i];if(item.type===2&&(item.name==='Photo Collector'||item.name==='Images'&&oldPhotoRoot(item))){if(images)throw Error('Keep one intended Photo Collector bin.');images=item;}}
  if(!images)images=root.createBin('Photo Collector');else images.name='Photo Collector';
  var identity='Storylens '+m.id+' - ';
  for(i=0;i<images.children.numItems;i++){item=images.children[i];var n=/^Screenshot\s+(\d+)/i.exec(item.name);if(n)highest=Math.max(highest,parseInt(n[1],10));if(m.folder_id&&String(item.nodeId)===String(m.folder_id))folder=item;else if(!folder&&item.type===2){for(var child=0;child<item.children.numItems;child++){if(String(item.children[child].name).indexOf(identity)===0){folder=item;break;}}}}
  if(!folder)folder=images.createBin('Screenshot '+(highest+1));
  var rows=m.photos||[];
  for(i=0;i<rows.length;i++){
   var row=rows[i],key=identity+row.id+' ',origin=row.origin==='screenshot-preview'?'screenshot-preview':'original',found=null,k,action='already_present';
   for(k=0;k<folder.children.numItems;k++)if(folder.children[k].name.indexOf(key)===0){found=folder.children[k];break;}
   if(!new File(row.path).exists)throw Error('A saved photo is missing. Reopen its Storylens collection.');
   if(found&&found.name.indexOf('PREVIEW')<0&&origin==='screenshot-preview')origin='original';
   else if(found&&new File(found.getMediaPath()).fsName.toLowerCase()!==new File(row.path).fsName.toLowerCase()){if(found.changeMediaPath(row.path,true)!==0||new File(found.getMediaPath()).fsName.toLowerCase()!==new File(row.path).fsName.toLowerCase())throw Error('Premiere could not replace this preview.');action='upgraded';}
   else if(!found){if(!app.project.importFiles([row.path],true,folder,false))throw Error('Premiere did not import a photo.');for(k=0;k<folder.children.numItems;k++)if(folder.children[k].getMediaPath&&new File(folder.children[k].getMediaPath()).fsName.toLowerCase()===new File(row.path).fsName.toLowerCase()){found=folder.children[k];break;}if(!found)throw Error('Premiere has not confirmed the imported photo.');action='imported';}
   found.name=key+(origin==='screenshot-preview'?'PREVIEW':'Original');
   r[action].push({photo_id:row.id,id:found.nodeId,path:found.getMediaPath(),origin:origin});if(origin==='screenshot-preview')r.preview_count++;else r.original_count++;
  }
  r.folder={name:folder.name,id:folder.nodeId,parent:'Photo Collector',parent_id:images.nodeId};r.status='done';
 }catch(e){r.status='failed';r.error=String(e);}return r;
}
