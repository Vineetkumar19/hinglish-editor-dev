(function(){
 function j(v){if(v===null||typeof v==='undefined')return 'null';if(typeof v==='string')return '"'+v.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t')+'"';if(typeof v!=='object')return String(v);var a=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)a.push(j(v[k]));return '['+a.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))a.push(j(k)+':'+j(v[k]));return '{'+a.join(',')+'}';}
 var graph={},roots=[],seen={},media=[],before=app.project.numItems;
 function walk(c){if(seen[c.id])return;seen[c.id]=true;var ls=[];graph[c.id]={id:c.id,name:c.name,width:c.width,height:c.height,duration:c.duration,fps:c.frameRate,layers:ls};
  for(var k=1;k<=c.numLayers;k++){var l=c.layer(k),s=l.source;if(!s)continue;var kind=s instanceof CompItem?'comp':s instanceof FootageItem?'media':'other';
   ls.push({index:k,id:l.id,name:l.name,source:s.id,sourceName:s.name,kind:kind,start:l.inPoint,enabled:l.enabled,solid:kind==='media'&&s.mainSource instanceof SolidSource,missing:kind==='media'&&s.footageMissing,path:kind==='media'&&s.file?s.file.fsName:null});if(kind==='comp')walk(s);}
 }
 for(var i=1;i<=app.project.numItems;i++){var it=app.project.item(i);if(it instanceof CompItem&&(it.id===24543||it===app.project.activeItem)){roots.push(it.id);walk(it);}if(it instanceof FootageItem&&it.file&&it.hasVideo&&media.length<100){var p=it.parentFolder;while(p&&p!==app.project.rootFolder){if(p.name==='Images'){media.push({id:it.id,name:it.name,path:it.file.fsName});break;}p=p.parentFolder;}}}
 var f=new File('D:/Full Drive/remove silence/output/copy-paste-evidence/inventory.json');f.encoding='UTF-8';f.open('w');f.write(j({read_only:true,project:app.project.file?app.project.file.fsName:'',roots:roots,comps:graph,media:media,item_count_before:before,item_count_after:app.project.numItems}));f.close();
})();
