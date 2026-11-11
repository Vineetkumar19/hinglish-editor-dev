(function(root){
 function rgb(hex){return [parseInt(hex.substr(1,2),16)/255,parseInt(hex.substr(3,2),16)/255,parseInt(hex.substr(5,2),16)/255];}
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function ease(p){for(var k=1;k<=p.numKeys;k++){var a=[];for(var j=0;j<p.keyInTemporalEase(k).length;j++)a.push(new KeyframeEase(0,66));p.setInterpolationTypeAtKey(k,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);p.setTemporalEaseAtKey(k,a,a);}}
 function folder(name,parent,defer){for(var i=1;i<=app.project.numItems;i++){var x=app.project.item(i);if(x instanceof FolderItem&&x.name===name&&x.parentFolder===parent)return x;}var f=app.project.items.addFolder(name);f.parentFolder=parent;defer(function(){if(!f.numItems)f.remove();});return f;}
 function prepare(comp,layers,p,keys){
  var plan=SLToolkitBuilderModel.make(p.id,p.settings,comp.width,comp.height),start=Math.max(0,comp.time),category=SLToolkitModel.find(p.id).category;
  if(start+plan.duration>10800)throw Error('The graphic would exceed the maximum composition duration.');
  return {apply:function(defer){
   var parent=folder('Effects',app.project.rootFolder,defer),sectionName='Graphics';
   for(var ci=0;ci<SLToolkitModel.categories().length;ci++)if(SLToolkitModel.categories()[ci].id===category){sectionName=SLToolkitModel.categories()[ci].name;break;}var section=folder(sectionName,parent,defer);
   var source=app.project.items.addComp(plan.name,comp.width,comp.height,comp.pixelAspect||1,plan.duration,comp.frameRate);source.comment='Storylens Toolkit:'+p.id+':v1';source.parentFolder=section;defer(function(){source.remove();});
   for(var i=0;i<plan.layers.length;i++){
    var spec=plan.layers[i],layer;
    if(spec.type==='text'){
     layer=source.layers.addText(spec.text);var doc=layer.property('ADBE Text Properties').property('ADBE Text Document'),d=doc.value;d.font='ArialMT';d.fontSize=spec.fontSize;d.applyFill=true;d.fillColor=rgb(spec.color);d.applyStroke=false;d.justification=ParagraphJustification.CENTER_JUSTIFY;doc.setValue(d);
     var bounds=layer.sourceRectAtTime(0,false);if(bounds.width>spec.maxWidth){d=doc.value;d.fontSize=Math.max(1,d.fontSize*spec.maxWidth/bounds.width);doc.setValue(d);bounds=layer.sourceRectAtTime(0,false);}
     tr(layer,'ADBE Position').setValue([spec.position[0]-bounds.left-bounds.width/2,spec.position[1]-bounds.top-bounds.height/2]);
     if(spec.counter){SLToolkitControls.slider(layer,'Start value',spec.counter.start,defer,keys);SLToolkitControls.slider(layer,'Direction',spec.counter.direction,defer,keys);doc.expression='var n=Math.max(0,Math.floor(effect("Start value")(1)+time*effect("Direction")(1)));var m=Math.floor(n/60),s=n%60;m+":"+(s<10?"0":"")+s;';}
    }else{
     layer=source.layers.addShape();tr(layer,'ADBE Position').setValue(spec.position);var vectors=layer.property('ADBE Root Vectors Group');
     if(spec.type==='rect'){
      var rect=vectors.addProperty('ADBE Vector Shape - Rect');rect.property('ADBE Vector Rect Size').setValue(spec.size);rect.property('ADBE Vector Rect Roundness').setValue(spec.radius||0);vectors.addProperty('ADBE Vector Graphic - Fill').property('ADBE Vector Fill Color').setValue(rgb(spec.color));
     }else{
      var path=vectors.addProperty('ADBE Vector Shape - Group'),shape=new Shape();shape.vertices=spec.points;shape.closed=false;shape.inTangents=[];shape.outTangents=[];for(var pi=0;pi<spec.points.length;pi++){shape.inTangents.push(spec.inTangents?spec.inTangents[pi]:[0,0]);shape.outTangents.push(spec.outTangents?spec.outTangents[pi]:[0,0]);}path.property('ADBE Vector Shape').setValue(shape);var stroke=vectors.addProperty('ADBE Vector Graphic - Stroke');stroke.property('ADBE Vector Stroke Color').setValue(rgb(spec.color));stroke.property('ADBE Vector Stroke Width').setValue(spec.stroke);
      if(spec.draw){var trim=vectors.addProperty('ADBE Vector Filter - Trim').property('ADBE Vector Trim End');trim.setValueAtTime(0,0);trim.setValueAtTime(Math.min(1,plan.duration*.35),100);ease(trim);}
     }
    }
    layer.name=spec.name;layer.comment='Storylens Toolkit editable '+(spec.role||spec.type);layer.inPoint=0;layer.outPoint=plan.duration;
    var opacity=tr(layer,'ADBE Opacity'),alpha=spec.opacity===undefined?100:spec.opacity,entry=Math.min(.35,plan.duration/4),exit=Math.min(.3,plan.duration/4),delay=.2*i/Math.max(1,plan.layers.length-1);opacity.setValueAtTime(delay,0);opacity.setValueAtTime(delay+entry,alpha);opacity.setValueAtTime(plan.duration-exit,alpha);opacity.setValueAtTime(plan.duration,0);ease(opacity);
    if(spec.grow){tr(layer,'ADBE Anchor Point').setValue([-spec.size[0]/2,0]);tr(layer,'ADBE Position').setValue([spec.position[0]-spec.size[0]/2,spec.position[1]]);var scale=tr(layer,'ADBE Scale');scale.setValueAtTime(0,[0,100]);scale.setValueAtTime(Math.min(1,plan.duration*.4),[100,100]);ease(scale);}
    if(spec.pop){var scale=tr(layer,'ADBE Scale');scale.setValueAtTime(0,[75,75]);scale.setValueAtTime(.25,[108,108]);scale.setValueAtTime(.45,[100,100]);ease(scale);}
   }
   var oldDuration=comp.duration;if(start+plan.duration>comp.duration){defer(function(){comp.duration=oldDuration;});comp.duration=start+plan.duration;}
   var inserted=comp.layers.add(source);defer(function(){inserted.remove();});inserted.name=plan.name;inserted.startTime=start;inserted.inPoint=start;inserted.outPoint=start+plan.duration;inserted.comment=source.comment;
   return {ok:true,name:plan.name,changed:1,createdLayers:plan.layers.length,editable:true,comp_id:source.id,layer_id:inserted.id,message:plan.name+' added at '+start.toFixed(2)+'s. Double-click its layer to edit text, shapes and animation.'};
  }};
 }
 root.SLToolkitBuilders={prepare:prepare,folder:folder,ease:ease};
})(typeof $!=='undefined'&&$.global?$.global:this);
