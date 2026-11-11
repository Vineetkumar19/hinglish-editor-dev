const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
function fixture(types=['text']){
 const changes=[];let begin=0,end=0,failProperty='';
 class Property{constructor(name,value=0,parent=null){this.name=this.matchName=name;this.value=value;this.parent=parent;this.children=[];this.keys=[];this.expression='';this.canSetExpression=true;this.isSpatial=false;}
  get propertyIndex(){return this.parent.children.indexOf(this)+1;}get numProperties(){return this.children.length;}get numKeys(){return this.keys.length;}
  property(k){return typeof k==='number'?this.children[k-1]:this.children.find(x=>x.matchName===k||x.name===k)||null;}
  addProperty(k){if(k===failProperty)throw Error('Unavailable property '+k);const p=new Property(k,0,this);this.children.push(p);changes.push(k);
   if(k==='ADBE Slider Control')p.children.push(new Property('ADBE Slider Control-0001',0,p));
   if(k==='ADBE Gaussian Blur 2')p.children.push(new Property('ADBE Gaussian Blur 2-0001',0,p));
   if(k==='ADBE Text Animator')for(const n of ['ADBE Text Animator Properties','ADBE Text Selectors'])p.children.push(new Property(n,0,p));
   if(k==='ADBE Text Expressible Selector')for(const n of ['ADBE Text Range Type2','ADBE Text Expressible Amount'])p.children.push(new Property(n,0,p));return p;}
  setValue(v){this.value=v;}setValueAtTime(t,v){this.keys.push({t,v});this.value=v;}keyInTemporalEase(){return [1];}setInterpolationTypeAtKey(k,a,b){this.keys[k-1].interpolation=[a,b];}setTemporalEaseAtKey(k,a,b){this.keys[k-1].ease=[a,b];}valueAtTime(){return this.value;}remove(){this.parent.children.splice(this.propertyIndex-1,1);}
 }
 class AVLayer{constructor(type){this.name=type;this.locked=false;this.inPoint=0;this.outPoint=20;this.motionBlur=false;this.enabled=true;this.effects=new Property('ADBE Effect Parade');this.transform=new Property('ADBE Transform Group');for(const [n,v] of [['ADBE Position',[540,960]],['ADBE Scale',[80,80]],['ADBE Opacity',85]])this.transform.children.push(new Property(n,v,this.transform));this.text=type==='text'?new Property('ADBE Text Properties'):null;if(this.text){this.text.children.push(new Property('ADBE Text Animators',0,this.text));this.text.children.push(new Property('ADBE Text Document','Original cricket words',this.text));}}
  property(n){return n==='ADBE Effect Parade'?this.effects:n==='ADBE Transform Group'?this.transform:n==='ADBE Text Properties'?this.text:null;}
 }
 class CompItem{constructor(){this.time=5;this.duration=20;this.frameDuration=1/30;this.width=1080;this.height=1920;this.selectedLayers=types.map(t=>new AVLayer(t));this.motionBlur=false;}}
 const comp=new CompItem(),ctx={JSON,Math,Number,String,Error,isFinite,CompItem,AVLayer,KeyframeInterpolationType:{BEZIER:'bezier',LINEAR:'linear'},KeyframeEase:function(speed,influence){this.speed=speed;this.influence=influence;},app:{project:{activeItem:comp},beginUndoGroup(){begin++;},endUndoGroup(){end++;}}};vm.createContext(ctx);for(const f of ['model.js','host.jsx'])vm.runInContext(fs.readFileSync('editor_plugins/quick-motion/'+f,'utf8'),ctx);
 return {comp,changes,ctx,run:(p={})=>JSON.parse(ctx.storylensQuickMotion({id:'text-up',duration:2,blur:true,exit:true,...p})),groups:()=>[begin,end],fail:k=>failProperty=k};
}
test('text motion adds editable animator/progress keys with ease and blur without changing text or layer transforms',()=>{
 const f=fixture(),l=f.comp.selectedLayers[0],r=f.run();assert.equal(r.ok,true);assert.equal(r.layers,1);assert.equal(f.comp.time,5);assert.deepEqual(f.groups(),[1,1]);assert.equal(l.text.property('ADBE Text Document').value,'Original cricket words');assert.equal(l.transform.property('ADBE Position').expression,'');
 const slider=l.effects.property(1).property(1);assert.deepEqual(slider.keys.map(k=>[k.t,k.v]),[[5,0],[7,100],[19.466666666666665,100],[19.966666666666665,0]]);assert(slider.keys.every(k=>k.ease[0][0].influence>=33));const animator=l.text.property('ADBE Text Animators').property(1);assert(animator.property('ADBE Text Animator Properties').property('ADBE Text Blur'));assert.match(animator.property('ADBE Text Selectors').property(1).property('ADBE Text Expressible Amount').expression,/effect\(/);
});
test('all recipes apply to eligible layers and element motions preserve existing transform keys',()=>{
 const m=require('../editor_plugins/quick-motion/model.js');for(const preset of m.catalog()){const f=fixture([preset.kind==='text'?'text':'footage']),l=f.comp.selectedLayers[0],pos=l.transform.property('ADBE Position');pos.keys.push({t:0,v:[100,200]});const r=f.run({id:preset.id});assert.equal(r.ok,true,preset.id+': '+r.error);assert.equal(pos.keys.length,1);assert.deepEqual(pos.value,[540,960]);if(preset.kind==='element')assert.match(l.transform.property('ADBE Opacity').expression,/value/);}
});
test('mixed selection, locked layer, short duration and existing user expressions fail before changing any layer',()=>{
 for(const kind of ['mixed','locked','short','expression']){const f=fixture(kind==='mixed'?['text','footage']:['text','text']);if(kind==='locked')f.comp.selectedLayers[1].locked=true;if(kind==='short')f.comp.selectedLayers[1].outPoint=6;if(kind==='expression')f.comp.selectedLayers[1].transform.property('ADBE Position').expression='wiggle(2,10)';const r=f.run(kind==='expression'?{id:'element-left'}:{});assert.equal(r.ok,undefined,kind);assert.equal(f.changes.length,0,kind);assert.deepEqual(f.groups(),[0,0]);}
});
test('applying another preset replaces only this feature animation and preserves owner effects',()=>{
 const f=fixture(['footage']),l=f.comp.selectedLayers[0];l.effects.addProperty('Owner colour');assert.equal(f.run({id:'element-left'}).ok,true);assert.equal(f.run({id:'element-zoom-in'}).ok,true);assert.equal(l.effects.children.filter(x=>x.name.indexOf('SLQ ')===0).length,2);assert(l.effects.property('Owner colour'));assert.equal(l.transform.property('ADBE Position').expression,'');assert.match(l.transform.property('ADBE Scale').expression,/value/);
});
test('unavailable animator property rolls back new effects and closes undo without reporting success',()=>{
 const f=fixture();f.fail('ADBE Text Blur');const r=f.run();assert.match(r.error,/could not|did not/i);assert.equal(f.comp.selectedLayers[0].effects.numProperties,0);assert.equal(f.comp.selectedLayers[0].text.property('ADBE Text Animators').numProperties,0);assert.deepEqual(f.groups(),[1,1]);assert.equal(f.comp.time,5);
});
test('opacity-only motion preserves an unrelated owner position expression',()=>{
 const f=fixture(['footage']),p=f.comp.selectedLayers[0].transform.property('ADBE Position');p.expression='wiggle(2,10)';assert.equal(f.run({id:'element-fade'}).ok,true);assert.equal(p.expression,'wiggle(2,10)');
});
test('similarly named owner effects are preserved when replacing Storylens motion',()=>{
 const f=fixture(['footage']),effects=f.comp.selectedLayers[0].effects;effects.addProperty('Owner effect').name='SLQ Element Owner custom';assert.equal(f.run({id:'element-up'}).ok,true);assert(effects.property('SLQ Element Owner custom'));
});
module.exports={fixture};
