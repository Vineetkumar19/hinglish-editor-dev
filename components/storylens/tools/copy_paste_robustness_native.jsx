/* Bounded AE validation fixture. Owner compositions are read only. No save/render. */
(function(){
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/model.js'));
 var label='Storylens Copy Safety Review',folder=null,master=null,holder=null,i,created=false;
 for(i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem&&it.name===label)master=it;}
 if(!master){
  var first=SLCopyPaste.item(24598),second=SLCopyPaste.item(24599);
  if(!(first instanceof FootageItem)||!(second instanceof FootageItem))throw Error('The isolated check sources are unavailable.');
  app.beginUndoGroup('Storylens isolated Copy safety check');
  try{
   folder=app.project.items.addFolder('Storylens Copy Safety Check');
   holder=app.project.items.addComp('Image 1 - safety check',640,360,1,3,30);holder.parentFolder=folder;
   var a=holder.layers.add(first),b=holder.layers.add(second);a.name='0001';b.name='0002';
   a.property('ADBE Transform Group').property('ADBE Scale').setValue([4,4]);b.property('ADBE Transform Group').property('ADBE Scale').setValue([4,4]);
   master=app.project.items.addComp(label,640,360,1,3,30);master.parentFolder=folder;
   var target=master.layers.add(holder);target.name='Ambiguous picture holder';target.selected=true;master.openInViewer();created=true;
  }finally{app.endUndoGroup();}
 }
 holder=master.layer(1).source;
 var owner=SLCopyPaste.item(24543),ownerLayer=null,original=SLCopyPaste.item(24516);
 for(i=1;i<=owner.numLayers;i++)if(owner.layer(i).id===24556)ownerLayer=owner.layer(i);
 var scan=null,problem=null;
 try{scan=SLCopyPasteModel.scan(SLCopyPaste.graph(holder),holder.id);}catch(e){problem={code:e.code,message:e.message};}
 var data={fixture_created:created,project_items:app.project.numItems,fixture:{comp:master.id,layer:master.layer(1).id,source:holder.id,layers:holder.numLayers,comment:master.layer(1).comment,scan:scan,problem:problem},owner:{comp:owner.id,source:ownerLayer.source.id,comment:ownerLayer.comment,original_layers:original.numLayers,original_source:original.layer(1).source.id},history_length:SLCopyPaste.history?SLCopyPaste.history.length:0};
 var file=new File('D:/Full Drive/remove silence/output/copy-paste-evidence/robustness-native-state.json');file.encoding='UTF-8';file.open('w');file.write(SLCopyPaste.json(data));file.close();
})();
