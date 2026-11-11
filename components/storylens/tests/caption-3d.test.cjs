const {test}=require('node:test'),assert=require('node:assert/strict');
const model=require('../editor_plugins/caption-3d/model.cjs');
test('four surface counts and colours, no combined jo sample',()=>{
 const variants=model.catalog.families.find(f=>f.id==='3d2').variants;
 assert.deepEqual(variants.map(v=>v.words),[1,2,3,4]);
 assert.deepEqual(variants.map(v=>v.colour),['yellow','blue','red','black']);
 assert(variants.every(v=>!v.text.includes('jo')));
});
test('3D3 has four different reference surfaces',()=>assert.deepEqual(model.catalog.families.find(f=>f.id==='3d3').variants.map(v=>v.layout),['ground','wall','corner','column']));
test('trusted plan preserves word order, applies initial capitals and excludes punctuation-only tokens',()=>{
 const p=model.prepare({family:'3d2',variant:'red',text:'Make - it happen',format:'vertical'});
 assert.equal(p.rows.map(r=>r.text).join(' '),'Make It Happen');assert.equal(p.font,'Anton-Regular');
 assert.throws(()=>model.prepare({family:'3d2',variant:'red',text:'too many words for this variant'}),/3 words/);
 assert.throws(()=>model.prepare({family:'3d2',variant:'../host'}),/Choose/);
 assert.equal(model.prepare({family:'3d2',variant:'red',text:'Make — it… happen'}).rows.length,3);
 assert.throws(()=>model.prepare({family:'3d2',variant:'yellow',text:''}),/1 words/);
});
test('camera titles keep four approved patterns and both formats',()=>{
 assert.equal(model.catalog.families.find(f=>f.id==='3d1').variants.length,4);
 assert.equal(model.prepare({family:'3d1',variant:'boost',format:'horizontal'}).format,'horizontal');
 assert.throws(()=>model.prepare({family:'3d3',variant:'ground',format:'square'}),/format/);
});
