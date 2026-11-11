'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {fixture}=require('./quick-motion-native.test.cjs');
function motionFixture(types=['text']){const f=fixture(types);f.ctx.$={global:f.ctx};for(const file of ['model.js','motion.jsx','host.jsx'])vm.runInContext(fs.readFileSync('editor_plugins/effects-toolkit/'+file,'utf8'),f.ctx);f.run=(id,settings={})=>JSON.parse(f.ctx.storylensToolkit({id,settings}));return f;}
test('motion tools preserve source values and add editable native controls',()=>{
 for(const id of ['shake','handheld','float','arc','pulse']){const f=motionFixture(),l=f.comp.selectedLayers[0],position=l.transform.property('ADBE Position');const r=f.run(id);assert.equal(r.ok,true,id+': '+r.error);assert.deepEqual(position.value,[540,960]);assert(l.effects.numProperties>0);assert.match(l.transform.property(id==='pulse'?'ADBE Scale':'ADBE Position').expression,/Storylens Toolkit/);}
});
test('second layer custom expression rejects entire motion selection before changes',()=>{
 const f=motionFixture(['text','text']);f.comp.selectedLayers[1].transform.property('ADBE Position').expression='wiggle(1,4)';assert.match(f.run('float').error,/expression/i);assert.equal(f.changes.length,0);
});
test('reapply updates existing tool controls and does not stack a second animation',()=>{
 const f=motionFixture(),l=f.comp.selectedLayers[0];assert.equal(f.run('float').ok,true);const count=l.effects.numProperties;assert.equal(f.run('float',{amount:50}).ok,true);assert.equal(l.effects.numProperties,count);assert.equal(l.effects.property('SLT float · amount').property(1).value,50);
});
test('short layer fails arc before adding controls',()=>{
 const f=motionFixture();f.comp.selectedLayers[0].outPoint=5.2;assert.match(f.run('arc',{duration:1}).error,/duration|room/i);assert.equal(f.changes.length,0);
});
test('control creation failure removes controls already added in this attempt',()=>{
 const f=motionFixture();f.fail('ADBE Slider Control');assert.ok(f.run('float').error);assert.equal(f.comp.selectedLayers[0].effects.numProperties,0);assert.equal(f.comp.selectedLayers[0].transform.property('ADBE Position').expression,'');
});
module.exports={motionFixture};
test('Follow Mask Path binds the selected mask index and preserves its geometry',()=>{
 const f=motionFixture(),l=f.comp.selectedLayers[0],P=l.transform.constructor,rotation=new P('ADBE Rotate Z',0,l.transform);l.transform.children.push(rotation);l.selectedProperties=[{matchName:'ADBE Mask Shape',parentProperty:{propertyIndex:2}}];const r=f.run('follow-path');assert.equal(r.ok,true,r.details);assert.equal(l.effects.property('SLT follow-path · Path').property(1).value,2);assert.match(l.transform.property('ADBE Position').expression,/pointOnPath/);
});
test('Bounce requires selected numeric keys and preserves the original keys',()=>{
 const f=motionFixture(),l=f.comp.selectedLayers[0],p=l.transform.property('ADBE Position');p.keys=[{t:0,v:[1,2]},{t:1,v:[3,4]}];p.selectedKeys=[1,2];l.selectedProperties=[p];const before=JSON.stringify(p.keys),r=f.run('bounce');assert.equal(r.ok,true,r.details);assert.equal(JSON.stringify(p.keys),before);assert.match(p.expression,/velocityAtTime/);
});
test('document focus zoom keeps its opening transform and ends on the selected focus point',()=>{
 const f=motionFixture();for(const file of ['typography-model.js','builders-model.js'])vm.runInContext(fs.readFileSync('editor_plugins/effects-toolkit/'+file,'utf8'),f.ctx);const l=f.comp.selectedLayers[0],r=f.run('focus-zoom',{duration:2,amount:150,x:25,y:50});assert.equal(r.ok,true,r.details);
 const expr=l.transform.property('ADBE Position').expression;for(const progress of [0,100]){const values={Progress:progress,amount:150,x:25,y:50};const actual=vm.runInNewContext(expr,{Math,time:1,inPoint:0,value:[540,960],thisComp:{width:1080,height:1920},effect:name=>()=>values[name.split(' · ')[1]]});assert.deepEqual(Array.from(actual),progress===0?[540,960]:[945,960]);}
});
