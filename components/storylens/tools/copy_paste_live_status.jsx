(function(){
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/model.js'));
 $.evalFile(new File('D:/Full Drive/remove silence/editor_plugins/copy-paste/host.jsx'));
 var before=app.project.revision,out={revision:before,selected:[],templates:[],history:[]},master=null,i;
 for(i=1;i<=app.project.numItems;i++){var c=app.project.item(i);if(c instanceof CompItem&&c.name==='Comp 1')master=c;}
 for(i=0;i<app.project.selection.length;i++){var a=app.project.selection[i];out.selected.push({id:a.id,name:a.name});}
 if(master){out.playhead=master.time;for(i=1;i<=master.numLayers;i++){var l=master.layer(i);if(!(l.source instanceof CompItem))continue;var t={comp:master,layer:l,root:l.source},row={layer:l.id,name:l.name,source:l.source.id,selected:l.selected};out.templates.push(row);try{var r=SLCopyPaste.read(t);row.total=r.scan.slots.length;row.next=r.next;row.first=r.scan.slots.length?r.scan.slots[0].name:null;}catch(e){row.error=String(e.message||e);}}}
 var h=SLCopyPaste.history||[];for(i=0;i<h.length;i++){var v=h[i];out.history.push({layer:v.layer.id,root:v.root.id,title:v.title,comment:v.comment,current: v.layer.source===v.root&&String(v.layer.comment)===v.comment});}
 out.revision_after=app.project.revision;var f=new File('D:/Full Drive/remove silence/output/copy-paste-evidence/live-template-status.json');f.open('w');f.write(SLCopyPaste.json(out));f.close();
})();
