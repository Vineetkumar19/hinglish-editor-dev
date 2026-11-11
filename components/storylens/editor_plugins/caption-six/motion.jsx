/* Text-local Caption 6 rise/blur, cut replacements and editable drawn paths. */
(function(g){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function verifyFill(l,w){var d=l.property('ADBE Text Properties').property('ADBE Text Document').value;for(var i=0;i<3;i++)if(Math.abs(d.fillColor[i]-w.fill_rgb[i]/255)>.003)throw Error('Caption 6 could not retain the colour for '+w.text+'. Retry keeps existing layers.');}
 function ease(property){for(var k=1;k<=property.numKeys;k++){var es=[],count=property.keyInTemporalEase(k).length;for(var j=0;j<count;j++)es.push(new KeyframeEase(0,66));property.setInterpolationTypeAtKey(k,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);property.setTemporalEaseAtKey(k,es,es);if(property.isSpatial){var z=[];for(j=0;j<property.keyValue(k).length;j++)z.push(0);property.setSpatialTangentsAtKey(k,z,z);}}}
 function animate(l,w,page,position,factor){
  var onset=Math.max(0,w.start-page.start),off=Math.min(page.end-page.start,w.visible_end-page.start),available=Math.max(.001,off-onset),rise=Math.min(w.motion.seconds,available*.55),fade=Math.min(w.motion.fade_seconds,available*.45),p=tr(l,'ADBE Position'),alpha=tr(l,'ADBE Opacity');
  l.inPoint=onset;l.outPoint=off;tr(l,'ADBE Rotate Z').setValue(0);
  if(page.motion_kind==='cut'){p.setValue([position.x,position.y]);alpha.setValue(100);return;}
  // Native spatial tangents are zero: no diagonal path, tilt or camera zoom.
  p.setValueAtTime(onset,[position.x,position.y+w.motion.y*factor]);p.setValueAtTime(onset+rise,[position.x,position.y]);alpha.setValueAtTime(onset,0);alpha.setValueAtTime(onset+fade,100);
  var effect=l.property('ADBE Effect Parade').addProperty('ADBE Gaussian Blur 2'),blur=effect.property(1);blur.setValueAtTime(onset,7.5*factor);blur.setValueAtTime(onset+rise,0);
  if(page.motion_kind==='count'&&available>.16){var exit=Math.min(.14,available*.30),exitStart=Math.max(onset+rise,off-exit);p.setValueAtTime(exitStart,[position.x,position.y]);p.setValueAtTime(off,[position.x,position.y-32*factor]);alpha.setValueAtTime(exitStart,100);alpha.setValueAtTime(off,0);blur.setValueAtTime(exitStart,0);blur.setValueAtTime(off,7.5*factor);}
  ease(p);ease(alpha);ease(blur);
  // Cubic ease-out: start at 3*distance/time and settle with zero velocity.
  // One spatial speed applies to the straight 2D path in native AE.
  p.setTemporalEaseAtKey(1,[new KeyframeEase(0,33.333)],[new KeyframeEase(3*w.motion.y*factor/Math.max(.001,rise),33.333)]);p.setTemporalEaseAtKey(2,[new KeyframeEase(0,33.333)],[new KeyframeEase(0,33.333)]);
 }
 function decorate(){return null;}
 function finish(scene){
  var page=scene.page,c=scene.comp,geometry=scene.geometry,factor=geometry.factor*geometry.fit;
  for(var di=0;di<page.decorations.length;di++){
   var spec=page.decorations[di],target=spec.target_rows||[],bounds=[1e20,1e20,-1e20,-1e20],found=false,i,j;
   for(i=0;i<page.rows.length;i++){var row=page.rows[i];if(target.length&&target.indexOf(row.source_row)<0)continue;var box=geometry.rows[row.id];bounds[0]=Math.min(bounds[0],box.left);bounds[1]=Math.min(bounds[1],box.top);bounds[2]=Math.max(bounds[2],box.right);bounds[3]=Math.max(bounds[3],box.bottom);found=true;}
   if(!found||!spec.path||!spec.path.length)continue;
   // Retain the traced Bezier shape, resizing around its current target lettering.
   var minX=1e20,minY=1e20,maxX=-1e20,maxY=-1e20;
   for(i=0;i<spec.path.length;i++)for(j=0;j<4;j++){var pt=spec.path[i][j];minX=Math.min(minX,pt[0]);maxX=Math.max(maxX,pt[0]);minY=Math.min(minY,pt[1]);maxY=Math.max(maxY,pt[1]);}
   var circle=spec.kind==='circle',pad=circle?76*factor:10*factor,x0=bounds[0]-pad,x1=bounds[2]+pad,y0=circle?bounds[1]-14*factor:bounds[3]+14*factor,y1=circle?bounds[3]+16*factor:bounds[3]+62*factor;
   function point(p){return [x0+(p[0]-minX)/Math.max(1,maxX-minX)*(x1-x0),y0+(p[1]-minY)/Math.max(1,maxY-minY)*(y1-y0)];}
   var vertices=[],ins=[],outs=[],last=null;
   for(i=0;i<spec.path.length;i++){var seg=spec.path[i],a=point(seg[0]),b=point(seg[1]),d=point(seg[2]),e=point(seg[3]);if(i===0){vertices.push(a);ins.push([0,0]);outs.push([b[0]-a[0],b[1]-a[1]]);}else outs[outs.length-1]=[b[0]-a[0],b[1]-a[1]];vertices.push(e);ins.push([d[0]-e[0],d[1]-e[1]]);outs.push([0,0]);last=e;}
   var shape=new Shape();shape.vertices=vertices;shape.inTangents=ins;shape.outTangents=outs;shape.closed=false;
   var layer=c.layers.addShape();layer.name='EDIT '+(circle?'drawn ellipse':'drawn underline');var root=layer.property('ADBE Root Vectors Group');root.addProperty('ADBE Vector Shape - Group');root.addProperty('ADBE Vector Graphic - Stroke');root.addProperty('ADBE Vector Filter - Trim');
   root.property('ADBE Vector Shape - Group').property('ADBE Vector Shape').setValue(shape);
   var stroke=root.property('ADBE Vector Graphic - Stroke'),hex=spec.color||'#FFFFFF',rgb=[parseInt(hex.substr(1,2),16)/255,parseInt(hex.substr(3,2),16)/255,parseInt(hex.substr(5,2),16)/255];stroke.property('ADBE Vector Stroke Color').setValue(rgb);stroke.property('ADBE Vector Stroke Width').setValue((spec.stroke||3)*factor);stroke.property('ADBE Vector Stroke Line Cap').setValue(2);
   tr(layer,'ADBE Position').setValue([0,0]);tr(layer,'ADBE Anchor Point').setValue([0,0]);
   var trigger=Math.max(0,Math.min(page.words.length-1,Math.floor((spec.trigger||0)*page.words.length/page.template_source.split(/\s+/).length))),start=Math.max(0,page.words[trigger].start-page.start+(spec.delay||0)),span=page.end-page.start,draw=Math.min(spec.duration||.45,Math.max(.001,span-start));
   if(start>=span){layer.remove();continue;}layer.inPoint=start;layer.outPoint=span;var end=root.property('ADBE Vector Filter - Trim').property('ADBE Vector Trim End');end.setValueAtTime(start,0);end.setValueAtTime(start+draw,100);for(i=1;i<=end.numKeys;i++)end.setInterpolationTypeAtKey(i,KeyframeInterpolationType.LINEAR,KeyframeInterpolationType.LINEAR);
   if(spec.glow){var glow=layer.duplicate();glow.name='Underline soft glow';var fx=glow.property('ADBE Effect Parade').addProperty('ADBE Gaussian Blur 2');fx.property(1).setValue(6*factor);tr(glow,'ADBE Opacity').setValue(55);glow.moveAfter(layer);}
  }
 }
 g.StorylensCaptionSixMotion={verifyFill:verifyFill,animate:animate,decorate:decorate,finish:finish};
})(typeof $!=='undefined'?$.global:this);
