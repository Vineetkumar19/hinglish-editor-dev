/* Reusable native surface titles. This authors placement; it does not solve footage. */
(function(global){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function ease(p){
  // Ask the actual key for its ease cardinality. Host property-type flags can
  // differ from the temporal array accepted by AE, especially spatial Position.
  for(var k=1;k<=p.numKeys;k++){
   p.setInterpolationTypeAtKey(k,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);
   var incoming=p.keyInTemporalEase(k),outgoing=p.keyOutTemporalEase(k),a=[],b=[],d;
   for(d=0;d<incoming.length;d++)a.push(new KeyframeEase(0,66));
   for(d=0;d<outgoing.length;d++)b.push(new KeyframeEase(0,72));
   try{p.setTemporalEaseAtKey(k,a,b);}catch(e){
    // Some AE hosts report a different size through the getters. Honour the
    // explicit native dimension error once; never mask other native failures.
    var expected=String(e).match(/Value array does not have ([123]) elements/i);if(!expected)throw e;
    a=[];b=[];for(d=0;d<Number(expected[1]);d++){a.push(new KeyframeEase(0,66));b.push(new KeyframeEase(0,72));}p.setTemporalEaseAtKey(k,a,b);
   }
   if(p.isSpatial){var tangent=p.keyInSpatialTangent(k),zero=[];for(d=0;d<tangent.length;d++)zero.push(0);p.setSpatialTangentsAtKey(k,zero,zero);}
  }
 }
 function rotate(p,a){
  var x=p[0],y=p[1],z=p[2],r=Math.PI/180,c=Math.cos(a[0]*r),s=Math.sin(a[0]*r),v=y*c-z*s;z=y*s+z*c;y=v;
  c=Math.cos(a[1]*r);s=Math.sin(a[1]*r);v=x*c+z*s;z=-x*s+z*c;x=v;
  c=Math.cos(a[2]*r);s=Math.sin(a[2]*r);return [x*c-y*s,x*s+y*c,z];
 }
/* Surface projection and safe selected-title editing. No footage tracking is performed. */
 function poseFor(plan){
  var p={pitch:12,turn:-44,roll:-3,seam:0};
  if(plan.layout==='ground'){p.pitch=-64;p.turn=12;p.roll=-8;}
  else if(plan.layout==='corner'){p.pitch=18;p.turn=0;p.roll=0;}
  else if(plan.layout==='column'){p.pitch=8;p.turn=-44;p.roll=8;}
  else if(plan.surface==='left'){p.turn=44;p.roll=3;}
  else if(plan.surface==='front'){p.turn=0;p.roll=0;}
  var input=plan.perspective||{};for(var k in p)if(input.hasOwnProperty(k))p[k]=Number(input[k]);return p;
 }
 function inkBounds(ink){var b={left:1e8,top:1e8,right:-1e8,bottom:-1e8};for(var i=0;i<ink.length;i++){b.left=Math.min(b.left,ink[i].x);b.top=Math.min(b.top,ink[i].y);b.right=Math.max(b.right,ink[i].x+ink[i].w);b.bottom=Math.max(b.bottom,ink[i].y+ink[i].h);}return b;}
 function geometry(plan,specs,w,h){
  var pose=poseFor(plan),orientation=[pose.pitch,pose.turn,pose.roll],zoom=w*.95,factor=Math.min(w/1500,h/1500),cx=w/2,cy=h*.48,i;
  if(plan.layout==='corner'&&specs.length===2)factor=Math.min(w/2200,h/1500);
  for(i=0;i<specs.length;i++){var s=specs[i];s.box=inkBounds(s.ink);s.anchor=(s.box.left+s.box.right)/2;s.rot=0;if(plan.layout==='corner'){if(s.side==='left'){s.anchor=s.box.right;s.rot=52;}else{s.anchor=s.box.left;s.rot=-52;}}}
  function project(x,y,s){var v=rotate([x-s.anchor,y-850,0],[0,s.rot,0]);if(plan.layout==='corner'){if(s.side==='left')v[0]-=pose.seam/2;else v[0]+=pose.seam/2;}v=rotate(v,orientation);var z=v[2]*factor;if(zoom+z<zoom*.12)throw Error('Reduce the perspective angle or title size.');var k=zoom/(zoom+z);return [w/2+(cx-w/2+v[0]*factor)*k,h/2+(cy-h/2+v[1]*factor)*k];}
  function quad(s,l,t,r,b){return [project(l,t,s),project(r,t,s),project(l,b,s),project(r,b,s)];}
  var box;
  for(var fit=0;fit<10;fit++){
   box={left:1e9,top:1e9,right:-1e9,bottom:-1e9};var safe=true;
   try{for(i=0;i<specs.length;i++){var s=specs[i],points=quad(s,s.box.left-10,s.box.top-10,s.box.right+10,s.box.bottom+10);quad(s,0,0,s.source.width,s.source.height);for(var j=0;j<4;j++){box.left=Math.min(box.left,points[j][0]);box.top=Math.min(box.top,points[j][1]);box.right=Math.max(box.right,points[j][0]);box.bottom=Math.max(box.bottom,points[j][1]);}}}catch(e){safe=false;}
   if(!safe){factor*=.7;continue;}
   var ratio=Math.min(1,w*.78/Math.max(1,box.right-box.left),h*.74/Math.max(1,box.bottom-box.top));factor*=ratio*.998;cx+=w/2-(box.left+box.right)/2;cy+=h*.48-(box.top+box.bottom)/2;
  }
  var result={pose:pose,bounds:box,planes:[]};
  for(i=0;i<specs.length;i++){var s=specs[i];result.planes.push({side:s.side,quad:quad(s,0,0,s.source.width,s.source.height),inkQuad:quad(s,s.box.left,s.box.top,s.box.right,s.box.bottom),seam:[project(s.anchor,650,s),project(s.anchor,1050,s)]});}
  return result;
 }
 function clearProperty(p){p.expression='';while(p.numKeys)p.removeKey(p.numKeys);}
 function readValue(p,t){if(p.valueAtTime)return p.valueAtTime(t,false);return p.value;}
 function textLayers(source){var a=[];for(var i=1;i<=source.numLayers;i++){var l=source.layer(i);if(l.property('ADBE Text Properties'))a.push(l);}a.sort(function(a,b){var ma=String(a.comment||'').match(/^Storylens row (\d+)/),mb=String(b.comment||'').match(/^Storylens row (\d+)/);if(ma&&mb)return Number(ma[1])-Number(mb[1]);return readValue(tr(a,'ADBE Position'),4)[1]-readValue(tr(b,'ADBE Position'),4)[1];});return a;}
 function measure(source){var rows=textLayers(source),ink=[];for(var i=0;i<rows.length;i++){var l=rows[i],r=l.sourceRectAtTime(7.6,false),p=readValue(tr(l,'ADBE Position'),7.6),a=readValue(tr(l,'ADBE Anchor Point'),7.6),s=readValue(tr(l,'ADBE Scale'),7.6);if(a.length<2)a=[r.left,r.top];if(s.length<2)s=[100,100];var points=[],angle=Number(readValue(tr(l,'ADBE Rotate Z'),4))||0;for(var x=0;x<2;x++)for(var y=0;y<2;y++)points.push(rotate([(r.left+(x?r.width:0)-a[0])*s[0]/100,(r.top+(y?r.height:0)-a[1])*s[1]/100,0],[0,0,angle]));var b={left:1e8,top:1e8,right:-1e8,bottom:-1e8};for(var j=0;j<points.length;j++){b.left=Math.min(b.left,p[0]+points[j][0]);b.right=Math.max(b.right,p[0]+points[j][0]);b.top=Math.min(b.top,p[1]+points[j][1]);b.bottom=Math.max(b.bottom,p[1]+points[j][1]);}ink.push({x:b.left,y:b.top,w:b.right-b.left,h:b.bottom-b.top});}return ink;}
 function pinFor(plane){var fx=plane.property('ADBE Effect Parade');for(var i=1;i<=fx.numProperties;i++){var p=fx.property(i);if(p.name==='Surface perspective'&&p.matchName==='ADBE Corner Pin')return p;}return null;}
 function colourFor(family,variant){var c=global.StorylensSurfaceCatalog;if(!c)throw Error('Reopen Storylens to load the surface catalogue.');for(var i=0;i<c.families.length;i++)if(c.families[i].id===family)for(var j=0;j<c.families[i].variants.length;j++)if(c.families[i].variants[j].id===variant)return c.families[i].variants[j];throw Error('Choose a supported surface title.');}
 var metaPrefix='Storylens Surface v3\n';
 function metadata(source){var text=String(source.comment||'');if(text.indexOf(metaPrefix)!==0)return null;var lines=text.slice(metaPrefix.length).split('\n'),m={};for(var i=0;i<lines.length;i++){var at=lines[i].indexOf('=');if(at<1)continue;var k=lines[i].slice(0,at),v=lines[i].slice(at+1);if(/^[a-z_]+$/.test(k)&&/^[a-zA-Z0-9_., -]*$/.test(v))m[k]=v;}return m;}
 function saveMeta(source,plan,updateId){var pose=poseFor(plan),m={family:plan.family,variant:plan.variant,audio:plan.sound_mode||'pop_click',motion:plan.motion||'none',surface:plan.surface,delay:plan.delay===undefined ? .35 : plan.delay,pitch:pose.pitch,turn:pose.turn,roll:pose.roll,seam:pose.seam,sound:plan.sound_fx===false?0:1,update:updateId||''},lines=[];for(var k in m)if(m.hasOwnProperty(k))lines.push(k+'='+m[k]);source.comment=metaPrefix+lines.join('\n');}
 function collect(source,plan){var specs=[];for(var i=1;i<=source.numLayers;i++){var l=source.layer(i);if(!(l.source instanceof CompItem))continue;var rows=textLayers(l.source);if(!rows.length)continue;var side=plan.surface;if(plan.layout==='corner'){side='right';if(/Storylens Surface left/.test(String(l.comment||''))||/left/i.test(l.name)||/left/i.test(l.source.name)||Number(readValue(tr(l,'ADBE Anchor Point'),7.6)[0])>1000)side='left';}specs.push({plane:l,source:l.source,side:side,ink:measure(l.source)});}specs.sort(function(a,b){if(a.side===b.side)return 0;if(a.side==='left')return -1;return 1;});return specs;}
 function selected(request){
  var c=app.project&&app.project.activeItem;if(!(c instanceof CompItem)||c.selectedLayers.length!==1)throw Error('Select one 3D2 or 3D3 title precomp in your timeline.');var l=c.selectedLayers[0];
  if(!(l.source instanceof CompItem)||!/^3D[23] Surface Precomp$/.test(String(l.comment||'')))throw Error('Select the outer 3D2 or 3D3 title precomp.');
  if(request){if(storylensProjectId()!==request.project_id||String(c.id)!==String(request.comp_id)||String(l.id)!==String(request.layer_id))throw Error('Select the same title in the same project, then retry.');}
  if(l.locked)throw Error('Unlock the selected title before changing it.');var m=metadata(l.source),family,variant;
  if(m){family=m.family;variant=m.variant;}else{var found=String(l.source.name).match(/^(3D[23])\s*-\s*(Ground|Wall|Corner|Column|Yellow|Blue|Red|Black)(?:\s|$)/i);if(!found)throw Error('This older title cannot be identified safely. Choose a current surface preset.');family=found[1].toLowerCase();variant=found[2].toLowerCase();}
  var v=colourFor(family,variant),plan={family:family,variant:variant,layout:v.layout,surface:'right',motion:'none',delay:.35,sound_fx:true,perspective:{},rows:v.rows};if(plan.layout==='corner')plan.surface='both';if(plan.layout==='ground')plan.surface='ground';
  if(m){plan.sound_mode=m.audio||'pop_click';plan.surface=m.surface;plan.motion=m.motion;plan.delay=Number(m.delay);plan.sound_fx=m.sound!=='0';for(var k in {pitch:0,turn:0,roll:0,seam:0})plan.perspective[k]=Number(m[k]);}
  var specs=collect(l.source,plan);if(!specs.length)throw Error('The selected title has no editable surface precomps.');if(plan.layout==='corner'&&specs.length!==2)throw Error('This older single-wall corner needs the current Corner preset once before switching both sides.');var words=[];for(var i=0;i<specs.length;i++){var rows=textLayers(specs[i].source);for(var j=0;j<rows.length;j++){var doc=rows[j].property('ADBE Text Properties').property('ADBE Text Document').value;words.push(doc.text===undefined?String(rows[j].name).replace(/^EDIT - /,''):doc.text);}}plan.text=words.join(' ');if(global.StorylensCaptionSounds.state){var audio=global.StorylensCaptionSounds.state(l.source);if(audio){plan.sound_mode=audio.mode;plan.sound_fx=audio.enabled;}}
  var geo=geometry(plan,specs,l.source.width,l.source.height);for(var i=0;i<specs.length;i++){var pin=pinFor(specs[i].plane);if(pin)for(var j=0;j<4;j++)geo.planes[i].quad[j]=readValue(pin.property('ADBE Corner Pin-000'+(j+1)),6.8);}
  return {ok:true,plan:plan,geometry:geo,legacy:!m,context:{project_id:storylensProjectId(),comp_id:String(c.id),layer_id:String(l.id),source_id:String(l.source.id),time:c.time},layer:l,source:l.source,specs:specs,meta:m};
 }
 function describe(){var r=selected();return {ok:true,plan:r.plan,geometry:r.geometry,legacy:r.legacy,context:r.context};}
 function stripAudio(source){for(var i=source.numLayers;i>=1;i--){var l=source.layer(i);if(/^SFX - /.test(l.name)&&l.source&&/^Storylens Caption SFX /.test(String(l.source.comment||'')))l.remove();}}
 function caseWord(text,upper){text=String(text);if(upper)return text.toUpperCase();var lower=text.toLowerCase();for(var i=0;i<lower.length;i++){var c=lower.charAt(i);if(c.toUpperCase()!==c.toLowerCase())return lower.slice(0,i)+c.toUpperCase()+lower.slice(i+1);}return lower;}
 function caseDocument(doc,plan){if(doc.text!==undefined)doc.text=String(doc.text).replace(/\S+/g,function(w){return caseWord(w,plan.family==='3d2'&&plan.variant==='yellow');});if(typeof FontCapsOption!=='undefined')doc.fontCapsOption=FontCapsOption.FONT_NORMAL_CAPS;return doc;}
 function caseSource(source,plan){var rows=textLayers(source);for(var i=0;i<rows.length;i++){var p=rows[i].property('ADBE Text Properties').property('ADBE Text Document');if(p.numKeys){for(var k=1;k<=p.numKeys;k++)p.setValueAtKey(k,caseDocument(p.keyValue(k),plan));}else p.setValue(caseDocument(p.value,plan));}}
 function configureText(source,plan){stripAudio(source);var rows=textLayers(source),chars=0,words=0,step=Math.min(.055,3.3/Math.max(1,plan.text.length));for(var i=0;i<rows.length;i++){
  var l=rows[i],group=l.property('ADBE Text Properties').property('ADBE Text Animators');for(var a=group.numProperties;a>=1;a--){var old=group.property(a);if(old.name==='Word entrance'||old.name==='Typewriter')old.remove();}
  var opacity=tr(l,'ADBE Opacity');clearProperty(opacity);opacity.setValue(100);
  var doc=l.property('ADBE Text Properties').property('ADBE Text Document').value,text=doc.text;if(text===undefined)text=String(l.name).replace(/^EDIT - /,'');
  if(plan.motion==='words'||plan.motion==='typewriter'){
   var animator=group.addProperty('ADBE Text Animator');animator.name='Typewriter';if(plan.motion==='words')animator.name='Word entrance';var props=animator.property('ADBE Text Animator Properties');props.addProperty('ADBE Text Opacity').setValue(0);if(plan.motion==='words')props.addProperty('ADBE Text Position 3D').setValue([0,35,0]);var selector=animator.property('ADBE Text Selectors').addProperty('ADBE Text Expressible Selector');selector.property('ADBE Text Range Type2').setValue(1);var onset=plan.delay+chars*step;
   if(plan.motion==='words'){selector.property('ADBE Text Range Type2').setValue(3);onset=plan.delay+words*.18;selector.property('ADBE Text Expressible Amount').expression='var t='+onset+'+(textIndex-1)*.18;ease(time,t,t+.30,100,0);';}
   else selector.property('ADBE Text Expressible Amount').expression='time<'+onset+'+(textIndex-1)*'+step+'?100:0;';
  }
  chars+=String(text).length+1;words+=String(text).split(/\s+/).length;
 }}
 function moveQuad(quad,motion,side){var out=[],cx=0,cy=0;for(var i=0;i<4;i++){cx+=quad[i][0]/4;cy+=quad[i][1]/4;}var scale=1,dx=0,dy=0;if(motion==='emerge')scale=.85;if(motion==='attach')scale=1.18;if(motion==='slide'){var a=quad[0],b=quad[1];if(side==='ground'){b=quad[2];dx=(b[0]-a[0])*.24;dy=(b[1]-a[1])*.24;}else{var sign=1;if(side==='left')sign=-1;dx=(b[0]-a[0])*.24*sign;dy=(b[1]-a[1])*.24*sign;}}for(var i=0;i<4;i++)out.push([cx+(quad[i][0]-cx)*scale+dx,cy+(quad[i][1]-cy)*scale+dy]);return out;}
 function configure(wrapper,plan,specs,geo,root,owned){
  for(var i=wrapper.numLayers;i>=1;i--){var audio=wrapper.layer(i);if(/^SFX - /.test(audio.name)&&audio.source&&/^Storylens Caption SFX /.test(String(audio.source.comment||'')))audio.remove();}
  for(var i=0;i<specs.length;i++){
   var s=specs[i],l=s.plane;if(l.locked)throw Error('Unlock the surface layers before updating this title.');l.parent=null;l.threeDLayer=false;l.collapseTransformation=false;tr(l,'ADBE Anchor Point').setValue([0,0]);clearProperty(tr(l,'ADBE Position'));tr(l,'ADBE Position').setValue([0,0]);tr(l,'ADBE Rotate Z').setValue(0);tr(l,'ADBE Scale').setValue([100,100]);
   var pin=pinFor(l);if(!pin){pin=l.property('ADBE Effect Parade').addProperty('ADBE Corner Pin');pin.name='Surface perspective';}var q=geo.planes[i].quad,side=s.side;if(plan.layout!=='corner')side=plan.surface;var start=moveQuad(q,plan.motion,side);
   for(var j=0;j<4;j++){var p=pin.property('ADBE Corner Pin-000'+(j+1));clearProperty(p);if(plan.motion==='emerge'||plan.motion==='attach'||plan.motion==='slide'){p.setValueAtTime(plan.delay,start[j]);p.setValueAtTime(plan.delay+.72,q[j]);ease(p);}else p.setValue(q[j]);}
   var op=tr(l,'ADBE Opacity');clearProperty(op);if(plan.motion==='none'||plan.motion==='words'||plan.motion==='typewriter')op.setValue(100);else{op.setValueAtTime(plan.delay,0);op.setValueAtTime(plan.delay+.55,100);ease(op);}l.enabled=true;if(plan.layout==='corner'&&plan.surface!=='both'&&plan.surface!==s.side)l.enabled=false;
   configureText(s.source,plan);
  }
  var sounds=0;if(plan.sound_fx!==false&&plan.motion!=='none')sounds=global.StorylensCaptionSounds.add(wrapper,0,global.StorylensCaptionSounds.events(plan.sound_mode,plan.delay),root,owned);return sounds;
 }
 function unused(item){var used=item.usedIn;return used&&used.length===0;}
 function update(patch,request){
  var r=selected(request),layer=r.layer,old=r.source;if(r.meta&&r.meta.update===request.request_id)return {ok:true,reused:true,context:r.context};if(String(old.id)!==String(request.source_id))throw Error('The selected title changed. Use Edit selected again.');
  var plan=r.plan,oldPose=poseFor(plan);plan.text=String(plan.text).replace(/\S+/g,function(w){return caseWord(w,plan.family==='3d2'&&plan.variant==='yellow');});plan.motion=patch.motion;plan.surface=patch.surface;plan.delay=patch.delay;plan.sound_fx=patch.sound_fx;plan.sound_mode=patch.sound_mode;plan.perspective={pitch:oldPose.pitch,turn:oldPose.turn,roll:oldPose.roll,seam:oldPose.seam};for(var pk in patch.perspective)if(patch.perspective.hasOwnProperty(pk))plan.perspective[pk]=patch.perspective[pk];var pose=poseFor(plan),changed=r.legacy;for(var k in pose)if(pose[k]!==oldPose[k])changed=true;
  var oldName=old.name,made=[],extra=[],staged=null,committed=false,oldItems=[old],names=[],root=old.parentFolder;app.beginUndoGroup('Update selected surface title');
  try{
   staged=old.duplicate();made.push(staged);staged.parentFolder=root;
   var specs=collect(staged,plan);for(var i=0;i<specs.length;i++){var s=specs[i],source=s.source;oldItems.push(source);var copy=source.duplicate();made.push(copy);copy.parentFolder=root;caseSource(copy,plan);names.push({item:copy,name:source.name});s.plane.replaceSource(copy,false);s.source=copy;if(r.legacy&&plan.layout==='column'){var rows=textLayers(copy),small=null,word=null;for(var ri=0;ri<rows.length;ri++){var rp=tr(rows[ri],'ADBE Rotate Z');if(Math.abs(Number(readValue(rp,7.6)))>45)word=rows[ri];else small=rows[ri];}if(small&&word){var sr=small.sourceRectAtTime(7.6,false),sc=readValue(tr(small,'ADBE Scale'),7.6),wp=readValue(tr(word,'ADBE Position'),7.6),pos=tr(small,'ADBE Position');clearProperty(pos);pos.setValue([wp[0]-sr.width*sc[0]/100-12,wp[1]-sr.height*sc[1]/100-24]);}}s.ink=measure(copy);}
   var geo=geometry(plan,specs,staged.width,staged.height);if(!changed)for(var i=0;i<geo.planes.length;i++)geo.planes[i].quad=r.geometry.planes[i].quad;
   var sounds=configure(staged,plan,specs,geo,root,{items:extra,layers:[]});saveMeta(staged,plan,request.request_id);global.StorylensCaptionSounds.mark(staged,plan.sound_mode,plan.sound_fx!==false&&plan.motion!=='none','');
   layer.replaceSource(staged,false);committed=true;var cleanup=[];
   for(var i=0;i<oldItems.length;i++)try{if(unused(oldItems[i]))oldItems[i].remove();}catch(e){cleanup.push(String(e));}
   staged.name=oldName;for(var i=0;i<names.length;i++)names[i].item.name=names[i].name;
   return {ok:true,updated:true,text:plan.text,context:{project_id:request.project_id,comp_id:request.comp_id,layer_id:request.layer_id,source_id:String(staged.id),time:request.time},sounds:sounds,cleanup:cleanup};
  }catch(e){if(!committed){for(var i=made.length-1;i>=0;i--)try{made[i].remove();}catch(_){}for(var i=extra.length-1;i>=0;i--)try{if(unused(extra[i]))extra[i].remove();}catch(_){}throw e;}return {ok:true,updated:true,text:plan.text,context:{project_id:request.project_id,comp_id:request.comp_id,layer_id:request.layer_id,source_id:String(staged.id),time:request.time},warning:'The title changed, but its old unused source could not be fully cleaned.'};}
  finally{app.endUndoGroup();}
 }
 function create(plan,request){
  request=request||{};var own=[],parents=[],placed=[],undo=false,root=null,successful=false;
  if(!app.project)app.newProject();
  var c=app.project.activeItem,active=c instanceof CompItem?c:null,track=null,start=active?active.time:0;
  if(request.comp_id&&(!active||String(active.id)!==String(request.comp_id)))throw Error('Return to the composition where you started, then retry.');
  if(request.project_id&&storylensProjectId()!==request.project_id)throw Error('Return to the same project, then retry.');
  if(typeof request.time==='number')start=request.time;
  if(active&&active.duration-start<.6)throw Error('Move the playhead earlier in the composition.');
  var marker=request.request_id?'Storylens 3D '+request.request_id:'';
  if(marker)for(var n=1;n<=app.project.numItems;n++){var item=app.project.item(n);if(String(item.comment||'')===marker+' done')return {ok:true,reused:true};if(String(item.comment||'')===marker+' building')throw Error('The previous title may be incomplete. Undo that insertion before starting another.');}
  if(active&&active.selectedLayers.length===1&&active.selectedLayers[0].nullLayer&&active.selectedLayers[0].threeDLayer)track=active.selectedLayers[0];
  function folder(name,parent){var f=app.project.items.addFolder(name);own.push(f);f.parentFolder=parent;return f;}
  function comp(name,w,h,parent){var x=app.project.items.addComp(name,w,h,1,8,30);own.push(x);x.parentFolder=parent;x.bgColor=[0,0,0];x.resolutionFactor=[2,2];x.motionBlur=true;x.shutterAngle=90;x.renderer='ADBE Classic 3d';return x;}
  function font(){var names=['Anton-Regular','Impact','Montserrat-Black','Arial-BoldMT'];for(var i=0;i<names.length;i++)try{var f=app.fonts.getFontsByPostScriptName(names[i]);if(f.length&&!f[0].isSubstitute)return names[i];}catch(ignore){}return 'Arial-BoldMT';}
  var typeface=font(),motion=plan.motion||'none',surface=plan.surface||(plan.layout==='corner'?'both':plan.layout==='ground'?'ground':'right');
  function reveal(layer,onset,step){
   var animator=layer.property('ADBE Text Properties').property('ADBE Text Animators').addProperty('ADBE Text Animator');animator.name=motion==='words'?'Word entrance':'Typewriter';
   var props=animator.property('ADBE Text Animator Properties');props.addProperty('ADBE Text Opacity').setValue(0);
   if(motion==='words')props.addProperty('ADBE Text Position 3D').setValue([0,35,0]);
   var selector=animator.property('ADBE Text Selectors').addProperty('ADBE Text Expressible Selector');
   selector.property('ADBE Text Range Type2').setValue(motion==='words'?3:1);
   selector.property('ADBE Text Expressible Amount').expression=motion==='words'?'var t='+onset+'+(textIndex-1)*0.18;ease(time,t,t+0.30,100,0);':'time<'+onset+'+(textIndex-1)*'+step+'?100:0;';
  }
  function block(rows,name,align){
   var x=comp(name,1400,1700,root),texts=[],total=0,i,bounds=[];
   for(i=0;i<rows.length;i++){
    var row=rows[i],l=x.layers.addText(row.text);l.name='EDIT - '+row.text;l.comment='Storylens row '+i;l.motionBlur=true;
    var p=l.property('ADBE Text Properties').property('ADBE Text Document'),d=p.value;d.font=typeface;d.fontSize=row.size;d.applyFill=true;d.fillColor=plan.colourValue;d.applyStroke=false;d.tracking=0;d.justification=ParagraphJustification.LEFT_JUSTIFY;d=caseDocument(d,plan);p.setValue(d);
    var r=l.sourceRectAtTime(0,false),s=Math.min(1,1120/Math.max(1,r.width));tr(l,'ADBE Anchor Point').expression='var r=sourceRectAtTime(7.6,false);[r.left,r.top]';tr(l,'ADBE Scale').setValue([s*100,s*100]);tr(l,'ADBE Scale').expression='var r=sourceRectAtTime(7.6,false);var s=Math.min(1,1120/Math.max(1,r.width))*100;[s,s]';
    texts.push({layer:l,h:r.height*s,w:r.width*s});total+=r.height*s+22;
   }
   var y=(1700-total+22)/2,chars=0,step=Math.min(.055,3.3/Math.max(1,plan.text?plan.text.length:120));
   for(i=0;i<texts.length;i++){
    var t=texts[i],px=align==='right'?1370-t.w:align==='left'?30:(1400-t.w)/2,py=y,enter=.12+i*.20,pos=tr(t.layer,'ADBE Position'),op=tr(t.layer,'ADBE Opacity');
    pos.setValue([px,py]);pos.expression='var r=sourceRectAtTime(7.6,false);var w=r.width*transform.scale[0]/100;value+[('+t.w+'-w)*'+(align==='left'?0:align==='right'?1:.5)+',0]';
    op.setValueAtTime(0,0);op.setValueAtTime(.12,100);op.setValueAtTime(7.3,100);op.setValueAtTime(8,0);ease(op);
    if(motion==='words'||motion==='typewriter')reveal(t.layer,motion==='typewriter' ? .12+chars*step : enter,step);chars+=rows[i].text.length+1;
    t.layer.outPoint=8;bounds.push({x:px,y:py,w:t.w,h:t.h});y+=t.h+22;
   }
   if(plan.layout==='column'){
    var word=texts[1],small=texts[0],scale=Math.min(1,1240/Math.max(1,word.w));tr(word.layer,'ADBE Scale').expression='';tr(word.layer,'ADBE Scale').setValue([scale*100,scale*100]);tr(word.layer,'ADBE Rotate Z').setValue(-90);tr(word.layer,'ADBE Position').expression='';tr(word.layer,'ADBE Position').setValue([800,1450]);tr(small.layer,'ADBE Position').expression='';tr(small.layer,'ADBE Position').setValue([788-small.w,1426-small.h]);
    bounds=[{x:800,y:1450-word.w*scale,w:word.h*scale,h:word.w*scale},{x:788-small.w,y:1426-small.h,w:small.w,h:small.h}];
   }
   if(plan.family==='3d2'&&plan.colour!=='black'){
    var fx=x.layers.addSolid([1,1,1],'FX - TEXT ONLY',1400,1700,1,8);fx.adjustmentLayer=true;fx.source.parentFolder=root;own.push(fx.source);
    var match='ADBE Glo2';for(i=0;app.effects&&i<app.effects.length;i++)if(/^deep\s*glow\s*2$/i.test(app.effects[i].displayName)){match=app.effects[i].matchName;break;}
    var glow;try{glow=fx.property('ADBE Effect Parade').addProperty(match);}catch(pluginError){if(match==='ADBE Glo2')throw pluginError;match='ADBE Glo2';glow=fx.property('ADBE Effect Parade').addProperty(match);}if(match==='ADBE Glo2'){glow.property('ADBE Glo2-0002').setValue(14);glow.property('ADBE Glo2-0003').setValue(.45);}else{for(i=1;i<=glow.numProperties;i++){var v=glow.property(i);if(/^radius$/i.test(v.name))v.setValue(16);if(/^exposure$/i.test(v.name))v.setValue(.18);}}
    fx.moveToBeginning();
   }
   return {source:x,ink:bounds};
  }
  function offset(side){
   if(motion==='emerge')return [0,0,140];if(motion==='attach')return [0,0,-200];
   if(motion==='slide')return side==='ground'?[0,240,0]:side==='left'?[-230,0,0]:[230,0,0];return [0,0,0];
  }
  try{
   app.beginUndoGroup('Add '+plan.family.toUpperCase()+' title');undo=true;
   var family=global.StorylensCaptionFolders.family(plan.family.toUpperCase(),parents);
   root=folder(plan.variant.charAt(0).toUpperCase()+plan.variant.slice(1),family);root.comment=marker?marker+' building':'';
   var blocks=[],layout=plan.layout;
   if(layout==='corner'){
    var left=[],right=[];for(var i=0;i<plan.rows.length;i++)(plan.rows[i].side==='left'?left:right).push(plan.rows[i]);
    {var l=block(left,'Left Wall','right');l.anchor=1400;l.rot=32;l.side='left';blocks.push(l);}
    {var r=block(right,'Right Wall','left');r.anchor=0;r.rot=-32;r.side='right';blocks.push(r);}
   }else{var label='Right Wall';if(layout==='ground')label='Ground';else if(layout==='column')label='Column';else if(surface==='left')label='Left Wall';else if(surface==='front')label='Front Wall';var spec=block(plan.rows,label);spec.side=surface;blocks.push(spec);}
   if(!active){active=comp(plan.family.toUpperCase()+' - '+plan.variant+' - '+plan.format,plan.format==='horizontal'?1920:1080,plan.format==='horizontal'?1080:1920,root);start=0;}
   var w=active.width,h=active.height,wrapper=comp(plan.family.toUpperCase()+' - '+root.name,w,h,root);
   for(var b=0;b<blocks.length;b++){var spec=blocks[b];spec.plane=wrapper.layers.add(spec.source);spec.plane.name=spec.source.name;spec.plane.comment='Storylens Surface '+spec.side;}
   if(plan.delay===undefined)plan.delay=.35;if(!plan.text){var text=[];for(var ri=0;ri<plan.rows.length;ri++)text.push(plan.rows[ri].text);plan.text=text.join(' ');}
   var geo=geometry(plan,blocks,w,h),bounds=geo.bounds,soundCount=configure(wrapper,plan,blocks,geo,root,{items:own,layers:placed});saveMeta(wrapper,plan,'');global.StorylensCaptionSounds.mark(wrapper,plan.sound_mode||'pop_click',plan.sound_fx!==false&&plan.motion!=='none','');
   var outer=active.layers.add(wrapper);placed.push(outer);outer.name=wrapper.name;outer.threeDLayer=false;outer.collapseTransformation=false;outer.motionBlur=true;outer.startTime=start;outer.inPoint=start;outer.outPoint=Math.min(active.duration,start+8);outer.comment=plan.family.toUpperCase()+' Surface Precomp';var fitting=outer.property('ADBE Effect Parade').addProperty('ADBE Corner Pin');fitting.name='Fit surface';fitting.property('ADBE Corner Pin-0001').setValue([0,0]);fitting.property('ADBE Corner Pin-0002').setValue([w,0]);fitting.property('ADBE Corner Pin-0003').setValue([0,h]);fitting.property('ADBE Corner Pin-0004').setValue([w,h]);
   if(track){outer.threeDLayer=true;outer.parent=track;tr(outer,'ADBE Position').setValue([0,0,0]);tr(outer,'ADBE Orientation').setValue([0,0,0]);tr(outer,'ADBE Scale').setValue([100,100,100]);tr(outer,'ADBE Rotate X').setValue(0);tr(outer,'ADBE Rotate Y').setValue(0);tr(outer,'ADBE Rotate Z').setValue(0);}
   root.comment=marker?marker+' done':'';var previousSelection=active.selectedLayers;for(var si=0;si<previousSelection.length;si++)previousSelection[si].selected=false;outer.selected=true;successful=true;
   return {ok:true,font:typeface,composition:active.name,composition_id:String(wrapper.id),placed:1,surfaces:blocks.length,geometry:geo,family:plan.family,variant:plan.variant,motion:motion,bounds:bounds,sounds:soundCount,cameraSolvePerformed:false,context:{project_id:request.project_id||storylensProjectId(),comp_id:String(active.id),layer_id:String(outer.id),source_id:String(wrapper.id),time:active.time}};
  }catch(e){for(var p=placed.length-1;p>=0;p--)try{placed[p].remove();}catch(ignoreLayer){}for(var a=own.length-1;a>=0;a--)try{own[a].remove();}catch(ignoreItem){}global.StorylensCaptionFolders.cleanup(parents);throw e;}
  finally{if(undo)app.endUndoGroup();if(successful&&active)try{active.openInViewer();}catch(viewError){}}
 }
 global.StorylensSurfaceTitles={create:create,describe:describe,update:update,geometry:geometry,poseFor:poseFor};
})(typeof $!=='undefined'?$.global:this);
