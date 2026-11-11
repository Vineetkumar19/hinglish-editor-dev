/* Read the visible crop through native 2D/3D transforms. Temporary probe is removed. */
var SLCopyPasteViewport=(function(){
 function area(p){var a=0;for(var i=0;i<p.length;i++){var n=p[(i+1)%p.length];a+=p[i][0]*n[1]-n[0]*p[i][1];}return a/2;}
 function clip(subject,boundary){
  if(subject.length<3||boundary.length<3)return [];
  var sign=area(boundary)>=0?1:-1,out=subject;
  for(var k=0;k<boundary.length;k++){
   var a=boundary[k],b=boundary[(k+1)%boundary.length],input=out;out=[];if(!input.length)break;
   function side(p){return sign*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]));}
   for(var j=0;j<input.length;j++){var s=input[j],e=input[(j+1)%input.length],ds=side(s),de=side(e);
    if(ds>=-.001)out.push(s);
    if((ds<0&&de>0)||(ds>0&&de<0)){var f=ds/(ds-de);out.push([s[0]+(e[0]-s[0])*f,s[1]+(e[1]-s[1])*f]);}
   }
  }return out;
 }
 function convex(p){if(p.length<3)return false;var sign=0;for(var i=0;i<p.length;i++){var a=p[i],b=p[(i+1)%p.length],c=p[(i+2)%p.length],v=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]);if(Math.abs(v)<.001)continue;if(sign&&sign*v<0)return false;sign=v;}return !!sign;}
 function rect(p){
  var x=0,y=0,sum=0,l=Infinity,t=Infinity,r=-Infinity,b=-Infinity,i;
  // Area centroid is invariant to duplicate/collinear samples. Averaging
  // vertices incorrectly drags the centre toward densely sampled mask edges.
  for(i=0;i<p.length;i++){var next=p[(i+1)%p.length],cross=p[i][0]*next[1]-next[0]*p[i][1];sum+=cross;x+=(p[i][0]+next[0])*cross;y+=(p[i][1]+next[1])*cross;l=Math.min(l,p[i][0]);r=Math.max(r,p[i][0]);t=Math.min(t,p[i][1]);b=Math.max(b,p[i][1]);}
  if(Math.abs(sum)<.000001)throw Error('The visible picture area is degenerate.');x/=3*sum;y/=3*sum;
  var hx=Math.min(x-l,r-x),hy=Math.min(y-t,b-y),lo=0,hi=1;
  for(i=0;i<22;i++){var m=(lo+hi)/2,box=[[x-hx*m,y-hy*m],[x+hx*m,y-hy*m],[x+hx*m,y+hy*m],[x-hx*m,y+hy*m]];if(Math.abs(area(clip(box,p)))>=4*hx*hy*m*m-.001)lo=m;else hi=m;}
  return [x-hx*lo,y-hy*lo,x+hx*lo,y+hy*lo];
 }
 function contains(a,v){for(var i=0;i<a.length;i++)if(String(a[i])===String(v))return true;return false;}
 function routes(t,slot){
  var out=[],stack={},count=0;
  function walk(c,chain){
   if(stack[c.id]||chain.length>40||++count>6000)return;stack[c.id]=true;
   if(String(c.id)===String(slot.comp)){
    if(slot.empty)out.push(chain);else for(var z=0;z<slot.layers.length;z++)out.push(chain.concat([c.layer(slot.layers[z])]));
   }else for(var i=1;i<=c.numLayers;i++){var l=c.layer(i);if(l.source instanceof CompItem&&contains(slot.ancestors,String(l.source.id)))walk(l.source,chain.concat([l]));}
   delete stack[c.id];
  }
  walk(t.root,[t.layer]);return out;
 }
 function sourceTime(l,time){if(l.timeRemapEnabled)return l.property('ADBE Time Remapping').valueAtTime(time,false);return (time-l.startTime)*100/(l.stretch||100);}
 function times(route){
  var lo=0,hi=route[0].containingComp.duration,a=1,b=0;
  for(var i=0;i<route.length;i++){
   var l=route[i],u=(l.inPoint-b)/a,v=(l.outPoint-b)/a;lo=Math.max(lo,Math.min(u,v));hi=Math.min(hi,Math.max(u,v));
   if(l.timeRemapEnabled)break;var f=100/(l.stretch||100);a*=f;b=(b-l.startTime)*f;
  }
  var out=[];for(i=0;i<9;i++)out.push(lo+(hi-lo)*(.04+.92*i/8));return out;
 }
 function finish(all,w,h,warnings,method){
  if(!all.length)throw Error('No visible picture frame could be measured.');
  var max=0,best=null,i;for(i=0;i<all.length;i++)if(all[i].area>max){max=all[i].area;best=all[i];}
  var common=[[0,0],[w,0],[w,h],[0,h]],kept=0;for(i=0;i<all.length;i++)if(all[i].area>=max*.7){common=clip(common,all[i].poly);kept++;}
  if(common.length<3||Math.abs(area(common))<max*.06){common=best.poly;warnings.push('Large camera travel has no shared safe crop; review the moving shot.');}
  return {rect:rect(common),method:method,samples:all.length,stable_samples:kept,warnings:warnings};
 }
 function multiply(a,b){return [a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]];}
 function inversePoint(m,p){var d=m[0]*m[3]-m[1]*m[2];if(Math.abs(d)<.000001)throw Error('Singular 2D transform');var x=p[0]-m[4],y=p[1]-m[5];return [(m[3]*x-m[2]*y)/d,(-m[1]*x+m[0]*y)/d];}
 function matrix2D(layer,time,depth){
  if(depth>40||layer.threeDLayer||layer.collapseTransformation)throw Error('Use projected measurement');
  if(layer.autoOrient&&!(typeof AutoOrientType!=='undefined'&&layer.autoOrient===AutoOrientType.NO_AUTO_ORIENT))throw Error('Use projected auto orientation');
  var comp=layer.containingComp,source=layer.source;
  if(Math.abs((comp.pixelAspect||1)-(source&&source.pixelAspect||1))>.000001)throw Error('Use projected pixel aspect');
  var group=layer.property('ADBE Transform Group');
  function value(name){var p=group.property(name);if(!p)throw Error('Transform unavailable');return p.valueAtTime(time,false);}
  var a=value('ADBE Anchor Point'),p=value('ADBE Position'),s=value('ADBE Scale'),r=Number(value('ADBE Rotate Z'))*Math.PI/180,skew=group.property('ADBE Skew');
  if(skew&&Math.abs(skew.valueAtTime(time,false))>.000001)throw Error('Use projected skew');
  if(!a||!p||!s||!isFinite(a[0]+a[1]+p[0]+p[1]+s[0]+s[1]+r))throw Error('Transform unavailable');
  var c=Math.cos(r),n=Math.sin(r),sx=s[0]/100,sy=s[1]/100,m=[c*sx,n*sx,-n*sy,c*sy,0,0];m[4]=p[0]-m[0]*a[0]-m[2]*a[1];m[5]=p[1]-m[1]*a[0]-m[3]*a[1];
  if(layer.parent)m=multiply(matrix2D(layer.parent,time,depth+1),m);
  return m;
 }
 function fast2D(paths,w,h){
  var all=[];
  for(var pi=0;pi<paths.length;pi++){
   var route=paths[pi],ts=times(route),i,j,k;
   for(i=0;i<route.length;i++){
    var l=route[i],masks=l.property('ADBE Mask Parade');
    if(l.threeDLayer||l.collapseTransformation||l.trackMatteLayer||l.hasTrackMatte||masks&&masks.numProperties)throw Error('Use projected masks or camera');
   }
   for(var ti=0;ti<ts.length;ti++){
    var local=ts[ti],matrices=[],active=true;
    for(i=0;i<route.length;i++){
     l=route[i];if(l.enabled===false||local<l.inPoint||local>=l.outPoint){active=false;break;}
     var opacity=l.property('ADBE Transform Group').property('ADBE Opacity');if(opacity&&opacity.valueAtTime(local,false)<5){active=false;break;}
     matrices.push(matrix2D(l,local,0));local=sourceTime(l,local);
    }
    if(!active)continue;
    var poly=[[0,0],[w,0],[w,h],[0,h]];
    for(i=0;i<route.length&&poly.length>=3;i++){
     var comp=route[i].containingComp,boundary=[[0,0],[comp.width,0],[comp.width,comp.height],[0,comp.height]];
     for(j=0;j<boundary.length;j++)for(k=i;k<route.length;k++)boundary[j]=inversePoint(matrices[k],boundary[j]);
     poly=clip(poly,boundary);
    }
    if(poly.length>=3&&Math.abs(area(poly))>1)all.push({poly:poly,area:Math.abs(area(poly)),time:ts[ti]});
   }
  }
  return finish(all,w,h,[],'native-2d-viewport');
 }
 function measure(t,slot,w,h){
  var full=[[0,0],[w,0],[w,h],[0,h]],all=[],warnings=[],paths=routes(t,slot),probe=null,selection=t.comp.selectedLayers;
  // Native 2D math preserves all nine motion samples without creating text,
  // evaluating a probe expression or disturbing the Project bin's selection.
  if(paths.length&&paths.length<=24)try{return fast2D(paths,w,h);}catch(fastUnsupported){}
  // Non-native test fixtures and obsolete hosts cannot evaluate camera expressions.
  if(typeof t.comp.layers.addText!=='function')return {rect:[0,0,w,h],method:'holder-only',warnings:['Animated viewport could not be measured.']};
  if(!paths.length||paths.length>24)throw Error('The selected holder has too many different visible frame paths.');
  try{
   var point=null,shapeProbe=false;
   if(typeof t.comp.layers.addShape==='function')try{
    probe=t.comp.layers.addShape();
    point=probe.property('ADBE Root Vectors Group').addProperty('ADBE Vector Shape - Group').property('ADBE Vector Shape');shapeProbe=true;
   }catch(shapeUnavailable){if(probe){probe.remove();probe=null;}point=null;}
   if(!point){probe=t.comp.layers.addText('');point=probe.property('ADBE Text Properties').property('ADBE Text Document');}
   probe.name='Storylens temporary frame probe';probe.enabled=false;probe.guideLayer=true;probe.shy=true;
   for(var pi=0;pi<paths.length;pi++){
    var route=paths[pi],refs=['thisLayer'],flags=[],queries=[],groups=[],i,j,k;
    for(i=0;i<route.length;i++){
     if(i)refs.push('L['+(i-1)+'].source.layer('+route[i].index+')');flags.push(!!route[i].threeDLayer);if(route[i].collapseTransformation)warnings.push('Collapsed transformations need visual review.');
     var c=route[i].containingComp,group=[];
     for(j=0;j<4;j++){group.push(queries.length);queries.push({start:i,p:[[0,0],[c.width,0],[c.width,c.height],[0,c.height]][j]});}groups.push(group);
     var masks=route[i].property('ADBE Mask Parade');
     if(masks)for(j=1;j<=masks.numProperties;j++){
      var mask=masks.property(j);if(typeof MaskMode==='undefined')continue;if(mask.maskMode===MaskMode.NONE)continue;if(mask.inverted||(mask.maskMode!==MaskMode.ADD&&mask.maskMode!==MaskMode.INTERSECT)){warnings.push('Subtractive or inverted masks need visual review.');continue;}
      group=[];for(k=0;k<24;k++){group.push(queries.length);queries.push({start:i+1,maskLayer:i,mask:j,u:k/24});}groups.push(group);
     }
     try{var matte=route[i].trackMatteLayer;if(matte){group=[];for(k=0;k<4;k++){group.push(queries.length);queries.push({start:i,matte:matte.index,comp:i,corner:k});}groups.push(group);warnings.push('Track matte bounds sampled; arbitrary matte effects are not measured.');}}catch(_){}
    }
    var ts=times(route),activeTimes=[];
    for(var ti=0;ti<ts.length;ti++){
     var rootTime=ts[ti],local=rootTime,active=true;
     for(i=0;i<route.length;i++){var l=route[i];if(l.enabled===false||local<l.inPoint||local>=l.outPoint){active=false;break;}var tr=l.property('ADBE Transform Group'),op=tr&&tr.property('ADBE Opacity');if(op&&typeof op.valueAtTime==='function'&&op.valueAtTime(local,false)<5){active=false;break;}local=sourceTime(l,local);}
     if(active)activeTimes.push(rootTime);
    }
    if(!activeTimes.length)continue;
    // The same nine explicit times share ONE expression evaluation. Repeated
    // valueAtTime calls make AE invalidate/evaluate its graph on every sample.
    var setup='';for(i=1;i<refs.length;i++)setup+='L.push('+refs[i]+');';
    var expr='var L=[thisComp.layer('+t.layer.index+')];'+setup+
     'var Q='+SLCopyPaste.json(queries)+',F='+SLCopyPaste.json(flags)+',ST='+SLCopyPaste.json(activeTimes)+';var vertices=[],frames=[];for(var st=0;st<ST.length;st++){'+
     'var C=[thisComp],T=[ST[st]];for(var z=1;z<L.length;z++){C.push(L[z-1].source);T.push(L[z-1].sourceTime(T[z-1]));}'+
     'var out=[];for(var qi=0;qi<Q.length;qi++){var q=Q[qi],p=q.p;'+
     'if(q.mask!==undefined)p=L[q.maskLayer].mask(q.mask).maskPath.pointOnPath(q.u,T[q.maskLayer]);'+
     'if(q.matte!==undefined){var m=C[q.comp].layer(q.matte),r=m.sourceRectAtTime(T[q.comp],false);p=m.toComp([r.left+(q.corner===1||q.corner===2?r.width:0),r.top+(q.corner>=2?r.height:0)],T[q.comp]);}'+
     'for(var z=q.start;z<L.length;z++)p=F[z]?L[z].fromCompToSurface(p,T[z]):L[z].fromComp(p,T[z]);'+
     (shapeProbe?'vertices.push([p[0],p[1]]);':'out.push(p[0]+","+p[1]);')+'}frames.push(out.join(";"));}'+(shapeProbe?'createPath(vertices,[],[],false);':'frames.join("|");');
    point.expression=expr;
    var evaluated=point.valueAtTime(activeTimes[0],false);if(point.expressionError)throw Error(point.expressionError);
    var frames=shapeProbe?evaluated.vertices:String(evaluated.text).split('|');if(frames.length!==(shapeProbe?activeTimes.length*queries.length:activeTimes.length))throw Error('Incomplete frame time samples.');
    SLCopyPasteViewport.lastProjection={shape:shapeProbe,samples:activeTimes.length,time:activeTimes[0]};
    for(ti=0;ti<activeTimes.length;ti++){
     rootTime=activeTimes[ti];var values=shapeProbe?frames.slice(ti*queries.length,(ti+1)*queries.length):frames[ti].split(';');if(values.length!==queries.length)throw Error('Incomplete frame projection.');
     var poly=full;
     for(i=0;i<groups.length&&poly.length>=3;i++){
      var boundary=[];for(j=0;j<groups[i].length;j++){var parts=shapeProbe?values[groups[i][j]]:values[groups[i][j]].split(','),v=[Number(parts[0]),Number(parts[1])];if(!v||!isFinite(v[0])||!isFinite(v[1]))throw Error('Invalid projected picture frame.');boundary.push([v[0],v[1]]);}
      if(!convex(boundary)){warnings.push('An irregular mask needs visual review.');continue;}poly=clip(poly,boundary);
     }
     if(poly.length>=3&&Math.abs(area(poly))>1)all.push({poly:poly,area:Math.abs(area(poly)),time:rootTime});
    }
   }
  }finally{if(probe)probe.remove();for(var si=0;si<selection.length;si++)selection[si].selected=true;}
  return finish(all,w,h,warnings,'native-projected-viewport');
 }
 return {measure:measure,clip:clip,rect:rect};
})();
