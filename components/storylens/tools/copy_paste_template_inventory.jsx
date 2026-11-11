/* Read-only template inventory. No composition edits, selections, save or render. */
(function(){
 var before=app.project.revision,count=app.project.numItems,result={read_only:true,templates:[]};
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/model.js'));
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/host.jsx'));
 try{
  var master=SLCopyPaste.targetRef?SLCopyPaste.item(SLCopyPaste.targetRef.comp):null,i,j;
  if(!(master instanceof CompItem)){for(i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem&&it.name==='Comp 1'){master=it;break;}}}
  if(!(master instanceof CompItem))throw Error('Main template timeline unavailable.');
  result.master={id:master.id,name:master.name};result.project=app.project.file?app.project.file.fsName:'';
  for(i=1;i<=master.numLayers;i++){
   var layer=master.layer(i),root=layer.source;if(!(root instanceof CompItem))continue;
   var row={layer:layer.id,index:i,name:layer.name,source:root.id,folder:root.parentFolder.name,comment:layer.comment};result.templates.push(row);
   try{row.graph=SLCopyPaste.graph(root,true);
    for(var id in row.graph)if(row.graph.hasOwnProperty(id)){var c=SLCopyPaste.item(id);row.graph[id].width=c.width;row.graph[id].height=c.height;
     for(j=0;j<row.graph[id].layers.length;j++){var r=row.graph[id].layers[j],l=c.layer(r.index),s=l.source;r.out=l.outPoint;r.adjustment=!!l.adjustmentLayer;r.guide=!!l.guideLayer;r.matte=!!l.isTrackMatte;r.width=s.width;r.height=s.height;if(s instanceof FootageItem&&s.file)r.file=s.file.fsName;}
    }
    try{row.scan=SLCopyPasteModel.scan(row.graph,root.id);}catch(e){row.failure={code:e.code,message:String(e.message||e),details:e.details};}
   }catch(e){row.failure={message:String(e.message||e)};}
  }
 }catch(e){result.error=String(e.message||e);}
 result.items_before=count;result.items_after=app.project.numItems;result.revision_before=before;result.revision_after=app.project.revision;
 var file=new File('D:/Full Drive/remove silence/output/copy-paste-evidence/scroll-template-inventory.json');file.encoding='UTF-8';file.open('w');file.write(SLCopyPaste.json(result));file.close();
})();
