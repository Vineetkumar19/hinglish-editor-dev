(function(){
 $.evalFile(new File(Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/host.jsx'));
 var roots=[];
 for(var i=1;i<=app.project.rootFolder.numItems;i++){
  var folder=app.project.rootFolder.item(i);if(!(folder instanceof FolderItem)||folder.name==='Untitled 1')continue;
  var comps=[];
  function walk(f){for(var j=1;j<=f.numItems;j++){
   var item=f.item(j);if(item instanceof FolderItem)walk(item);else if(item instanceof CompItem){
    var layers=[];for(var k=1;k<=Math.min(item.numLayers,6);k++){var l=item.layer(k);layers.push({name:l.name,source:l.source?l.source.name:null});}
    comps.push({id:item.id,name:item.name,duration:item.duration,width:item.width,height:item.height,numLayers:item.numLayers,usedBy:(item.usedIn||[]).length,layers:layers});
   }
  }}walk(folder);
  comps.sort(function(a,b){return SLTemplateModel.rank(b,folder.name)-SLTemplateModel.rank(a,folder.name);});
  roots.push({id:folder.id,name:folder.name,candidates:comps.slice(0,8)});
 }
 roots.sort(function(a,b){return SLTemplateAlinerModel.natural(a.name,b.name);});
 var out=new File('D:/Full Drive/remove silence/output/template-aliner-evidence/imported-main-compositions.json');out.encoding='UTF-8';out.open('w');out.write(hJSON({read_only:true,folders:roots}));out.close();
})();
