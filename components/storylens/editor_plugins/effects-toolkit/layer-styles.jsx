(function(root){
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function capture(group,keys){var out=[];for(var i=1;i<=group.numProperties;i++){
  var p=group.property(i),node={index:i,match:p.matchName,name:p.name};
  if(p.numProperties)node.children=capture(p,keys);
  else{
   var value;try{value=p.value;}catch(e){if(p.isModified)throw Error('This effect has a custom control that cannot be copied: '+p.name);continue;}
   if(value===undefined||Object.prototype.toString.call(value)==='[object Array]'&&!value.length)continue;
   if(typeof value==='object'&&Object.prototype.toString.call(value)!=='[object Array]')throw Error('This effect contains unsupported custom data: '+p.name);
   node.value=value;node.keys=p.numKeys?keys.snapshot(p):[];node.expression=p.canSetExpression?p.expression:'';
  }
  out.push(node);
 }return out;}
 function paste(group,nodes,keys){for(var i=0;i<nodes.length;i++){var node=nodes[i],p=group.property(node.index);if(!p||p.matchName!==node.match){p=group.property(node.match);if(!p)throw Error('The effect structure differs at '+node.name+'.');}if(node.children)paste(p,node.children,keys);else{if(node.keys.length)keys.restore(p,node.keys);else p.setValue(node.value);if(node.expression){p.expression=node.expression;if(p.expressionError)throw Error(p.expressionError);}}}}
 function prepare(comp,layers,p,keys){
  if(!layers.length)throw Error('Select visual layers first.');var id=p.id,s=p.settings;
  for(var i=0;i<layers.length;i++)if(layers[i].locked||!layers[i].property('ADBE Effect Parade'))throw Error('Select unlocked visual layers.');
  if(id==='effect-stack'){
   if(s.mode==='copy'){
    if(layers.length!==1)throw Error('Select one layer to copy its effect stack.');var source=layers[0].property('ADBE Effect Parade'),effects=[];
    if(!source.numProperties)throw Error('The selected layer has no effects to copy.');
    for(i=1;i<=source.numProperties;i++){var effect=source.property(i);effects.push({name:effect.name,match:effect.matchName,enabled:effect.enabled,properties:capture(effect,keys)});}
    return {readonly:true,apply:function(){root.SLToolkitEffectClipboard={comp:comp,effects:effects};return {ok:true,changed:0,message:'Effect stack copied. Select destination layers in this composition and choose Paste.'};}};
   }
   var clipboard=root.SLToolkitEffectClipboard;if(!clipboard)throw Error('Copy an effect stack first.');if(clipboard.comp!==comp)throw Error('Paste effect stacks in the same composition so layer references remain valid.');
   for(i=0;i<layers.length;i++)for(var j=0;j<clipboard.effects.length;j++){var group=layers[i].property('ADBE Effect Parade'),spec=clipboard.effects[j];if(group.property(spec.name))throw Error('A destination already has an effect named '+spec.name+'. Rename that effect before pasting.');if(group.canAddProperty&&!group.canAddProperty(spec.match))throw Error('An effect in this stack is unavailable: '+spec.name);}
   return {apply:function(defer){for(var i=0;i<layers.length;i++)for(var j=0;j<clipboard.effects.length;j++)(function(layer,spec){var e=layer.property('ADBE Effect Parade').addProperty(spec.match);e.name=spec.name;defer(function(){var effect=layer.property('ADBE Effect Parade').property(spec.name);if(effect)effect.remove();});if(spec.enabled!==undefined)e.enabled=spec.enabled;paste(e,spec.properties,keys);})(layers[i],clipboard.effects[j]);return {ok:true,changed:layers.length,message:'Effect stack pasted. Source and destination layers remain separate and editable.'};}};
  }
  if(id==='rgb-split')for(i=0;i<layers.length;i++){if(layers[i].threeDLayer||layers[i].parent)throw Error('RGB Split needs unparented 2D artwork. Precompose a parented or 3D setup first.');if(tr(layers[i],'ADBE Position').expression)throw Error('Precompose position expressions before applying RGB Split.');}
  return {apply:function(defer){
   for(var i=0;i<layers.length;i++)(function(layer){
    if(id==='outline'){
     var copy=layer.duplicate();copy.name='Outline - '+layer.name;copy.comment='Storylens Toolkit outline v1';defer(function(){copy.remove();});copy.moveAfter(layer);
     var fill=copy.property('ADBE Effect Parade').addProperty('ADBE Fill');SLToolkitStyling.parameter(fill,'Color').setValue(SLToolkitStyling.rgb(s.color));var choke=copy.property('ADBE Effect Parade').addProperty('ADBE Simple Choker');SLToolkitStyling.parameter(choke,'Choke Matte').setValue(-s.width);return;
    }
    var parent=SLToolkitBuilders.folder('Effects',app.project.rootFolder,defer),section=SLToolkitBuilders.folder('Layer Styling',parent,defer),source=app.project.items.addComp('RGB Split - '+layer.name,comp.width,comp.height,comp.pixelAspect||1,comp.duration,comp.frameRate);source.parentFolder=section;source.comment='Storylens Toolkit:rgb-split:v1';defer(function(){source.remove();});
    var names=['Red','Green','Blue'];
    for(var channel=0;channel<3;channel++){
     layer.copyToComp(source);var copy=source.layer(1);copy.name=names[channel];copy.enabled=true;copy.blendingMode=BlendingMode.ADD;var mixer=copy.property('ADBE Effect Parade').addProperty('ADBE CHANNEL MIXER');
     for(var out=0;out<3;out++)for(var input=0;input<3;input++)SLToolkitStyling.parameter(mixer,names[out]+'-'+names[input]).setValue(out===channel&&input===channel?100:0);
     tr(copy,'ADBE Position').expression='value+['+((channel-1)*s.distance)+',0];';
    }
    var added=comp.layers.add(source);added.name='RGB Split - '+layer.name;added.inPoint=layer.inPoint;added.outPoint=layer.outPoint;added.moveAfter(layer);defer(function(){added.remove();});var old=layer.enabled;defer(function(){layer.enabled=old;});layer.enabled=false;
   })(layers[i]);
   return {ok:true,changed:layers.length,editable:true,message:SLToolkitModel.find(id).name+' created. The original layers are kept; edit the added layers or precomp.'};
  }};
 }
 root.SLToolkitLayerStyles={prepare:prepare,capture:capture,paste:paste};
})(typeof $!=='undefined'&&$.global?$.global:this);
