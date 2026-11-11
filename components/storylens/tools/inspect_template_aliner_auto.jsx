(function(){
 // Read-only native evidence: all imported folder graphs, no timeline mutation.
 $.evalFile(new File(Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/host.jsx'));
 var all=[],root=app.project.rootFolder;
 for(var f=1;f<=root.numItems;f++){
  var folder=root.item(f);if(!(folder instanceof FolderItem))continue;
  var comps=[],ids={};
  function walk(dir){for(var i=1;i<=dir.numItems;i++){var item=dir.item(i);if(item instanceof FolderItem)walk(item);else if(item instanceof CompItem){comps.push(item);ids[item.id]=true;}}}
  walk(folder);if(!comps.length)continue;
  function descendants(comp,seen){if(seen[comp.id])return 0;seen[comp.id]=true;var total=0;for(var k=1;k<=comp.numLayers;k++){var child=comp.layer(k).source;if(child instanceof CompItem&&ids[child.id]&&!seen[child.id])total+=1+descendants(child,seen);}return total;}
  var rows=[];for(var j=0;j<comps.length;j++){
   var comp=comps[j],users=comp.usedIn||[],used=0;for(var u=0;u<users.length;u++)if(ids[users[u].id])used++;
   rows.push({id:comp.id,name:comp.name,width:comp.width,height:comp.height,duration:comp.duration,numLayers:comp.numLayers,usedBy:used,descendants:descendants(comp,{})});
  }
  var answer=SLTemplateAlinerModel.choose(rows,folder.name,{width:1920,height:1080});
  all.push({folder_id:folder.id,folder:folder.name,selected:answer.selected,ranked:answer.comps.slice(0,5),candidate_count:rows.length});
 }
 var file=new File('D:/Full Drive/remove silence/output/template-aliner-evidence/automatic-selection-native.json');file.encoding='UTF-8';file.open('w');file.write(hJSON({read_only:true,project:storylensProjectId(),folders:all}));file.close();
})();
