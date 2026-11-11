(function(){
 var names=['Collapse All Folders','Collapse Folders','Close All Folders','Close Folders','Expand or Collapse','Expand/Collapse','Expand All Folders','Project','Find','Deselect All'],rows=[];
 for(var i=0;i<names.length;i++){var id=0;try{id=app.findMenuCommandId(names[i]);}catch(_){}rows.push({name:names[i],id:id});}
 var f=new File('D:/Full Drive/remove silence/output/template-aliner-evidence/folder-command-probe.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(rows));f.close();
})();
