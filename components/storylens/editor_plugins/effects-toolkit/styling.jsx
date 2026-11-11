(function(root){
 function rgb(hex){return [parseInt(hex.substr(1,2),16)/255,parseInt(hex.substr(3,2),16)/255,parseInt(hex.substr(5,2),16)/255];}
 function parameter(effect,key){var p=effect.property(key);if(p)return p;var clean=function(s){return String(s).toLowerCase().replace(/[^a-z0-9]/g,'');};for(var i=1;i<=effect.numProperties;i++)if(clean(effect.property(i).name)===clean(key))return effect.property(i);throw Error('This AE effect does not expose the expected '+key+' control. No substitute parameter was used.');}
 function recipes(id,s){
  if(id==='shadow')return [{match:'ADBE Drop Shadow',values:[{key:1,value:rgb(s.color)},{key:2,value:s.opacity,percent:true},{key:3,value:s.angle},{key:4,value:s.distance},{key:5,value:s.softness}]}];
  if(id==='glow')return [{match:'ADBE Glo2',values:[{key:'ADBE Glo2-0002',value:s.radius},{key:'ADBE Glo2-0003',value:s.intensity}]}];
  if(id==='light-sweep')return [{match:'CC Light Sweep',values:[{key:'Width',value:s.width},{key:'Sweep Intensity',value:s.intensity}],sweep:true}];
  if(id==='exposure-contrast')return [{match:'ADBE Exposure2',values:[{key:'Exposure',value:s.exposure}]},{match:'ADBE Brightness & Contrast 2',values:[{key:'Contrast',value:s.contrast}]}];
  if(id==='white-balance')return [{match:'ADBE Color Balance 2',values:[{key:'Midtone Red Balance',value:s.temperature*.3},{key:'Midtone Blue Balance',value:-s.temperature*.3},{key:'Midtone Green Balance',value:-s.tint*.3}]}];
  if(id==='saturation')return [{match:'ADBE HUE SATURATION',values:[{key:'Master Saturation',value:s.amount}]}];
  if(id==='duotone')return [{match:'ADBE Tint',values:[{key:1,value:rgb(s.shadows)},{key:2,value:rgb(s.highlights)},{key:3,value:s.amount}]}];
  if(id==='spot-color')return [{match:'ADBE Leave Color',values:[{key:'Amount to Decolor',value:100},{key:'Color To Leave',value:rgb(s.color)},{key:'Tolerance',value:s.tolerance},{key:'Edge Softness',value:s.softness}]}];
  if(id==='color-look'){
   if(s.look==='monochrome')return recipes('duotone',{shadows:'#000000',highlights:'#ffffff',amount:s.amount});
   if(s.look==='soft')return [{match:'ADBE Brightness & Contrast 2',values:[{key:'Contrast',value:-s.amount*.25},{key:'Brightness',value:s.amount*.05}]}];
   return recipes('white-balance',{temperature:(s.look==='warm'?1:-1)*s.amount*.45,tint:0});
  }
  if(id==='archival')return [{match:'ADBE Tint',values:[{key:1,value:[.07,.05,.03]},{key:2,value:[.92,.85,.69]},{key:3,value:s.amount}]},{match:'ADBE Noise',values:[{key:'Amount of Noise',value:s.grain}]}];
  throw Error('Choose a supported styling tool.');
 }
 function prepare(comp,layers,p,keys){
  if(p.id==='outline'||p.id==='rgb-split'||p.id==='effect-stack'){if(typeof SLToolkitLayerStyles==='undefined')throw Error('The layer-style helper is not loaded. Reopen Storylens.');return SLToolkitLayerStyles.prepare(comp,layers,p,keys);}
  var list=recipes(p.id,p.settings),marker='[Storylens Toolkit effect:'+p.id+']';if(!layers.length)throw Error('Select a visual layer first.');
  for(var i=0;i<layers.length;i++){
   var layer=layers[i],group=layer.property('ADBE Effect Parade');if(layer.locked||!group)throw Error('Select unlocked visual layers.');
   if(p.id==='light-sweep'&&Math.max(comp.time,layer.inPoint)+p.settings.duration>Math.min(comp.duration,layer.outPoint))throw Error('The layer needs enough time for the light sweep.');
   for(var j=0;j<list.length;j++){
    var old=group.property('SLT '+p.id+' '+(j+1));if(old&&(old.matchName!==list[j].match||String(layer.comment).indexOf(marker)<0))throw Error('An effect has the same name as this tool. Rename it before applying.');
    if(!old&&group.canAddProperty&&!group.canAddProperty(list[j].match))throw Error('The '+list[j].match+' effect is unavailable in this AE installation.');
    if(old)for(var k=0;k<list[j].values.length;k++){var prop=parameter(old,list[j].values[k].key);if(prop.numKeys||prop.expression)throw Error('This effect setting is animated. Edit it directly in Effect Controls.');}
   }
  }
  return {apply:function(defer){
   for(var i=0;i<layers.length;i++)(function(layer){
    var oldComment=layer.comment||'';defer(function(){layer.comment=oldComment;});if(oldComment.indexOf(marker)<0)layer.comment=oldComment+(oldComment?'\n':'')+marker;
    for(var j=0;j<list.length;j++)(function(spec,index){
     var group=layer.property('ADBE Effect Parade'),name='SLT '+p.id+' '+(index+1),effect=group.property(name),fresh=!effect;
     if(fresh){effect=group.addProperty(spec.match);effect.name=name;defer(function(){var e=layer.property('ADBE Effect Parade').property(name);if(e)e.remove();});}
     for(var k=0;k<spec.values.length;k++)(function(setting){
      var prop=parameter(layer.property('ADBE Effect Parade').property(name),setting.key),old=prop.value,value=setting.value;
      if(!fresh)defer(function(){parameter(layer.property('ADBE Effect Parade').property(name),setting.key).setValue(old);});
      if(setting.percent)value=value/100*(prop.hasMax?prop.maxValue:100);
      if(Object.prototype.toString.call(value)==='[object Array]'&&old&&old.length===4&&value.length===3)value=[value[0],value[1],value[2],1];
      prop.setValue(value);
     })(spec.values[k]);
     if(spec.sweep){var center=parameter(layer.property('ADBE Effect Parade').property(name),'Center');if(center.expression)throw Error('The sweep Center has an expression. Edit it directly.');var oldKeys=center.numKeys?keys.snapshot(center):[],oldCenter=center.value;
      if(!fresh)defer(function(){var c=parameter(layer.property('ADBE Effect Parade').property(name),'Center');if(oldKeys.length)keys.restore(c,oldKeys);else{while(c.numKeys)c.removeKey(c.numKeys);c.setValue(oldCenter);}});
      var bounds=layer.sourceRectAtTime(comp.time,false),start=Math.max(comp.time,layer.inPoint);while(center.numKeys)center.removeKey(center.numKeys);center.setValueAtTime(start,[bounds.left-bounds.width*.25,bounds.top+bounds.height/2]);center.setValueAtTime(start+p.settings.duration,[bounds.left+bounds.width*1.25,bounds.top+bounds.height/2]);
      for(var n=1;n<=center.numKeys;n++){var a=[];for(var q=0;q<center.keyInTemporalEase(n).length;q++)a.push(new KeyframeEase(0,66));center.setInterpolationTypeAtKey(n,KeyframeInterpolationType.BEZIER,KeyframeInterpolationType.BEZIER);center.setTemporalEaseAtKey(n,a,a);}
     }
    })(list[j],j);
   })(layers[i]);
   return {ok:true,changed:layers.length,editable:true,message:SLToolkitModel.find(p.id).name+' applied. Refine the native settings in Effect Controls.'};
  }};
 }
 root.SLToolkitStyling={prepare:prepare,parameter:parameter,rgb:rgb};
})(typeof $!=='undefined'&&$.global?$.global:this);
