/* Solid native 3D text. Cinema 4D's renderer ID is ADBE Ernst; ADBE Advanced 3d is Classic. */
(function(g){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function named(c,name){for(var i=1;i<=c.numLayers;i++)if(c.layer(i).name===name)return c.layer(i);return null;}
 function rendererFor(c){var list=c.renderers||[];for(var i=0;i<list.length;i++)if(list[i]==='ADBE Ernst'||/cinema\s*4d/i.test(list[i]))return list[i];throw Error('Solid 3D1 needs the Cinema 4D renderer in this composition.');}
 function optionalMaterial(properties,name,value){
  var p=null;
  try{p=properties.property(name);if(!p){if(properties.canAddProperty&&!properties.canAddProperty(name))return false;p=properties.addProperty(name);}if(!p)return false;p.setValue(value);return true;}
  catch(e){if(!/hidden|not supported|cannot add|can not add/i.test(String(e)))throw Error('3D1 material '+name+': '+String(e));try{if(p)p.remove();}catch(ignore){}return false;}
 }
 function letterContrast(l,warnings){
  // Shade geometry independently of the front face. No light layers, raster effects or reduced depth.
  var name='READABILITY - Letter contrast',animators=l.property('ADBE Text Properties').property('ADBE Text Animators'),a=animators.property(name);
  if(!a){a=animators.addProperty('ADBE Text Animator');a.name=name;}
  var selectors=a.property('ADBE Text Selectors');if(!selectors.numProperties)selectors.addProperty('ADBE Text Selector');
  var names=['ADBE 3DText Side Bright','ADBE 3DText Back Bright','ADBE 3DText Bevel Bright'],values=[-78,-85,-35],parts=['Side','Back','Bevel'],factors=[.22,.15,.65],fill=l.property('ADBE Text Properties').property('ADBE Text Document').value.fillColor||[1,1,1];
  for(var j=0;j<names.length;j++){
   // Adding to an indexed AE group invalidates its property references; reacquire each time.
   var properties=animators.property(name).property('ADBE Text Animator Properties');
   if(!optionalMaterial(properties,names[j],values[j])){
    // Some AE builds hide a material even though addProperty returns it. Use its colour override instead.
    properties=animators.property(name).property('ADBE Text Animator Properties');var f=factors[j];
    if(!optionalMaterial(properties,'ADBE 3DText '+parts[j]+' RGB',[fill[0]*f,fill[1]*f,fill[2]*f,1])&&j===0){var warning='The title imported with solid depth, but this AE renderer did not allow darker side shading.';if(warnings&&warnings.join('|').indexOf(warning)<0)warnings.push(warning);}
   }
  }
 }
 function blackOutline(c,faces,title){
  // C4D ignores a text-layer Character stroke. A small ring of black native text faces
  // behind each editable face supplies the visible contour without flattening the 3D rig.
  for(var i=c.numLayers;i>=1;i--){var old=c.layer(i);if(/^Storylens 3D1 outline (MAIN|SUB) [0-7]$/.test(String(old.comment||''))){old.locked=false;old.remove();}}
  var effects=title.property('ADBE Effect Parade'),width=effects.property('STROKE - Black outline');
  if(!width){width=effects.addProperty('ADBE Slider Control');width.name='STROKE - Black outline';width.property('ADBE Slider Control-0001').setValue(c.width/270);}
  var offsets=[[1,0],[.70710678,.70710678],[0,1],[-.70710678,.70710678],[-1,0],[-.70710678,-.70710678],[0,-1],[.70710678,-.70710678]];
  for(var row=0;row<faces.length;row++){
   var face=faces[row],doc=face.property('ADBE Text Properties').property('ADBE Text Document').value,part=row===0?'MAIN':'SUB';
   for(var n=0;n<offsets.length;n++){
    var l=c.layers.addText(doc.text);l.name='OUTLINE - '+part+' '+n;l.comment='Storylens 3D1 outline '+part+' '+n;l.threeDLayer=true;l.parent=face;l.shy=true;l.startTime=face.startTime;l.inPoint=face.inPoint;l.outPoint=face.outPoint;
    var text=l.property('ADBE Text Properties').property('ADBE Text Document'),d=text.value;d.font=doc.font;d.fontSize=doc.fontSize;d.tracking=doc.tracking;d.justification=doc.justification;d.applyFill=true;d.fillColor=[0,0,0];d.applyStroke=false;text.setValue(d);
    text.expression='var t=parent.text.sourceText;t.getStyleAt(0,time).setText(t).setApplyFill(true).setFillColor([0,0,0]).setApplyStroke(false);';
    tr(l,'ADBE Anchor Point').expression='parent.anchorPoint';
    tr(l,'ADBE Position').expression='var a=parent.anchorPoint;var w=Math.max(0,Math.min(40,thisComp.layer("TITLE POSITION - Move both lines").effect("STROKE - Black outline")(1)));[a[0]+w*'+offsets[n][0]+',a[1]+w*'+offsets[n][1]+',a[2]+0.35];';
    tr(l,'ADBE Scale').setValue([100,100,100]);tr(l,'ADBE Orientation').setValue([0,0,0]);tr(l,'ADBE Rotate X').setValue(0);tr(l,'ADBE Rotate Y').setValue(0);tr(l,'ADBE Rotate Z').setValue(0);tr(l,'ADBE Opacity').expression='parent.active ? parent.opacity : 0';
    var geometry=l.property('ADBE Extrsn Options Group'),depth=geometry&&geometry.property('ADBE Extrsn Depth');if(!depth)throw Error('The 3D1 black outline geometry could not be created. The original title is kept.');depth.setValue(0);l.moveToEnd();l.locked=true;
   }
  }
 }
 function extrude(c,depth,fresh,warnings){
  c.renderer=rendererFor(c);var main=named(c,'EDIT - MAIN'),sub=named(c,'EDIT - SUBTITLE'),title=named(c,'TITLE POSITION - Move both lines');if(!main||!sub||!title)throw Error('The editable 3D1 text rig is missing.');
  var faces=[main,sub],control=title.property('ADBE Effect Parade').property('DEPTH - Letter sides');if(control)control.property('ADBE Slider Control-0001').setValue(depth);
  for(var i=0;i<faces.length;i++){
   var l=faces[i];l.threeDLayer=true;if(fresh){tr(l,'ADBE Orientation').setValue([0,0,0]);tr(l,'ADBE Rotate X').setValue(0);tr(l,'ADBE Rotate Y').setValue(0);tr(l,'ADBE Rotate Z').setValue(0);}
   var geometry=l.property('ADBE Extrsn Options Group'),d=geometry&&geometry.property('ADBE Extrsn Depth');if(!d)throw Error('This AE renderer did not expose real text extrusion. The original title is kept.');
   d.setValue(depth);if(d.canSetExpression&&control)d.expression='Math.max(1,thisComp.layer("TITLE POSITION - Move both lines").effect("DEPTH - Letter sides")(1));';
   // Bevel Depth is hidden while Bevel Style is None. Preserve the owner's bevel settings.
   letterContrast(l,warnings);
  }
  blackOutline(c,faces,title);
  // The title's pivot is the precomp centre, so outer rotations turn the object about its own centre.
  if(String(c.comment||'').indexOf('[Storylens solid 3d ')<0){var p=tr(title,'ADBE Position'),v=p.value;if(p.numKeys){var base=p.keyValue(1)[2];for(var k=1;k<=p.numKeys;k++){var value=p.keyValue(k);p.setValueAtKey(k,[value[0],value[1],value[2]-base]);}}else if(!p.expressionEnabled)p.setValue([v[0],v[1],0]);}
  // Retain the authored camera push as object-scale animation without taking over the parent's camera.
  var rig=named(c,'CAMERA MOVE - Edit these keys'),scale=tr(title,'ADBE Scale');if(rig&&!scale.numKeys&&!scale.expressionEnabled)scale.expression='var z=thisComp.layer("CAMERA MOVE - Edit these keys").transform.position[2];var s=1750/Math.max(500,2240-z)*100;[s,s,s];';
  for(var i=c.numLayers;i>=1;i--)if(/^DEPTH - (MAIN|SUB) \d+$/.test(c.layer(i).name))c.layer(i).remove();
  return c.renderer;
 }
 function mark(c,depth,id){c.comment=String(c.comment||'').replace(/\n?\[Storylens solid 3d [0-9.]+ [a-f0-9]*\]/g,'')+'\n[Storylens solid 3d '+depth+' '+(id||'')+']';}
 function prepare(c,depth,fresh,warnings){var r=extrude(c,depth,fresh,warnings);mark(c,depth,'');return r;}
 function context(c,l){return {project_id:storylensProjectId(),comp_id:String(c.id),layer_id:String(l.id),source_id:String(l.source.id),time:c.time};}
 function upgrade(patch,request){
  var info=g.StorylensCaptionAudioEdit.describe(),c=app.project.activeItem,l=c.selectedLayers[0],old=l.source;if(info.plan.family!=='3d1')throw Error('Select a 3D1 outer title layer to enable solid depth.');
  if(storylensProjectId()!==request.project_id||String(c.id)!==String(request.comp_id)||String(l.id)!==String(request.layer_id))throw Error('Select the same title in the same project, then retry.');
  var match=String(old.comment||'').match(/\[Storylens solid 3d [0-9.]+ ([a-f0-9]+)\]/);if(match&&match[1]===request.request_id)return {ok:true,reused:true,context:context(c,l)};
  if(String(old.id)!==String(request.source_id))throw Error('The selected title changed. Load it again before enabling depth.');
  var effects=l.property('ADBE Effect Parade'),masks=l.property('ADBE Mask Parade');if(effects&&effects.numProperties||masks&&masks.numProperties)throw Error('Move outer effects or masks inside the title precomp before enabling solid 3D. They flatten a collapsed 3D precomp.');
  var wanted=rendererFor(c),previous=c.renderer,was3d=l.threeDLayer,wasCollapsed=l.collapseTransformation,name=old.name,copy=null,committed=false,warnings=[];app.beginUndoGroup('Enable solid 3D1 depth');
  try{copy=old.duplicate();copy.parentFolder=old.parentFolder;var r=extrude(copy,patch.depth,false,warnings);if(r!==wanted)throw Error('The containing composition and title need the same 3D renderer.');mark(copy,patch.depth,request.request_id);c.renderer=r;l.replaceSource(copy,false);l.threeDLayer=true;l.collapseTransformation=true;committed=true;var cleanup=[];try{if(old.usedIn.length===0)old.remove();}catch(e){cleanup.push(String(e));}copy.name=name;return {ok:true,depth_updated:true,depth:patch.depth,renderer:r,context:context(c,l),cleanup:cleanup,warnings:warnings};}
  catch(e){if(!committed){try{l.threeDLayer=was3d;l.collapseTransformation=wasCollapsed;if(copy&&l.source===copy)l.replaceSource(old,false);c.renderer=previous;if(copy)copy.remove();}catch(_){}throw e;}return {ok:true,depth_updated:true,context:context(c,l),warning:'Solid depth is enabled; an older unused source remains.'};}
  finally{app.endUndoGroup();}
 }
 g.StorylensSolidTitles={rendererFor:rendererFor,prepare:prepare,upgrade:upgrade};
})(typeof $!=='undefined'?$.global:this);
