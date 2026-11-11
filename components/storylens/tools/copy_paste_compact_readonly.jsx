(function(){
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/model.js'));
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/host.jsx'));
 var comps=[],media=[],i,j,it,l;
 for(i=1;i<=app.project.numItems;i++) {it=app.project.item(i);if(it instanceof FootageItem)media.push(it.id);if(it instanceof CompItem&&(it.selectedLayers.length||it===app.project.activeItem)){var layers=[];for(j=1;j<=it.numLayers;j++){l=it.layer(j);layers.push({id:l.id,index:j,name:l.name,selected:l.selected,source:l.source?l.source.id:null,comment:l.comment});}comps.push({id:it.id,name:it.name,layers:layers});}}
 var data={project:app.project.file?app.project.file.fsName:null,revision:app.project.revision,item_count:app.project.numItems,media_ids:media,clipboard:SLCopyPaste.clipboard,history:(SLCopyPaste.history||[]).length,target:SLCopyPaste.targetRef,comps:comps};
 var file=new File('D:/Full Drive/remove silence/output/copy-paste-evidence/compact-direct-native-'+String((SLCopyPaste.history||[]).length)+'.json');file.encoding='UTF-8';file.open('w');file.write(SLCopyPaste.json(data));file.close();
})();
