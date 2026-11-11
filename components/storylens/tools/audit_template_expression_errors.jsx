(function(){
 $.evalFile(new File(Folder.userData.fsName+'/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/host.jsx'));
 var comp=app.project.activeItem,rows=[],seen={};
 function walkProperty(group,compName,layerName,path){
  for(var k=1;k<=group.numProperties;k++){
   var prop=group.property(k),name=path+'/'+prop.name;
   try{if(prop.canSetExpression&&prop.expression&&prop.expressionError)rows.push({comp:compName,layer:layerName,property:name,error:prop.expressionError});}catch(_){}
   if(prop.numProperties)walkProperty(prop,compName,layerName,name);
  }
 }
 function walk(c){if(seen[c.id])return;seen[c.id]=true;for(var i=1;i<=c.numLayers;i++){var l=c.layer(i);walkProperty(l,c.name,l.name,'');if(l.source instanceof CompItem)walk(l.source);}}
 if(!(comp instanceof CompItem)||comp.name!=='rcb final - Template Aliner check')throw Error('Open the labelled review composition.');
 walk(comp);
 var f=new File('D:/Full Drive/remove silence/output/template-fonts/native-expression-findings.json');f.encoding='UTF-8';f.open('w');f.write(hJSON({errors:rows,read_only:true}));f.close();
})();
