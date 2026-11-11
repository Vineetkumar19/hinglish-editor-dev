const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),{test}=require('node:test');
const text=fs.readFileSync('tools/hyperframes-runtime/node_modules/hyperframes/dist/chunk-YCW345M4.js','utf8');
const fn=text.match(/async function getCachedGpuEncoder\(\) \{[\s\S]*?\n\}/)[0];
test('requested Hyperframes GPU must reject an unavailable encoder instead of returning CPU fallback',async()=>{
 const ctx=vm.createContext({cachedGpuEncoder:undefined,detectGpuEncoder:async()=>null});vm.runInContext(fn,ctx);await assert.rejects(vm.runInContext('getCachedGpuEncoder()',ctx),/GPU/);
});
test('available encoder is retained and probed once',async()=>{
 let probes=0;const ctx=vm.createContext({cachedGpuEncoder:undefined,detectGpuEncoder:async()=>{probes++;return 'nvenc';}});vm.runInContext(fn,ctx);assert.equal(await vm.runInContext('getCachedGpuEncoder()',ctx),'nvenc');assert.equal(await vm.runInContext('getCachedGpuEncoder()',ctx),'nvenc');assert.equal(probes,1);
});
