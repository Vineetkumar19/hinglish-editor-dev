(function(root){
 var tag='// Storylens Toolkit motion v1:';
 function prop(layer,name){return layer.property('ADBE Transform Group').property(name);}
 function prepare(comp,layers,p,keys){
  var id=p.id,s=p.settings,records=[],i,j,animated=id==='shake'||id==='arc'||id==='follow-path'||id==='focus-zoom'||id==='photo-pan';
  if(!/^(bounce|shake|handheld|float|arc|follow-path|pulse|focus-zoom|photo-pan)$/.test(id))throw Error('This tool has no loaded motion handler. Reopen Storylens.');
  if(!layers.length)throw Error('Select a text, image, video or shape layer first.');
  for(i=0;i<layers.length;i++){
   var layer=layers[i],effects=layer.property('ADBE Effect Parade'),rec={layer:layer,expressions:[],controls:{},start:Math.max(comp.time,layer.inPoint),path:0};
   if(!effects||layer.locked||layer.nullLayer||layer.adjustmentLayer)throw Error('Select unlocked visual layers.');
   if(animated&&rec.start+s.duration>Math.min(comp.duration,layer.outPoint)-comp.frameDuration)throw Error('The layer needs room for the full animation duration after the playhead.');
   if(id==='bounce'){
    var ps=layer.selectedProperties||[];for(j=0;j<ps.length;j++)if(ps[j].canSetExpression&&ps[j].numKeys&&ps[j].selectedKeys.length)rec.expressions.push({p:ps[j],body:'bounce'});
    if(!rec.expressions.length)throw Error('Select keyframes on numeric properties before adding Bounce.');
   }else if(id==='pulse')rec.expressions.push({p:prop(layer,'ADBE Scale'),body:'pulse'});
   else{rec.expressions.push({p:prop(layer,'ADBE Position'),body:id});if(id==='arc')rec.expressions.push({p:prop(layer,'ADBE Opacity'),body:'fade'});if(id==='focus-zoom'||id==='photo-pan'){if(layer.threeDLayer||layer.parent)throw Error('Documentary camera moves need an unparented 2D layer.');rec.expressions.push({p:prop(layer,'ADBE Scale'),body:'document-scale'});}}
   if(id==='follow-path'){
    if(layer.threeDLayer||layer.parent)throw Error('Follow Mask Path currently needs an unparented 2D layer.');
    ps=layer.selectedProperties||[];for(j=0;j<ps.length;j++)if(ps[j].matchName==='ADBE Mask Shape'){if(rec.path)throw Error('Select exactly one mask path per moving layer.');rec.path=ps[j].parentProperty.propertyIndex;}
    if(!rec.path)throw Error('Select a Mask Path on the moving layer first.');
    var rotation=prop(layer,'ADBE Rotate Z');if(rotation.numKeys||rotation.expression)throw Error('Use a static Rotation for Follow Mask Path.');
    rec.controls['Path']=rec.path;rec.controls['Base rotation']=rotation.value;if(s.orient==='yes')rec.expressions.push({p:rotation,body:'orient'});
   }
   for(j=0;j<rec.expressions.length;j++){
    var property=rec.expressions[j].p;if(!property||!property.canSetExpression||property.dimensionsSeparated)throw Error('Select numeric properties with combined dimensions.');
    var value=property.value,vector=Object.prototype.toString.call(value)==='[object Array]';if(typeof value!=='number'&&!vector)throw Error('This motion needs a numeric transform property.');if(vector)for(var vi=0;vi<value.length;vi++)if(typeof value[vi]!=='number'||!isFinite(value[vi]))throw Error('This motion needs finite numeric values.');
    if(property.expression&&property.expression.indexOf(tag+id+'\n')!==0)throw Error('This property already has another expression. Choose a different property or remove that expression first.');
   }
   for(var k in s)if(Object.prototype.hasOwnProperty.call(s,k)&&typeof s[k]==='number'&&k!=='duration')rec.controls[k]=s[k];
   if(animated)rec.controls['Progress']=0;
   for(k in rec.controls)if(Object.prototype.hasOwnProperty.call(rec.controls,k)){
    var existing=effects.property('SLT '+id+' · '+k);if(existing){var owned=false;for(j=0;j<rec.expressions.length;j++)if(rec.expressions[j].p.expression.indexOf(tag+id+'\n')===0)owned=true;
     if(!owned)throw Error('A control has the same name as this tool. Rename it before applying.');
     if(existing.matchName!=='ADBE Slider Control')throw Error('A control with this name is not a Slider. Rename it first.');
     if(k!=='Progress'&&(existing.property(1).numKeys||existing.property(1).expression))throw Error('A tool adjustment is animated. Edit its keyframes directly, or remove this tool before replacing it.');
    }
   }
   records.push(rec);
  }
  function expression(body){
   var prefix='function c(n){return effect('+SLQuickMotionModel.quote('SLT '+id+' · ')+'+n)(1);} var t=time-inPoint;';
   if(body==='bounce')return prefix+'var n=0;if(numKeys){n=nearestKey(time).index;if(key(n).time>time)n--;}var v=value;if(n>0&&time-key(n).time<10){var dt=time-key(n).time;var a=c("amount")/100,f=c("frequency"),d=c("decay");v=value+velocityAtTime(key(n).time-thisComp.frameDuration/10)*a*Math.sin(dt*f*2*Math.PI)/Math.exp(d*dt);}v;';
   if(body==='pulse')return prefix+'value*(1+c("amount")/100*Math.sin(t*c("frequency")*2*Math.PI));';
   if(body==='handheld')return prefix+'wiggle(c("frequency"),c("amount"));';
   if(body==='float')return prefix+'var d=Math.sin(t*c("frequency")*2*Math.PI)*c("amount");value.length>2?[value[0],value[1]+d,value[2]]:[value[0],value[1]+d];';
   prefix+='var u=Math.max(0,Math.min(1,c("Progress")/100));';
   if(body==='fade')return prefix+'value*u;';
   if(body==='shake')return prefix+'seedRandom(index,true);var d=wiggle(c("frequency"),c("amount"))-value;time<c("Progress").key(1).time?value:value+d*Math.pow(1-u,2);';
   if(body==='arc')return prefix+'var dx=-c("distance")*(1-u),dy=-c("height")*4*u*(1-u);value.length>2?[value[0]+dx,value[1]+dy,value[2]]:[value[0]+dx,value[1]+dy];';
   if(body==='document-scale')return prefix+'var f=1+(c("amount")/100-1)*u;value.length>2?[value[0]*f,value[1]*f,value[2]*f]:[value[0]*f,value[1]*f];';
   if(body==='photo-pan')return prefix+'[value[0]+c("distance")*u,value[1]];';
   if(body==='focus-zoom')return prefix+'var px=thisComp.width*c("x")/100,py=thisComp.height*c("y")/100,f=(c("amount")/100-1)*u;[value[0]+(thisComp.width/2-px)*u+(value[0]-px)*f,value[1]+(thisComp.height/2-py)*u+(value[1]-py)*f];';
   prefix+='var path=mask(Math.round(c("Path"))).maskPath;var a=path.pointOnPath(0),b=path.pointOnPath(u),rad=c("Base rotation")*Math.PI/180;';
   if(body==='orient')return prefix+'var v=path.tangentOnPath(u);value+Math.atan2(v[1]*scale[1],v[0]*scale[0])*180/Math.PI;';
   return prefix+'var dx=(b[0]-a[0])*scale[0]/100,dy=(b[1]-a[1])*scale[1]/100;value+[dx*Math.cos(rad)-dy*Math.sin(rad),dx*Math.sin(rad)+dy*Math.cos(rad)];';
  }
  return {apply:function(defer){
   for(var n=0;n<records.length;n++){
    var rec=records[n];
    for(var key in rec.controls)if(Object.prototype.hasOwnProperty.call(rec.controls,key))(function(rec,key){
     var name='SLT '+id+' · '+key,group=rec.layer.property('ADBE Effect Parade'),effect=group.property(name);
     if(effect){var old=effect.property(1).value,oldKeys=effect.property(1).numKeys?keys.snapshot(effect.property(1)):[];defer(function(){var control=rec.layer.property('ADBE Effect Parade').property(name).property(1);if(oldKeys.length)keys.restore(control,oldKeys);else{while(control.numKeys)control.removeKey(control.numKeys);control.setValue(old);}});}
     else{effect=group.addProperty('ADBE Slider Control');effect.name=name;defer(function(){var e=rec.layer.property('ADBE Effect Parade').property(name);if(e)e.remove();});}
     var control=rec.layer.property('ADBE Effect Parade').property(name).property(1);
     if(key==='Progress'){while(control.numKeys)control.removeKey(control.numKeys);control.setValueAtTime(rec.start,0);control.setValueAtTime(rec.start+s.duration,100);for(var k=1;k<=2;k++){control.setInterpolationTypeAtKey(k,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);control.setTemporalEaseAtKey(k,[new KeyframeEase(0,66)],[new KeyframeEase(0,66)]);}}
     else control.setValue(rec.controls[key]);
    })(rec,key);
    for(var j=0;j<rec.expressions.length;j++)(function(entry){var old=entry.p.expression;defer(function(){entry.p.expression=old;});entry.p.expression=tag+id+'\n'+expression(entry.body);if(entry.p.expressionError)throw Error(entry.p.expressionError);})(rec.expressions[j]);
   }
   return {ok:true,name:SLToolkitModel.find(id).name,changed:records.length,editable:true,message:'Applied to '+records.length+' layer(s). Adjust SLT controls in Effect Controls; Progress keyframes control entrance timing.'};
  }};
 }
 root.SLToolkitMotion={prepare:prepare};
})(typeof $!=='undefined'&&$.global?$.global:this);
