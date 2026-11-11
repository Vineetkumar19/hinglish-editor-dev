/* Exact downloaded image -> root Downloads bin; never insert/replace a layer. */
function storylensPanelImageDownload(m){
 var undo=false;
 try{
  if(!app.project||!m||m.expected_project_id!==storylensProjectId())throw Error('The project changed. Retry adding the saved image to the intended project.');
  if(!/^[a-f0-9]{24}$/.test(m.id||''))throw Error('Choose a saved Storylens image.');
  var file=new File(m.path),path=String(file.fsName).replace(/\\/g,'/').toLowerCase();
  if(path.indexOf('/output/image-downloads/downloads/')<0||!file.exists||!/^Image-[a-f0-9]{16}\.(jpg|png|gif|tif|bmp)$/i.test(file.name))throw Error('The saved image is unavailable. Download it again.');
  var folder=null,footage=null,i,item,previousSelection=app.project.selection||[];
  function legacy(candidate){for(var n=1;n<=app.project.numItems;n++){var f=app.project.item(n);if(f instanceof FootageItem&&f.parentFolder===candidate&&(String(f.comment||'').indexOf('storylens-direct-image:')===0||f.file&&/\/output\/image-downloads\/downloads\//i.test(String(f.file.fsName).replace(/\\/g,'/'))))return true;}return false;}
  for(i=1;i<=app.project.numItems;i++){item=app.project.item(i);if(item instanceof FolderItem&&item.parentFolder===app.project.rootFolder&&(item.name==='Image Downloader'||item.name==='Downloads'&&legacy(item))){if(folder)throw Error('Keep one intended Image Downloader folder and retry.');folder=item;}}
  app.beginUndoGroup('Storylens image download');undo=true;
  if(!folder)folder=app.project.items.addFolder('Image Downloader');else folder.name='Image Downloader';
  for(i=1;i<=app.project.numItems;i++){item=app.project.item(i);if(item instanceof FootageItem&&item.parentFolder===folder&&item.file&&String(item.file.fsName).toLowerCase()===String(file.fsName).toLowerCase())footage=item;}
  if(!footage){var options=new ImportOptions(file);options.sequence=false;footage=app.project.importFile(options);footage.parentFolder=folder;footage.comment='storylens-direct-image:'+m.id;}
  footage.selected=false;
  for(i=0;i<previousSelection.length;i++)if(!previousSelection[i].selected)previousSelection[i].selected=true;
  return hJSON({ok:true,id:m.id,project_id:storylensProjectId(),folder:'Image Downloader',folder_id:folder.id,footage_id:footage.id,path:footage.file.fsName});
 }catch(e){return hJSON({error:'The image is saved, but could not be added to Downloads. Retry adding it.',code:'image_download_native',details:String(e)});}
 finally{if(undo)app.endUndoGroup();}
}
