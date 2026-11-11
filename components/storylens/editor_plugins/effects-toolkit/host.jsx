/* Native toolkit dispatcher. Every mutation is preflighted and journalled. */
function storylensToolkit(input){
 var started=false,journal=[],comp,selection,i,j,p,tool,s,groups=[],result;
 function defer(fn){journal.push(fn);}
 function easeCopy(a,scale){var out=[];for(var n=0;n<a.length;n++)out.push(new KeyframeEase(a[n].speed*scale,a[n].influence));return out;}
 function snapshot(property){var out=[];for(var k=1;k<=property.numKeys;k++){var key={t:property.keyTime(k),v:property.keyValue(k),inType:property.keyInInterpolationType(k),outType:property.keyOutInterpolationType(k),inEase:easeCopy(property.keyInTemporalEase(k),1),outEase:easeCopy(property.keyOutTemporalEase(k),1),continuous:property.keyTemporalContinuous(k),auto:property.keyTemporalAutoBezier(k),selected:false};var selected=property.selectedKeys;for(var n=0;n<selected.length;n++)if(selected[n]===k)key.selected=true;if(property.isSpatial){key.inT=property.keyInSpatialTangent(k);key.outT=property.keyOutSpatialTangent(k);key.spatialContinuous=property.keySpatialContinuous(k);key.spatialAuto=property.keySpatialAutoBezier(k);key.roving=property.keyRoving(k);}if(property.keyLabel)key.label=property.keyLabel(k);out.push(key);}return out;}
 function metadata(property,k,key,reverse,speed){
  property.setInterpolationTypeAtKey(k,reverse?key.outType:key.inType,reverse?key.inType:key.outType);
  property.setTemporalContinuousAtKey(k,false);property.setTemporalAutoBezierAtKey(k,false);
  property.setTemporalEaseAtKey(k,easeCopy(reverse?key.outEase:key.inEase,property.isSpatial?Math.abs(speed):speed),easeCopy(reverse?key.inEase:key.outEase,property.isSpatial?Math.abs(speed):speed));
  property.setTemporalContinuousAtKey(k,key.continuous);property.setTemporalAutoBezierAtKey(k,key.auto);
  if(property.isSpatial){property.setSpatialAutoBezierAtKey(k,false);property.setSpatialContinuousAtKey(k,false);property.setSpatialTangentsAtKey(k,reverse?key.outT:key.inT,reverse?key.inT:key.outT);property.setSpatialContinuousAtKey(k,key.spatialContinuous);property.setSpatialAutoBezierAtKey(k,key.spatialAuto);property.setRovingAtKey(k,key.roving);}
  if(key.label!==undefined&&property.setLabelAtKey)property.setLabelAtKey(k,key.label);property.setSelectedAtKey(k,key.selected);
 }
 function restore(property,keys){for(var n=property.numKeys;n>=1;n--)property.removeKey(n);for(n=0;n<keys.length;n++)property.setValueAtTime(keys[n].t,keys[n].v);for(n=0;n<keys.length;n++)metadata(property,n+1,keys[n],false,1);}
 function backup(property,keys){defer(function(){restore(property,keys);});}
 function selectedProperties(){var out=[],ps=comp.selectedProperties;for(var n=0;n<ps.length;n++)if(ps[n].propertyType===PropertyType.PROPERTY&&ps[n].numKeys&&ps[n].selectedKeys.length){if(ps[n].expressionEnabled)throw Error('Disable the expression on the selected keyed property before changing its keyframes.');out.push(ps[n]);}if(!out.length)throw Error('Select timeline keyframes first, then click this tool.');return out;}
 function begin(){app.beginUndoGroup('Storylens '+tool.name);started=true;}
 function finish(message,count){return {ok:true,name:tool.name,changed:count,message:message,editable:true};}
 try{
  p=SLToolkitModel.validate(input);tool=SLToolkitModel.find(p.id);s=p.settings;comp=app.project.activeItem;
  if(!(comp instanceof CompItem)&&!(tool.category==='delivery'&&tool.number<=94))throw Error('Open the composition you want to edit first.');selection=comp instanceof CompItem?comp.selectedLayers.slice(0):[];
  for(i=0;i<selection.length;i++)if(selection[i].locked)throw Error('Unlock the selected layers before applying this tool.');
  if(p.id==='ease'||p.id==='ease-copy'||p.id==='retime'||p.id==='reverse'){
   var properties=selectedProperties(),selectedCount=0;
   for(i=0;i<properties.length;i++){var ks=snapshot(properties[i]),sel=[],times=[],untouched=[];for(j=0;j<ks.length;j++)if(ks[j].selected){sel.push(j+1);times.push(ks[j].t);selectedCount++;}else untouched.push(ks[j].t);groups.push({property:properties[i],keys:ks,selected:sel,times:times,untouched:untouched});}
   if(p.id==='ease-copy'&&s.mode==='copy'){
    if(selectedCount!==1)throw Error('Select exactly one keyframe to copy its easing.');
    $.global.SLToolkitEaseClipboard=groups[0].keys[groups[0].selected[0]-1];return SLQuickMotionModel.stringify(finish('Easing copied. Select destination keyframes and choose Paste.',1));
   }
   var clipboard=$.global.SLToolkitEaseClipboard,remap=null;
   if(p.id==='ease-copy'){
    if(!clipboard)throw Error('Copy easing from one keyframe first.');
    for(i=0;i<groups.length;i++)if(groups[i].keys[0].inEase.length!==clipboard.inEase.length)throw Error('Source and destination easing dimensions differ. Copy from a property with matching dimensions.');
   }
   if(p.id==='retime'||p.id==='reverse'){
    var low=Infinity,high=-Infinity;for(i=0;i<groups.length;i++)for(j=0;j<groups[i].times.length;j++){low=Math.min(low,groups[i].times[j]);high=Math.max(high,groups[i].times[j]);}
    remap=SLToolkitModel.retime(groups,p.id==='reverse'?high-low:s.duration,p.id==='reverse');
    for(i=0;i<groups.length;i++){
     SLToolkitModel.checkCollisions(remap[i].times,groups[i].untouched,.00001);
     for(j=0;j<groups[i].selected.length;j++){if(groups[i].keys[groups[i].selected[j]-1].roving)throw Error('Turn off Rove Across Time on selected keys before retiming.');if(remap[i].times[j]<-10800||remap[i].times[j]>10800)throw Error('The requested key times exceed After Effects limits.');}
    }
   }
   begin();
   for(i=0;i<groups.length;i++){
    var g=groups[i],property=g.property;backup(property,g.keys);
    if(remap){
     for(j=g.selected.length-1;j>=0;j--)property.removeKey(g.selected[j]);
     for(j=0;j<g.selected.length;j++)property.setValueAtTime(remap[i].times[j],g.keys[g.selected[j]-1].v);
     for(j=0;j<g.selected.length;j++)metadata(property,property.nearestKeyIndex(remap[i].times[j]),g.keys[g.selected[j]-1],p.id==='reverse',remap[i].speedScale);
    }else for(j=0;j<g.selected.length;j++){
     var k=g.selected[j],key=g.keys[k-1],inEase=key.inEase,outEase=key.outEase,inType=key.inType,outType=key.outType;
     if(p.id==='ease-copy'){inEase=easeCopy(clipboard.inEase,1);outEase=easeCopy(clipboard.outEase,1);inType=clipboard.inType;outType=clipboard.outType;}
     else if(s.mode==='linear'){inType=outType=KeyframeInterpolationType.LINEAR;}
     else{if(s.mode!=='out'){inType=KeyframeInterpolationType.BEZIER;inEase=[];for(var n=0;n<key.inEase.length;n++)inEase.push(new KeyframeEase(0,s.influence));}if(s.mode!=='in'){outType=KeyframeInterpolationType.BEZIER;outEase=[];for(n=0;n<key.outEase.length;n++)outEase.push(new KeyframeEase(0,s.influence));}}
     property.setTemporalContinuousAtKey(k,false);property.setTemporalAutoBezierAtKey(k,false);property.setInterpolationTypeAtKey(k,inType,outType);property.setTemporalEaseAtKey(k,inEase,outEase);
    }
   }
   result=finish(tool.name+' applied to '+selectedCount+' keyframes. Values remain editable in the timeline.',selectedCount);
  }else if(p.id==='stagger'){
   if(selection.length<2)throw Error('Select at least two timeline layers to stagger.');selection.sort(function(a,b){return (s.order==='bottom-up'?-1:1)*(a.index-b.index);});var layers=[];
   for(i=0;i<selection.length;i++)layers.push({start:selection[i].startTime,inPoint:selection[i].inPoint,outPoint:selection[i].outPoint});var starts=SLToolkitModel.stagger(layers,s.step,s.mode);
   for(i=0;i<starts.length;i++)if(starts[i]<-10800||starts[i]>10800)throw Error('Layer timing exceeds After Effects limits.');
   begin();for(i=0;i<selection.length;i++)(function(layer,old,next){defer(function(){layer.startTime=old;});layer.startTime=next;})(selection[i],layers[i].start,starts[i]);result=finish('Staggered '+selection.length+' layers. Adjust their start times in the timeline.',selection.length);
  }else if(tool.category==='delivery'&&typeof SLToolkitDelivery!=='undefined'){
   var task=SLToolkitDelivery.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});if(!task.readonly)begin();result=task.apply(defer);
  }else if(tool.category==='library'&&typeof SLToolkitLibrary!=='undefined'){
   var task=SLToolkitLibrary.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});if(!task.readonly)begin();result=task.apply(defer);
  }else if(tool.category==='timing'&&typeof SLToolkitTiming!=='undefined'){
   var task=SLToolkitTiming.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});begin();result=task.apply(defer);
  }else if(tool.category==='layers'&&typeof SLToolkitLayers!=='undefined'){
   var task=SLToolkitLayers.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});begin();result=task.apply(defer);
  }else if(tool.category==='camera'&&typeof SLToolkitCamera!=='undefined'){
   var task=SLToolkitCamera.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});begin();result=task.apply(defer);
  }else if(tool.category==='masks'&&typeof SLToolkitMasks!=='undefined'){
   var task=SLToolkitMasks.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});begin();result=task.apply(defer);
  }else if(tool.category==='transitions'&&typeof SLToolkitTransitions!=='undefined'){
   var task=SLToolkitTransitions.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});begin();result=task.apply(defer);
  }else if((tool.category==='styling'||tool.category==='colour'||p.id==='archival')&&typeof SLToolkitStyling!=='undefined'){
   var task=SLToolkitStyling.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});if(!task.readonly)begin();result=task.apply(defer);
  }else if(typeof SLToolkitBuilderModel!=='undefined'&&typeof SLToolkitBuilders!=='undefined'&&function(){for(var b=0;b<SLToolkitBuilderModel.ids.length;b++)if(SLToolkitBuilderModel.ids[b]===p.id)return true;return false;}()){
   var task=SLToolkitBuilders.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});begin();result=task.apply(defer);
  }else if(tool.category==='typography'&&typeof SLToolkitTypography!=='undefined'){
   var task=SLToolkitTypography.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});if(!task.readonly)begin();result=task.apply(defer);
  }else if(tool.category==='text'&&typeof SLToolkitText!=='undefined'){
   var task=SLToolkitText.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});begin();result=task.apply(defer);
  }else if(typeof SLToolkitMotion!=='undefined'){
   var task=SLToolkitMotion.prepare(comp,selection,p,{snapshot:snapshot,restore:restore});begin();result=task.apply(defer);
  }else throw Error('This tool module has not loaded. Reopen Storylens and try again.');
  return SLQuickMotionModel.stringify(result);
 }catch(e){var rollback=true;if(started)for(i=journal.length-1;i>=0;i--)try{journal[i]();}catch(ignore){rollback=false;}return SLQuickMotionModel.stringify({error:started?'The tool could not finish. '+(rollback?'Changes from this attempt were restored.':'Use After Effects Undo before retrying.'):String(e.message||e),code:'effects_toolkit',details:String(e),partial:started&&!rollback});}
 finally{if(started)app.endUndoGroup();}
}
