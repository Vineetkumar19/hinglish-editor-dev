/* Native editable text glow and measured recipe zoom; no reference decorations. */
(function(g){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function verifyFill(l,w){var doc=l.property('ADBE Text Properties').property('ADBE Text Document').value,expected=w.fill_rgb,actual=doc.fillColor;if(doc.applyFill===false||doc.applyStroke===true)throw Error('AE did not retain the caption fill style. Existing layers are kept.');for(var i=0;i<3;i++)if(Math.abs(actual[i]-expected[i]/255)>.002)throw Error('AE did not retain the caption fill colour for '+w.text+'. Channel '+i+' expected '+expected[i]+' actual '+actual[i]+'. Existing layers are kept.');}

 function decorate(l,w,factor,page){
  // Keep the foreground untouched: a separate blurred copy supplies only the
  // soft halo. A brightness/glow effect on the original can clip lime to white.
  var glow=l.duplicate();glow.name='Glow - '+w.text;glow.comment='Storylens soft-glow helper';glow.moveAfter(l);glow.shy=true;l.containingComp.hideShyLayers=true;
  var halo=glow.property('ADBE Effect Parade').addProperty('ADBE Gaussian Blur 2');halo.property(1).setValue(w.appearance.glow_radius*factor);
  var alpha=tr(glow,'ADBE Opacity'),strength=w.appearance.glow_strength*(w.colour==='lime'?1:.35);for(var ai=1;ai<=alpha.numKeys;ai++)alpha.setValueAtKey(ai,alpha.keyValue(ai)*strength);
  var appearance=w.appearance,shadow=l.property('ADBE Effect Parade').addProperty('ADBE Drop Shadow');
  var colour=shadow.property(1),black=colour.value&&colour.value.length===3?[0,0,0]:[0,0,0,1];colour.setValue(black);var opacity=shadow.property(2);opacity.setValue(appearance.shadow_opacity*(opacity.hasMax?opacity.maxValue:255));
  shadow.property(3).setValue(180);shadow.property(4).setValue(appearance.shadow_y*factor);shadow.property(5).setValue(appearance.shadow_blur*factor);
  var blur=l.property('ADBE Effect Parade').addProperty('ADBE Gaussian Blur 2').property(1),onset=Math.max(0,w.start-page.start);blur.setValueAtTime(onset,appearance.entry_blur*factor);blur.setValueAtTime(Math.min(page.end-page.start,onset+w.motion.seconds),0);
  return glow;
 }
 function finish(scene,made,run){
  var c=scene.comp,page=scene.page,controller=c.layers.addNull();controller.name='Caption motion';controller.enabled=false;
  if(controller.source){controller.source.parentFolder=run;made.unshift(controller.source);}
  var pivot=scene.geometry.pivot;tr(controller,'ADBE Anchor Point').setValue([0,0]);tr(controller,'ADBE Position').setValue(pivot);tr(controller,'ADBE Scale').setValue([100,100]);
  for(var i=0;i<scene.texts.length;i++)scene.texts[i].parent=controller;
  for(i=0;i<(scene.helpers||[]).length;i++)scene.helpers[i].parent=controller;
  var onset=0;
  var scale=tr(controller,'ADBE Scale'),position=tr(controller,'ADBE Position'),end=page.end-page.start,path=page.camera_path,factor=c.width/720*scene.geometry.fit;
  for(i=0;i<path.length;i++){var t=onset+path[i][0];if(t>end)break;var value=path[i][1]*100;scale.setValueAtTime(t,[value,value]);position.setValueAtTime(t,[pivot[0]+path[i][2]*factor,pivot[1]+path[i][3]*factor]);}
  // These keys already sample the measured easing. Linear interpolation avoids
  // introducing a new zero-velocity pause at every sampled video frame.
  for(i=1;i<=scale.numKeys;i++){scale.setInterpolationTypeAtKey(i,KeyframeInterpolationType.LINEAR,KeyframeInterpolationType.LINEAR);position.setInterpolationTypeAtKey(i,KeyframeInterpolationType.LINEAR,KeyframeInterpolationType.LINEAR);}
 }
 g.StorylensCaptionTwoMotion={decorate:decorate,finish:finish,verifyFill:verifyFill};
})(typeof $!=='undefined'?$.global:this);
