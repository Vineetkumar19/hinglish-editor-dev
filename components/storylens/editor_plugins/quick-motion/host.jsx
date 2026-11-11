/* Applies to the current native selection only. No imports, fonts or source text edits. */
function storylensQuickMotion(input){
 var comp,selected,plans=[],records=[],started=false,i,j,oldTime=0,tag='// Storylens quick motion v1\n';
 function prop(layer,name){return layer.property('ADBE Transform Group').property(name);}
 function anims(layer){return layer.property('ADBE Text Properties').property('ADBE Text Animators');}
 function own(name,prefix){name=String(name);var key=prefix+'Progress ',at=name.lastIndexOf(key);return name.indexOf(prefix)===0&&at>=0&&/^[0-9]+-[0-9]+n*$/.test(name.substring(at+key.length));}
 function keys(p,plan){var times=[plan.start,plan.end],values=plan.recipe.motion==='out'?[100,0]:[0,100],k,n,a;if(plan.exit){times.push(plan.exitStart,plan.exitEnd);values.push(100,0);}for(k=0;k<times.length;k++)p.setValueAtTime(times[k],values[k]);for(k=1;k<=p.numKeys;k++){if(plan.recipe.motion==='typewriter'){p.setInterpolationTypeAtKey(k,KeyframeInterpolationType.LINEAR,KeyframeInterpolationType.LINEAR);continue;}a=[];for(n=0;n<p.keyInTemporalEase(k).length;n++)a.push(new KeyframeEase(0,k===1?66:70));p.setInterpolationTypeAtKey(k,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);p.setTemporalEaseAtKey(k,a,a);}}
 function addEffect(rec,match,name){var e=rec.layer.property('ADBE Effect Parade').addProperty(match);e.name=name;rec.newEffects.push(name);return e.propertyIndex;}
 function effect(rec,index){return rec.layer.property('ADBE Effect Parade').property(index);}
 function textProperty(rec,index,match,value){anims(rec.layer).property(index).property('ADBE Text Animator Properties').addProperty(match).setValue(value);}
 function expression(rec,name,body){var p=prop(rec.layer,name);p.expression=tag+body;}
 function removeNames(group,names){for(var k=group.numProperties;k>=1;k--)for(var n=0;n<names.length;n++)if(group.property(k).name===names[n]){group.property(k).remove();break;}}
 try{
  var p=SLQuickMotionModel.validate(input),recipe=SLQuickMotionModel.find(p.id);comp=app.project.activeItem;if(!(comp instanceof CompItem))throw Error('Open your video composition and select a layer first.');oldTime=comp.time;selected=comp.selectedLayers.slice(0);if(!selected.length)throw Error('Select your text or element layer on the timeline, then choose an animation.');
  // Validate the entire selection before creating any controls.
  for(i=0;i<selected.length;i++){
   var layer=selected[i],visual=layer instanceof AVLayer||(typeof TextLayer!=='undefined'&&layer instanceof TextLayer)||(typeof ShapeLayer!=='undefined'&&layer instanceof ShapeLayer);if(!visual||layer.locked||layer.nullLayer||layer.adjustmentLayer)throw Error('Select unlocked text, footage, image or shape layers.');if(recipe.kind==='text'&&!layer.property('ADBE Text Properties'))throw Error('Text Animations needs text layers only. Use Element Motion for images or video.');
   if(recipe.kind==='text'&&p.text_scope==='word'){var doc=layer.property('ADBE Text Properties').property('ADBE Text Document').value,wordText=String(doc.text!==undefined?doc.text:doc).replace(/^\s+|\s+$/g,'');if(!wordText||wordText.split(/\s+/).length!==1)throw Error('Word mode needs a one-word text layer. Choose Words for a full line.');}
   var begin=Math.max(oldTime,layer.inPoint);plans.push(SLQuickMotionModel.plan(p,begin,Math.min(layer.outPoint,comp.duration),comp.frameDuration));var rec={layer:layer,prefix:'SLQ '+(recipe.kind==='text'?'Text ':'Element '),oldEffects:[],oldAnimators:[],newEffects:[],newAnimators:[],expressions:[],blur:layer.motionBlur};
   var group=layer.property('ADBE Effect Parade');if(!group)throw Error('This layer cannot receive motion controls. Select a text or visual layer.');for(j=1;j<=group.numProperties;j++)if(own(group.property(j).name,rec.prefix))rec.oldEffects.push(group.property(j).name);
   if(recipe.kind==='text'){group=anims(layer);for(j=1;j<=group.numProperties;j++)if(own(group.property(j).name,rec.prefix))rec.oldAnimators.push(group.property(j).name);}
   else for(j=0;j<3;j++){var name=['ADBE Position','ADBE Scale','ADBE Opacity'][j],property=prop(layer,name),needed=name==='ADBE Opacity'||name==='ADBE Position'&&(recipe.motion==='left'||recipe.motion==='right'||recipe.motion==='up'||recipe.motion==='down')||name==='ADBE Scale'&&(recipe.motion==='zoom-in'||recipe.motion==='zoom-out');if(needed&&(!property||!property.canSetExpression||property.dimensionsSeparated&&name==='ADBE Position'))throw Error('Use a layer with combined Position dimensions and editable transform properties.');if(needed&&property.expression&&property.expression.indexOf(tag)!==0)throw Error('This layer already has a custom transform expression. Use another layer or remove that expression before applying Element Motion.');if(property&&property.canSetExpression)rec.expressions.push({name:name,value:property.expression||''});}
   records.push(rec);
  }
  app.beginUndoGroup('Storylens '+recipe.name);started=true;
  for(i=0;i<records.length;i++){
   var rec=records[i],plan=plans[i],control=rec.prefix+'Progress '+String(new Date().getTime())+'-'+i;while(rec.layer.property('ADBE Effect Parade').property(control))control+='n';var controlIndex=addEffect(rec,'ADBE Slider Control',control);keys(effect(rec,controlIndex).property(1),plan);
   var motion=recipe.motion,dx=motion==='left'?1:motion==='right'?-1:0,dy=motion==='up'||motion==='words'?1:motion==='down'?-1:0;
   if(recipe.kind==='text'){
    var animator=anims(rec.layer).addProperty('ADBE Text Animator'),ai=animator.propertyIndex;animator.name=rec.prefix+recipe.name+' '+control;rec.newAnimators.push(animator.name);
    textProperty(rec,ai,'ADBE Text Opacity',0);if(dx||dy)textProperty(rec,ai,'ADBE Text Position 3D',[dx*70,dy*50,0]);if(motion==='pop')textProperty(rec,ai,'ADBE Text Scale 3D',[75,75,100]);if(plan.blur&&motion!=='typewriter')textProperty(rec,ai,'ADBE Text Blur',[motion==='blur'?18:7,motion==='blur'?18:7]);
    var selectors=anims(rec.layer).property(ai).property('ADBE Text Selectors');while(selectors.numProperties)selectors.property(1).remove();var selector=selectors.addProperty('ADBE Text Expressible Selector');selector.property('ADBE Text Range Type2').setValue(p.text_scope!=='word'&&(motion==='words'||motion==='random')?3:1);selector.property('ADBE Text Expressible Amount').expression=SLQuickMotionModel.selector(recipe,control,37);
   }else{
    // Add expressions to underlying values: existing authored transform keys remain intact.
    for(j=0;j<rec.expressions.length;j++)if(prop(rec.layer,rec.expressions[j].name).expression.indexOf(tag)===0)prop(rec.layer,rec.expressions[j].name).expression='';
    var progress='var p=Math.max(0,Math.min(1,effect('+SLQuickMotionModel.quote(control)+')(1)/100));';
    expression(rec,'ADBE Opacity',progress+'value*p;');
    if(dx||dy)expression(rec,'ADBE Position',progress+'var v=value;var d=['+(dx*Math.min(160,comp.width*.08))+','+(dy*Math.min(120,comp.height*.08))+'];v.length>2?[v[0]+d[0]*(1-p),v[1]+d[1]*(1-p),v[2]]:[v[0]+d[0]*(1-p),v[1]+d[1]*(1-p)];');
    if(motion==='zoom-in'||motion==='zoom-out')expression(rec,'ADBE Scale',progress+'var s='+(motion==='zoom-in'?'.85+.15*p':'1.15-.15*p')+';value.length>2?[value[0]*s,value[1]*s,value[2]*s]:[value[0]*s,value[1]*s];');
    if(plan.blur){var bi=addEffect(rec,'ADBE Gaussian Blur 2',rec.prefix+'Blur '+control);effect(rec,bi).property(1).expression=progress+'(1-p)*7;';}
   }
   rec.layer.motionBlur=true;
  }
  // Commit replacements only after every selected layer was built successfully.
  for(i=0;i<records.length;i++){removeNames(records[i].layer.property('ADBE Effect Parade'),records[i].oldEffects);if(recipe.kind==='text')removeNames(anims(records[i].layer),records[i].oldAnimators);}
  return SLQuickMotionModel.stringify({ok:true,name:recipe.name,layers:records.length,duration:p.duration,kind:recipe.kind,text_scope:recipe.kind==='text'?p.text_scope:null,start:plans[0].start,exit:p.exit&&recipe.motion!=='out',editable:true});
 }catch(e){
  var rollback=true;if(started)for(i=records.length-1;i>=0;i--)try{var rec=records[i];removeNames(rec.layer.property('ADBE Effect Parade'),rec.newEffects);if(rec.newAnimators.length)removeNames(anims(rec.layer),rec.newAnimators);for(j=0;j<rec.expressions.length;j++)prop(rec.layer,rec.expressions[j].name).expression=rec.expressions[j].value;rec.layer.motionBlur=rec.blur;}catch(ignore){rollback=false;}
  return SLQuickMotionModel.stringify({error:started?'The animation could not finish. '+(rollback?'New controls were removed.':'Use After Effects Undo before retrying.'):' '+String(e.message||e),code:'quick_motion',details:String(e),partial:started&&!rollback});
 }finally{if(started){try{comp.time=oldTime;}catch(ignoreTime){}app.endUndoGroup();}}
}
