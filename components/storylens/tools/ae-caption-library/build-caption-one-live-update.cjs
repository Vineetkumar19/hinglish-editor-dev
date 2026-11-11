// Owner-authorized isolated live review. Does not save or replace owner compositions.
const fs=require('fs'),path=require('path'),model=require('../../editor_plugins/caption-patterns/model.cjs');
const base=path.resolve('output/caption-one-native-live-20261029'),job='bf7a0636b61d2754b422a6763e958fb9';
const reviewId=require('crypto').randomBytes(10).toString('hex'),resultFile='native-review-'+reviewId+'.json';
fs.writeFileSync(path.join(base,'review-invocation.json'),JSON.stringify({reviewId,resultFile}));
const saved=require('../../editor_plugins/caption-patterns/bridge.cjs').savedWords(process.cwd(),path.resolve('output/captions/ae-speech',job));
const plan=model.prepare({script:saved.caption_script,words:saved.words,duration:saved.duration});
fs.writeFileSync(path.join(base,'revised-plan.json'),JSON.stringify(plan,null,2));
const source=fs.readFileSync('editor_plugins/caption-patterns/geometry.jsx','utf8')+'\n'+fs.readFileSync('editor_plugins/caption-patterns/engine.jsx','utf8')+'\n'+`(function(){
 var base=${JSON.stringify(base.replace(/\\/g,'/'))},plan=${JSON.stringify(plan)},target=null,scenes=[],original=[],common=1,opened=false;
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function write(name,v){var f=new File(base+'/'+name);f.encoding='UTF-8';if(!f.open('w'))throw Error('Cannot write native review');f.write(hJSON(v));f.close();}
 function snapshot(p){var keys=[];for(var k=1;k<=p.numKeys;k++)keys.push({time:p.keyTime(k),value:p.keyValue(k)});return {property:p,value:p.value,keys:keys};}
 function restore(o){var p=o.property;while(p.numKeys)p.removeKey(p.numKeys);if(o.keys.length)for(var k=0;k<o.keys.length;k++)p.setValueAtTime(o.keys[k].time,o.keys[k].value);else p.setValue(o.value);}
 try{
  if(!app.project||!app.project.file||app.project.file.fsName!==new File('D:/AE mere edited files/captions.aep').fsName)throw Error('Return to the original caption project.');
  for(var i=1;i<=app.project.numItems;i++)if(app.project.item(i) instanceof CompItem&&String(app.project.item(i).id)==='594')target=app.project.item(i);
  if(!target)throw Error('The isolated test composition is unavailable.');
  for(var pi=0;pi<plan.pages.length;pi++){
   var page=plan.pages[pi],c=null,outer=null;
   for(i=1;i<=target.numLayers;i++){var candidate=target.layer(i);if(candidate.source instanceof CompItem&&candidate.source.comment===('Storylens caption pattern caption_1_ae_v1 '+page.pattern_id+' slots '+page.source_start)&&candidate.source.parentFolder.comment.indexOf('Storylens AE Caption 1 ${job} ')===0){c=candidate.source;outer=candidate;break;}}
   if(!c)throw Error('A generated caption changed before the correction.');
   var texts=[];for(var wi=0;wi<page.words.length;wi++){var w=page.words[wi],l=null;for(i=1;i<=c.numLayers;i++)if(c.layer(i).comment.indexOf('Source word '+w.index+';')===0){l=c.layer(i);break;}if(!l)throw Error('Editable source word missing');if(l.property('ADBE Text Properties').property('ADBE Text Document').value.text!==w.text)throw Error('An owner word was edited; preserve it before updating.');texts.push(l);}
   scenes.push({page:page,comp:c,texts:texts,outer:outer});
  }
  app.beginUndoGroup('Caption 1 - readable gaps and word entrances');opened=true;
  try{
   for(pi=0;pi<scenes.length;pi++){var scene=scenes[pi];page=scene.page;scene.metrics=[];for(wi=0;wi<page.words.length;wi++){w=page.words[wi];l=scene.texts[wi];var prop=l.property('ADBE Text Properties').property('ADBE Text Document'),doc=prop.value,properties=[];var names=['ADBE Position','ADBE Anchor Point','ADBE Scale','ADBE Opacity','ADBE Rotate Z'];for(i=0;i<names.length;i++)properties.push(snapshot(tr(l,names[i])));original.push({layer:l,doc:doc,properties:properties});doc.fontSize=w.size*target.width/720;doc.horizontalScale=1;doc.verticalScale=1;prop.setValue(doc);scene.metrics.push(l.sourceRectAtTime(0,false));}common=Math.min(common,$.global.StorylensCaptionGeometry.layout(page,scene.metrics,target.width,target.height).fit);}
   var audit=[],words=0;
   for(pi=0;pi<scenes.length;pi++){scene=scenes[pi];page=scene.page;var geometry=$.global.StorylensCaptionGeometry.layout(page,scene.metrics,target.width,target.height,common);for(wi=0;wi<page.words.length;wi++){l=scene.texts[wi];var rect=scene.metrics[wi],position=geometry.words[wi];tr(l,'ADBE Anchor Point').setValue([rect.left+rect.width/2,rect.top+rect.height/2]);tr(l,'ADBE Scale').setValue([common*100,common*100]);$.global.StorylensCaptionPatterns.animate(l,page.words[wi],page,position,target.width/720*common);words++;}audit.push({index:pi,start:page.start,end:page.end,words:page.words,geometry:geometry,metrics:scene.metrics});}
   write('native-motion-spacing-receipt.json',{ok:true,revision:${model.profile.layout_revision},review_id:'${reviewId}',precomps:scenes.length,words:words,common_scale:common,main_font_px:56*target.width/720*common,support_font_px:32*target.width/720*common,owner_project_saved:false,original_comp_untouched:true,pages:audit});
  }catch(e){for(i=original.length-1;i>=0;i--){var o=original[i];try{o.layer.property('ADBE Text Properties').property('ADBE Text Document').setValue(o.doc);for(var k=0;k<o.properties.length;k++)restore(o.properties[k]);}catch(ignore){}}throw e;}finally{app.endUndoGroup();opened=false;}
  var folder=new Folder(base+'/motion-frames');folder.create();var frames=[];
  for(i=0;i<=18;i++){var t=i/30,file=new File(folder.fsName+'/opening-'+('000'+i).slice(-3)+'.png');target.saveFrameToPng(t,file);frames.push({time:t,path:file.fsName});}
  var seen={};for(pi=0;pi<plan.pages.length;pi++){page=plan.pages[pi];if(seen[page.pattern_id])continue;seen[page.pattern_id]=true;t=Math.max(page.start,Math.min(page.end-.02,page.words[page.words.length-1].end));file=new File(folder.fsName+'/settled-'+page.pattern_id+'.png');target.saveFrameToPng(t,file);frames.push({time:t,path:file.fsName,pattern:page.pattern_id});}
  var footage=target.layer(target.numLayers),wasEnabled=footage.enabled;
  try{footage.enabled=true;target.saveFrameToPng(1,new File(folder.fsName+'/over-owner-footage.png'));}finally{footage.enabled=wasEnabled;}
  target.time=0;target.openInViewer();var result={ok:true,review_id:'${reviewId}',frames:frames,source_enabled_preserved:footage.enabled===wasEnabled};write('native-motion-frames.json',result);write('${resultFile}',result);
 }catch(e){if(opened)try{app.endUndoGroup();}catch(ignore){}var error={ok:false,review_id:'${reviewId}',error:String(e),line:e.line};write('native-motion-spacing-error.json',error);write('${resultFile}',error);}
})();`;
fs.writeFileSync(path.join(base,'apply-readable-sizes.jsx'),source);
require('../motion-engines-runtime/node_modules/acorn').parse(source,{ecmaVersion:3});console.log('Prepared guarded update for 31 existing Caption 1 precomps; ES3 syntax passed.');
