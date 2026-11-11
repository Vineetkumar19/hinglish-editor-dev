/* Read-only native load/scan diagnostic. No edits, imports, saves or renders. */
(function(){
 var root='D:/Full Drive/remove silence',file=new File(root+'/output/template-text-repair/native-scan.json'),report={phase:'begin',version:app.version,errors:[]},started=new Date().getTime();
 function quote(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t')+'"';}
 function json(v){if(v===null||typeof v==='undefined')return 'null';if(typeof v==='string')return quote(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var out=[],k;if(v instanceof Array){for(k=0;k<v.length;k++)out.push(json(v[k]));return '['+out.join(',')+']';}for(k in v)if(v.hasOwnProperty(k))out.push(quote(k)+':'+json(v[k]));return '{'+out.join(',')+'}';}
 function save(){report.elapsed_ms=new Date().getTime()-started;file.encoding='UTF-8';if(file.open('w')){file.write(json(report));file.close();}}
 try{
  report.phase='loading-model';save();$.evalFile(new File(root+'/editor_plugins/template-text/model.js'));
  report.phase='loading-host';save();$.evalFile(new File(root+'/editor_plugins/template-text/host.jsx'));
  report.phase='loaded';report.json_available=typeof JSON;report.null_is_comp=(null instanceof CompItem);report.undefined_is_comp=((void 0) instanceof CompItem);report.items_before=app.project.numItems;report.revision_before=app.project.revision;report.project=app.project.file?app.project.file.fsName:'';save();
  var comp=app.project.activeItem;
  if(!(comp instanceof CompItem)){var matches=[];for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(item instanceof CompItem&&item.name==='rcb final')matches.push(item);}if(matches.length===1)comp=matches[0];}
  if(!(comp instanceof CompItem))throw Error('No unique final composition to scan.');
  report.composition=comp.name;report.roots=[];for(var ri=1;ri<=comp.numLayers;ri++){var rl=comp.layer(ri),rs=rl.source;report.roots.push({name:rl.name,enabled:rl.enabled,source_type:typeof rs,source_bool:!!rs,is_comp:rs instanceof CompItem,source_name:rs?rs.name:'',source_layers:rs&&rs instanceof CompItem?rs.numLayers:0});}report.phase='scanning';save();
  var has=SLTemplateText.textIndex(),checks=[],baseText=SLTemplateText.text,reads=0,hits=0;
  SLTemplateText.text=function(l){reads++;var p=baseText(l);if(p)hits++;return p;};
  for(var ci=1;ci<=comp.numLayers;ci++){var src=comp.layer(ci).source;if(!src||!(src instanceof CompItem))continue;checks.push({name:src.name,id:src.id,index:has(src),reads:reads,hits:hits});}
  SLTemplateText.text=baseText;report.index_checks=checks;save();
  var snapshot=SLTemplateText.scan(comp),target=new File(root+'/output/template-text-repair/native-snapshot.json');target.encoding='UTF-8';if(target.open('w')){target.write(json(snapshot));target.close();}
  report.phase='complete';report.templates=snapshot.templates.length;report.texts=0;for(var j=0;j<snapshot.templates.length;j++)report.texts+=snapshot.templates[j].texts.length;report.audio=snapshot.audio.length;report.warnings=snapshot.warnings;
 }catch(e){report.errors.push({message:String(e),line:e.line,file:e.fileName,stack:$.stack});report.phase='failed';}
 report.items_after=app.project.numItems;report.revision_after=app.project.revision;save();
})();
