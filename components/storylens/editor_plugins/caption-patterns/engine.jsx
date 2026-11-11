/* Caption 1 fixed native recipes. No project save, render, or renderer change on the owner timeline. */
(function(g){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function context(){var c=app.project&&app.project.activeItem;if(!(c instanceof CompItem))throw Error('Open the composition for your captions first.');return {project_id:storylensProjectId(),comp_id:String(c.id),width:c.width,height:c.height,fps:c.frameRate,duration:c.duration,time:c.time};}
 function timingContext(){
  var target=context(),c=app.project.activeItem,clips=[],unsupported=[];
  for(var i=1;i<=c.numLayers;i++){var l=c.layer(i),s=l.source;if(!l.enabled&&!l.audioEnabled)continue;
   if(s instanceof CompItem){var tag=String(l.comment||''),sourceTag=String(s.comment||'');if(/^Storylens caption pattern caption_[1236]_ae_v1 /.test(sourceTag)||/^(3D1 Camera Precomp|3D2 Surface Precomp|3D3 Surface Precomp)$/.test(tag)||/\[Storylens 3D1 (boost|look|clicks|standout)\]/.test(sourceTag)||s.hasAudio===false)continue;unsupported.push(l.name+': nested footage needs Script duration');continue;}
   if(!s||!(s instanceof FootageItem))continue;if(l.audioEnabled===false||s.hasAudio===false||!s.file||(!s.hasVideo&&!s.hasAudio)||s.mainSource&&s.mainSource.isStill)continue;
   if(l.timeRemapEnabled||l.stretch!==undefined&&l.stretch!==100)unsupported.push(l.name+': speed or time remapping');clips.push({path:s.file.fsName,start:Math.max(0,l.inPoint),end:Math.min(c.duration,l.outPoint),source_in:Math.max(0,Math.max(0,l.inPoint)-l.startTime),kind:s.hasVideo?'video':'audio',track:0,stretch:100});
  }
  return {host:'aftereffects',project_id:target.project_id,sequence_id:target.comp_id,name:c.name,width:c.width,height:c.height,fps:c.frameRate,duration:c.duration,clips:clips,unsupported:unsupported};
 }
 function classic(c){var list=c.renderers||[];for(var i=0;i<list.length;i++)if(list[i]==='ADBE Advanced 3d'||/classic/i.test(list[i]))return list[i];throw Error('This caption pattern needs the Classic 3D renderer inside its own precomps.');}
 function font(names){for(var i=0;i<names.length;i++)try{var found=app.fonts.getFontsByPostScriptName(names[i]);for(var j=0;j<found.length;j++)if(!found[j].isSubstitute)return names[i];}catch(ignore){}throw Error('Activate the caption font '+names.join(' or ')+', then reopen the panel and retry.');}
 function folder(name,parent,made){for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(item instanceof FolderItem&&item.name===name&&item.parentFolder===parent)return item;}var f=app.project.items.addFolder(name);f.parentFolder=parent;made.push(f);return f;}
 function fitGradient(colour,text){
  if(colour.parent!==text)colour.parent=text;
  // Parenting preserves world rotation. The colour must follow the text in local space.
  tr(colour,'ADBE Rotate Z').setValue(0);tr(colour,'ADBE Anchor Point').setValue([8,256]);
  tr(colour,'ADBE Position').expression='var r=parent.sourceRectAtTime(time,false);[r.left+r.width/2,r.top+r.height/2]';
  tr(colour,'ADBE Scale').expression='var r=parent.sourceRectAtTime(time,false);[Math.max(1,r.width+8)/16*100,Math.max(1,r.height+8)/512*100]';
 }
 function animate(l,w,page,position,factor){
  var onset=Math.max(0,w.start-page.start),span=page.end-page.start,travel=Math.min(w.motion.seconds,Math.max(.001,span-onset)),p=tr(l,'ADBE Position'),alpha=tr(l,'ADBE Opacity'),rotation=tr(l,'ADBE Rotate Z');
  while(p.numKeys)p.removeKey(p.numKeys);while(alpha.numKeys)alpha.removeKey(alpha.numKeys);while(rotation.numKeys)rotation.removeKey(rotation.numKeys);
  p.setValueAtTime(onset,[position.x+w.motion.x*factor,position.y+w.motion.y*factor]);p.setValueAtTime(onset+travel,[position.x,position.y]);
  rotation.setValueAtTime(onset,w.motion.rotation||0);rotation.setValueAtTime(onset+travel,0);
  alpha.setValueAtTime(onset,0);alpha.setValueAtTime(Math.min(span,onset+(w.motion.fade_seconds||.133466667)),100);
  var properties=[p,rotation,alpha];for(var i=0;i<properties.length;i++){var property=properties[i];for(var k=1;k<=property.numKeys;k++){var count=property.keyInTemporalEase(k).length,eases=[];for(var n=0;n<count;n++)eases.push(new KeyframeEase(0,i===2?40:66));property.setInterpolationTypeAtKey(k,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);property.setTemporalEaseAtKey(k,eases,eases);if(property===p&&property.isSpatial){var tangents=[];for(n=0;n<property.keyValue(k).length;n++)tangents.push(0);property.setSpatialTangentsAtKey(k,tangents,tangents);}}}
 }
 function insert(plan,request,profile){
  var current=context(),owner=app.project.activeItem,styleName=profile.folder_name||'Caption 1',extension=null;if(profile.id==='caption_2_ae_v1')extension=g.StorylensCaptionTwoMotion;if(profile.id==='caption_3_ae_v1')extension=g.StorylensCaptionThreeMotion;if(profile.id==='caption_6_ae_v1')extension=g.StorylensCaptionSixMotion;if(current.project_id!==request.project_id||current.comp_id!==request.comp_id)throw Error('Return to the same project and composition before adding these captions.');
  var origin=plan.timing_method==='speech'?0:request.time;if(origin<0||origin+plan.duration>owner.duration+1/owner.frameRate)throw Error('These captions exceed the composition. Choose a shorter duration or extend it, then retry.');
  var marker='Storylens AE '+styleName+' '+request.request_id+' target '+request.comp_id;for(var i=1;i<=app.project.numItems;i++){var old=app.project.item(i);if(old instanceof FolderItem&&String(old.comment||'')===marker+' done')return {ok:true,reused:true,groups:plan.pages.length};}
  var fonts={};for(var fontRole in profile.fonts)if(profile.fonts.hasOwnProperty(fontRole))fonts[fontRole]=font(profile.fonts[fontRole]);var gradientFile=plan.gradient_path?new File(plan.gradient_path):null;if(gradientFile&&!gradientFile.exists)throw Error('The Caption 1 gradient is missing. Restore its saved pattern assets and retry.');
  var made=[],layers=[],run=null,gradient=null,result=null,scenes=[],commonScale=1;app.beginUndoGroup('Generate '+styleName+' patterns');
  try{
   var top=folder('Auto Captions',app.project.rootFolder,made),standard=folder('Standard',top,made),style=folder(styleName,standard,made);run=app.project.items.addFolder(styleName+' - '+request.request_id.substr(0,6));run.parentFolder=style;run.comment=marker+' building';made.push(run);
   for(var pi=0;pi<plan.pages.length;pi++){
    var page=plan.pages[pi],span=page.end-page.start,c=app.project.items.addComp('Caption '+('000'+(pi+1)).slice(-3)+' - '+page.pattern_id.replace(/_/g,' '),owner.width,owner.height,1,span,owner.frameRate);made.push(c);c.parentFolder=run;c.renderer=classic(c);c.bgColor=[0,0,0];c.comment='Storylens caption pattern '+profile.id+' '+page.pattern_id+' slots '+page.source_start;if(page.template_source)c.comment+='; reference '+page.reference_sha256+'; template_slot '+page.template_slot+'; template_source '+page.template_source;c.resolutionFactor=[2,2];
    var factor=owner.width/720;if(profile.design_unit==='short_side')factor=Math.min(owner.width,owner.height*.75)/720;var texts=[],metrics=[];
    for(var wi=0;wi<page.words.length;wi++){
     var w=page.words[wi],l=c.layers.addText(w.text),property=l.property('ADBE Text Properties').property('ADBE Text Document'),doc=property.value;if(extension&&typeof doc.resetCharStyle==='function')doc.resetCharStyle();doc.font=fonts[w.font];doc.fontSize=w.size*factor;doc.tracking=w.tracking===undefined?profile.tracking[w.font]:w.tracking;doc.applyFill=true;
     // AE's live CEP path misassigned the nested conditional array setter.
     // Resolve RGB in explicit branches before touching the native document.
     var fillRGB=[1,1,1];if(w.fill_rgb){fillRGB=[w.fill_rgb[0]/255,w.fill_rgb[1]/255,w.fill_rgb[2]/255];}else if(w.colour==='lime'){fillRGB=[225/255,1,93/255];}doc.fillColor=fillRGB;doc.applyStroke=false;doc.fauxBold=false;doc.fauxItalic=false;doc.baselineShift=0;doc.horizontalScale=1;doc.verticalScale=1;if(typeof FontCapsOption!=='undefined')doc.fontCapsOption=FontCapsOption.FONT_NORMAL_CAPS;doc.justification=ParagraphJustification.LEFT_JUSTIFY;property.setValue(doc);if(extension)extension.verifyFill(l,w);l.name='EDIT '+(wi+1)+' - '+w.text;l.comment='Source word '+w.index+'; fixed '+page.pattern_id+' '+w.row+' slot';l.inPoint=0;l.outPoint=span;
     var rect=l.sourceRectAtTime(0,false);metrics.push(rect);texts.push(l);tr(l,'ADBE Anchor Point').setValue([rect.left+rect.width/2,rect.top+rect.height/2]);
    }
    if(!profile.independent_fit)commonScale=Math.min(commonScale,g.StorylensCaptionGeometry.layout(page,metrics,owner.width,owner.height).fit);scenes.push({page:page,comp:c,texts:texts,metrics:metrics});
   }
   for(pi=0;pi<scenes.length;pi++){
    var scene=scenes[pi];page=scene.page;c=scene.comp;texts=scene.texts;metrics=scene.metrics;span=page.end-page.start;
    var geometry=g.StorylensCaptionGeometry.layout(page,metrics,owner.width,owner.height,commonScale);
    for(wi=0;wi<page.words.length;wi++){
     w=page.words[wi];l=texts[wi];var position=geometry.words[wi];tr(l,'ADBE Scale').setValue([position.scale*100,position.scale*100]);if(extension&&extension.animate)extension.animate(l,w,page,position,factor*position.scale);else animate(l,w,page,position,factor*position.scale);if(extension){var helper=extension.decorate(l,w,factor*position.scale,page);if(helper){if(!scene.helpers)scene.helpers=[];scene.helpers.push(helper);}}
     if(w.gradient){
      if(!gradient){gradient=app.project.importFile(new ImportOptions(gradientFile));gradient.name='Caption 1 gradient';gradient.parentFolder=run;made.push(gradient);}
      var colour=c.layers.add(gradient);if(typeof colour.setTrackMatte!=='function')throw Error('Editable gradient captions need After Effects 23 or newer.');colour.name='Blue gradient - '+w.text;fitGradient(colour,l);colour.inPoint=0;colour.outPoint=span;colour.setTrackMatte(l,TrackMatteType.ALPHA);l.enabled=false;
     }
    }
    scene.geometry=geometry;if(extension)extension.finish(scene,made,run);
    var placed=owner.layers.add(c);layers.push(placed);placed.name=c.name;var reviewWords=[];for(var ri=0;ri<page.words.length;ri++)if(page.words[ri].review_reason)reviewWords.push(page.words[ri].source);if(reviewWords.length){placed.name+=' [Review audio]';placed.comment='Review script/audio match: '+reviewWords.join(' ');}placed.threeDLayer=false;placed.collapseTransformation=false;placed.startTime=origin+page.start;placed.inPoint=placed.startTime;placed.outPoint=Math.min(owner.duration,origin+page.end);tr(placed,'ADBE Position').setValue([owner.width/2,owner.height/2]);
   }
   var wordCount=0;for(pi=0;pi<plan.pages.length;pi++)wordCount+=plan.pages[pi].words.length;run.comment=marker+' done';result={ok:true,groups:plan.pages.length,words:wordCount,timing_method:plan.timing_method,folder_id:String(run.id),notice:plan.review_notice||'',message:'Added '+plan.pages.length+' editable '+styleName+' precomps.'};
  }catch(e){for(var i=layers.length-1;i>=0;i--)try{layers[i].remove();}catch(ignore){}for(i=made.length-1;i>=0;i--)try{if(!(made[i] instanceof FolderItem)||made[i].numItems===0)made[i].remove();}catch(ignore){}for(i=made.length-1;i>=0;i--)try{if(made[i] instanceof FolderItem&&made[i].numItems===0)made[i].remove();}catch(ignore){}throw e;}
  finally{app.endUndoGroup();}
  return result;
 }
 g.StorylensCaptionPatterns={context:context,timingContext:timingContext,insert:insert,animate:animate,fitGradient:fitGradient};
})(typeof $!=='undefined'?$.global:this);
