const fs=require('fs'),path=require('path'),crypto=require('crypto'),model=require('../../editor_plugins/caption-patterns/model.cjs');
const base=path.resolve('output/caption-one-safe-width-20261029'),nonce=crypto.randomBytes(10).toString('hex');
const jobs=[['8148f4080dd39ea045e6e1c7c1cc514b','1142'],['bf7a0636b61d2754b422a6763e958fb9','594']].map(([id,comp])=>{
 const old=JSON.parse(fs.readFileSync(`output/captions/ae-patterns/${id}/plan.json`)).plan,input={script:old.script,duration:old.duration};
 if(old.timing_method==='speech')input.words=old.pages.flatMap(p=>p.words.map(w=>({text:w.source,start:w.start,end:w.end})));
 const plan=model.prepare(input);if(plan.pages.length!==old.pages.length||plan.pages.some((p,i)=>p.source_start!==old.pages[i].source_start||p.words.length!==old.pages[i].words.length))throw Error('The test needs fresh generation because its pagination changed.');
 return {id,comp,old,plan};
});
fs.writeFileSync(path.join(base,'plans.json'),JSON.stringify(jobs,null,2));
const source=fs.readFileSync('editor_plugins/caption-patterns/geometry.jsx','utf8')+'\n'+fs.readFileSync('editor_plugins/caption-patterns/engine.jsx','utf8')+'\n'+`(function(){
 var base=${JSON.stringify(base.replace(/\\/g,'/'))},nonce='${nonce}',jobs=${JSON.stringify(jobs)},scenes=[],old=[],colourStates=[],created=[],opened=false;
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function write(v){var f=new File(base+'/native-'+nonce+'.json');f.encoding='UTF-8';f.open('w');f.write(hJSON(v));f.close();}
 function snapshot(p){var keys=[];for(var k=1;k<=p.numKeys;k++)keys.push({time:p.keyTime(k),value:p.keyValue(k)});return {p:p,value:p.value,keys:keys};}
 function restore(o){while(o.p.numKeys)o.p.removeKey(o.p.numKeys);if(o.keys.length)for(var k=0;k<o.keys.length;k++)o.p.setValueAtTime(o.keys[k].time,o.keys[k].value);else o.p.setValue(o.value);}
 try{
  if(!app.project.file||app.project.file.fsName!==new File('D:/AE mere edited files/captions.aep').fsName)throw Error('Return to the original caption project.');
  for(var ji=0;ji<jobs.length;ji++){var job=jobs[ji],target=null;job.common=1;
   for(var i=1;i<=app.project.numItems;i++)if(app.project.item(i) instanceof CompItem&&String(app.project.item(i).id)===job.comp)target=app.project.item(i);
   if(!target)throw Error('Missing isolated caption review.');job.target=target;
   for(var pi=0;pi<job.plan.pages.length;pi++){var page=job.plan.pages[pi],oldPage=job.old.pages[pi],c=null,outer=null;
    for(i=1;i<=target.numLayers;i++){var candidate=target.layer(i);if(candidate.source instanceof CompItem&&candidate.source.comment===('Storylens caption pattern caption_1_ae_v1 '+oldPage.pattern_id+' slots '+oldPage.source_start)&&String(candidate.source.parentFolder.comment).indexOf('Storylens AE Caption 1 '+job.id+' ')===0){c=candidate.source;outer=candidate;break;}}
    if(!c)throw Error('The generated test caption changed.');var texts=[],colours=[],gradient=null;
    for(var wi=0;wi<page.words.length;wi++){var w=page.words[wi],l=null;for(i=1;i<=c.numLayers;i++)if(String(c.layer(i).comment).indexOf('Source word '+w.index+';')===0){l=c.layer(i);break;}if(!l)throw Error('Editable source word missing');var doc=l.property('ADBE Text Properties').property('ADBE Text Document').value;if(doc.text!==oldPage.words[wi].text)throw Error('An owner word was edited; keep it before applying the review.');texts.push(l);var colour=null;for(i=1;i<=c.numLayers;i++)if(c.layer(i).name.indexOf('Blue gradient - ')===0&&c.layer(i).parent===l){colour=c.layer(i);gradient=colour.source;break;}colours.push(colour);}
    scenes.push({job:job,page:page,comp:c,outer:outer,texts:texts,colours:colours,gradient:gradient});
   }
  }
  var dir=new Folder(base+'/native-frames');dir.create();jobs[0].target.layer(2).source.saveFrameToPng(jobs[0].target.layer(2).source.duration-.02,new File(dir.fsName+'/before-risky.png'));
  app.beginUndoGroup('Caption 1 - measured safe-width packing');opened=true;
  try{
   for(var si=0;si<scenes.length;si++){var scene=scenes[si];page=scene.page;scene.metrics=[];var factor=scene.job.target.width/720;
    for(wi=0;wi<page.words.length;wi++){w=page.words[wi];l=scene.texts[wi];var prop=l.property('ADBE Text Properties').property('ADBE Text Document'),properties=[],names=['ADBE Position','ADBE Anchor Point','ADBE Scale','ADBE Opacity','ADBE Rotate Z'];for(i=0;i<names.length;i++)properties.push(snapshot(tr(l,names[i])));old.push({layer:l,doc:prop.value,comment:l.comment,enabled:l.enabled,properties:properties});doc=prop.value;doc.text=w.text;doc.font=w.font==='bold'?'Inter-Bold':'Inter-Medium';doc.fontSize=w.size*factor;doc.tracking=w.font==='bold'?-81:-98;doc.horizontalScale=1;doc.verticalScale=1;prop.setValue(doc);scene.metrics.push(l.sourceRectAtTime(0,false));}
    scene.job.common=Math.min(scene.job.common,$.global.StorylensCaptionGeometry.layout(page,scene.metrics,scene.job.target.width,scene.job.target.height).fit);
   }
   var report=[];
   for(si=0;si<scenes.length;si++){scene=scenes[si];page=scene.page;target=scene.job.target;factor=target.width/720;var geometry=$.global.StorylensCaptionGeometry.layout(page,scene.metrics,target.width,target.height,scene.job.common);
    for(wi=0;wi<page.words.length;wi++){w=page.words[wi];l=scene.texts[wi];var rect=scene.metrics[wi],position=geometry.words[wi];l.comment='Source word '+w.index+'; fixed '+page.pattern_id+' '+w.row+' slot';tr(l,'ADBE Anchor Point').setValue([rect.left+rect.width/2,rect.top+rect.height/2]);tr(l,'ADBE Scale').setValue([position.scale*100,position.scale*100]);$.global.StorylensCaptionPatterns.animate(l,w,page,position,factor*position.scale);
     colour=scene.colours[wi];if(colour)colourStates.push({layer:colour,enabled:colour.enabled});
     if(w.gradient){if(!colour){if(!scene.gradient)throw Error('Missing owned gradient source');colour=scene.comp.layers.add(scene.gradient);created.push(colour);colour.name='Blue gradient - '+w.text;colour.inPoint=0;colour.outPoint=scene.comp.duration;colour.setTrackMatte(l,TrackMatteType.ALPHA);}$.global.StorylensCaptionPatterns.fitGradient(colour,l);colour.enabled=true;l.enabled=false;}else{if(colour)colour.enabled=false;l.enabled=true;}
    }
    report.push({comp_id:scene.job.comp,index:page.index,pattern:page.pattern_id,words:page.words,geometry:geometry,common_scale:scene.job.common});
   }
  }catch(e){for(i=created.length-1;i>=0;i--)try{created[i].remove();}catch(ignore){}for(i=0;i<colourStates.length;i++)try{colourStates[i].layer.enabled=colourStates[i].enabled;}catch(ignore){}for(i=0;i<old.length;i++)try{var o=old[i];o.layer.property('ADBE Text Properties').property('ADBE Text Document').setValue(o.doc);o.layer.enabled=o.enabled;o.layer.comment=o.comment;for(var k=0;k<o.properties.length;k++)restore(o.properties[k]);}catch(ignore){}throw e;}finally{app.endUndoGroup();opened=false;}
  for(si=0;si<scenes.length;si++){scene=scenes[si];if(scene.job.comp==='1142'||scene.page.index===0||scene.page.index===27)scene.comp.saveFrameToPng(scene.comp.duration-.02,new File(dir.fsName+'/'+scene.job.comp+'-'+scene.page.index+'.png'));}
  var review=jobs[0].target;review.time=8.5;review.openInViewer();write({ok:true,nonce:nonce,updated_precomps:scenes.length,project_saved:false,outer_placement_preserved:true,pages:report});
 }catch(e){if(opened)try{app.endUndoGroup();}catch(ignore){}write({ok:false,nonce:nonce,error:String(e),line:e.line});}
})();`;
require('../motion-engines-runtime/node_modules/acorn').parse(source,{ecmaVersion:3});fs.writeFileSync(path.join(base,'apply-safe-width.jsx'),source);fs.writeFileSync(path.join(base,'invocation.json'),JSON.stringify({nonce,resultFile:'native-'+nonce+'.json'}));console.log('Prepared guarded native safe-width review:',nonce);
