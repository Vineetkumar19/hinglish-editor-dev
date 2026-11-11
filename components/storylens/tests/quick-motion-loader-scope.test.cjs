const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const {fixture}=require('./quick-motion-native.test.cjs');
test('evalFile with a local receiver publishes the animation model to the explicit ExtendScript global',()=>{
 const ctx={JSON:undefined,$:{}};ctx.$.global=ctx;vm.createContext(ctx);vm.runInContext('(function(){'+fs.readFileSync('editor_plugins/quick-motion/model.js','utf8')+'}).call({localReceiver:true});',ctx);assert(ctx.SLQuickMotionModel,'The native host must find this on the AE global, not the evalFile receiver');assert.equal(ctx.SLQuickMotionModel.find('text-up').kind,'text');
});
test('native AE text and shape objects remain eligible when their AVLayer base check returns false',()=>{
 for(const kind of ['text','shape']){const f=fixture([kind]),NativeClass=f.ctx.AVLayer;f.ctx.AVLayer=function BaseOnly(){};f.ctx[kind==='text'?'TextLayer':'ShapeLayer']=NativeClass;assert.equal(f.comp.selectedLayers[0] instanceof f.ctx.AVLayer,false);const r=f.run({id:kind==='text'?'text-fade':'element-up'});assert.equal(r.ok,true,kind+': '+r.error);}
});
