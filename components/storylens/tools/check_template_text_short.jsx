/* Owner-authorized 40%-duration recovery composition; real saved model plan. */
(function(){
 var root='D:/Full Drive/remove silence',job='780d11d9727747eea2d41262',started=new Date().getTime(),report={phase:'starting',job:job},testComp=null;
 function write(name,value){var f=new File(root+'/output/template-text-repair/'+name);f.encoding='UTF-8';if(f.open('w')){f.write(JSON.stringify(value));f.close();}}
 function read(path){var f=new File(path);f.encoding='UTF-8';if(!f.open('r'))throw Error('Saved input unavailable');var s=f.read();f.close();return JSON.parse(s);}
 function save(){report.elapsed_ms=new Date().getTime()-started;write('short-native-progress.json',report);}
 try{
  $.evalFile(new File(root+'/editor_plugins/after-effects-cep/jsx/host.jsx'));$.evalFile(new File(root+'/editor_plugins/shared/aftereffects-panel.jsx'));
  $.evalFile(new File(root+'/editor_plugins/template-text/model.js'));$.evalFile(new File(root+'/editor_plugins/template-text/host.jsx'));
  var originalPlan=read(root+'/output/template-text/'+job+'/plan.json'),original=SLTemplateText.item(originalPlan.composition_id);
  if(!original||SLTemplateText.scan(original).fingerprint!==originalPlan.fingerprint)throw Error('Original timeline changed; stopped before making the test composition.');
  report.items_before=app.project.numItems;report.original_duration=original.duration;
  var prepared=read(root+'/output/template-text-repair/short-prepared.json');testComp=SLTemplateText.item(prepared.id);
  if(!testComp||Math.abs(testComp.duration-prepared.duration)>.001)throw Error('Trim the prepared test composition to its work area first.');
  testComp.openInViewer();report.composition_id=String(testComp.id);report.duration=testComp.duration;report.phase='scanning short composition';save();
  var snapshot=SLTemplateText.scan(testComp),remap={},allowed={},actions=[];
  for(i=1;i<=original.numLayers;i++)remap[String(original.layer(i).id)]=String(testComp.layer(i).id);
  for(i=0;i<snapshot.templates.length;i++){var t=snapshot.templates[i];for(var k=0;k<t.texts.length;k++)allowed[t.layer_id+'/'+t.texts[k].id]=true;}
  for(i=0;i<originalPlan.actions.length;i++){var a=originalPlan.actions[i],id=remap[a.template_layer_id];if(allowed[id+'/'+a.text_id])actions.push({template_layer_id:id,text_id:a.text_id,action:a.action,text:a.text});}
  var plan={job_id:job+'-short-review',project_id:snapshot.project_id,composition_id:snapshot.composition_id,fingerprint:snapshot.fingerprint,actions:actions};
  report.templates=snapshot.templates.length;report.actions=actions.length;write('short-native-input.json',{snapshot:snapshot,plan:plan,source_job:job,scope:'First 40% of unchanged timeline; existing locally inferred actions filtered by actual visible slots.'});
  SLTemplateText.progress=function(value){report.native=value;report.phase=value.stage;save();if(value.elapsed_ms>180000)throw Error('Short review exceeded three minutes; rolling back staged copies.');};
  report.phase='applying';save();report.result=SLTemplateText.apply({plan:plan});report.phase='complete';save();
 }catch(e){report.phase='failed';report.error=String(e);report.details=e.details||'';save();}
 finally{SLTemplateText.progress=null;report.items_after=app.project.numItems;report.original_duration_after=original?original.duration:null;save();}
})();
