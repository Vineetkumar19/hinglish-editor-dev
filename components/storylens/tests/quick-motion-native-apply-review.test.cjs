const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const {fixture}=require('./quick-motion-native.test.cjs');
test('native apply final review: an unsupported layer cannot pass the repaired concrete-type checks',()=>{
 const f=fixture();f.ctx.AVLayer=function OtherAV(){};f.ctx.TextLayer=function OtherText(){};f.ctx.ShapeLayer=function OtherShape(){};assert.match(f.run().error,/unlocked text/);assert.equal(f.changes.length,0);assert.deepEqual(f.groups(),[0,0]);
});
test('native apply final review: a locked native TextLayer in a mixed selection prevents all edits',()=>{
 const f=fixture(['text','text']);f.ctx.TextLayer=f.ctx.AVLayer;f.ctx.AVLayer=function BaseOnly(){};f.comp.selectedLayers[1].locked=true;assert.match(f.run().error,/unlocked text/);assert.equal(f.changes.length,0);assert.deepEqual(f.groups(),[0,0]);
});
test('native apply final review: publishing on the AE global preserves unrelated native globals',()=>{
 const ctx={JSON:undefined,ownerMarker:{keep:true},$:{}};ctx.$.global=ctx;vm.createContext(ctx);const source=fs.readFileSync('editor_plugins/quick-motion/model.js','utf8');vm.runInContext('(function(){'+source+'}).call({});',ctx);assert.equal(ctx.ownerMarker.keep,true);assert.equal(ctx.SLQuickMotionModel.catalog().length,18);assert.equal(ctx.JSON,undefined);
});
