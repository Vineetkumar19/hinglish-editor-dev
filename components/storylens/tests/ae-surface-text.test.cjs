const fs=require('node:fs'),assert=require('node:assert/strict'),{test}=require('node:test'),mock=require('./helpers/ae-3d-mock.cjs'),model=require('../editor_plugins/caption-3d/model.cjs');
const engine=fs.readFileSync('editor_plugins/caption-3d/folders.jsx','utf8')+fs.readFileSync('editor_plugins/caption-3d/engine.jsx','utf8');
for(const family of model.catalog.families.filter(f=>f.id!=='3d1'))for(const variant of family.variants)test(family.id+' '+variant.id+' inserts editable planes with smooth motion and keeps owner camera',()=>{
 const r=mock(true,true),before=r.owner._layers.length;r.run(engine);const receipt=r.context.StorylensSurfaceTitles.create(model.prepare({family:family.id,variant:variant.id,motion:"slide"}));
 assert.equal(receipt.ok,true);assert.equal(receipt.font,'Anton-Regular');assert.equal(r.saves,0);assert.equal(r.imports,0);assert.equal(r.owner.time,3);assert.equal(r.owner.renderer,'OWNER RENDERER');assert.equal(r.owner._layers.filter(l=>l.kind==='camera').length,1);
 const outer=r.owner._layers.find(l=>l.kind==='av');assert.equal(outer.parent,r.track);assert(outer.threeDLayer);
 const planes=outer.source._layers.filter(l=>l.kind==='av');assert.equal(planes.length,variant.layout==='corner'?2:1);assert.equal(r.owner._layers.length,before+1);
 assert(!r.owner._layers.some(l=>l.adjustmentLayer));
 const texts=planes.flatMap(l=>l.source._layers.filter(t=>t.kind==='text'));assert.equal(texts.length,variant.rows.length);
 assert(planes.every(l=>!l.threeDLayer&&l.property('ADBE Effect Parade').property('Surface perspective').property('ADBE Corner Pin-0001').numKeys===2));
 assert.equal(texts.map(l=>l.text).join(' '),variant.text);
 if(variant.colour==='black')assert(!planes.some(l=>l.source._layers.some(t=>t.adjustmentLayer)));
 if(variant.layout==='corner')assert(planes.every(l=>l.property('ADBE Effect Parade').property('Surface perspective')));
});
test('idempotent retry does not insert twice; context mismatch preserves project',()=>{
 const r=mock();r.run(engine);const p=model.prepare({family:'3d2',variant:'yellow'}),request={request_id:'a'.repeat(32),comp_id:String(r.owner.id),project_id:'project-1',time:3};
 r.context.StorylensSurfaceTitles.create(p,request);const count=r.items.length;assert.equal(r.context.StorylensSurfaceTitles.create(p,request).reused,true);assert.equal(r.items.length,count);
 assert.throws(()=>r.context.StorylensSurfaceTitles.create(p,{...request,comp_id:'999'}),/Return/);assert.equal(r.items.length,count);
});
test('failed creation removes only attempt-owned items',()=>{const r=mock();r.run(engine);const before=r.items.length;r.failText();assert.throws(()=>r.context.StorylensSurfaceTitles.create(model.prepare({family:'3d3',variant:'wall'})),/Injected/);assert.equal(r.items.length,before);assert.deepEqual(r.owner._layers,[r.camera]);});
test('standalone default creates one word instead of two old groups',()=>{const r=mock();r.run(fs.readFileSync('tools/ae-surface-text/build.jsx','utf8'));assert.deepEqual(r.alerts,[]);assert.equal(r.owner._layers.filter(l=>l.kind==='av').length,1);});
test('attach utility preserves animation guard and works on either family',()=>{
 const r=mock();r.run(engine);r.context.StorylensSurfaceTitles.create(model.prepare({family:'3d3',variant:'wall'}));const root=r.owner._layers.find(l=>l.kind==='av'),track=r.owner.layers.addNull();track.threeDLayer=true;root.property('ADBE Transform Group').property('ADBE Scale').numKeys=1;r.owner.selectedLayers=[root,track];r.run(fs.readFileSync('output/ae-3d3-surface/Attach to Track Null.jsx','utf8'));assert.equal(root.parent,undefined);assert.equal(r.alerts.length,1);
});
for(const family of ['3d2','3d3'])test(family+' reproduces native easing shape despite a misleading Position type',()=>{
 const r=mock(true,false,{misleadingPosition:true});r.run(engine);
 assert.equal(r.context.StorylensSurfaceTitles.create(model.prepare({family,variant:family==='3d2'?'red':'corner'})).ok,true);
});
for(const nativeEaseCount of [1,2,3])test('host-reported easing cardinality '+nativeEaseCount+' is honoured',()=>{
 const r=mock(true,false,{misleadingPosition:true,nativeEaseCount});r.run(engine);assert.equal(r.context.StorylensSurfaceTitles.create(model.prepare({family:'3d3',variant:'wall'})).ok,true);
});
test('native explicit dimension error takes precedence over inconsistent getter arrays',()=>{
 const r=mock(true,false,{misleadingPosition:true,reportedEaseCount:3,nativeEaseCount:1});r.run(engine);assert(r.context.StorylensSurfaceTitles.create(model.prepare({family:'3d3',variant:'corner'})).ok);
});
