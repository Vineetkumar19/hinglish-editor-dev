(function(root){
 var tag='// Storylens Toolkit transition v1:';
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function prepare(comp,layers,p,keys){
  var id=p.id,s=p.settings,start=comp.time-s.duration/2,end=comp.time+s.duration/2,records=[],i,j;
  if(layers.length!==2)throw Error('Select exactly two overlapping clips. Put the incoming clip above the outgoing clip.');
  if(start<0||end>comp.duration)throw Error('Move the playhead far enough from the composition edges for this transition.');
  layers=layers.slice(0);layers.sort(function(a,b){return a.index-b.index;});
  for(i=0;i<layers.length;i++){
   var l=layers[i];if(l.locked||l.threeDLayer||l.parent||!l.property('ADBE Effect Parade'))throw Error('Use two unlocked, unparented 2D visual layers.');
   if(l.inPoint>start||l.outPoint<end)throw Error('Both clips need overlap for the whole transition around the playhead. Extend their trim handles, then retry.');
   var names=['ADBE Opacity'];if(id==='whip'||id==='glitch-transition')names.push('ADBE Position');if(id==='zoom-transition')names.push('ADBE Scale');
   for(j=0;j<names.length;j++){var property=tr(l,names[j]);if(!property||!property.canSetExpression||property.dimensionsSeparated)throw Error('Use editable combined transform properties.');if(property.expression&&property.expression.indexOf(tag+id+'\n')!==0)throw Error('A clip already has another transform expression. Precompose it or remove that expression first.');}
   var progress=l.property('ADBE Effect Parade').property('SLT '+id+' · Progress');if(progress&&tr(l,'ADBE Opacity').expression.indexOf(tag+id+'\n')!==0)throw Error('A Progress control conflicts with this transition. Rename it before applying.');
   if(id==='shape-reveal'&&i===0){var masks=l.property('ADBE Mask Parade');if(!masks||masks.numProperties)throw Error('Shape Reveal needs an incoming layer without masks. Precompose its existing masks first.');}
   records.push({layer:l,incoming:i===0});
  }
  function prefix(){return tag+id+'\nvar u=Math.max(0,Math.min(1,effect('+SLQuickMotionModel.quote('SLT '+id+' · Progress')+')(1)/100));';}
  return {apply:function(defer){
   for(var i=0;i<records.length;i++)(function(rec){var l=rec.layer,incoming=rec.incoming;
    SLToolkitControls.slider(l,'SLT '+id+' · Progress',0,defer,keys,{start:start,end:end});
    var opacity=incoming?'value*u;':'u<1?value:0;';
    if(id==='whip'||id==='shape-reveal')opacity=incoming?'value;':'u<1?value:0;';
    if(id==='glitch-transition'&&incoming)opacity='var f=Math.floor(time*'+s.rate+');value*Math.max(0,Math.min(1,u+(u>0&&u<1?Math.sin(f*7.13)*.2:0)));';
    SLToolkitControls.assign(tr(l,'ADBE Opacity'),'expression',prefix()+opacity,defer);
    if(id==='whip'){
     var dx=s.direction==='left'?-comp.width:s.direction==='right'?comp.width:0,dy=s.direction==='up'?-comp.height:s.direction==='down'?comp.height:0;
     SLToolkitControls.assign(tr(l,'ADBE Position'),'expression',prefix()+'var f='+(incoming?'u-1':'u')+';[value[0]+'+dx+'*f,value[1]+'+dy+'*f];',defer);
    }
    if(id==='zoom-transition')SLToolkitControls.assign(tr(l,'ADBE Scale'),'expression',prefix()+'var f=1+'+(s.amount/100)+'*'+(incoming?'(1-u)':'u')+';value.length>2?[value[0]*f,value[1]*f,value[2]*f]:[value[0]*f,value[1]*f];',defer);
    if(id==='glitch-transition')SLToolkitControls.assign(tr(l,'ADBE Position'),'expression',prefix()+'var f=Math.floor(time*'+s.rate+'),d=Math.sin(f*12.71)*'+s.amount+'*Math.sin(Math.PI*u);[value[0]+d,value[1]];',defer);
    if(id==='blur-transition'){
     var name='SLT '+id+' Blur',group=l.property('ADBE Effect Parade');if(group.property(name))throw Error('Remove the existing transition blur before replacing it.');var blur=group.addProperty('ADBE Motion Blur');blur.name=name;defer(function(){var b=l.property('ADBE Effect Parade').property(name);if(b)b.remove();});blur.property(1).setValue(s.angle);blur.property(2).expression=prefix()+s.amount+'*Math.sin(Math.PI*u);';
    }
    if(id==='shape-reveal'&&incoming){
     var mask=l.property('ADBE Mask Parade').addProperty('ADBE Mask Atom');mask.name='SLT Shape Reveal';defer(function(){var m=l.property('ADBE Mask Parade').property('SLT Shape Reveal');if(m)m.remove();});
     var edges=s.direction==='left'?'right=left+r.width*u;':s.direction==='right'?'left=right-r.width*u;':s.direction==='up'?'bottom=top+r.height*u;':'top=bottom-r.height*u;';
     mask.property('ADBE Mask Shape').expression=prefix()+'var r=sourceRectAtTime(time,false),left=r.left,top=r.top,right=r.left+r.width,bottom=r.top+r.height;'+edges+'createPath([[left,top],[right,top],[right,bottom],[left,bottom]],[],[],true);';
    }
   })(records[i]);
   if(id==='flash-transition'){
    var flash=comp.layers.addShape();flash.name='SLT Flash';flash.comment='Storylens Toolkit flash v1';defer(function(){flash.remove();});tr(flash,'ADBE Position').setValue([comp.width/2,comp.height/2]);var v=flash.property('ADBE Root Vectors Group');v.addProperty('ADBE Vector Shape - Rect').property('ADBE Vector Rect Size').setValue([comp.width,comp.height]);v.addProperty('ADBE Vector Graphic - Fill').property('ADBE Vector Fill Color').setValue([1,1,1]);var opacity=tr(flash,'ADBE Opacity');opacity.setValueAtTime(start,0);opacity.setValueAtTime(comp.time,s.amount);opacity.setValueAtTime(end,0);if(typeof SLToolkitBuilders!=='undefined')SLToolkitBuilders.ease(opacity);flash.inPoint=start;flash.outPoint=Math.min(comp.duration,end+comp.frameDuration);
   }
   return {ok:true,changed:2,editable:true,message:SLToolkitModel.find(id).name+' applied around the playhead. Edit Progress keyframes and native effects to refine it.'};
  }};
 }
 root.SLToolkitTransitions={prepare:prepare};
})(typeof $!=='undefined'&&$.global?$.global:this);
