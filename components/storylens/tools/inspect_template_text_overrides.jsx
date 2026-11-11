(function(){var root='D:/Full Drive/remove silence/',report={rows:[]};
function write(){var f=new File(root+'output/template-text-repair/override-diagnostics.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(report));f.close();}
try{$.evalFile(new File(root+'editor_plugins/template-text/host.jsx'));
 var comp=app.project.itemByID(24516),top=null;for(var i=1;i<=comp.numLayers;i++)if(String(comp.layer(i).id)==='65712')top=comp.layer(i);
 var visited={};function walk(c,path){if(visited[c.id])return;visited[c.id]=true;for(var j=1;j<=c.numLayers;j++){var l=c.layer(j),ep=l.property('ADBE Layer Overrides');
  function inspect(g,prefix){if(!g)return;for(var k=1;k<=g.numProperties;k++){var p=g.property(k);if(p.numProperties){inspect(p,prefix+'/'+p.name);continue;}try{var v=p.value;if(!(v instanceof TextDocument))continue;var src=p.essentialPropertySource,owner=src?src.propertyGroup(src.propertyDepth):null;report.rows.push({path:path.concat([j]).join('/'),name:prefix+'/'+p.name,text:v.text,sourceMatch:src?src.matchName:null,sourceText:src?String(src.value.text):null,sourceLayer:owner?owner.index:null,sourceComp:owner&&owner.containingComp?String(owner.containingComp.id):null,sourceCompName:owner&&owner.containingComp?owner.containingComp.name:null,pull:typeof p.pullFromSource});}catch(e){report.rows.push({name:p.name,error:String(e)});}}}
  inspect(ep,'');if(l.source&&l.source instanceof CompItem)walk(l.source,path.concat([j]));}}
 walk(top.source,[]);report.ok=true;
}catch(e){report.error=String(e);}write();})();
