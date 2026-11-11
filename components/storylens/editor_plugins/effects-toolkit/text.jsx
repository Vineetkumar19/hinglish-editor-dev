(function(root){
 var tag='// Storylens Toolkit text v1:';
 function animators(l){return l.property('ADBE Text Properties').property('ADBE Text Animators');}
 function document(l){return l.property('ADBE Text Properties').property('ADBE Text Document');}
 function prepare(comp,layers,p,keys){var id=p.id,s=p.settings,records=[],i,j,animated=id!=='word-emphasis',name='SLT Text '+id;
  if(!layers.length)throw Error('Select a text layer first.');
  for(i=0;i<layers.length;i++){
   var layer=layers[i];if(layer.locked||!layer.property('ADBE Text Properties'))throw Error('Select unlocked text layers only.');
   var doc=document(layer),start=Math.max(comp.time,layer.inPoint),text=String(doc.value.text!==undefined?doc.value.text:doc.value),owned=!!animators(layer).property(name);
   if(animated&&start+s.duration>Math.min(layer.outPoint,comp.duration)-comp.frameDuration)throw Error('The layer needs room for the full animation duration.');
   if(id==='word-emphasis'&&(s.word!==Math.floor(s.word)||s.word>text.replace(/^\s+|\s+$/g,'').split(/\s+/).length))throw Error('Choose a word number that exists in this text layer.');
   if(id==='scramble'){if(doc.expression&&doc.expression.indexOf(tag+id)!==0)throw Error('This text already has a source-text expression. Use another text layer.');owned=doc.expression&&doc.expression.indexOf(tag+id)===0;}
   if(id==='masked-reveal'){var masks=layer.property('ADBE Mask Parade');if(!masks)throw Error('This layer does not support masks.');owned=!!masks.property(name);if(masks.numProperties>(owned?1:0))throw Error('Masked Reveal needs a text layer without other masks. Keep existing masks on a precomposition.');}
   var group=layer.property('ADBE Effect Parade');for(var k in s)if(Object.prototype.hasOwnProperty.call(s,k)&&k!=='duration'){var e=group.property('SLT '+id+' · '+k);if(e&&(!owned||e.matchName!=='ADBE Slider Control'||e.property(1).numKeys||e.property(1).expression))throw Error('This tool control is already animated or belongs to another setup. Edit it in Effect Controls.');}
   var progressControl=group.property('SLT '+id+' · Progress');if(progressControl&&(!owned||progressControl.matchName!=='ADBE Slider Control'||progressControl.property(1).expression))throw Error('The Progress control conflicts with this tool. Rename that control before applying.');
   records.push({layer:layer,start:start});
  }
  function prefix(){return tag+id+'\nfunction c(n){return effect('+SLQuickMotionModel.quote('SLT '+id+' · ')+'+n)(1);}';}
  function progress(){return prefix()+'var u=Math.max(0,Math.min(1,c("Progress")/100));';}
  return {apply:function(defer){
   for(var i=0;i<records.length;i++){
    var rec=records[i],layer=rec.layer;
    for(var k in s)if(Object.prototype.hasOwnProperty.call(s,k)&&k!=='duration')SLToolkitControls.slider(layer,'SLT '+id+' · '+k,s[k],defer,keys);
    if(animated)SLToolkitControls.slider(layer,'SLT '+id+' · Progress',0,defer,keys,{start:rec.start,end:rec.start+s.duration});
    if(id==='scramble'){
     SLToolkitControls.assign(document(layer),'expression',progress()+'var original=value.toString(),out="",alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",cut=Math.floor(original.length*u);seedRandom(Math.floor(time*c("rate")),true);for(var i=0;i<original.length;i++)out+=i<cut||/\\s/.test(original.charAt(i))?original.charAt(i):alphabet.charAt(Math.floor(random(alphabet.length)));u>=1?value:value.style.setText(out);',defer);continue;
    }
    if(id==='masked-reveal'){
     var masks=layer.property('ADBE Mask Parade'),mask=masks.property(name);if(!mask){mask=masks.addProperty('ADBE Mask Atom');mask.name=name;(function(l){defer(function(){var m=l.property('ADBE Mask Parade').property(name);if(m)m.remove();});})(layer);}
     SLToolkitControls.assign(layer.property('ADBE Mask Parade').property(name).property('ADBE Mask Shape'),'expression',progress()+'var r=sourceRectAtTime(time,false),p=2+c("feather")*2,left=r.left-p,top=r.top-p,right=left+(r.width+2*p)*u,bottom=top+r.height+2*p;createPath([[left,top],[right,top],[right,bottom],[left,bottom]],[],[],true);',defer);
     SLToolkitControls.assign(layer.property('ADBE Mask Parade').property(name).property('ADBE Mask Feather'),'expression',prefix()+'[c("feather"),c("feather")];',defer);continue;
    }
    var group=animators(layer),animator=group.property(name),newAnimator=!animator;if(!animator){animator=group.addProperty('ADBE Text Animator');animator.name=name;(function(l){defer(function(){var a=animators(l).property(name);if(a)a.remove();});})(layer);}
    function property(match,expression){var props=animators(layer).property(name).property('ADBE Text Animator Properties'),a=props.property(match);if(!a){a=props.addProperty(match);(function(l,m){defer(function(){var group=animators(l).property(name);if(group){var a=group.property('ADBE Text Animator Properties').property(m);if(a)a.remove();}});})(layer,match);}SLToolkitControls.assign(animators(layer).property(name).property('ADBE Text Animator Properties').property(match),'expression',expression,defer);}
    if(id==='tracking')property('ADBE Text Tracking Amount',progress()+'c("amount")*(1-u);');
    if(id==='word-emphasis')property('ADBE Text Scale 3D',prefix()+'[c("scale"),c("scale"),100];');
    if(id==='text-flip'){property('ADBE Text Scale 3D','[100,-100,100];');property('ADBE Text Opacity','0;');}
    if(id==='line-reveal'){property('ADBE Text Position 3D',prefix()+'[0,c("distance"),0];');property('ADBE Text Opacity','0;');property('ADBE Text Blur','[5,5];');}
    var selectors=animators(layer).property(name).property('ADBE Text Selectors'),selector=selectors.property('SLT Selector');if(!selector){selector=selectors.addProperty('ADBE Text Expressible Selector');selector.name='SLT Selector';(function(l){defer(function(){var a=animators(l).property(name);if(a){var s=a.property('ADBE Text Selectors').property('SLT Selector');if(s)s.remove();}});})(layer);}
    // A new animator may contain AE's default range selector; remove it only when it has no authored keys.
    selectors=animators(layer).property(name).property('ADBE Text Selectors');
    if(newAnimator)for(j=selectors.numProperties;j>=1;j--)if(selectors.property(j).name!=='SLT Selector')selectors.property(j).remove();
    selector=animators(layer).property(name).property('ADBE Text Selectors').property('SLT Selector');
    var based=selector.property('ADBE Text Range Type2'),old=based.value;(function(prop,value){defer(function(){prop.setValue(value);});})(based,old);based.setValue(id==='word-emphasis'?3:id==='line-reveal'?4:1);
    var body=id==='word-emphasis'?prefix()+'textIndex===Math.round(c("word"))?100:0;':id==='tracking'?'100;':progress()+'var offset=c("stagger")/100*(textIndex-1)/Math.max(1,textTotal-1);var a=Math.max(0,Math.min(1,(u-offset)/(1-c("stagger")/100)));100*(1-a);';
    SLToolkitControls.assign(selector.property('ADBE Text Expressible Amount'),'expression',body,defer);
   }
   return {ok:true,name:SLToolkitModel.find(id).name,changed:layers.length,editable:true,message:'Text animation applied to '+layers.length+' layer(s). Edit SLT controls and Progress keys in AE.'};
  }};
 }
 root.SLToolkitText={prepare:prepare};
})(typeof $!=='undefined'&&$.global?$.global:this);
