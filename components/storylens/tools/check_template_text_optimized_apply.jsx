/* Bounded native comparison using the saved local model plan; original kept. */
(function(){
 var root='D:/Full Drive/remove silence',started=new Date().getTime(),report={phase:'starting'},original=null,testComp=null;
 function read(path){var f=new File(path);f.encoding='UTF-8';if(!f.open('r'))throw Error('Saved input unavailable');var s=f.read();f.close();return JSON.parse(s);}
 function save(){report.total_ms=new Date().getTime()-started;var f=new File(root+'/output/template-text-repair/optimized-native-progress.json');f.encoding='UTF-8';if(f.open('w')){f.write(JSON.stringify(report));f.close();}}
 try{
  $.evalFile(new File(root+'/editor_plugins/after-effects-cep/jsx/host.jsx'));$.evalFile(new File(root+'/editor_plugins/shared/aftereffects-panel.jsx'));$.evalFile(new File(root+'/editor_plugins/template-text/model.js'));$.evalFile(new File(root+'/editor_plugins/template-text/host.jsx'));
  save();var seed=read(root+'/output/template-text-repair/optimized-native-seed.json'),input=seed.input,full=seed.plan;original=SLTemplateText.item(full.composition_id);
  if(!original)throw Error('Original timeline unavailable; comparison stopped.');
  report.items_before=app.project.numItems;
  testComp=SLTemplateText.item(97215);if(!testComp||Math.abs(testComp.duration-input.snapshot.duration)>.001)throw Error('Comparison composition changed.');testComp.openInViewer();
  report.composition_id=String(testComp.id);report.duration=testComp.duration;report.phase='scanning';save();
  var scanStarted=new Date().getTime(),snapshot=SLTemplateText.scan(testComp),remap={},allowed={},actions=[],i,k;report.scan_ms=new Date().getTime()-scanStarted;
  for(i=0;i<snapshot.templates.length;i++){var live=snapshot.templates[i],saved=null;for(k=0;k<input.snapshot.templates.length;k++)if(input.snapshot.templates[k].source_id===live.source_id)saved=input.snapshot.templates[k];if(!saved||Math.abs(live.start-saved.start)>.001||Math.abs(live.end-saved.end)>.001)throw Error('Placed timing changed; comparison stopped: '+live.source_id+' '+live.start+' '+live.end+' '+(saved?JSON.stringify(saved):'unmatched'));var prior={};for(k=0;k<saved.texts.length;k++)prior[saved.texts[k].id]=input.values[saved.texts[k].ref];for(k=0;k<live.texts.length;k++)if(prior[live.texts[k].id]!==live.texts[k].text)throw Error('Authored text changed; comparison stopped.');}
  var mapping=SLTemplateText.item(seed.mapping_comp_id);for(i=1;i<=mapping.numLayers;i++)remap[String(mapping.layer(i).id)]=String(testComp.layer(i).id);
  for(i=0;i<snapshot.templates.length;i++){var t=snapshot.templates[i];for(k=0;k<t.texts.length;k++)allowed[t.layer_id+'/'+t.texts[k].id]=true;}
  for(i=0;i<full.actions.length;i++){var a=full.actions[i],id=remap[a.template_layer_id];if(allowed[id+'/'+a.text_id])actions.push({template_layer_id:id,text_id:a.text_id,action:a.action,text:a.text});}
  var plan={job_id:full.job_id+'-optimized-review',project_id:snapshot.project_id,composition_id:snapshot.composition_id,fingerprint:snapshot.fingerprint,actions:actions};
  SLTemplateText.progress=function(value){report.native=value;report.phase=value.stage;save();if(value.elapsed_ms>600000)throw Error('Comparison exceeded ten minutes; rolling back staged copies.');};
  report.result=SLTemplateText.apply({plan:plan});report.phase='auditing';save();
  var audit={checked:0,hidden:0,headings:[],failures:[],originals_checked:0},roots={},checked={};
  for(i=1;i<=testComp.numLayers;i++)roots[String(testComp.layer(i).id)]=testComp.layer(i);
  function locate(c,path){var parts=path.split('/'),l,on=true;for(var n=0;n<parts.length;n++){l=c.layer(Number(parts[n]));on=on&&l.enabled;if(!on&&n<parts.length-1)return {layer:l,visible:false};if(n<parts.length-1)c=l.source;}return {layer:l,visible:on};}
  for(i=0;i<actions.length;i++){var action=actions[i],found=locate(roots[action.template_layer_id].source,action.text_id);audit.checked++;
   if(action.action==='hide'){if(found.visible)audit.failures.push('Still visible: '+action.text_id);else audit.hidden++;}
   else{var text=SLTemplateText.text(found.layer);audit.headings.push({text:text?String(text.value.text):'',expected:action.text,enabled:found.visible});if(found.visible&&(!text||String(text.value.text)!==action.text))audit.failures.push('Heading differs: '+action.text);}
  }
  for(i=0;i<snapshot.templates.length;i++){var t=snapshot.templates[i];for(k=0;k<t.texts.length;k++){var row=t.texts[k],key=row.comp_id+'/'+row.layer_id;if(checked[key])continue;checked[key]=true;var old=SLTemplateText.item(row.comp_id).layer(row.layer_index),prop=SLTemplateText.text(old);if(!prop.numKeys&&!prop.expressionEnabled){audit.originals_checked++;if(String(prop.value.text)!==row.text||old.enabled!==row.current_enabled)audit.failures.push('Original changed: '+key);}}}
  report.audit=audit;report.phase='complete';testComp.time=3;testComp.openInViewer();
 }catch(e){report.phase='failed';report.error=String(e);report.details=e.details||'';}
 finally{SLTemplateText.progress=null;report.items_after=app.project.numItems;report.original_duration=original?original.duration:null;save();}
})();

