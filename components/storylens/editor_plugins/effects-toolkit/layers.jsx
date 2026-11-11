(function(root){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function bounds(l,time){var r=l.sourceRectAtTime(time,false),a=tr(l,'ADBE Anchor Point').value,p=tr(l,'ADBE Position').value,s=tr(l,'ADBE Scale').value,t=tr(l,'ADBE Rotate Z').value*Math.PI/180,minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity,points=[[r.left,r.top],[r.left+r.width,r.top],[r.left,r.top+r.height],[r.left+r.width,r.top+r.height]];for(var i=0;i<4;i++){var x=(points[i][0]-a[0])*s[0]/100,y=(points[i][1]-a[1])*s[1]/100,xx=p[0]+x*Math.cos(t)-y*Math.sin(t),yy=p[1]+x*Math.sin(t)+y*Math.cos(t);minX=Math.min(minX,xx);maxX=Math.max(maxX,xx);minY=Math.min(minY,yy);maxY=Math.max(maxY,yy);}if(!isFinite(minX+maxX+minY+maxY))throw Error('The layer bounds could not be measured.');return {left:minX,top:minY,right:maxX,bottom:maxY,width:maxX-minX,height:maxY-minY,cx:(minX+maxX)/2,cy:(minY+maxY)/2};}
 function shift(property,delta,defer,keys){var old=property.value,oldKeys=property.numKeys?keys.snapshot(property):[];defer(function(){if(oldKeys.length)keys.restore(property,oldKeys);else property.setValue(old);});function moved(v){var a=[];for(var i=0;i<v.length;i++)a.push(v[i]+(delta[i]||0));return a;}if(property.numKeys)for(var k=1;k<=property.numKeys;k++)property.setValueAtKey(k,moved(property.keyValue(k)));else property.setValue(moved(old));}
 function prepare(comp,layers,p,keys){var id=p.id,s=p.settings,i,j,plans=[],minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
  if(!layers.length)throw Error('Select timeline layers first.');
  if(id==='precompose'){
   var selected={};for(i=0;i<layers.length;i++)selected[layers[i].id]=true;for(i=0;i<layers.length;i++)if(layers[i].parent&&!selected[layers[i].parent.id])throw Error('Select the parent layer too, or unparent before precomposing.');
  }else if(id==='parent-null'){
   for(i=0;i<layers.length;i++)if(layers[i].parent!==layers[0].parent||!!layers[i].threeDLayer!==!!layers[0].threeDLayer)throw Error('Selected layers must share the same parent and 2D/3D mode.');
  }else for(i=0;i<layers.length;i++){
   var l=layers[i];if(l.threeDLayer||l.parent)throw Error('Use unparented 2D layers for these layout operations.');
   var position=tr(l,'ADBE Position');if(position.expression||position.dimensionsSeparated)throw Error('Use combined Position without a custom expression.');
   if(id==='anchor'||id==='fit-fill')for(j=0;j<3;j++){var prop=tr(l,['ADBE Scale','ADBE Rotate Z','ADBE Anchor Point'][j]);if(prop.numKeys||prop.expression)throw Error('Apply this layout before animating scale, rotation or anchor point.');}
   if(id==='fit-fill'&&position.numKeys)throw Error('Fit/Fill needs a static Position. Apply sizing before animation.');
   if(id==='fit-fill'&&s.mode==='fill'&&Math.abs(tr(l,'ADBE Rotate Z').value/90-Math.round(tr(l,'ADBE Rotate Z').value/90))>.0001)throw Error('Rotate to a multiple of 90 degrees before Fill, or precompose the rotated content.');
   var b=bounds(l,comp.time);plans.push({layer:l,b:b});minX=Math.min(minX,b.left);minY=Math.min(minY,b.top);maxX=Math.max(maxX,b.right);maxY=Math.max(maxY,b.bottom);
  }
  if(id==='align'&&s.mode.indexOf('distribute')===0&&layers.length<3)throw Error('Select at least three layers to distribute.');
  if(id==='fit-fill'&&(comp.width-2*s.margin<=0||comp.height-2*s.margin<=0))throw Error('Reduce the margin so the target frame has positive dimensions.');
  var all=[];
  if(id==='resize-content'){
   var width=Math.ceil(maxX-minX+2*s.padding),height=Math.ceil(maxY-minY+2*s.padding);if(width<4||height<4||width>30000||height>30000)throw Error('The measured size is outside After Effects composition limits.');
   for(i=1;i<=comp.numLayers;i++){var l=comp.layer(i);if(typeof CameraLayer!=='undefined'&&l instanceof CameraLayer||typeof LightLayer!=='undefined'&&l instanceof LightLayer)continue;if(l.parent||l.threeDLayer||l.locked||tr(l,'ADBE Position').expression||tr(l,'ADBE Position').dimensionsSeparated)throw Error('Resize to Content needs unlocked unparented 2D layers without Position expressions throughout this composition.');all.push(l);}
  }
  return {apply:function(defer){
   if(id==='precompose'){
    var indices=[],low=Infinity,high=-Infinity;for(var i=0;i<layers.length;i++){indices.push(layers[i].index);low=Math.min(low,layers[i].inPoint);high=Math.max(high,layers[i].outPoint);}indices.sort(function(a,b){return a-b;});var parent=SLToolkitBuilders.folder('Effects',app.project.rootFolder,defer),folder=SLToolkitBuilders.folder('Layer Utilities',parent,defer),source=comp.layers.precompose(indices,s.name,true);
    // Native Precompose is one undoable graph operation; it cannot be reconstructed safely after a subsequent failure.
    defer(function(){throw Error('Use native Undo to restore Precompose.');});source.parentFolder=folder;
    if(s.duration==='trimmed'){var wrapper=null;for(i=1;i<=comp.numLayers;i++)if(comp.layer(i).source===source)wrapper=comp.layer(i);if(!wrapper)throw Error('The new precomp layer could not be identified.');for(i=1;i<=source.numLayers;i++)source.layer(i).startTime-=low;source.duration=high-low;wrapper.startTime=low;wrapper.inPoint=low;wrapper.outPoint=high;}
    return {ok:true,changed:1,message:'Layers precomposed as '+s.name+'. Use AE Undo to restore the original layer structure.'};
   }
   if(id==='parent-null'){
    var group=SLToolkitCamera.ownedNull(comp,s.name,defer),parent=layers[0].parent,dimensions=layers[0].threeDLayer?3:2,mean=[];group.threeDLayer=!!layers[0].threeDLayer;group.parent=parent;
    for(var d=0;d<dimensions;d++){var sum=0;for(var i=0;i<layers.length;i++)sum+=tr(layers[i],'ADBE Position').value[d]||0;mean.push(sum/layers.length);}tr(group,'ADBE Anchor Point').setValue(dimensions===3?[0,0,0]:[0,0]);tr(group,'ADBE Position').setValue(mean);
    for(i=0;i<layers.length;i++)(function(l){var old=l.parent;defer(function(){l.parent=old;});l.parent=group;})(layers[i]);return {ok:true,changed:layers.length,message:'Layers parented to '+s.name+'. Animate the new control null.'};
   }
   if(id==='resize-content'){
    var oldWidth=comp.width,oldHeight=comp.height;defer(function(){comp.width=oldWidth;comp.height=oldHeight;});for(var i=0;i<all.length;i++)shift(tr(all[i],'ADBE Position'),[-minX+s.padding,-minY+s.padding],defer,keys);comp.width=width;comp.height=height;return {ok:true,changed:all.length,message:'Composition resized to '+width+' × '+height+' at the current frame. Review the rest of the animation.'};
   }
   var sorted=plans.slice(0);if(id==='align'&&s.mode.indexOf('distribute')===0)sorted.sort(function(a,b){return s.mode==='distribute-x'?a.b.cx-b.b.cx:a.b.cy-b.b.cy;});
   for(var i=0;i<sorted.length;i++)(function(plan,index){var l=plan.layer,b=plan.b,delta=[0,0];
    if(id==='anchor'){
     var rect=l.sourceRectAtTime(comp.time,false),old=tr(l,'ADBE Anchor Point').value,x=s.position.indexOf('left')>=0?0:s.position.indexOf('right')>=0?1:.5,y=s.position.indexOf('top')>=0?0:s.position.indexOf('bottom')>=0?1:.5,next=[rect.left+rect.width*x,rect.top+rect.height*y],scale=tr(l,'ADBE Scale').value,angle=tr(l,'ADBE Rotate Z').value*Math.PI/180,dx=(next[0]-old[0])*scale[0]/100,dy=(next[1]-old[1])*scale[1]/100;delta=[dx*Math.cos(angle)-dy*Math.sin(angle),dx*Math.sin(angle)+dy*Math.cos(angle)];defer(function(){tr(l,'ADBE Anchor Point').setValue(old);});tr(l,'ADBE Anchor Point').setValue(next);
    }else if(id==='fit-fill'){
     if(b.width<=0||b.height<=0)throw Error('The layer has no measurable visible area.');var factor=s.mode==='fit'?Math.min((comp.width-2*s.margin)/b.width,(comp.height-2*s.margin)/b.height):Math.max((comp.width-2*s.margin)/b.width,(comp.height-2*s.margin)/b.height),old=tr(l,'ADBE Scale').value;defer(function(){tr(l,'ADBE Scale').setValue(old);});tr(l,'ADBE Scale').setValue([old[0]*factor,old[1]*factor]);var after=bounds(l,comp.time);delta=[comp.width/2-after.cx,comp.height/2-after.cy];
    }else{
     var left=s.reference==='composition'?s.margin:minX,right=s.reference==='composition'?comp.width-s.margin:maxX,top=s.reference==='composition'?s.margin:minY,bottom=s.reference==='composition'?comp.height-s.margin:maxY;
     if(s.mode==='left')delta[0]=left-b.left;if(s.mode==='right')delta[0]=right-b.right;if(s.mode==='center-x')delta[0]=(left+right)/2-b.cx;if(s.mode==='top')delta[1]=top-b.top;if(s.mode==='bottom')delta[1]=bottom-b.bottom;if(s.mode==='center-y')delta[1]=(top+bottom)/2-b.cy;
     if(s.mode==='distribute-x')delta[0]=sorted[0].b.cx+(sorted[sorted.length-1].b.cx-sorted[0].b.cx)*index/(sorted.length-1)-b.cx;if(s.mode==='distribute-y')delta[1]=sorted[0].b.cy+(sorted[sorted.length-1].b.cy-sorted[0].b.cy)*index/(sorted.length-1)-b.cy;
    }
    shift(tr(l,'ADBE Position'),delta,defer,keys);
   })(sorted[i],i);
   return {ok:true,changed:layers.length,message:SLToolkitModel.find(id).name+' applied. Positions and native transforms remain editable.'};
  }};
 }
 root.SLToolkitLayers={prepare:prepare,bounds:bounds,shift:shift};
})(typeof $!=='undefined'&&$.global?$.global:this);
