/* Read-only inventory for the authorized recovery project. */
(function(){var base='D:/Full Drive/remove silence/',out={ok:false,templates:[]};try{
 if(!app.project.file||app.project.file.fsName.indexOf('Storylens recovery')<0)throw Error('Recovery required.');
 $.evalFile(new File(base+'editor_plugins/copy-paste/model.js'));$.evalFile(new File(base+'editor_plugins/copy-paste/host.jsx'));
 var c=app.project.itemByID(24516);if(!c)throw Error('Master unavailable.');
 for(var i=1;i<=c.numLayers;i++){var l=c.layer(i);if(!(l.source instanceof CompItem))continue;var g=SLCopyPaste.graph(l.source,true),reuse=SLCopyPaste.reusable({comp:c,layer:l,root:l.source},g),count=0,kept=0,three=0;
 for(var id in g)if(g.hasOwnProperty(id)){count++;if(reuse[id])kept++;var child=app.project.itemByID(Number(id));for(var k=1;k<=child.numLayers;k++)if(child.layer(k).threeDLayer)three++;}
 out.templates.push({layer:l.id,root:l.source.id,name:l.source.name,comps:count,reusable:kept,threeD:three});
 }out.ok=true;out.items=app.project.numItems;
}catch(e){out.error=String(e);out.line=e.line;}var f=new File(base+'output/copy-paste-evidence/scroll-speed/private-inventory.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(out));f.close();})();
