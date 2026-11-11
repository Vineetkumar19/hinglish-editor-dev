const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const {fixture}=require('./quick-motion-native.test.cjs');
test('repair: all eighteen presets return usable replies in an AE-like runtime without browser JSON',()=>{
 const model=require('../editor_plugins/quick-motion/model.js');for(const p of model.catalog()){const f=fixture([p.kind==='text'?'text':'footage']);f.ctx.JSON=undefined;const result=f.run({id:p.id});assert.equal(result.ok,true,p.id);assert.equal(result.layers,1);}
});
test('repair: validation errors remain readable without JSON and never mutate the selected layer',()=>{
 const f=fixture();f.ctx.JSON=undefined;f.comp.selectedLayers[0].locked=true;const r=f.run();assert.match(r.error,/unlocked/);assert.equal(f.changes.length,0);
});
test('repair: native loading failure uses the actual installed serializer instead of failing in its catch handler',()=>{
 const b=require('../editor_plugins/quick-motion/bridge.cjs'),context={JSON:undefined,File:function(p){this.path=p;},$:{evalFile(){throw Error('Load failure');}}};vm.createContext(context);const host=fs.readFileSync('editor_plugins/after-effects-cep/jsx/host.jsx','utf8').split('\n').slice(0,3).join('\n');vm.runInContext(host,context);const r=JSON.parse(vm.runInContext(b.nativeRequest(process.cwd(),{id:'text-up',duration:2}),context));assert.equal(r.code,'quick_motion');assert.match(r.details,/Load failure/);
});
test('repair: Word mode requires one word and leaves a full line untouched, while Words accepts the line',()=>{
 const single=fixture(),layer=single.comp.selectedLayers[0];layer.text.property('ADBE Text Document').value={text:'WINNING'};const r=single.run({text_scope:'word',id:'text-random'});assert.equal(r.ok,true);assert.equal(r.text_scope,'word');const selector=layer.text.property('ADBE Text Animators').property(1).property('ADBE Text Selectors').property(1);assert.equal(selector.property('ADBE Text Range Type2').value,1);
 const line=fixture(),failed=line.run({text_scope:'word'});assert.match(failed.error,/one.word|Words/);assert.equal(line.changes.length,0);assert.equal(line.run({text_scope:'words'}).ok,true);
});
test('repair: text scope crosses the bridge only through its validated enum',()=>{
 const b=require('../editor_plugins/quick-motion/bridge.cjs');assert.equal(b.prepare({action:'applyMotion',id:'text-up',duration:1,text_scope:'word'}).payload.text_scope,'word');assert.throws(()=>b.prepare({action:'applyMotion',id:'text-up',duration:1,text_scope:'anything'}),/Word|mode|scope/);
});
