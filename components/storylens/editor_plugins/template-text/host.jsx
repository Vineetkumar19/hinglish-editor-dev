/* Final text pass. Read-only scan; isolated staged edits; no save/render/source deletion. */
var SLTemplateText=typeof SLTemplateText==='undefined'?{}:SLTemplateText;
SLTemplateText.item=function(id){if(typeof app.project.itemByID==='function'){try{return app.project.itemByID(Number(id));}catch(_){return null;}}for(var i=1;i<=app.project.numItems;i++)if(String(app.project.item(i).id)===String(id))return app.project.item(i);return null;};
SLTemplateText.json=function(value){return hJSON(value);};
SLTemplateText.hash=function(value){var s=hJSON(value),h=2166136261;for(var i=0;i<s.length;i++){h^=s.charCodeAt(i);h+=(h<<1)+(h<<4)+(h<<7)+(h<<8)+(h<<24);}return String(s.length)+':'+(h>>>0).toString(16);};
SLTemplateText.text=function(layer){try{return layer.property('ADBE Text Properties').property('ADBE Text Document');}catch(_){return null;}};
SLTemplateText.branchMarker='\nStorylens Template Text hidden branch:1';
SLTemplateText.enabled=function(layer){return layer.enabled||String(layer.comment||'').indexOf(SLTemplateText.branchMarker)>=0;};
SLTemplateText.decorationMarker='\nStorylens Template Text hidden decoration:1';
SLTemplateText.baseName=function(name){return name.replace(/ \[(?:Template Text |SLTT )[^\]]+\]$/,'');};
SLTemplateText.alias=function(names,original,replacement){var keys=[original,SLTemplateText.baseName(original)];for(var i=0;i<keys.length;i++){var key=keys[i];if(!names.hasOwnProperty(key))names[key]=replacement;else if(names[key]!==replacement)names[key]=null;}};
SLTemplateText.overrideSignature=function(comp){var rows=[SLTemplateText.baseName(comp.name),comp.numLayers];for(var n=1;n<=comp.numLayers;n++){var l=comp.layer(n),p=SLTemplateText.text(l);if(!p)continue;var text=String(p.value.text),match=String(l.comment||'').match(/\nStorylens Template Text baseline:([^\r\n]+)/);if(match)try{text=JSON.parse(match[1]).text;}catch(_){}rows.push([n,SLTemplateText.baseName(l.name),text]);}return hJSON(rows);};
// Essential Properties can retain text from the original asset after replacing
// a precomp. Only touch Source Text; media/color overrides belong to the owner.
SLTemplateText.syncOverrides=function(group,records){var result={changed:0,unresolved:[]},signatures={};
 function signature(c){var id=String(c.id);if(!signatures.hasOwnProperty(id))signatures[id]=SLTemplateText.overrideSignature(c);return signatures[id];}
 function walk(g){if(!g)return;for(var i=1;i<=g.numProperties;i++){var p=g.property(i);if(p.numProperties){walk(p);continue;}var src=null;try{src=p.essentialPropertySource;}catch(_){}if(!src||src.matchName!=='ADBE Text Document')continue;
  var owner=src.propertyGroup(src.propertyDepth),original=owner&&owner.containingComp;if(!original)continue;var exact=[],similar=[],seen={};
  for(var j=0;j<records.length;j++){var r=records[j];if(String(r.original.id)===String(original.id))exact.push(r.copy);else if(signature(r.original)===signature(original))similar.push(r.copy);}
  var choices=exact.length?exact:similar,candidates=[];for(j=0;j<choices.length;j++)if(!seen[choices[j].id]){seen[choices[j].id]=true;candidates.push(choices[j]);}
  if(!candidates.length)continue;if(candidates.length!==1){result.unresolved.push('Ambiguous title override: '+(p.name||original.name));continue;}
  var layer=candidates[0].layer(owner.index),target=SLTemplateText.text(layer);if(!target)continue;
  if(target.numKeys||p.numKeys||p.expressionEnabled){result.unresolved.push('Animated title override: '+(p.name||original.name));continue;}
  var doc=target.value;if(!layer.enabled&&!layer.isTrackMatte)doc.text='';p.setValue(doc);result.changed++;
 }}walk(group);return result;
};
SLTemplateText.cleanDecorations=function(comps){
 var changed=0,unresolved=[],visibility={},hasText=SLTemplateText.textIndex();
 function visible(c,stack){var id=String(c.id);if(visibility.hasOwnProperty(id))return visibility[id];if(stack[id])return true;var next={};for(var k in stack)next[k]=true;next[id]=true;
  for(var i=1;i<=c.numLayers;i++){var l=c.layer(i);if(l.guideLayer||!l.enabled&&!l.isTrackMatte)continue;if(SLTemplateText.text(l)){visibility[id]=true;return true;}if(l.source&&l.source instanceof CompItem&&visible(l.source,next)){visibility[id]=true;return true;}}
  visibility[id]=false;return false;
 }
 function rect(l){try{var g=l.property('ADBE Transform Group'),at=(l.inPoint+l.outPoint)/2;
  if(l.threeDLayer){var orient=g.property('ADBE Orientation').valueAtTime(at,false);if(Math.abs(orient[0])+Math.abs(orient[1])+Math.abs(orient[2])>.01||Math.abs(g.property('ADBE Rotate X').valueAtTime(at,false))>.01||Math.abs(g.property('ADBE Rotate Y').valueAtTime(at,false))>.01)return null;}
  var rotation=g.property('ADBE Rotate Z');if(Math.abs(Number(rotation.valueAtTime(at,false)))>.01)return null;
  var p=g.property('ADBE Position').valueAtTime(at,false),s=g.property('ADBE Scale').valueAtTime(at,false),a=g.property('ADBE Anchor Point').valueAtTime(at,false),b=l.sourceRectAtTime(at,false);
  if(!p||!s||!a||s[0]<=0||s[1]<=0)return null;
  return {x:p[0]+(b.left-a[0])*s[0]/100,y:p[1]+(b.top-a[1])*s[1]/100,w:b.width*s[0]/100,h:b.height*s[1]/100,space:(l.parent?String(l.parent.id):'')+'/'+(l.threeDLayer?'3d':'2d'),z:l.threeDLayer?p[2]:0};
 }catch(_){return null;}}
 for(var ci=0;ci<comps.length;ci++){
  var c=comps[ci],nodes=[],layers={},names={},owners=[],i,j,groups={},wholeTextGroup=/^(?:text|title|heading|caption|paragraph)(?:[ _\d]|$)/i.test(c.name);
  function group(l){var p=l.parent,depth=0;while(p&&SLTemplateTextModel.decorationCandidate(p.name)&&depth++<32)p=p.parent;return p&&p.nullLayer?String(p.id):null;}
  for(i=1;i<=c.numLayers;i++){var l=c.layer(i),isText=!!SLTemplateText.text(l),source=l.source;
   var textGroup=source&&source instanceof CompItem&&hasText(source)&&/text|title|heading|caption|paragraph/i.test(l.name+' '+source.name);
   var groupId=group(l),isDecoration=SLTemplateTextModel.decorationCandidate(l.name);
   if(!isText&&!textGroup&&!isDecoration&&!l.nullLayer&&!l.isTrackMatte)wholeTextGroup=false;
   if(groupId){if(!groups[groupId])groups[groupId]={owners:[],other:false};if(isText||textGroup)groups[groupId].owners.push(String(l.id));else if(!isDecoration&&!l.nullLayer)groups[groupId].other=true;}
   if(!isText&&!textGroup&&!isDecoration)continue;
   var node={id:String(l.id),name:l.name,text:!!(isText||textGroup),enabled:!l.guideLayer&&(l.enabled||l.isTrackMatte)&&(!textGroup||visible(source,{})),matte:!!l.isTrackMatte,protectedLayer:!!(l.nullLayer||l.adjustmentLayer),rect:rect(l),ownerIds:[]};
   node.group=groupId;nodes.push(node);layers[node.id]=l;if(node.text){owners.push(node);if(names[l.name]===undefined)names[l.name]=node.id;else names[l.name]=null;}
  }
  for(i=0;i<nodes.length;i++)if(!nodes[i].text){var d=nodes[i],layer=layers[d.id];
   if(layer.parent&&layers[String(layer.parent.id)]&&SLTemplateText.text(layer.parent))d.ownerIds.push(String(layer.parent.id));
   if(d.group&&groups[d.group]&&!groups[d.group].other)d.ownerIds=d.ownerIds.concat(groups[d.group].owners);
   d.dedicatedTitle=wholeTextGroup;
   if(wholeTextGroup&&owners.length===1)d.ownerIds.push(owners[0].id);
   // Explicit authored text sizing links work for 3D/parented title groups too.
   function refs(group){for(var pi=1;pi<=group.numProperties;pi++){var prop=group.property(pi);if(prop.canSetExpression&&prop.expression){var re=/thisComp\s*\.\s*layer\s*\(\s*["']([^"']+)["']\s*\)/g,m;while((m=re.exec(prop.expression)))if(names[m[1]])d.ownerIds.push(names[m[1]]);}if(prop.numProperties)refs(prop);}}
   refs(layer);
  }
  var matches=SLTemplateTextModel.decorationOwners(nodes),matched={};
  for(i=0;i<matches.length;i++){var match=matches[i],allHidden=true;matched[match.id]=true;
   for(j=0;j<match.owners.length;j++)for(var oi=0;oi<owners.length;oi++)if(owners[oi].id===match.owners[j]&&owners[oi].enabled)allHidden=false;
   var decoration=layers[match.id],comment=String(decoration.comment||''),marked=comment.indexOf(SLTemplateText.decorationMarker)>=0,lock=decoration.locked;
   if(!allHidden&&!marked)continue;decoration.locked=false;
   try{if(allHidden&&decoration.enabled){decoration.enabled=false;decoration.comment=comment+SLTemplateText.decorationMarker;changed++;}else if(!allHidden&&marked){decoration.enabled=true;decoration.comment=comment.split(SLTemplateText.decorationMarker).join('');}}finally{decoration.locked=lock;}
  }
  for(i=0;i<nodes.length;i++)if(!nodes[i].text&&!nodes[i].matte&&!matched[nodes[i].id])unresolved.push(c.name+' / '+nodes[i].name);
 }
 return {hidden:changed,unresolved:unresolved};
};
SLTemplateText.intersect=function(segments,start,end){var out=[];for(var i=0;i<segments.length;i++){var s=segments[i];if(Math.abs(s.b-s.a)<1e-8){if(s.a>=start&&s.a<end)out.push(s);continue;}var lo=Math.max(Math.min(s.a,s.b),start),hi=Math.min(Math.max(s.a,s.b),end);if(hi-lo<.00001)continue;var rate=(s.b-s.a)/(s.end-s.start);if(Math.abs(rate)<1e-8){if(s.a>=start&&s.a<end)out.push(s);continue;}var u=s.start+(lo-s.a)/rate,v=s.start+(hi-s.a)/rate,from=Math.min(u,v),to=Math.max(u,v);out.push({start:from,end:to,a:s.a+(from-s.start)*rate,b:s.a+(to-s.start)*rate});}return out;};
SLTemplateText.visible=function(segments,layer){
 var active=SLTemplateText.intersect(segments,layer.inPoint,layer.outPoint),property=null,out=[];
 try{property=layer.property('ADBE Transform Group').property('ADBE Opacity');}catch(_){}
 if(!property||!property.valueAtTime)return active;
 if(!property.numKeys&&!property.expressionEnabled)return Number(property.value)>0.5?active:[];
 for(var i=0;i<active.length;i++){
  var s=active[i],span=s.end-s.start,points=[s.start,s.end],count=Math.min(480,Math.max(2,Math.ceil(span*4))),rate=(s.b-s.a)/span;
  for(var n=1;n<count;n++)points.push(s.start+span*n/count);
  if(Math.abs(rate)>1e-8)for(n=1;n<=property.numKeys;n++){var t=s.start+(property.keyTime(n)-s.a)/rate;if(t>s.start&&t<s.end)points.push(t);}
  points.sort(function(a,b){return a-b;});var start=null;
  function visible(t){return Number(property.valueAtTime(s.a+(t-s.start)*rate,false))>0.5;}
  for(n=0;n<points.length-1;n++){var a=points[n],b=points[n+1],mid=(a+b)/2,on=visible(mid);
   if(on&&start===null)start=a;
   if(start!==null&&(!on||n===points.length-2)){var end=on?b:a;if(end-start>.001)out.push({start:start,end:end,a:s.a+(start-s.start)*rate,b:s.a+(end-s.start)*rate});start=null;}
  }
 }return out;
};
SLTemplateText.map=function(segments,layer,warnings){var slices=SLTemplateText.intersect(segments,layer.inPoint,layer.outPoint),out=[],i,j;
 if(!layer.timeRemapEnabled){var speed=100/layer.stretch;if(!isFinite(speed)||speed===0)return [];for(i=0;i<slices.length;i++){var s=slices[i];out.push({start:s.start,end:s.end,a:(s.a-layer.startTime)*speed,b:(s.b-layer.startTime)*speed});}return out;}
 var p=layer.property('ADBE Time Remapping');if(p.expressionEnabled){warnings.push('Time-remapped expression kept: '+layer.name);return [];}
 for(i=0;i<slices.length;i++){var points=[Math.min(slices[i].a,slices[i].b),Math.max(slices[i].a,slices[i].b)];for(j=1;j<=p.numKeys;j++){var t=p.keyTime(j);if(t>points[0]&&t<points[1])points.push(t);}points.sort(function(a,b){return a-b;});
  for(j=0;j<points.length-1;j++){var a=points[j],b=points[j+1],aa=p.valueAtTime(a,false),bb=p.valueAtTime(b,false),mid=p.valueAtTime((a+b)/2,false);if(Math.abs(mid-(aa+bb)/2)>.001){warnings.push('Nonlinear time remap kept: '+layer.name);return [];}var clipped=SLTemplateText.intersect([slices[i]],a,b);for(var n=0;n<clipped.length;n++){var z=clipped[n];out.push({start:z.start,end:z.end,a:aa+(z.a-a)*(bb-aa)/(b-a),b:aa+(z.b-a)*(bb-aa)/(b-a)});}}
 }return out;
};
SLTemplateText.containsText=function(c,stack){if(!c)return false;if(stack[c.id])return false;stack[c.id]=true;for(var i=1;i<=c.numLayers;i++){var l=c.layer(i);if(SLTemplateText.text(l))return true;if(l.source&&l.source instanceof CompItem&&SLTemplateText.containsText(l.source,stack))return true;}return false;};
// Native layer/property access is expensive. Cache both positive and negative
// reachability for this operation only, including shared text-free artwork.
SLTemplateText.textIndex=function(testLayer){var seen={},positive={},parents={};return function(c){
 if(!c||!(c instanceof CompItem))return false;var root=String(c.id);
 if(seen[root])return positive[root]===true;
 // Iterative graph traversal also avoids ExtendScript's recursive closure
 // behaviour. Native host checks, not JavaScript mocks, exercise this path.
 var pending=[c],mark=[],at=0,n,id,l,s,child;
 while(pending.length){var current=pending.pop();id=String(current.id);if(seen[id])continue;seen[id]=true;
  for(n=1;n<=current.numLayers;n++){l=current.layer(n);if((testLayer?testLayer(l):SLTemplateText.text(l))&&!positive[id]){positive[id]=true;mark.push(id);}
   s=l.source;if(!s||!(s instanceof CompItem))continue;child=String(s.id);if(!parents[child])parents[child]=[];parents[child].push(id);
   if(positive[child]&&!positive[id]){positive[id]=true;mark.push(id);}if(!seen[child])pending.push(s);
  }
 }
 while(at<mark.length){var up=parents[mark[at++]]||[];for(n=0;n<up.length;n++)if(!positive[up[n]]){positive[up[n]]=true;mark.push(up[n]);}}
 return positive[root]===true;
};};
SLTemplateText.projectTitles=function(master,snapshot){
 if(!master.layers||typeof master.layers.addShape!=='function')return [];
 var probe=null,selection=master.selectedLayers||[],queries=[],fingerprint=[],i,j,k;
 try{
  probe=master.layers.addShape();probe.name='Storylens temporary title geometry';probe.enabled=false;probe.guideLayer=true;probe.shy=true;
  var point=probe.property('ADBE Root Vectors Group').addProperty('ADBE Vector Shape - Group').property('ADBE Vector Shape'),roots={};
  for(i=1;i<=master.numLayers;i++)roots[String(master.layer(i).id)]=master.layer(i);
  for(i=0;i<snapshot.templates.length;i++){var template=snapshot.templates[i],root=roots[template.layer_id];
   for(j=0;j<template.texts.length;j++){var row=template.texts[j],text=row.baseline_text||row.text;
    if(row.background_text||row.expression||row.unsafe||!row.enabled||!text.replace(/\s/g,'')||text.length>180||text.split(/\s+/).length>18)continue;
    var path=row.id.split('/'),refs=['thisComp.layer('+root.index+')'],flags=[!!root.collapseTransformation],c=root.source;
    for(k=0;k<path.length;k++){var layer=c.layer(Number(path[k]));refs.push('L['+k+'].source.layer('+layer.index+')');flags.push(!!layer.collapseTransformation);if(k<path.length-1)c=layer.source;}
    var run=row.runs[0];for(k=1;k<row.runs.length;k++)if(row.runs[k].end-row.runs[k].start>run.end-run.start)run=row.runs[k];
    if(!run||run.end-run.start<1.5)continue;var times=[];for(k=1;k<=3;k++)times.push(run.start+(run.end-run.start)*k/4);
    row.projected={usable:false,reason:'geometry_unavailable'};
    queries.push({row:row,refs:refs,flags:flags,times:times});
   }
  }
  for(i=0;i<queries.length;i+=24){var batch=queries.slice(i,i+24),expr='var V=[];';
   for(j=0;j<batch.length;j++){var q=batch[j];expr+='var L=['+q.refs[0]+'];';for(k=1;k<q.refs.length;k++)expr+='L.push('+q.refs[k]+');';
    expr+='var F='+JSON.stringify(q.flags)+',ST='+JSON.stringify(q.times)+';for(var s=0;s<ST.length;s++){var T=[ST[s]];for(var z=1;z<L.length;z++)T.push(L[z-1].sourceTime(T[z-1]));var r=L[L.length-1].sourceRectAtTime(T[T.length-1],false);for(var n=0;n<4;n++){var p=[r.left+(n===1||n===2?r.width:0),r.top+(n>=2?r.height:0)];for(z=L.length-1;z>=0;z--)p=z>0&&F[z-1]?L[z].toWorld(p,T[z]):L[z].toComp(p,T[z]);V.push([p[0],p[1]]);}}';
   }point.expression=expr+'createPath(V,[],[],false);';
   var shape=point.valueAtTime(0,false);if(point.expressionError)throw Error(point.expressionError);var vertices=shape.vertices,at=0;if(vertices.length!==batch.length*12)throw Error('Incomplete title geometry.');
   for(j=0;j<batch.length;j++){q=batch[j];var samples=[];for(var s=0;s<3;s++){var xs=[],ys=[];for(k=0;k<4;k++){var v=vertices[at++];xs.push(v[0]);ys.push(v[1]);}samples.push({left:Math.min.apply(Math,xs),right:Math.max.apply(Math,xs),top:Math.min.apply(Math,ys),bottom:Math.max.apply(Math,ys)});}
    q.row.projected=SLTemplateTextModel.titleGeometry(samples,master.width,master.height);
    var rounded=[];for(s=0;s<samples.length;s++)rounded.push([Math.round(samples[s].left),Math.round(samples[s].right),Math.round(samples[s].top),Math.round(samples[s].bottom)]);
    fingerprint.push([q.row.layer_id,q.row.id,rounded]);
   }
  }
 }catch(e){snapshot.warnings.push('Some title positions need visual review: '+String(e));}
 finally{if(probe)probe.remove();for(i=0;i<selection.length;i++)try{selection[i].selected=true;}catch(_){}}
 return fingerprint;
};
SLTemplateText.scan=function(comp,options){
 var legacy=options&&options.legacy===true,nativeStates={},textStates={};
 var result={version:1,project_id:String(storylensProjectId()),composition_id:String(comp.id),name:comp.name,duration:comp.duration,fps:comp.frameRate,templates:[],audio:[],warnings:[]},fingerprint=[],count=0,measurements={};
 var hasText=SLTemplateText.textIndex();
 function walk(c,segments,path,stack,rows,displayOpacity,backgroundText,displayRotation){if(stack[c.id])throw Error('Template Text: this template contains a circular composition.');if(path.length>32)throw Error('Template Text: a template is nested too deeply.');var next={};for(var k in stack)next[k]=true;next[c.id]=true;
  for(var i=1;i<=c.numLayers;i++){var l=c.layer(i),p=SLTemplateText.text(l),layerPath=path.concat([i]);
   var nativeKey=String(c.id)+'/'+String(l.id);if(legacy||!nativeStates[nativeKey]){nativeStates[nativeKey]=true;fingerprint.push([String(c.id),i,String(l.id),l.name,l.enabled,l.startTime,l.inPoint,l.outPoint,l.stretch,l.source?String(l.source.id):'',l.timeRemapEnabled?String(l.property('ADBE Time Remapping').valueAtTime(l.inPoint,false)):'']);}
   fingerprint.push(['guide',nativeKey,!!l.guideLayer,!!l.isTrackMatte]);
   if(l.guideLayer)continue;
   var traversable=SLTemplateText.enabled(l)||l.isTrackMatte;
   if(!p&&(!l.source||!(l.source instanceof CompItem)||!traversable||!hasText(l.source,{})))continue;
   var active=SLTemplateText.visible(segments,l);if(!active.length)continue;
   var opacity=1;try{var opacityProperty=l.property('ADBE Transform Group').property('ADBE Opacity'),span=active[0];if(opacityProperty&&opacityProperty.valueAtTime){opacity=0;for(var sampleIndex=1;sampleIndex<=3;sampleIndex++)opacity=Math.max(opacity,Number(opacityProperty.valueAtTime(span.a+(span.b-span.a)*sampleIndex/4,false))/100);}}catch(_){}
   opacity=(isFinite(opacity)?opacity:1)*(displayOpacity===undefined?1:displayOpacity);
   var titleRotation=Number(displayRotation)||0;try{var rotate=l.property('ADBE Transform Group').property('ADBE Rotate Z');if(rotate&&!rotate.numKeys&&!rotate.expressionEnabled)titleRotation+=Number(rotate.value)||0;}catch(_){}
   var verticalAngle=((titleRotation%180)+180)%180;
   var backdrop=!!backgroundText||verticalAngle>=60&&verticalAngle<=120||/(?:background|newspaper|additional[_ ]text)/i.test(l.name+' '+(l.source?l.source.name:''));
   if(p){
    var cacheKey=String(c.id)+'/'+String(l.id),info=measurements[cacheKey];
    if(!info){
     var sample=Math.max(l.inPoint,Math.min(l.outPoint-.001,(l.inPoint+l.outPoint)/2)),doc=p.valueAtTime(sample,true),text=String(doc.text),keys=[],fontSizes=[],prefix=true,longest=text;
     for(var z=1;z<=p.numKeys;z++){var keyDoc=p.keyValue(z),keyText=String(keyDoc.text);keys.push([p.keyTime(z),keyText]);fontSizes.push(Number(keyDoc.fontSize)||Number(doc.fontSize));if(keyText.length>longest.length)longest=keyText;}
     for(z=0;z<keys.length;z++)if(longest.indexOf(keys[z][1])!==0)prefix=false;
     var baseline=longest,baselineState=null,comment=String(l.comment||'');try{var marker=comment.match(/\nStorylens Template Text baseline:([^\r\n]+)/);if(marker){baselineState=JSON.parse(marker[1]);baseline=baselineState.text;}}catch(_){}
     var expression=p.expressionEnabled?String(p.expression):'',bounds={width:1,height:1};
     // Protected expressions/changing phrases and filler are never resized.
     // Their bounds must not trigger expensive expression/render evaluation.
     if(!expression&&prefix&&baseline.length<=180&&baseline.split(/\s+/).length<=18)bounds=l.sourceRectAtTime(sample,false);
     info={text:longest,sample_text:text,baseline_text:baseline,font_size:baselineState&&baselineState.font_size||Number(doc.fontSize)||0,font_sizes:baselineState&&baselineState.font_sizes||fontSizes,expression:expression,enabled:baselineState&&baselineState.action==='hide'&&baselineState.enabled===true?true:!!l.enabled,current_enabled:!!l.enabled,bounds:baselineState&&baselineState.bounds||{width:Math.max(1,bounds.width),height:Math.max(1,bounds.height)},text_keys:keys,unsafe:l.isTrackMatte?'Text used as a track matte is kept.':!prefix?'Source Text changes between different phrases.':'',font:doc.font,current_font_size:Number(doc.fontSize)||0,comment:comment};
     measurements[cacheKey]=info;
    }
    var row={id:layerPath.join('/'),comp_id:String(c.id),layer_index:i,layer_id:String(l.id),name:l.name,text:info.text,baseline_text:info.baseline_text,font_size:info.font_size,font_sizes:info.font_sizes,expression:info.expression,enabled:info.enabled,current_enabled:info.current_enabled,runs:[],bounds:info.bounds,text_keys:info.text_keys,unsafe:info.unsafe};
    row.display_opacity=opacity;row.background_text=backdrop;
    var z;
    for(z=0;z<active.length;z++)row.runs.push({start:Math.max(0,active[z].start),end:Math.min(comp.duration,active[z].end)});
    if(row.runs.length){if(++count>5000)throw Error('Template Text: more than 5,000 visible text slots. Work on a shorter composition.');rows.push(row);}
    if(legacy)fingerprint.push([row.id,row.runs,info.sample_text,row.text_keys,row.expression,info.font,info.current_font_size,row.bounds.width,row.bounds.height,info.comment]);
    else{if(!textStates[cacheKey]){textStates[cacheKey]=true;fingerprint.push(['text',cacheKey,info.sample_text,row.text_keys,row.expression,info.font,info.current_font_size,row.bounds.width,row.bounds.height,info.comment]);}fingerprint.push(['slot',cacheKey,row.id,row.runs]);}
   }
   if(traversable&&l.source&&l.source instanceof CompItem&&active.length)walk(l.source,SLTemplateText.map(active,l,result.warnings),layerPath,next,rows,opacity,backdrop,titleRotation);
  }
 }
 function audio(c,segments,stack){if(stack[c.id])return;var next={};for(var k in stack)next[k]=true;next[c.id]=true;var solo=false;for(var n=1;n<=c.numLayers;n++)if(c.layer(n).solo)solo=true;
  for(var i=1;i<=c.numLayers;i++){var l=c.layer(i),s=l.source;if(!s||!l.audioEnabled||solo&&!l.solo)continue;var beforeWarnings=result.warnings.length,mapped=SLTemplateText.map(segments,l,result.warnings);for(var wi=beforeWarnings;wi<result.warnings.length;wi++)result.warnings[wi]='audio: '+result.warnings[wi];if(!mapped.length)continue;
   if(s instanceof CompItem){audio(s,mapped,next);continue;}
   if(!(s instanceof FootageItem)||!s.hasAudio||!s.file)continue;
   var levels=l.property('ADBE Audio Group').property('ADBE Audio Levels');if(levels.numKeys||levels.expressionEnabled){result.warnings.push('audio: animated audio levels need the final narration file.');continue;}
   var fx=l.property('ADBE Effect Parade');if(fx&&fx.numProperties){result.warnings.push('audio: audio effects need the final narration file.');continue;}
   var db=levels.value,gain=Math.pow(10,(db[0]+db[1])/40);
   for(var z=0;z<mapped.length;z++){var m=mapped[z],speed=(m.b-m.a)/(m.end-m.start);if(speed<=0){result.warnings.push('audio: reversed or frozen audio needs the final narration file.');continue;}var lo=Math.max(0,m.a),hi=Math.min(s.duration,m.b);if(hi<=lo)continue;result.audio.push({path:s.file.fsName,start:m.start+(lo-m.a)/speed,end:m.start+(hi-m.a)/speed,source_in:lo,rate:speed,gain:gain});}
  }
 }
 for(var i=1;i<=comp.numLayers;i++){var l=comp.layer(i),s=l.source;fingerprint.push(['master',String(l.id),l.name,l.enabled,l.startTime,l.inPoint,l.outPoint,l.stretch,s?String(s.id):'',l.audioEnabled]);
  if(!SLTemplateText.enabled(l)||!s||!(s instanceof CompItem))continue;
  if(/ - Storylens Captions$/.test(s.name)){result.warnings.push('Existing Storylens captions are kept.');continue;}if(!hasText(s,{}))continue;
  var start=Math.max(0,l.inPoint),end=Math.min(comp.duration,l.outPoint);if(end<=start)continue;
  var rows=[],segments=SLTemplateText.map(SLTemplateText.visible([{start:0,end:comp.duration,a:0,b:comp.duration}],l),l,result.warnings);walk(s,segments,[],{},rows);
  if(rows.length)result.templates.push({layer_id:String(l.id),source_id:String(s.id),name:l.name,start:start,end:end,texts:rows});
 }
 audio(comp,[{start:0,end:comp.duration,a:0,b:comp.duration}],{});
 // A saved project can be reopened while the local models work. AE's session
 // revision is not durable; validate the actual source, timing and text instead.
 if(!legacy)fingerprint.push(SLTemplateText.projectTitles(comp,result));
 fingerprint.push(result.audio);result.fingerprint=(legacy?'':'v2:')+SLTemplateText.hash([result.project_id,result.composition_id,comp.duration,comp.frameRate,fingerprint]);return result;
};
SLTemplateText.apply=function(p){
 var applyStarted=new Date().getTime(),templateTimings=[],costs={duplicate_ms:0,decorate_ms:0,link_ms:0,expressions_ms:0,text_ms:0,empty_ms:0};
 if(!p.plan||p.plan.project_id!==String(storylensProjectId()))throw Error('Template Text: the project changed. Run again on the intended final composition.');
 var plan=p.plan,comp=SLTemplateText.item(plan.composition_id);if(!comp||!(comp instanceof CompItem))throw Error('Template Text: open the final composition again.');
 if(app.project.activeItem!==comp)throw Error('Template Text: return to the same final composition and press Run again.');
 var current=SLTemplateText.scan(comp,{legacy:String(plan.fingerprint).indexOf('v2:')!==0});if(current.fingerprint!==plan.fingerprint)throw Error('Template Text: the timeline or text changed during analysis. Run again; no text was changed.');
 costs.validation_ms=new Date().getTime()-applyStarted;
 var lookup={},allowed={},i,k,templates={},actions=plan.actions||[],created=[],folders=[],swaps=[],undo=false,changes=0,hidden=0,warnings=[],origins={},renderingBefore=null;
 for(i=0;i<current.templates.length;i++){var t=current.templates[i];templates[t.layer_id]=t;for(k=0;k<t.texts.length;k++)allowed[t.layer_id+'/'+t.texts[k].id]=t.texts[k];}
 if(!actions.length)throw Error('Template Text: no supported text changes were planned. Check Technical details.');
 for(i=0;i<actions.length;i++){var a=actions[i],key=a.template_layer_id+'/'+a.text_id,row=allowed[key];if(!row||lookup[key]||!(/^(replace|hide)$/).test(a.action)||typeof a.text!=='string'||a.text.length>300||String(row.unsafe||'').indexOf('matte')>=0||(row.expression||row.unsafe)&&a.action!=='hide')throw Error('Template Text: invalid or stale text plan. Run again; your project is unchanged.');lookup[key]=a;}
 var generation=String(new Date().getTime()),branchCopies={},editedLayers={},branchEdits={},branchSignatures={},branchConstraints={},branchNodes={},branchPaths={},rootSources={},textOnlyCache={},copyRecords=[];
 var hasEmpty=SLTemplateText.textIndex(function(l){var p=SLTemplateText.text(l);if(!p||!l.enabled||l.isTrackMatte||p.expressionEnabled)return false;for(var n=1;n<=p.numKeys;n++)if(String(p.keyValue(n).text).replace(/[\s\u200b\ufeff]/g,''))return false;return p.numKeys>0||!String(p.value.text).replace(/[\s\u200b\ufeff]/g,'');});
 function progress(stage){if(typeof SLTemplateText.progress==='function')SLTemplateText.progress({stage:stage,copies:created.length,elapsed_ms:new Date().getTime()-applyStarted,costs:costs});}
 for(i=0;i<actions.length;i++){var edit=actions[i],parts=edit.text_id.split('/');for(var depth=0;depth<parts.length;depth++){var prefixKey=edit.template_layer_id+'/'+parts.slice(0,depth).join('/');if(!branchEdits[prefixKey])branchEdits[prefixKey]=[];branchEdits[prefixKey].push([parts.slice(depth).join('/'),edit.action,edit.text]);}}
 // Hide-only differences in trimmed occurrences are compatible. All visible
 // kept/replaced slots form the constraint; missing slots are offscreen, not
 // permission to hide lettering that another occurrence explicitly retains.
 for(i=1;i<=comp.numLayers;i++){var rootLayer=comp.layer(i);rootSources[String(rootLayer.id)]=rootLayer.source;}
 for(var allowedKey in allowed)if(allowed.hasOwnProperty(allowedKey)){
  var allowedRow=allowed[allowedKey],rootId=allowedKey.split('/')[0],parts=allowedRow.id.split('/'),source=rootSources[rootId],edit=lookup[allowedKey];
  for(var depth=0;depth<parts.length;depth++){
   var prefix=parts.slice(0,depth),prefixKey=rootId+'/'+prefix.join('/'),node=branchNodes[prefixKey];
   if(!node){node={original:source,path:prefix,rootId:rootId};branchNodes[prefixKey]=node;}
   if(!edit||edit.action!=='hide'){if(!branchConstraints[prefixKey])branchConstraints[prefixKey]=[];branchConstraints[prefixKey].push([parts.slice(depth).join('/'),edit?edit.action:'keep',edit?edit.text:'']);}
   if(depth<parts.length-1){var childKey=rootId+'/'+parts.slice(0,depth+1).join('/');source=branchNodes[childKey]?branchNodes[childKey].original:source.layer(parseInt(parts[depth],10)).source;}
  }
 }
 function branchKey(original,path,rootId){var prefixKey=rootId+'/'+path.join('/');
  if(!branchSignatures.hasOwnProperty(prefixKey)){var edits=branchConstraints[prefixKey]||[];edits.sort(function(a,b){return a[0]<b[0]?-1:a[0]>b[0]?1:0;});branchSignatures[prefixKey]=hJSON(edits);}
  return rootId+'/'+String(original.id)+'/'+branchSignatures[prefixKey];
 }
 for(var nodeKey in branchNodes)if(branchNodes.hasOwnProperty(nodeKey)){var node=branchNodes[nodeKey],groupKey=branchKey(node.original,node.path,node.rootId);if(!branchPaths[groupKey])branchPaths[groupKey]=[];branchPaths[groupKey].push(node.path);}
 function textOnly(c,stack){var id=String(c.id);if(textOnlyCache.hasOwnProperty(id))return textOnlyCache[id];if(stack[id])return false;var next={};for(var k in stack)next[k]=true;next[id]=true;
  for(var n=1;n<=c.numLayers;n++){var l=c.layer(n);if(SLTemplateText.text(l)||l.nullLayer===true)continue;if(l.source&&l.source instanceof CompItem&&textOnly(l.source,next))continue;textOnlyCache[id]=false;return false;}
  textOnlyCache[id]=true;return true;
 }
 function cloneTree(original,path,rootId,stack,bucket,names){if(stack[original.id])throw Error('Circular template composition.');var next={};for(var x in stack)next[x]=true;next[original.id]=true;
  var reuseKey=branchKey(original,path,rootId);if(branchCopies[reuseKey])return branchCopies[reuseKey];
  if(created.length>=8000)throw Error('Template Text: this project exceeds the isolated composition limit. Work on a shorter composition.');progress('copy '+rootId);var stamp=new Date().getTime(),copy=original.duplicate();costs.duplicate_ms+=new Date().getTime()-stamp;created.push(copy);stamp=new Date().getTime();origins[String(copy.id)]=original.name;copy.selected=false;copy.name=original.name.replace(/ \[(?:Template Text |SLTT )[^\]]+\]$/,'')+' [SLTT '+rootId+'-'+generation+'-'+(path.length?path.join('-'):'root')+']';copy.parentFolder=bucket;costs.decorate_ms+=new Date().getTime()-stamp;
  SLTemplateText.alias(names,original.name,copy.name);
  copyRecords.push({original:original,copy:copy,rootId:rootId});
  var occurrences=branchPaths[reuseKey]||[path];
  for(var n=1;n<=copy.numLayers;n++){var layer=copy.layer(n),source=layer.source,childPath=null;if(!source||!(source instanceof CompItem))continue;
   for(var oi=0;oi<occurrences.length;oi++){var candidate=occurrences[oi].concat([n]);if(branchEdits[rootId+'/'+candidate.join('/')]){childPath=candidate;break;}}
   if(!childPath&&hasEmpty(source))childPath=path.concat([n]);
   if(childPath){var lock=layer.locked,name=layer.name;layer.locked=false;try{
    var marked=String(layer.comment||'').indexOf(SLTemplateText.branchMarker)>=0;if(marked){layer.enabled=true;layer.comment=String(layer.comment).split(SLTemplateText.branchMarker).join('');}
    if(!layer.isTrackMatte&&layer.enabled&&branchEdits[rootId+'/'+childPath.join('/')]&&!(branchConstraints[rootId+'/'+childPath.join('/')]||[]).length&&textOnly(source,{})){layer.enabled=false;layer.comment=String(layer.comment||'')+SLTemplateText.branchMarker;}
    else{var child=cloneTree(source,childPath,rootId,next,bucket,names);stamp=new Date().getTime();layer.replaceSource(child,false);layer.name=name;costs.link_ms+=new Date().getTime()-stamp;}
   }finally{layer.locked=lock;}}
  }branchCopies[reuseKey]=copy;return copy;
 }
 function properties(group,names,originalName){for(var n=1;n<=group.numProperties;n++){var prop=group.property(n);if(prop.canSetExpression&&prop.expression){var enabled=prop.expressionEnabled,failed=!!prop.expressionError,before=prop.expression,after=SLTemplateTextModel.expression(before,names,SLTemplateText.baseName(originalName));if(before!==after){prop.expression=after;prop.expressionEnabled=enabled||failed;}}if(prop.numProperties)properties(prop,names,originalName);}}
 function locate(root,path){var indices=path.split('/'),c=root,l;for(var n=0;n<indices.length;n++){l=c.layer(parseInt(indices[n],10));if(n<indices.length-1){if(!l.enabled&&String(l.comment||'').indexOf(SLTemplateText.branchMarker)>=0)return null;if(!l.source||!(l.source instanceof CompItem))throw Error('A nested text path changed.');c=l.source;}}return l;}
 costs.preparation_ms=new Date().getTime()-applyStarted-costs.validation_ms;
 try{
  app.beginUndoGroup('Template Text');undo=true;
  if(typeof app.disableRendering==='boolean'){renderingBefore=app.disableRendering;app.disableRendering=true;}
  var destination=null;for(i=1;i<=app.project.numItems;i++){var f=app.project.item(i);if(f instanceof FolderItem&&f.parentFolder===app.project.rootFolder&&f.comment==='Storylens Template Text output v1'){destination=f;break;}}
  if(!destination){destination=app.project.items.addFolder('Template Text');destination.comment='Storylens Template Text output v1';folders.push(destination);}
  for(var rootId in templates)if(templates.hasOwnProperty(rootId)){
   var templateStarted=new Date().getTime();
   var has=false;for(i=0;i<actions.length;i++)if(actions[i].template_layer_id===rootId)has=true;if(!has)continue;
   var originalLayer=null;for(i=1;i<=comp.numLayers;i++)if(String(comp.layer(i).id)===rootId)originalLayer=comp.layer(i);if(!originalLayer||originalLayer.locked)throw Error('Unlock the placed template before updating its text.');
   var bucket=app.project.items.addFolder(originalLayer.name+' — text '+generation);folders.push(bucket);bucket.parentFolder=destination;
   var names={},offset=created.length,copy=cloneTree(originalLayer.source,[],rootId,{},bucket,names),unique={};for(k in names)if(names.hasOwnProperty(k)){if(names[k])unique[k]=names[k];else warnings.push('Repeated named-controller reference kept: '+k);}
   progress('expressions '+rootId);var stamp=new Date().getTime();for(i=offset;i<created.length;i++)for(k=1;k<=created[i].numLayers;k++)properties(created[i].layer(k),unique,origins[String(created[i].id)]);costs.expressions_ms+=new Date().getTime()-stamp;
   progress('text '+rootId);stamp=new Date().getTime();
   for(i=0;i<actions.length;i++)if(actions[i].template_layer_id===rootId){
    var action=actions[i],old=allowed[rootId+'/'+action.text_id],layer=locate(copy,action.text_id);
    if(!layer){if(action.action!=='hide')throw Error('A retained heading cannot be inside a hidden text branch.');var mutedKey='muted/'+rootId+'/'+old.comp_id+'/'+old.layer_index;if(!editedLayers[mutedKey]){editedLayers[mutedKey]=true;hidden++;}continue;}
    var property=SLTemplateText.text(layer),locked=layer.locked;
    if(editedLayers[String(layer.id)])continue;editedLayers[String(layer.id)]=true;layer.locked=false;
    try{
     layer.comment=String(layer.comment||'').replace(/\nStorylens Template Text baseline:[^\r\n]+/g,'')+'\nStorylens Template Text baseline:'+hJSON({text:old.baseline_text||old.text,enabled:old.enabled,action:action.action,font_size:old.font_size,font_sizes:old.font_sizes,bounds:old.bounds});
     if(action.action==='hide'){layer.enabled=false;hidden++;continue;}layer.enabled=old.enabled;
     var doc=property.value;if(property.expressionEnabled)throw Error('Expression-controlled text cannot be overwritten.');
     var longest=old.text||'',keys=property.numKeys;
     if(keys){for(k=1;k<=keys;k++){doc=property.keyValue(k);if(old.font_sizes&&old.font_sizes[k-1])doc.fontSize=old.font_sizes[k-1];var part=String(doc.text),length=longest.length?Math.round(part.length/longest.length*action.text.length):action.text.length;doc.text=action.text.slice(0,Math.min(action.text.length,length));property.setValueAtKey(k,doc);}}
     else{doc.text=action.text;if(old.font_size)doc.fontSize=old.font_size;property.setValue(doc);}
     var at=(layer.inPoint+layer.outPoint)/2,box=layer.sourceRectAtTime(at,false),ratio=Math.min(1,old.bounds.width/Math.max(1,box.width),old.bounds.height/Math.max(1,box.height));
     if(ratio<.25||old.font_size*ratio<Math.min(24,old.font_size*.55)){layer.comment=String(layer.comment||'').replace(/\nStorylens Template Text baseline:[^\r\n]+/g,'')+'\nStorylens Template Text baseline:'+hJSON({text:old.baseline_text||old.text,enabled:old.enabled,action:'hide',font_size:old.font_size,font_sizes:old.font_sizes,bounds:old.bounds});layer.enabled=false;hidden++;warnings.push('Heading hidden because it would be too small: '+old.name);continue;}
     if(ratio<.999){if(keys){for(k=1;k<=keys;k++){doc=property.keyValue(k);doc.fontSize*=ratio;property.setValueAtKey(k,doc);}}else{doc=property.value;doc.fontSize*=ratio;property.setValue(doc);}}
     layer.comment=String(layer.comment||'').replace(/\nStorylens Template Text baseline:[^\r\n]+/g,'')+'\nStorylens Template Text baseline:'+hJSON({text:old.baseline_text||old.text,enabled:old.enabled,action:action.action,font_size:old.font_size,font_sizes:old.font_sizes,bounds:old.bounds});changes++;
    }finally{layer.locked=locked;}
   }
   costs.text_ms+=new Date().getTime()-stamp;
   var rootRecords=[];for(i=0;i<copyRecords.length;i++)if(copyRecords[i].rootId===rootId)rootRecords.push(copyRecords[i]);
   for(i=offset;i<created.length;i++)for(k=1;k<=created[i].numLayers;k++){var overrideResult=SLTemplateText.syncOverrides(created[i].layer(k).property('ADBE Layer Overrides'),rootRecords);warnings=warnings.concat(overrideResult.unresolved);}
   var oldComment=String(originalLayer.comment||''),newComment=oldComment;
   if(typeof SLCopyPaste!=='undefined'&&SLCopyPaste.graph&&typeof SLCopyPasteModel!=='undefined')try{var state=SLCopyPasteModel.state(oldComment);if(state&&state.owner===rootId&&state.root===String(originalLayer.source.id)){var oldSlots=SLCopyPasteModel.scan(SLCopyPaste.graph(originalLayer.source),originalLayer.source.id),newSlots=SLCopyPasteModel.scan(SLCopyPaste.graph(copy),copy.id);var sameSlots=oldSlots.slots.length===newSlots.slots.length;for(var si=0;sameSlots&&si<oldSlots.slots.length;si++){var aSlot=oldSlots.slots[si],bSlot=newSlots.slots[si];sameSlots=String(aSlot.source)===String(bSlot.source)&&aSlot.path===bSlot.path&&!!aSlot.empty===!!bSlot.empty&&String(aSlot.layers)===String(bSlot.layers);}if(state.signature===oldSlots.signature&&sameSlots){state.root=String(copy.id);state.signature=newSlots.signature;newComment=SLCopyPasteModel.writeState(oldComment,state);}else warnings.push('Copy Paste slot progress needs review on '+originalLayer.name);}}catch(_){warnings.push('Copy Paste slot progress was kept for review on '+originalLayer.name);}
   swaps.push({layer:originalLayer,source:originalLayer.source,replacement:copy,name:originalLayer.name,comment:oldComment,newComment:newComment});
   templateTimings.push({layer_id:rootId,elapsed_ms:new Date().getTime()-templateStarted,copies:created.length-offset});
  }
  // Empty text outside the currently visible intervals also needs to be off.
  // A blank first reveal key is not an empty layer; inspect every authored key.
  var emptyStarted=new Date().getTime();for(i=0;i<created.length;i++)for(k=1;k<=created[i].numLayers;k++){
   var emptyLayer=created[i].layer(k),emptyProperty=SLTemplateText.text(emptyLayer);
   if(!emptyLayer.enabled||emptyLayer.isTrackMatte||!emptyProperty||emptyProperty.expressionEnabled)continue;
   var empty=true,keyCount=emptyProperty.numKeys,ki;
   if(keyCount){for(ki=1;ki<=keyCount;ki++)if(String(emptyProperty.keyValue(ki).text).replace(/[\s\u200b\ufeff]/g,'')){empty=false;break;}}
   else empty=!String(emptyProperty.value.text).replace(/[\s\u200b\ufeff]/g,'');
   if(empty){var wasLocked=emptyLayer.locked;emptyLayer.locked=false;try{emptyLayer.enabled=false;hidden++;}finally{emptyLayer.locked=wasLocked;}}
  }
  costs.empty_ms+=new Date().getTime()-emptyStarted;
  var decorationResult=SLTemplateText.cleanDecorations(created);
  if(decorationResult.unresolved.length)warnings.push('Text decoration ownership needs review: '+decorationResult.unresolved.join('; '));
  for(i=0;i<swaps.length;i++){swaps[i].layer.replaceSource(swaps[i].replacement,false);swaps[i].layer.name=swaps[i].name;swaps[i].layer.comment=swaps[i].newComment;}
  return {ok:true,project_id:plan.project_id,composition_id:plan.composition_id,job_id:plan.job_id,changed:changes,hidden:hidden,decorations_hidden:decorationResult.hidden,decoration_review:decorationResult.unresolved,templates:swaps.length,warnings:warnings,undo:'Edit > Undo Template Text',elapsed_ms:new Date().getTime()-applyStarted,copies:created.length,template_timings:templateTimings,costs:costs};
 }catch(error){
  var restored=true;for(i=swaps.length-1;i>=0;i--)try{swaps[i].layer.replaceSource(swaps[i].source,false);swaps[i].layer.name=swaps[i].name;swaps[i].layer.comment=swaps[i].comment;}catch(_){restored=false;}
  for(i=created.length-1;i>=0;i--)try{created[i].remove();}catch(_){}for(i=folders.length-1;i>=0;i--)try{if(!folders[i].numItems)folders[i].remove();}catch(_){}
  var stopped=Error(restored?'Template Text: the update stopped; your original template layers are kept. Check Technical details before retrying.':'Template Text: choose Edit > Undo Template Text before retrying.');stopped.details=String(error);throw stopped;
 }finally{try{if(undo)app.endUndoGroup();}finally{if(renderingBefore!==null)app.disableRendering=renderingBefore;}}
};
function storylensPanelTemplateText(p){try{p=p||{};if(!app.project)throw Error('Template Text: open your finished project first.');if(p.action==='pickAudio'){var file=File.openDialog('Choose the final narrated video or audio');return hJSON({ok:true,path:file?file.fsName:''});}if(p.action==='apply')return hJSON(SLTemplateText.apply(p));if(p.action!=='scan')throw Error('Template Text: choose Run Template Text.');var comp=app.project.activeItem;if(!comp||!(comp instanceof CompItem))throw Error('Template Text: open your finished video composition first.');return hJSON({ok:true,snapshot:SLTemplateText.scan(comp)});}catch(error){var message=String(error).replace(/^Error: ?/,'');return hJSON({error:message.indexOf('Template Text:')===0?message:'Template Text could not finish. Check the current composition and Technical details before retrying.',code:'template_text_native',details:error.details||String(error)});}}
