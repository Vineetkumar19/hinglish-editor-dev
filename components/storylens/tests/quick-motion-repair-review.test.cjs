const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const {fixture}=require('./quick-motion-native.test.cjs');
test('repair final review: self-contained serialization round-trips Unicode, quotes and all JSON control characters',()=>{
 const ctx={JSON:undefined};vm.createContext(ctx);vm.runInContext(fs.readFileSync('editor_plugins/quick-motion/model.js','utf8'),ctx);const text='हिन्दी " \\ \u2028\u2029'+Array.from({length:32},(_,i)=>String.fromCharCode(i)).join('');ctx.sample=text;const encoded=vm.runInContext('SLQuickMotionModel.stringify({text:sample,values:[true,false,null,1.5]})',ctx);assert.deepEqual(JSON.parse(encoded),{text,values:[true,false,null,1.5]});const quoted=vm.runInContext('SLQuickMotionModel.quote(sample)',ctx);assert.equal(JSON.parse(quoted),text);
});
test('repair final review: Word-to-Words reapplication changes selector granularity without changing the text or accumulating controls',()=>{
 const f=fixture(),l=f.comp.selectedLayers[0];f.ctx.JSON=undefined;l.text.property('ADBE Text Document').value={text:'VICTORY'};assert.equal(f.run({id:'text-random',text_scope:'word'}).ok,true);assert.equal(f.run({id:'text-random',text_scope:'words'}).ok,true);const a=l.text.property('ADBE Text Animators');assert.equal(a.numProperties,1);assert.equal(a.property(1).property('ADBE Text Selectors').property(1).property('ADBE Text Range Type2').value,3);assert.equal(l.effects.numProperties,1);assert.equal(l.text.property('ADBE Text Document').value.text,'VICTORY');
});
test('repair final review: empty/multiline Word requests and malformed scopes cannot modify a layer',()=>{
 for(const value of ['', '  ', 'ONE\nTWO']){const f=fixture();f.ctx.JSON=undefined;f.comp.selectedLayers[0].text.property('ADBE Text Document').value={text:value};assert.match(f.run({text_scope:'word'}).error,/one.word|Words/);assert.equal(f.changes.length,0);}const f=fixture();f.ctx.JSON=undefined;assert.match(f.run({text_scope:'../text'}).error,/Word/);assert.equal(f.changes.length,0);
});
