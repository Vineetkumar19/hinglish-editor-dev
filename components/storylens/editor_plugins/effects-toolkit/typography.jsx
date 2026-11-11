(function(root){
 var attributes=['font','fontSize','applyFill','fillColor','applyStroke','strokeColor','strokeWidth','tracking','leading','autoLeading','justification','fauxBold','fauxItalic'];
 function tr(l,n){return l.property('ADBE Transform Group').property(n);}
 function source(l){return l.property('ADBE Text Properties').property('ADBE Text Document');}
 function style(doc){var out={};for(var i=0;i<attributes.length;i++)if(doc[attributes[i]]!==undefined)out[attributes[i]]=doc[attributes[i]];return out;}
 function setStyle(doc,data){for(var k in data)if(Object.prototype.hasOwnProperty.call(data,k))doc[k]=data[k];}
 function color(hex){return [parseInt(hex.substr(1,2),16)/255,parseInt(hex.substr(3,2),16)/255,parseInt(hex.substr(5,2),16)/255];}
 function balanced(text,max){var words=text.replace(/^\s+|\s+$/g,'').split(/\s+/),lines=Math.ceil(words.length/max),out=[],at=0;for(var i=0;i<lines;i++){var count=Math.ceil((words.length-at)/(lines-i));out.push(words.slice(at,at+count).join(' '));at+=count;}return out.join('\r');}
 function prepare(comp,layers,p,keys){var id=p.id,s=p.settings,records=[],i;
  if(id==='lower-third'){if(typeof SLToolkitBuilders==='undefined')throw Error('The layout builder is not loaded. Reopen Storylens.');return SLToolkitBuilders.prepare(comp,layers,p,keys);}
  if(!layers.length)throw Error('Select one or more text layers first.');
  if(id==='text-style'&&s.mode==='copy'&&layers.length!==1)throw Error('Select one text layer to copy its style.');
  if(id==='text-style'&&s.mode==='paste'&&!root.SLToolkitTextStyle)throw Error('Copy a text style first.');
  for(i=0;i<layers.length;i++){
   var l=layers[i];if(l.locked||!l.property('ADBE Text Properties'))throw Error('Select unlocked text layers only.');
   var doc=source(l),value=doc.value;if(doc.numKeys||doc.expression)throw Error('This tool needs static Source Text. Keep animated source text unchanged or duplicate it first.');
   if(id==='auto-fit'||id==='split-text'){
    if(l.threeDLayer||l.parent)throw Error('Use unparented 2D text for this layout tool.');
    for(var j=0;j<3;j++){var t=tr(l,['ADBE Position','ADBE Scale','ADBE Rotate Z'][j]);if(t.numKeys||t.expression||t.dimensionsSeparated)throw Error('This layout tool needs static combined transforms. Apply layout before animation.');}
    if(id==='split-text'&&(value.boxText||/[\r\n]/.test(value.text)||l.property('ADBE Text Properties').property('ADBE Text Animators').numProperties))throw Error('Split Text needs a single-line point-text layer without text animators.');
   }
   if(id==='text-box'&&l.threeDLayer)throw Error('Responsive Text Box currently needs 2D text.');
   if(id==='line-breaks'&&s.words!==Math.floor(s.words))throw Error('Words per line must be a whole number.');
   if(!String(value.text||'').replace(/\s/g,''))throw Error('Enter some text on the selected layer first.');
   records.push({layer:l,doc:doc,value:value,text:value.text,style:style(value)});
  }
  return {readonly:id==='text-style'&&s.mode==='copy',apply:function(defer){
   if(id==='text-style'&&s.mode==='copy'){root.SLToolkitTextStyle=records[0].style;return {ok:true,message:'Text style copied. Select destination text and choose Paste.',changed:0};}
   for(var i=0;i<records.length;i++)(function(rec){var l=rec.layer;
    if(id==='auto-fit'){var r=l.sourceRectAtTime(comp.time,false),scale=tr(l,'ADBE Scale'),old=scale.value;if(r.width<=0||r.height<=0)throw Error('The selected text has no measurable bounds.');var factor=Math.min(s.width/(r.width*Math.abs(old[0])/100),s.height/(r.height*Math.abs(old[1])/100));if(s.upscale==='no')factor=Math.min(1,factor);if(!isFinite(factor))throw Error('Restore a nonzero layer scale before fitting.');defer(function(){scale.setValue(old);});scale.setValue([old[0]*factor,old[1]*factor]);return;}
    if(id==='line-breaks'||id==='text-style'){defer(function(){var original=rec.doc.value;original.text=rec.text;setStyle(original,rec.style);rec.doc.setValue(original);});var next=rec.doc.value;if(id==='line-breaks')next.text=balanced(rec.text,s.words);else setStyle(next,root.SLToolkitTextStyle);rec.doc.setValue(next);return;}
    if(id==='split-text'){
     var words=rec.text.split(/\s+/),bounds=l.sourceRectAtTime(comp.time,false),position=tr(l,'ADBE Position').value,scale=tr(l,'ADBE Scale').value,angle=tr(l,'ADBE Rotate Z').value*Math.PI/180,prefix='',oldEnabled=l.enabled;
     var measure=l.duplicate();defer(function(){try{measure.remove();}catch(ignore){}});measure.enabled=false;
     function width(text){if(!text)return 0;var d=source(measure).value;d.text=text;d.justification=ParagraphJustification.LEFT_JUSTIFY;source(measure).setValue(d);return measure.sourceRectAtTime(comp.time,false).width;}
     for(var j=0;j<words.length;j++){
      var word=words[j];if(!word)continue;var next=l.duplicate();(function(copy){defer(function(){copy.remove();});})(next);next.name=word;var d=source(next).value;d.text=word;d.justification=ParagraphJustification.LEFT_JUSTIFY;source(next).setValue(d);var box=next.sourceRectAtTime(comp.time,false);
      // Measure a prefix including the next word; subtract that word to retain intervening space width.
      var offset=prefix?width(prefix+word)-width(word):0,dx=(bounds.left+offset-box.left)*scale[0]/100,dy=(bounds.top-box.top)*scale[1]/100;tr(next,'ADBE Position').setValue([position[0]+dx*Math.cos(angle)-dy*Math.sin(angle),position[1]+dx*Math.sin(angle)+dy*Math.cos(angle)]);prefix+=word+' ';
     }
     measure.remove();defer(function(){l.enabled=oldEnabled;});l.enabled=false;return;
    }
    if(id==='text-box'){
     var box=comp.layers.addShape();box.name='Box - '+l.name;box.comment='Storylens Toolkit responsive-box v1';defer(function(){box.remove();});box.parent=l;tr(box,'ADBE Position').setValue([0,0]);tr(box,'ADBE Anchor Point').setValue([0,0]);tr(box,'ADBE Scale').setValue([100,100]);tr(box,'ADBE Rotate Z').setValue(0);box.inPoint=l.inPoint;box.outPoint=l.outPoint;box.moveAfter(l);
     var vectors=box.property('ADBE Root Vectors Group'),rect=vectors.addProperty('ADBE Vector Shape - Rect');rect.name='Box';vectors.addProperty('ADBE Vector Graphic - Fill').property('ADBE Vector Fill Color').setValue(color(s.color));
     SLToolkitControls.slider(box,'Padding',s.padding,defer,keys);SLToolkitControls.slider(box,'Roundness',s.roundness,defer,keys);
     rect=box.property('ADBE Root Vectors Group').property('Box');rect.property('ADBE Vector Rect Size').expression='var r=parent.sourceRectAtTime(time,false),p=effect("Padding")(1);[r.width+2*p,r.height+2*p];';rect.property('ADBE Vector Rect Position').expression='var r=parent.sourceRectAtTime(time,false);[r.left+r.width/2,r.top+r.height/2];';rect.property('ADBE Vector Rect Roundness').expression='effect("Roundness")(1);';return;
    }
   })(records[i]);
   return {ok:true,changed:records.length,message:SLToolkitModel.find(id).name+' applied. The layers and text remain editable.',editable:true};
  }};
 }
 root.SLToolkitTypography={prepare:prepare,balanced:balanced,color:color};
})(typeof $!=='undefined'&&$.global?$.global:this);
