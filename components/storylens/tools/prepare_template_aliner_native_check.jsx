(function(){
 var output=new File('D:/Full Drive/remove silence/output/template-aliner-evidence/native-before.json');
 function write(value){output.encoding='UTF-8';output.open('w');output.write(hJSON(value));output.close();}
 try{
  $.evalFile(new File(Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/host.jsx'));
  var original=app.project.activeItem;if(!(original instanceof CompItem))throw Error('Open the owner video composition before creating a test copy.');
  var layers=[],i,l;for(i=1;i<=original.numLayers;i++){l=original.layer(i);layers.push({index:i,name:l.name,source_id:l.source?l.source.id:null,start:l.startTime,inPoint:l.inPoint,outPoint:l.outPoint,audio:l.audioEnabled,enabled:l.enabled});}
  app.beginUndoGroup('Prepare Template Aliner review copy');
  var copy=original.duplicate();copy.name=original.name+' - Template Aliner check';copy.parentFolder=original.parentFolder;copy.resolutionFactor=[4,4];
  for(i=1;i<=app.project.numItems;i++)app.project.item(i).selected=false;
  copy.selected=true;copy.openInViewer();app.endUndoGroup();
  write({ok:true,owner_project:app.project.file?app.project.file.fsName:null,original_comp_id:original.id,original_name:original.name,
   original_duration:original.duration,original_fps:original.frameRate,original_layers:layers,test_comp_id:copy.id,test_name:copy.name,
   test_duration:copy.duration,test_parent:copy.parentFolder.name,saved:false});
 }catch(error){try{write({error:String(error)});}catch(_){} }
})();
