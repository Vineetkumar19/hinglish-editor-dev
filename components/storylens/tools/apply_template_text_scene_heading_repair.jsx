/* Owner-authorized full native pass; saved real local-model decisions, no benchmark cutoff. */
(function(){var root='D:/Full Drive/remove silence',started=new Date().getTime(),report={phase:'starting'},comp=null;
 function save(){report.total_ms=new Date().getTime()-started;var f=new File(root+'/output/template-text-repair/scene-heading-native-progress.json');f.encoding='UTF-8';if(f.open('w')){f.write(JSON.stringify(report));f.close();}}
 function read(path){var f=new File(path);f.encoding='UTF-8';if(!f.open('r'))throw Error('Saved full plan unavailable');var s=f.read();f.close();return JSON.parse(s);}
 try{save();$.evalFile(new File(root+'/editor_plugins/after-effects-cep/jsx/host.jsx'));$.evalFile(new File(root+'/editor_plugins/shared/aftereffects-panel.jsx'));$.evalFile(new File(root+'/editor_plugins/template-text/model.js'));$.evalFile(new File(root+'/editor_plugins/template-text/host.jsx'));
  var seed=read(root+'/output/template-text-repair/scene-heading-native-seed.json'),plan=seed.plan;comp=SLTemplateText.item(plan.composition_id);if(!comp)throw Error('Open the prepared full recovery composition.');comp.openInViewer();report.composition_id=String(comp.id);report.duration=comp.duration;report.items_before=app.project.numItems;report.phase='validating';save();
  SLTemplateText.progress=function(value){report.native=value;report.phase=value.stage;save();};
  report.result=SLTemplateText.apply({plan:plan});report.phase='auditing';save();
  var audit={checked:0,hidden:0,headings:[],failures:[],originals_checked:0},roots={},checked={};
  for(var i=1;i<=comp.numLayers;i++)roots[String(comp.layer(i).id)]=comp.layer(i);
  function locate(c,path){var parts=path.split('/'),l,on=true;for(var n=0;n<parts.length;n++){l=c.layer(Number(parts[n]));on=on&&(l.enabled||l.isTrackMatte)&&!l.guideLayer;if(!on&&n<parts.length-1)return {layer:l,visible:false};if(n<parts.length-1)c=l.source;}return {layer:l,visible:on};}
  function longest(p){var text=String(p.valueAtTime(0,true).text);for(var k=1;k<=p.numKeys;k++){var next=String(p.keyValue(k).text);if(next.length>text.length)text=next;}return text;}
  for(i=0;i<plan.actions.length;i++){var action=plan.actions[i],found=locate(roots[action.template_layer_id].source,action.text_id);audit.checked++;
   if(action.action==='hide'){if(found.visible)audit.failures.push('Still visible: '+action.template_layer_id+'/'+action.text_id);else audit.hidden++;}
   else{var p=SLTemplateText.text(found.layer),text=p?longest(p):'';audit.headings.push({text:text,expected:action.text,enabled:found.visible,template_layer_id:action.template_layer_id,text_id:action.text_id,runs:seed.heading_runs[action.template_layer_id+'/'+action.text_id]||[]});if(!found.visible)audit.failures.push('Heading not visible: '+action.text);else if(text!==action.text)audit.failures.push('Heading differs: '+action.text);}
  }
  for(i=0;i<seed.originals.length;i++){var row=seed.originals[i],source=SLTemplateText.item(row.comp_id),old=source.layer(row.layer_index),p=SLTemplateText.text(old);audit.originals_checked++;if(longest(p)!==row.text||old.enabled!==row.enabled)audit.failures.push('Original changed: '+row.comp_id+'/'+row.layer_index);}
  report.audit=audit;report.phase=audit.failures.length?'needs_review':'complete';report.items_after=app.project.numItems;save();
  if(audit.headings.length&&audit.headings[0].runs.length){var interval=audit.headings[0].runs[0];comp.time=(interval.start+interval.end)/2;}comp.openInViewer();
 }catch(e){report.phase='failed';report.error=String(e);report.details=e.details||'';save();}
 finally{SLTemplateText.progress=null;report.items_after=app.project.numItems;save();}
})();
