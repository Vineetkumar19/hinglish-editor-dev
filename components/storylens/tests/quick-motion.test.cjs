const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const load=()=>require('../editor_plugins/quick-motion/model.js');
test('ten editable text recipes and eight bounded element motions have unique ids',()=>{
 const m=load(),all=m.catalog();assert.equal(all.filter(x=>x.kind==='text').length,10);assert.equal(all.filter(x=>x.kind==='element').length,8);assert.equal(new Set(all.map(x=>x.id)).size,18);
 for(const id of ['text-fade','text-typewriter','text-left','text-right','text-up','text-random'])assert(all.some(x=>x.id===id));
});
test('timing is exact, reserves a hold before fade-out, and rejects insufficient layer time',()=>{
 const m=load();for(const d of [1,2,3]){const p=m.plan({id:'text-up',duration:d,blur:true,exit:true},5,20,1/30);assert.equal(p.end-p.start,d);assert.equal(p.exitEnd,20-1/30);assert(p.exitStart>p.end);}
 assert.throws(()=>m.plan({id:'text-up',duration:3,exit:true},5,7,1/30),/room|short/i);
 for(const duration of [0,-1,Infinity,NaN,'2',11])assert.throws(()=>m.validate({id:'text-up',duration}),/duration/i);
 assert.throws(()=>m.validate({id:'../../bad',duration:1}),/preset/i);
});
test('random words reveal once each in a stable nonsequential permutation, including after text edits',()=>{
 const m=load();for(const n of [1,2,7,30]){const ranks=m.order(n,37);assert.deepEqual([...ranks].sort((a,b)=>a-b),Array.from({length:n},(_,i)=>i));assert.deepEqual(m.order(n,37),ranks);if(n>2)assert.notDeepEqual(ranks,Array.from({length:n},(_,i)=>i));}
});
test('selector expressions keep original text and fixed final positions; all progress endpoints resolve',()=>{
 const m=load();for(const recipe of m.catalog().filter(x=>x.kind==='text'))for(const total of [1,9])for(const progress of [0,100]){
  const expression=m.selector(recipe,'Control',37);const ctx={textIndex:1,textTotal:total,effect:()=>()=>progress,Math,linear:(v,a,b,x,y)=>x+(y-x)*Math.max(0,Math.min(1,(v-a)/(b-a))),ease:(v,a,b,x,y)=>{const t=Math.max(0,Math.min(1,(v-a)/(b-a)));return x+(y-x)*t*t*(3-2*t);}};
  assert.equal(vm.runInNewContext(expression,ctx),progress===0?100:0,recipe.id);
 }
});
test('native bridge accepts only whitelisted recipes, has no file access payload, and parses as ES3',()=>{
 const b=require('../editor_plugins/quick-motion/bridge.cjs');assert.equal(b.prepare({action:'motionCatalog'}).result.presets.length,18);const p=b.prepare({action:'applyMotion',id:'text-random',duration:2,blur:true,exit:true,path:'C:/secret'}).payload;assert.equal(p.path,undefined);assert.equal(p.id,'text-random');new vm.Script(b.nativeRequest(process.cwd(),p));
 const acorn=require('../tools/motion-engines-runtime/node_modules/acorn');for(const file of ['model.js','host.jsx'])acorn.parse(fs.readFileSync('editor_plugins/quick-motion/'+file,'utf8'),{ecmaVersion:3,allowReserved:'never'});
});
