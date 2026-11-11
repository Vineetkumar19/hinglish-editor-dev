/* Read-only verification of the completed recovery-project text pass. */
(function () {
 var root='D:/Full Drive/remove silence',job='780d11d9727747eea2d41262';
 $.evalFile(new File(root+'/editor_plugins/template-text/model.js'));
 $.evalFile(new File(root+'/editor_plugins/template-text/host.jsx'));
 function read(path){var f=new File(path);f.encoding='UTF-8';if(!f.open('r'))throw Error('Audit input unavailable');var s=f.read();f.close();return JSON.parse(s);}
 var plan=read(root+'/output/template-text/'+job+'/plan.json'),request=read(root+'/output/template-text/'+job+'/request.json');
 var result={job:job,project:app.project.file.fsName,checked:0,hidden:0,headings:[],failures:[],originals_checked:0,items:app.project.numItems};
 function item(id){for(var i=1;i<=app.project.numItems;i++)if(String(app.project.item(i).id)===String(id))return app.project.item(i);return null;}
 function locate(c,path){var parts=path.split('/'),l;for(var n=0;n<parts.length;n++){l=c.layer(Number(parts[n]));if(n<parts.length-1)c=l.source;}return l;}
 var comp=item(plan.composition_id),roots={};
 for(var i=1;i<=comp.numLayers;i++)roots[String(comp.layer(i).id)]=comp.layer(i);
 for(i=0;i<plan.actions.length;i++){
  var a=plan.actions[i],l=locate(roots[a.template_layer_id].source,a.text_id),p=SLTemplateText.text(l);result.checked++;
  if(a.action==='hide'){if(l.enabled)result.failures.push('Still visible: '+a.template_layer_id+'/'+a.text_id);else result.hidden++;}
  else{var text=String(p.value.text);result.headings.push({text:text,expected:a.text,enabled:l.enabled,layer:l.name,source:l.containingComp.name});if(l.enabled&&text!==a.text)result.failures.push('Heading differs: '+a.text);}
 }
 for(i=0;i<request.snapshot.templates.length;i++){
  var t=request.snapshot.templates[i],source=item(t.source_id);
  for(var j=0;j<t.texts.length;j++){var row=t.texts[j],ol=locate(source,row.id),op=SLTemplateText.text(ol);if(!op.numKeys&&!op.expressionEnabled){result.originals_checked++;if(String(op.value.text)!==row.text||ol.enabled!==row.current_enabled)result.failures.push('Original changed: '+t.layer_id+'/'+row.id);}}
 }
 var out=new File(root+'/output/template-text-repair/native-applied-audit.json');out.encoding='UTF-8';if(out.open('w')){out.write(JSON.stringify(result));out.close();}
})();
