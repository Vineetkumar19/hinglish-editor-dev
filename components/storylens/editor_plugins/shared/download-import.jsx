/* Import downloader media into one stable Video/Sound bin. No timeline edits. */
function storylensPanelDownloadImport(m){
 var ae=m&&m.host==='aftereffects',undo=false;
 function out(value){return typeof hJSON==='function'?hJSON(value):storylensPanelJSON(value);}
 try{
  if(!app.project||!m||!/^[a-f0-9]{32}$/.test(m.id||'')||!(m.kind==='video'||m.kind==='audio'))throw Error('Choose a saved video or audio output.');
  var projectId=ae?storylensProjectId():String(app.project.path||app.project.name);
  if(projectId!==m.expected_project_id)throw Error('The project changed. Select Video or Audio again in the intended project.');
  var file=new File(m.path),path=String(file.fsName).replace(/\\/g,'/').toLowerCase(),folderName=m.kind==='video'?'Downloader Video':'Downloader Audio',legacyName=m.kind==='video'?'Video':'Sound';
  if(!file.exists||path.indexOf('/output/downloads/'+m.id+'/'+m.kind+'/')<0||!(m.kind==='video'?/\.mp4$/i:/\.(wav|mp3)$/i).test(file.name))throw Error('The saved media is unavailable. Your other downloads are kept.');
  var bin=null,item=null,i,candidate,reused=false;
  function legacyAE(folder){for(var n=1;n<=app.project.numItems;n++){var f=app.project.item(n);if(f instanceof FootageItem&&f.parentFolder===folder&&f.file&&/\/output\/downloads\/[a-f0-9]{32}\//i.test(String(f.file.fsName).replace(/\\/g,'/')))return true;}return false;}
  function legacyPP(folder){for(var n=0;n<folder.children.numItems;n++){var f=folder.children[n];if(f.type!==ProjectItemType.BIN&&/\/output\/downloads\/[a-f0-9]{32}\//i.test(String(f.getMediaPath()).replace(/\\/g,'/')))return true;}return false;}
  if(ae){
   for(i=1;i<=app.project.numItems;i++){candidate=app.project.item(i);if(candidate instanceof FolderItem&&candidate.parentFolder===app.project.rootFolder&&(candidate.name===folderName||candidate.name===legacyName&&legacyAE(candidate))){if(bin)throw Error('Keep one intended root '+folderName+' folder and retry.');bin=candidate;}}
   app.beginUndoGroup('Storylens downloaded '+m.kind);undo=true;
   if(!bin)bin=app.project.items.addFolder(folderName);else bin.name=folderName;
   for(i=1;i<=app.project.numItems;i++){candidate=app.project.item(i);if(candidate instanceof FootageItem&&candidate.parentFolder===bin&&candidate.file&&String(candidate.file.fsName).replace(/\\/g,'/').toLowerCase()===path)item=candidate;}
   reused=!!item;if(!item){var options=new ImportOptions(file);options.sequence=false;item=app.project.importFile(options);item.parentFolder=bin;item.name=m.name||file.name;}
  }else if(m.host==='premiere'){
   var root=app.project.rootItem;
   for(i=0;i<root.children.numItems;i++){candidate=root.children[i];if(candidate.type===ProjectItemType.BIN&&(candidate.name===folderName||candidate.name===legacyName&&legacyPP(candidate))){if(bin)throw Error('Keep one intended root '+folderName+' bin and retry.');bin=candidate;}}
   if(!bin)bin=root.createBin(folderName);else bin.name=folderName;
   function find(){for(var j=0;j<bin.children.numItems;j++){var child=bin.children[j];if(child.type!==ProjectItemType.BIN&&String(child.getMediaPath()).replace(/\\/g,'/').toLowerCase()===path)return child;}return null;}
   item=find();reused=!!item;
   if(!item){if(!app.project.importFiles([file.fsName],true,bin,false))throw Error('Premiere did not confirm the import.');item=find();if(!item)throw Error('Premiere has not confirmed the media item yet.');item.name=m.name||file.name;}
  }else throw Error('Open the Storylens Adobe panel.');
  return out({ok:true,id:m.id,kind:m.kind,host:m.host,folder:folderName,item_id:ae?item.id:item.nodeId,project_id:projectId,path:file.fsName,reused:reused});
 }catch(e){return out({error:'The download is saved, but could not be added to the editor. Select Video or Audio to retry.',code:'download_delivery',details:String(e)});}
 finally{if(undo)app.endUndoGroup();}
}
