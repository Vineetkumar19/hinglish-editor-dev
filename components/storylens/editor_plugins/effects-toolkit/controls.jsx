(function(root){
 function slider(layer,name,value,defer,keys,timing){
  var group=layer.property('ADBE Effect Parade'),effect=group.property(name);
  if(effect){var old=effect.property(1).value,oldKeys=effect.property(1).numKeys?keys.snapshot(effect.property(1)):[];defer(function(){var p=layer.property('ADBE Effect Parade').property(name).property(1);if(oldKeys.length)keys.restore(p,oldKeys);else{while(p.numKeys)p.removeKey(p.numKeys);p.setValue(old);}});}
  else{effect=group.addProperty('ADBE Slider Control');effect.name=name;defer(function(){var e=layer.property('ADBE Effect Parade').property(name);if(e)e.remove();});}
  var p=layer.property('ADBE Effect Parade').property(name).property(1);
  if(timing){while(p.numKeys)p.removeKey(p.numKeys);p.setValueAtTime(timing.start,0);p.setValueAtTime(timing.end,100);for(var i=1;i<=2;i++){p.setInterpolationTypeAtKey(i,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);p.setTemporalEaseAtKey(i,[new KeyframeEase(0,66)],[new KeyframeEase(0,66)]);}}else p.setValue(value);
 }
 function assign(p,key,value,defer){var old=p[key];defer(function(){p[key]=old;});p[key]=value;if(key==='expression'&&p.expressionError)throw Error(p.expressionError);}
 root.SLToolkitControls={slider:slider,assign:assign};
})(typeof $!=='undefined'&&$.global?$.global:this);
