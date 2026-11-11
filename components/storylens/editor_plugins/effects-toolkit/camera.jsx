(function(root){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function isCamera(l){return typeof CameraLayer!=='undefined'&&l instanceof CameraLayer;}
 function ownedNull(comp,name,defer){var before={};for(var i=1;i<=app.project.numItems;i++)before[app.project.item(i).id]=true;var l=comp.layers.addNull();l.name=name;if(l.source&&!before[l.source.id]){var src=l.source;if(typeof SLToolkitBuilders!=='undefined'){var rootFolder=SLToolkitBuilders.folder('Effects',app.project.rootFolder,defer);src.parentFolder=SLToolkitBuilders.folder('Utilities',rootFolder,defer);}defer(function(){src.remove();});}defer(function(){l.remove();});return l;}
 function ease(p,indices){for(var i=0;i<indices.length;i++){var k=indices[i],a=[];for(var j=0;j<p.keyInTemporalEase(k).length;j++)a.push(new KeyframeEase(0,66));p.setInterpolationTypeAtKey(k,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);p.setTemporalEaseAtKey(k,a,a);}}
 function prepare(comp,layers,p,keys){var id=p.id,s=p.settings,camera=null,i,j,start=comp.time;
  if(id==='camera-rig'||id==='camera-orbit'||id==='focus-pull'){
   for(i=0;i<layers.length;i++)if(isCamera(layers[i])){if(camera)throw Error('Select one camera only.');camera=layers[i];}
   if(!camera&&comp.activeCamera)throw Error('Select the camera you want to change. Existing cameras will not be replaced automatically.');
   if(id==='focus-pull'&&!camera)throw Error('Select a camera before applying Focus Pull.');
   if(camera&&(id==='camera-rig'||id==='camera-orbit')){if(camera.parent)throw Error('This camera already has a parent rig. Animate that rig or select an unparented camera.');for(i=0;i<5;i++){var property=tr(camera,['ADBE Position','ADBE Orientation','ADBE Rotate X','ADBE Rotate Y','ADBE Rotate Z'][i]);if(property&&(property.numKeys||property.expression))throw Error('Use a static camera for the new rig so authored camera animation is preserved.');}}
  }
  if(s.duration&&id!=='title-3d'&&start+s.duration>comp.duration)throw Error('Move the playhead earlier or shorten the motion duration.');
  if(id==='parallax'||id==='ground-shadow'){
   if(layers.length<(id==='parallax'?2:1))throw Error(id==='parallax'?'Select at least two 2D planes for parallax.':'Select visual layers for the ground scene.');
   for(i=0;i<layers.length;i++)if(layers[i].parent||layers[i].threeDLayer||isCamera(layers[i])||layers[i].nullLayer)throw Error('Select unparented 2D visual layers; precompose an existing 3D or parented setup first.');
   for(i=0;i<layers.length;i++)for(j=0;j<3;j++)if(tr(layers[i],['ADBE Position','ADBE Scale','ADBE Anchor Point'][j]).expression)throw Error('Precompose transform expressions before building a separate 3D scene so authored motion remains intact.');
   if(id==='parallax'&&s.depth*(layers.length-1)/2>=comp.width*.8)throw Error('Reduce depth spacing so every plane stays in front of the camera.');
  }
  if(id==='focus-pull'){
   var focus=camera.property('ADBE Camera Options Group').property('ADBE Camera Focus Distance');if(!focus||focus.expression)throw Error('Use a camera with editable Focus Distance.');for(i=1;i<=focus.numKeys;i++)if(focus.keyTime(i)>=start&&focus.keyTime(i)<=start+s.duration)throw Error('Existing focus keys occupy this interval. Choose an empty interval or edit those keys directly.');
  }
  return {apply:function(defer){
   if(id==='camera-rig'||id==='camera-orbit'){
    if(!camera){camera=comp.layers.addCamera('SLT Camera',[comp.width/2,comp.height/2]);defer(function(){camera.remove();});}
    var rig=ownedNull(comp,'SLT Camera Rig',defer);rig.threeDLayer=true;tr(rig,'ADBE Position').setValue([comp.width/2,comp.height/2,0]);var oldParent=camera.parent;defer(function(){camera.parent=oldParent;});camera.parent=rig;
    SLToolkitControls.slider(rig,'Orbit X',0,defer,keys);SLToolkitControls.slider(rig,'Orbit Y',0,defer,keys);SLToolkitControls.slider(rig,'Dolly',0,defer,keys);tr(rig,'ADBE Rotate X').expression='value+effect("Orbit X")(1);';tr(rig,'ADBE Rotate Y').expression='value+effect("Orbit Y")(1);';tr(rig,'ADBE Position').expression='[value[0],value[1],value[2]+effect("Dolly")(1)];';
    if(id==='camera-orbit'){var orbit=rig.property('ADBE Effect Parade').property('Orbit Y').property(1);orbit.setValueAtTime(start,0);orbit.setValueAtTime(start+s.duration,s.angle);ease(orbit,[1,2]);}
    return {ok:true,changed:1,message:'Camera rig created. Edit Orbit X, Orbit Y and Dolly on SLT Camera Rig.'};
   }
   if(id==='focus-pull'){
    var options=camera.property('ADBE Camera Options Group'),focus=options.property('ADBE Camera Focus Distance'),old=focus.value,oldKeys=focus.numKeys?keys.snapshot(focus):[],dof=options.property('ADBE Camera Depth of Field'),oldDof=dof.value,aperture=options.property('ADBE Camera Aperture'),oldAperture=aperture.value;
    defer(function(){if(oldKeys.length)keys.restore(focus,oldKeys);else{while(focus.numKeys)focus.removeKey(focus.numKeys);focus.setValue(old);}dof.setValue(oldDof);aperture.setValue(oldAperture);});dof.setValue(true);aperture.setValue(s.aperture);focus.setValueAtTime(start,s.near);focus.setValueAtTime(start+s.duration,s.far);ease(focus,[focus.nearestKeyIndex(start),focus.nearestKeyIndex(start+s.duration)]);
    return {ok:true,changed:1,message:'Focus Pull keyframes added. Refine focus distances and aperture on the camera.'};
   }
   var parent=SLToolkitBuilders.folder('Effects',app.project.rootFolder,defer),folder=SLToolkitBuilders.folder('Camera & 3D',parent,defer),duration=id==='title-3d'?s.duration:comp.duration,scene=app.project.items.addComp(SLToolkitModel.find(id).name,comp.width,comp.height,comp.pixelAspect||1,duration,comp.frameRate);scene.parentFolder=folder;scene.comment='Storylens Toolkit:'+id+':v1';defer(function(){scene.remove();});
   if(id==='title-3d'){
    var available=false;for(i=0;i<scene.renderers.length;i++)if(scene.renderers[i]==='ADBE Ernst')available=true;if(!available)throw Error('The native Cinema 4D renderer is unavailable. Restore it before creating an extruded title.');scene.renderer='ADBE Ernst';
    var text=scene.layers.addText(s.title),doc=text.property('ADBE Text Properties').property('ADBE Text Document'),d=doc.value;d.font='ArialMT';d.fontSize=Math.min(comp.width,comp.height)*.14;d.applyFill=true;d.fillColor=SLToolkitStyling.rgb(s.color);d.applyStroke=false;d.justification=ParagraphJustification.CENTER_JUSTIFY;doc.setValue(d);var rect=text.sourceRectAtTime(0,false);if(rect.width>comp.width*.75){d=doc.value;d.fontSize*=comp.width*.75/rect.width;doc.setValue(d);rect=text.sourceRectAtTime(0,false);}text.threeDLayer=true;text.name='Editable title';tr(text,'ADBE Anchor Point').setValue([rect.left+rect.width/2,rect.top+rect.height/2,0]);tr(text,'ADBE Position').setValue([comp.width/2,comp.height/2,0]);tr(text,'ADBE Rotate Y').setValue(s.angle);text.property('ADBE Extrsn Options Group').property('ADBE Extrsn Depth').setValue(s.depth);
    var opacity=tr(text,'ADBE Opacity');opacity.setValueAtTime(0,0);opacity.setValueAtTime(.4,100);opacity.setValueAtTime(duration-.3,100);opacity.setValueAtTime(duration,0);ease(opacity,[1,2,3,4]);
   }else{
    for(i=0;i<layers.length;i++){
     layers[i].copyToComp(scene);var copy=scene.layer(1);copy.threeDLayer=true;copy.enabled=true;
     if(id==='parallax'){
      var depth=(i-(layers.length-1)/2)*s.depth;SLToolkitControls.slider(copy,'Depth',depth,defer,keys);tr(copy,'ADBE Position').expression='var z=effect("Depth")(1),f=(thisComp.width+z)/thisComp.width;[thisComp.width/2+(value[0]-thisComp.width/2)*f,thisComp.height/2+(value[1]-thisComp.height/2)*f,z];';tr(copy,'ADBE Scale').expression='var f=(thisComp.width+effect("Depth")(1))/thisComp.width;[value[0]*f,value[1]*f,value.length>2?value[2]:100];';
     }else copy.property('ADBE Material Options Group').property('ADBE Casts Shadows').setValue(1);
    }
   }
   var cam=scene.layers.addCamera('Scene Camera',[comp.width/2,comp.height/2]);cam.property('ADBE Camera Options Group').property('ADBE Camera Zoom').setValue(comp.width);tr(cam,'ADBE Position').setValue([comp.width/2,comp.height/2,-comp.width]);tr(cam,'ADBE Point of Interest').setValue([comp.width/2,comp.height/2,0]);
   if(id==='parallax'){var pos=tr(cam,'ADBE Position');pos.setValueAtTime(start,[comp.width/2,comp.height/2,-comp.width]);pos.setValueAtTime(start+s.duration,[comp.width/2+s.travel,comp.height/2,-comp.width]);ease(pos,[1,2]);}
   if(id==='ground-shadow'||id==='title-3d'){
    var light=scene.layers.addLight('Key Light',[comp.width/2,comp.height/2]);light.lightType=LightType.SPOT;tr(light,'ADBE Position').setValue([comp.width*.2,comp.height*.15,-comp.width*.8]);tr(light,'ADBE Point of Interest').setValue([comp.width/2,comp.height/2,0]);var lightOptions=light.property('ADBE Light Options Group');lightOptions.property('ADBE Light Intensity').setValue(100);lightOptions.property('ADBE Casts Shadows').setValue(true);
    if(id==='ground-shadow'){
     var floor=scene.layers.addSolid([.18,.18,.18],'Ground',Math.min(30000,comp.width*3),Math.min(30000,comp.height*3),comp.pixelAspect||1,scene.duration);if(floor.source){floor.source.parentFolder=folder;var floorSource=floor.source;defer(function(){floorSource.remove();});}floor.threeDLayer=true;tr(floor,'ADBE Position').setValue([comp.width/2,comp.height*s.height/100,0]);tr(floor,'ADBE Rotate X').setValue(90);floor.property('ADBE Material Options Group').property('ADBE Accepts Shadows').setValue(true);lightOptions.property('ADBE Light Shadow Darkness').setValue(s.darkness);lightOptions.property('ADBE Light Shadow Diffusion').setValue(25);
    }
   }
   var result=comp.layers.add(scene);defer(function(){result.remove();});result.name=scene.name;result.startTime=id==='title-3d'?start:0;result.inPoint=id==='title-3d'?start:0;result.outPoint=Math.min(comp.duration,result.startTime+scene.duration);
   if(id!=='title-3d')for(i=0;i<layers.length;i++)(function(l){var old=l.enabled;defer(function(){l.enabled=old;});l.enabled=false;})(layers[i]);
   return {ok:true,changed:1,editable:true,message:scene.name+' added as a separate editable scene. Original layers are kept; edit the camera, planes and lights inside the new precomp.'};
  }};
 }
 root.SLToolkitCamera={prepare:prepare,ownedNull:ownedNull};
})(typeof $!=='undefined'&&$.global?$.global:this);
