'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {fixture}=require('./quick-motion-native.test.cjs');
function textFixture(types=['text']){const f=fixture(types);f.ctx.$={global:f.ctx};for(const file of ['model.js','text-model.js','controls.jsx','text.jsx','host.jsx'])vm.runInContext(fs.readFileSync('editor_plugins/effects-toolkit/'+file,'utf8'),f.ctx);f.run=(id,settings={})=>JSON.parse(f.ctx.storylensToolkit({id,settings}));return f;}
test('tracking and flip use native text animators without replacing the text document',()=>{
 for(const id of ['tracking','text-flip','line-reveal']){const f=textFixture(),l=f.comp.selectedLayers[0],before=l.text.property('ADBE Text Document').value;const r=f.run(id);assert.equal(r.ok,true,id+': '+r.error);assert.equal(l.text.property('ADBE Text Document').value,before);assert(l.text.property('ADBE Text Animators').numProperties>0);}
});
test('word emphasis uses a word selector and refuses an out-of-range word before mutation',()=>{
 const f=textFixture(),r=f.run('word-emphasis',{word:2,scale:120});assert.equal(r.ok,true,r.error);const a=f.comp.selectedLayers[0].text.property('ADBE Text Animators').property(1);assert.equal(a.property('ADBE Text Selectors').property(1).property('ADBE Text Range Type2').value,3);
 const g=textFixture();assert.match(g.run('word-emphasis',{word:99}).error,/word/i);assert.equal(g.changes.length,0);
});
test('mixed text and footage rejects whole batch before mutating text',()=>{const f=textFixture(['text','footage']);assert.ok(f.run('tracking').error);assert.equal(f.changes.length,0);});
test('scramble keeps original source text and refuses owner source-text expression',()=>{
 const f=textFixture(),doc=f.comp.selectedLayers[0].text.property('ADBE Text Document');const r=f.run('scramble');assert.equal(r.ok,true,r.error);assert.equal(doc.value,'Original cricket words');assert.match(doc.expression,/value/);
 const g=textFixture();g.comp.selectedLayers[0].text.property('ADBE Text Document').expression='"Owner"';assert.match(g.run('scramble').error,/expression/i);assert.equal(g.changes.length,0);
});
module.exports={textFixture};
test('masked reveal creates an editable mask and samples its actual expression at half and full progress',()=>{
 const f=textFixture(),l=f.comp.selectedLayers[0],P=l.transform.constructor,masks=new P('ADBE Mask Parade'),original=l.property.bind(l);l.property=n=>n==='ADBE Mask Parade'?masks:original(n);
 const add=masks.addProperty.bind(masks);masks.addProperty=n=>{const mask=add(n);for(const child of ['ADBE Mask Shape','ADBE Mask Feather'])mask.children.push(new P(child,0,mask));return mask;};
 const r=f.run('masked-reveal');assert.equal(r.ok,true,r.details);const expr=masks.property('SLT Text masked-reveal').property('ADBE Mask Shape').expression;
 for(const progress of [50,100]){const points=vm.runInNewContext(expr,{Math,time:1,effect:name=>()=>name.endsWith('Progress')?progress:2,sourceRectAtTime:()=>({left:0,top:-20,width:100,height:20}),createPath:p=>p});assert.equal(points[1][0]-points[0][0],112*progress/100);assert.equal(points[2][1]-points[1][1],32);}
});
