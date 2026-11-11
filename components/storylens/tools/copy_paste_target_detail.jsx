(function(){
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/model.js'));
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/host.jsx'));
 var out={revision:app.project.revision,selected:[],comps:[]},ids=[50112,50154,81570,54379,53829,52990],i,j;
 for(i=0;i<app.project.selection.length;i++){var a=app.project.selection[i];out.selected.push({id:a.id,name:a.name});}
 for(i=0;i<ids.length;i++){var c=SLCopyPaste.item(ids[i]);if(!(c instanceof CompItem))continue;var row={id:c.id,name:c.name,folder:c.parentFolder.name,layers:[]};out.comps.push(row);
 for(j=1;j<=c.numLayers;j++){var l=c.layer(j),s=l.source,r={index:j,name:l.name,enabled:l.enabled,guide:l.guideLayer,adjust:l.adjustmentLayer,matte:l.isTrackMatte};if(s){r.source=s.name;r.id=s.id;r.folder=s.parentFolder.name;r.solid=s instanceof FootageItem&&s.mainSource instanceof SolidSource;}try{r.text=l.property('ADBE Text Properties').property('ADBE Text Document').value.text;}catch(_){}row.layers.push(r);}}
 out.revision_after=app.project.revision;var f=new File('D:/Full Drive/remove silence/output/copy-paste-evidence/target-detail.json');f.open('w');f.write(SLCopyPaste.json(out));f.close();
})();
