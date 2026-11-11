(function(root){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function prepare(comp,layers,p,keys){var id=p.id,s=p.settings,visual=[],nulls=[],i,keylight=null;
  if(!layers.length)throw Error('Select the required timeline layers first.');
  for(i=0;i<layers.length;i++){if(layers[i].locked)throw Error('Unlock selected layers first.');if(layers[i].nullLayer)nulls.push(layers[i]);else visual.push(layers[i]);}
  if(id==='matte'&&layers.length!==2)throw Error('Select the matte and the layer it should reveal.');
  if(id==='roto-assistant'&&(visual.length!==1||layers.length!==1||!visual[0].source||!(visual[0].source instanceof FootageItem||visual[0].source instanceof CompItem)))throw Error('Select one footage or precomposition layer for Roto Brush preparation.');
  if(id==='tracked-blur'&&(visual.length!==1||nulls.length!==1))throw Error('Select one visual layer and one tracked null. Create and review the track first.');
  if(id==='screen-replace'&&(visual.length!==1||nulls.length!==0&&nulls.length!==4))throw Error('Select one replacement layer and either no nulls or four corner nulls named TL, TR, BL, BR.');
  if(id==='green-screen'){for(i=0;app.effects&&i<app.effects.length;i++)if(/^Keylight\b/i.test(app.effects[i].displayName)){keylight=app.effects[i].matchName;break;}if(!keylight)throw Error('Keylight is not available in this AE installation. Restore the bundled effect before using Green Screen.');}
  var corners={};if(id==='screen-replace'&&nulls.length){for(i=0;i<nulls.length;i++){var clean=String(nulls[i].name).toLowerCase().replace(/[^a-z]/g,''),key=clean==='tl'||clean==='topleft'?'TL':clean==='tr'||clean==='topright'?'TR':clean==='bl'||clean==='bottomleft'?'BL':clean==='br'||clean==='bottomright'?'BR':null;if(!key||corners[key])throw Error('Name the four corner nulls TL, TR, BL and BR so their order is unambiguous.');corners[key]=nulls[i];}}
  if(id!=='matte'&&id!=='roto-assistant')for(i=0;i<visual.length;i++){
   if(!visual[i].property('ADBE Effect Parade'))throw Error('Select visual layers that can receive effects.');
   if(id==='rounded-crop'&&visual[i].property('ADBE Mask Parade').property('SLT Rounded Crop'))throw Error('This layer already has a Rounded Crop. Edit its Crop controls directly.');
   if(id==='green-screen'&&visual[i].property('ADBE Effect Parade').property('SLT Green Screen'))throw Error('This layer already has a Green Screen effect. Edit its Keylight controls directly.');
   if(id==='screen-replace')for(var corner in corners)if(Object.prototype.hasOwnProperty.call(corners,corner)&&visual[i].property('ADBE Effect Parade').property('SLT Corner '+corner))throw Error('An existing corner control uses this name. Edit or rename it before applying screen replacement.');
   if(id==='screen-replace'&&(visual[i].threeDLayer||visual[i].property('ADBE Effect Parade').property('SLT Screen Replacement')))throw Error('Use a 2D replacement layer without an existing SLT Screen Replacement. Existing points can be edited directly.');
  }
  return {apply:function(defer){
   if(id==='matte'){
    var ordered=layers.slice(0);ordered.sort(function(a,b){return a.index-b.index;});var matte=ordered[0],target=ordered[1],old=target.trackMatteLayer,oldType=target.trackMatteType,oldEnabled=matte.enabled;
    if(!target.setTrackMatte)throw Error('This matte helper requires After Effects 23 or newer.');defer(function(){if(old)target.setTrackMatte(old,oldType);else target.removeTrackMatte();matte.enabled=oldEnabled;});
    var types={'alpha':TrackMatteType.ALPHA,'alpha-inverted':TrackMatteType.ALPHA_INVERTED,'luma':TrackMatteType.LUMA,'luma-inverted':TrackMatteType.LUMA_INVERTED};target.setTrackMatte(matte,types[s.mode]);matte.enabled=false;
    return {ok:true,changed:1,message:'Track matte assigned. Refine the matte layer and mode in the timeline.'};
   }
   if(id==='roto-assistant'){
    var copy=visual[0].duplicate();copy.name='Roto work - '+visual[0].name;copy.comment='Storylens Toolkit roto preparation v1';defer(function(){copy.remove();});copy.openInViewer();
    return {ok:true,changed:1,requires_review:true,message:'Roto copy prepared in Layer view. Paint with Roto Brush, review the propagated selection, then Freeze. The source layer is kept.'};
   }
   if(id==='tracked-blur'){
    var copy=visual[0].duplicate();copy.name='Tracked blur - '+visual[0].name;copy.comment='Storylens Toolkit tracked blur v1';defer(function(){copy.remove();});if(copy.property('ADBE Effect Parade').property('SLT Tracking target'))throw Error('This footage already has a tracking link. Edit that link or select the original layer.');
    var control=copy.property('ADBE Effect Parade').addProperty('ADBE Layer Control');control.name='SLT Tracking target';control.property(1).setValue(nulls[0].index);
    SLToolkitControls.slider(copy,'SLT Region radius',s.radius,defer,keys);var blur=copy.property('ADBE Effect Parade').addProperty('ADBE Gaussian Blur 2');blur.name='SLT Tracked blur';blur.property(1).setValue(s.blur);
    var masks=copy.property('ADBE Mask Parade'),had=masks.numProperties,mask=masks.addProperty('ADBE Mask Atom');mask.name='SLT Tracking region';mask.maskMode=had?MaskMode.INTERSECT:MaskMode.ADD;mask.property('ADBE Mask Feather').setValue([s.feather,s.feather]);
    mask.property('ADBE Mask Shape').expression='var target=effect("SLT Tracking target")(1),p=fromComp(target.toComp(target.anchorPoint)),r=effect("SLT Region radius")(1),k=r*.55228475;createPath([[p[0],p[1]-r],[p[0]+r,p[1]],[p[0],p[1]+r],[p[0]-r,p[1]]],[[-k,0],[0,-k],[k,0],[0,k]],[[k,0],[0,k],[-k,0],[0,-k]],true);';
    return {ok:true,changed:1,requires_review:true,message:'Blur linked to the selected tracked null. Review the full shot for tracking drift and adjust region size or feather.'};
   }
   if(id==='screen-replace'){
    var layer=visual[0],group=layer.property('ADBE Effect Parade');
    for(var key in corners)if(Object.prototype.hasOwnProperty.call(corners,key))(function(k){var e=group.addProperty('ADBE Layer Control');e.name='SLT Corner '+k;defer(function(){var effect=layer.property('ADBE Effect Parade').property('SLT Corner '+k);if(effect)effect.remove();});e.property(1).setValue(corners[k].index);})(key);
    var pin=group.addProperty('ADBE Corner Pin');pin.name='SLT Screen Replacement';defer(function(){var e=layer.property('ADBE Effect Parade').property('SLT Screen Replacement');if(e)e.remove();});
    var names=['TL','TR','BL','BR'];for(i=0;i<names.length;i++)if(corners[names[i]])pin.property(i+1).expression='var target=effect("SLT Corner '+names[i]+'")(1);fromComp(target.toComp(target.anchorPoint));';
    return {ok:true,changed:1,requires_review:true,message:nulls.length?'Corner Pin linked to TL/TR/BL/BR. Review perspective and tracking through the shot.':'Corner Pin added. Place its four points on the screen corners and keyframe or track them as required.'};
   }
   for(var i=0;i<visual.length;i++)(function(layer){
    if(id==='green-screen'){
     var group=layer.property('ADBE Effect Parade'),effect=group.addProperty(keylight);effect.name='SLT Green Screen';defer(function(){var e=layer.property('ADBE Effect Parade').property('SLT Green Screen');if(e)e.remove();});var color=SLToolkitStyling.parameter(effect,'Screen Colour'),rgb=SLToolkitStyling.rgb(s.color);if(color.value.length===4)rgb.push(1);color.setValue(rgb);SLToolkitStyling.parameter(effect,'Screen Gain').setValue(s.gain);SLToolkitStyling.parameter(effect,'Screen Balance').setValue(s.balance);return;
    }
    for(var k in s)if(Object.prototype.hasOwnProperty.call(s,k))SLToolkitControls.slider(layer,'SLT Crop '+k,s[k],defer,keys);
    var masks=layer.property('ADBE Mask Parade'),had=masks.numProperties,mask=masks.addProperty('ADBE Mask Atom');mask.name='SLT Rounded Crop';mask.maskMode=had?MaskMode.INTERSECT:MaskMode.ADD;defer(function(){var m=layer.property('ADBE Mask Parade').property('SLT Rounded Crop');if(m)m.remove();});
    mask.property('ADBE Mask Shape').expression='var b=sourceRectAtTime(time,false),w=b.width*effect("SLT Crop width")(1)/100,h=b.height*effect("SLT Crop height")(1)/100,l=b.left+(b.width-w)/2,t=b.top+(b.height-h)/2,r=l+w,d=t+h,c=Math.min(effect("SLT Crop radius")(1),w/2,h/2),k=c*.55228475;createPath([[l+c,t],[r-c,t],[r,t+c],[r,d-c],[r-c,d],[l+c,d],[l,d-c],[l,t+c]],[[-k,0],[0,0],[0,-k],[0,0],[k,0],[0,0],[0,k],[0,0]],[[0,0],[k,0],[0,0],[0,k],[0,0],[-k,0],[0,0],[0,-k]],true);';
   })(visual[i]);
   return {ok:true,changed:visual.length,editable:true,message:id==='green-screen'?'Keylight added. Sample the screen colour and refine Screen Matte in Effect Controls.':'Rounded crop added. Adjust SLT Crop controls in Effect Controls.'};
  }};
 }
 root.SLToolkitMasks={prepare:prepare};
})(typeof $!=='undefined'&&$.global?$.global:this);
